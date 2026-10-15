"""Server-authoritative combat, progression, dropped weapons and projectiles."""
import math
import secrets
from rules import (ITEMS,RANGED,TARGET_HEIGHTS,BODY_MULTIPLIERS,PERSISTENT,
                   level_for_xp,kill_reward,death_penalty,zone_from_height,public_integer,MOVES,grip_risk_multiplier)


def angle(a): return (a+math.pi)%math.tau-math.pi


class Combat:
    def emit(self,kind,**fields):
        self.learning_event(kind,fields)
        self.event_serial += 1
        actor=next((self.fighters.get(fields.get(k)) for k in ("source_id","target_id","source","target") if self.fighters.get(fields.get(k))),None)
        fields.setdefault("world_id",actor["world_id"] if actor else self.default_world)
        self.events.append(dict(id=self.event_serial,kind=kind,time=self.clock,**fields))
        self.events=self.events[-80:]

    def sync_progress(self,f):
        match=self.match_for(f)
        if match and not match['mode']['ranked']:return
        for s in self.sessions.values():
            if s["fighter"]==f["id"]:
                for key in PERSISTENT: s["user"][key]=f[key]
                if not s["guest"]: self.save()
                break

    def grant(self,f,**values):
        for key,value in values.items(): f[key]=max(0,f.get(key,0)+value)
        old=f["level"];f["level"]=level_for_xp(f["xp"])
        if f["level"]>old:self.emit("level",target=f["id"],level=f["level"])
        self.sync_progress(f)

    def parry_reward(self,defender,attacker,projectile=False):
        self.grant(defender,xp=(12 if projectile else 15)+attacker["level"]*5,
                   skill=max(1,attacker["level"]//3),parries=1)

    def leaderboards(self):
        rows={}
        for u in self.users.values():
            rows["user:"+u["username"].lower()]=dict(username=u["username"],bot=False,level=level_for_xp(u["xp"]),
                    **{k:u[k] for k in ("xp","skill","coins","kills")})
        for f in self.fighters.values():
            match=self.match_for(f)
            if match and not match['mode']['ranked']:continue
            key=f["id"] if f["bot"] or f["name"].startswith("Guest-") else "user:"+f["name"].lower()
            rows[key]=dict(username=f["name"],bot=f["bot"],**{k:f[k] for k in ("level","xp","skill","coins","kills")})
        return {key:[{k:public_integer(v) if isinstance(v,int) and not isinstance(v,bool) else v for k,v in row.items()} for row in sorted(rows.values(),key=lambda r:(r[key],r["xp"],r["username"]),reverse=True)[:12]]
                for key in ("skill","level","xp","coins","kills")}

    def lift(self,f):
        remaining=f["jump"]
        return math.sin((.55-remaining)/.55*math.pi)*.65 if remaining>0 else 0.

    def try_disarm(self,disarmer,victim,parry=False):
        """Rare blade contact against an exhausted grip; failed pulls earn nothing."""
        if not self.can_fight(disarmer,victim):return False
        for fighter in (disarmer,victim):
            if fighter['dead']>0 or fighter['spawn_safe']>0 or fighter.get('downed',0)>0 or fighter['fall']>0 or fighter['disarmed']>0:return False
        melee={'blade','spear','axe','mace'}
        if ITEMS[disarmer['weapon']]['family'] not in melee or ITEMS[victim['weapon']]['family'] not in melee:return False
        if self.clock<victim['grip_test_after'] or victim['stamina']>=25:return False
        dx,dz=victim['x']-disarmer['x'],victim['z']-disarmer['z']
        if math.hypot(dx,dz)>1.8 or abs(angle(math.atan2(dx,dz)-disarmer['yaw']))>.25:return False
        if parry:
            if not disarmer['block'] or not 0<=self.clock-disarmer['block_since']<=.07 or not self.guard_matches(victim,disarmer):return False
        elif victim['block'] or victim['cooldown']<=.1 or victim['windup']>0:return False
        # All opponents share this retry window, so surrounding one target cannot
        # turn many failed pulls in the same instant into a guaranteed disarm.
        victim['grip_test_after']=self.clock+3.
        chance=(.04 if parry else .08)*grip_risk_multiplier(victim['grip_upgrades'])
        if self.rng.random()>=chance:
            self.emit('grip_hold',source=disarmer['id'],target=victim['id'])
            return False
        return self.drop_weapon(victim,disarmer)

    def drop_weapon(self,f,disarmer=None):
        if f["weapon"]=="fists" or f["dead"]>0:return False
        item=f["weapon"]
        f["weapon"]="fists";f["attack"]="";f["windup"]=0;f["cooldown"]=.6;f["queued_attack"]=""
        f["disarmed"]=1.0 if disarmer else .3
        yaw=f["yaw"]+.8
        self.drops.append(dict(id="drop-"+secrets.token_hex(4),weapon=item,owner=f["id"],
            world_id=f["world_id"],
            x=f["x"],y=1.25,z=f["z"],vx=math.sin(yaw)*2.5,vz=math.cos(yaw)*2.5,vy=3.2,age=0.,expires=self.clock+25))
        self.emit("disarm" if disarmer else "drop",source=disarmer["id"] if disarmer else f["id"],target=f["id"],weapon=item)
        if disarmer:
            self.grant(disarmer,xp=25+10*f["level"],skill=max(1,f["level"]//2),disarms=1)
            self.grant(f,skill=-(2+f["level"]))
        ticket=f.get('attack_learning')
        if ticket and not ticket['projectile']:self.learning.finish(ticket,miss=True)
        return True

    def pickup_candidate(self,f):
        if f['dead']>0 or f.get('downed',0)>0:return None
        nearby=[d for d in self.drops if d['world_id']==f['world_id'] and d['age']>=.45 and d['y']<=.22
                and d['expires']>self.clock and math.hypot(d['x']-f['x'],d['z']-f['z'])<1.7]
        # Recover your dropped blade first when several weapons lie at your feet.
        return min(nearby,key=lambda d:(d['owner']!=f['id'],math.hypot(d['x']-f['x'],d['z']-f['z']))) if nearby else None

    def pickup_hint(self,f):
        chosen=self.pickup_candidate(f)
        if not chosen:return {}
        return dict(id=chosen['id'],weapon=chosen['weapon'],own=chosen['owner']==f['id'],
                    ready=f['disarmed']<=0 and f['fall']<=0,distance=round(math.hypot(chosen['x']-f['x'],chosen['z']-f['z']),2))

    def pickup_weapon(self,f):
        if f["dead"]>0 or f["disarmed"]>0 or f['fall']>0:return False
        chosen=self.pickup_candidate(f)
        if not chosen:return False
        if f["weapon"]!="fists":self.drop_weapon(f)
        self.drops.remove(chosen);f["weapon"]=chosen["weapon"];f["cooldown"]=.3;f["disarmed"]=0
        # A punch already in flight must not become an instant sword strike.
        ticket=f.get('attack_learning')
        if ticket and not ticket['projectile']:self.learning.finish(ticket,miss=True)
        f.update(attack='',windup=0.,queued_attack='',queued_repeat=False)
        # Picking up another player's weapon never adds it to permanent inventory.
        self.emit("pickup",source=f["id"],weapon=chosen["weapon"],drop_id=chosen['id'],own=chosen['owner']==f['id'])
        return True

    def damage(self,attacker,victim,base,zone,kind="hit",magic="",pierce=0.,learning_ticket=None):
        if victim["dead"]>0 or victim["spawn_safe"]>0 or attacker["spawn_safe"]>0 or not self.can_fight(attacker,victim):return
        if victim.get('downed',0)>0:
            victim['down_hp']-=max(0,base);victim['last_hurt']=self.clock
            if victim['down_hp']<=0:self.finish_kill(self.fighters.get(victim.get('downer','')) or attacker,victim,zone)
            return
        armour=ITEMS.get(victim["armour"],{}).get("reduction",0)*(1-pierce)
        if zone=="head":armour=ITEMS.get(victim["helmet"],{}).get("reduction",0)
        amount=min(75.,base*BODY_MULTIPLIERS[zone]*(1-armour))
        absorbed=min(victim["ward"],amount);victim["ward"]-=absorbed;amount-=absorbed
        actual=min(victim['hp'],amount)
        victim["hp"]=max(0.,victim["hp"]-amount)
        if amount>0:victim['last_hurt']=self.clock
        downed=victim['hp']<=0 and self.mode_down(victim,attacker)
        if downed:actual=max(0,actual-1)
        ticket=learning_ticket if learning_ticket is not None else attacker.get('attack_learning') if kind=='hit' else None
        self.learning_damage(attacker,victim,actual,ticket,blocked=base<=0 and victim['block'])
        if kind!="burn":self.balanced_hit(victim,amount,zone)
        if magic=="frost" and amount>0:victim["slow"]=2.5
        if magic=="lightning" and amount>0:
            victim["stamina"]=max(0,victim["stamina"]-12)
            victim["cooldown"]=max(victim["cooldown"],.18)
        if magic=="fire" and amount>0 and kind!="burn":
            victim["burn"]=3.;victim["burn_source"]=attacker["id"];victim["burn_tick"]=0.
        self.emit(kind,source=attacker["id"],target=victim["id"],damage=round(amount,1),zone=zone,weapon=attacker["weapon"])
        if downed:self.script_event('down',attacker,zone)
        if victim["hp"]<=0:self.finish_kill(attacker,victim,zone)

    def finish_kill(self,attacker,victim,zone='body'):
        if victim['dead']>0:return
        victim.update(hp=0.,dead=3.5,windup=0.,attack='',queued_attack='');victim['deaths']+=1
        self.mode_eliminated(victim,attacker)
        if attacker:
            attacker['kills']+=1
            reward=kill_reward(victim["level"])
            penalty=death_penalty(victim["level"],attacker["level"])
            actual_loss=min(victim["skill"],penalty)
            self.grant(attacker,**reward)
            if attacker["dead"]<=0 and attacker.get('downed',0)<=0:
                attacker.update(hp=attacker["max_hp"],stamina=100.)
            self.grant(victim,skill=-penalty)
            self.emit("kill",source=attacker["name"],target=victim["name"],source_id=attacker["id"],target_id=victim["id"],
                      xp=reward["xp"],skill=reward["skill"],coins=reward["coins"],lost_skill=actual_loss)
            self.script_event('kill',attacker,zone)
        else:self.sync_progress(victim)

    def strike(self,attacker):
        ticket=attacker.get('attack_learning')
        try:self.perform_strike(attacker)
        finally:
            if ticket and not ticket['projectile']:self.learning.finish(ticket,miss=True)

    def perform_strike(self,attacker):
        if attacker["spawn_safe"]>0 or attacker["dead"]>0 or attacker["disarmed"]>0 or attacker["fall"]>0 or attacker.get('downed',0)>0:return
        item=ITEMS[attacker["weapon"]]
        if attacker['attack']=='feint':return
        if item["family"]=="rope":self.fire_rope(attacker);return
        if item["family"] in RANGED:
            self.shoot(attacker,item)
            return
        move=MOVES.get(attacker["attack"],MOVES["left"])
        reach=item["reach"]+move["reach"]
        arc=move["arc"]
        for victim in list(self.fighters.values()):
            if victim["dead"]>0 or victim["dodge"]>0 or victim["spawn_safe"]>0 or not self.can_fight(attacker,victim):continue
            dx,dz=victim["x"]-attacker["x"],victim["z"]-attacker["z"]
            if math.hypot(dx,dz)>reach or abs(angle(math.atan2(dx,dz)-attacker["yaw"]))>arc:continue
            facing=abs(angle(math.atan2(-dx,-dz)-victim["yaw"]))<1.15
            armed=ITEMS[victim["weapon"]]["family"]!="unarmed"
            matching=self.guard_matches(attacker,victim)
            if victim["block"] and facing and armed:
                tight=abs(angle(math.atan2(-dx,-dz)-victim["yaw"]))<.55
                if self.clock-victim["block_since"]<=.18 and tight and matching:
                    # A timed blade parry consumes exactly zero stamina.
                    attacker["cooldown"]=max(attacker["cooldown"],.85)
                    self.parry_reward(victim,attacker)
                    self.emit("parry",source=attacker["id"],target=victim["id"],damage=0)
                    self.try_disarm(victim,attacker,parry=True);attacker["cooldown"]=max(attacker["cooldown"],.85)
                    return
            if attacker["attack"]=="disarm":
                if self.try_disarm(attacker,victim):return
                continue
            multiplier=move["multiplier"]
            base=item["damage"]*multiplier
            if victim["block"] and facing and armed:
                if matching:base=0
                else:base*=1-ITEMS.get(victim["shield"],{}).get("reduction",.35)
            height=TARGET_HEIGHTS[attacker.get("aim_zone","body")]+self.lift(attacker)-self.lift(victim)+(1.1 if victim["fall"]>0 else 0)
            if not .12<=height<=2.2:continue
            self.damage(attacker,victim,base,zone_from_height(height),magic=item.get("magic",""),pierce=item.get("armour_pierce",0))

    def shoot(self,attacker,item,spell=""):
        if attacker["dead"]>0 or attacker["spawn_safe"]>0:return
        yaw=attacker["yaw"];pitch=attacker.get("aim_pitch",0.)
        speed=item.get("speed",20)
        height=TARGET_HEIGHTS[attacker.get("aim_zone","body")]
        ticket=attacker.get('attack_learning') if not spell else None
        if ticket and not ticket['done']:ticket['projectile']=True
        self.projectiles.append(dict(id="arrow-"+secrets.token_hex(4),owner=attacker["id"],weapon=attacker["weapon"],
            world_id=attacker["world_id"],origin_x=attacker["x"],origin_y=1.35+self.lift(attacker),origin_z=attacker["z"],
            kind=spell or item.get("family","bow"),magic="frost" if spell=="frostbolt" else "fire" if spell=="firebolt" else item.get("magic",""),
            x=attacker["x"]+math.sin(yaw)*.6,y=1.35+self.lift(attacker),z=attacker["z"]+math.cos(yaw)*.6,
            vx=math.sin(yaw)*speed,vz=math.cos(yaw)*speed,vy=(height-1.35)*2-pitch*speed*.15,
            gravity=item.get("gravity",0),damage=item["damage"],age=0.,life=min(4.,item.get("reach",40)/speed),bounces=0,_learning=ticket))
        self.emit("shoot",source=attacker["id"],weapon=attacker["weapon"])

    def cast_spell(self,f):
        spell=ITEMS.get(f["spell"],{})
        if not spell or f["spell_cd"]>0 or f["stamina"]<spell["cost"] or f["dead"]>0 or f["spawn_safe"]>0:return False
        f["stamina"]-=spell["cost"];f["spell_cd"]=spell["cooldown"]
        if f["spell"]=="heal":f["hp"]=min(f["max_hp"],f["hp"]+spell["healing"])
        elif f["spell"]=="ward":f["ward"]=spell["absorb"];f["ward_time"]=3.
        elif f["spell"]=="shock":
            for target in list(self.fighters.values()):
                if target is not f and math.hypot(f["x"]-target["x"],f["z"]-target["z"])<=spell["reach"]:
                    self.damage(f,target,spell["damage"],"body",kind="spell_hit")
        else:self.shoot(f,spell,f["spell"])
        self.emit("spell",source=f["id"],spell=f["spell"])
        return True

    def tick_objects(self,dt):
        for drop in self.drops:
            drop["age"]+=dt
            if drop["y"]>.06 or drop["vy"]>0:
                drop["x"]+=drop["vx"]*dt;drop["z"]+=drop["vz"]*dt;drop["y"]+=drop["vy"]*dt;drop["vy"]-=9.8*dt
                if drop["y"]<.06:drop["y"]=.06;drop["vy"]=0;drop["vx"]=drop["vz"]=0
        self.drops=[d for d in self.drops if self.clock<d["expires"]]
        alive=[]
        for p in self.projectiles:
            old=(p["x"],p["y"],p["z"]);p["age"]+=dt;p["vy"]-=p["gravity"]*dt
            p["x"]+=p["vx"]*dt;p["y"]+=p["vy"]*dt;p["z"]+=p["vz"]*dt
            if p["age"]>p["life"] or p["y"]<.05:
                self.learning.finish(p.get('_learning'),miss=True)
                continue
            attacker=self.fighters.get(p["owner"])
            if not attacker or attacker["world_id"]!=p["world_id"]:
                self.learning.finish(p.get('_learning'),miss=True)
                continue
            consumed=False
            for victim in self.fighters.values():
                if victim["dead"]>0 or victim["spawn_safe"]>0 or victim["dodge"]>0 or not self.can_fight(attacker,victim):continue
                # Swept segment versus the upright hit capsule; avoids fast-bolt tunnelling.
                dx,dz=p["x"]-old[0],p["z"]-old[2];den=dx*dx+dz*dz
                t=max(0,min(1,((victim["x"]-old[0])*dx+(victim["z"]-old[2])*dz)/den)) if den else 0
                cx,cy,cz=old[0]+t*dx,old[1]+t*(p["y"]-old[1]),old[2]+t*dz
                height=cy-self.lift(victim)+(1.1 if victim["fall"]>0 else 0)
                if math.hypot(cx-victim["x"],cz-victim["z"])>.45 or not .12<=height<=2.2:continue
                facing=abs(angle(math.atan2(-p["vx"],-p["vz"])-victim["yaw"]))<1.15
                blade=ITEMS[victim["weapon"]]["family"] in ("blade","spear","axe","mace")
                timed=victim["block"] and self.clock-victim["block_since"]<=.18
                swinging=victim["windup"]>0 and victim["attack"]!="disarm"
                if blade and facing and (timed or swinging) and p["bounces"]<2:
                    self.learning_reward(p.get('_learning'),-10,True)
                    self.learning.finish(p.get('_learning'))
                    p['_learning']=None
                    self.parry_reward(victim,attacker,True)
                    speed=max(.001,math.hypot(p["vx"],p["vz"]))
                    dx,dy,dz=p.get("origin_x",attacker["x"])-cx,p.get("origin_y",1.35)-cy,p.get("origin_z",attacker["z"])-cz
                    length=max(.001,math.sqrt(dx*dx+dy*dy+dz*dz))
                    p.update(owner=victim["id"],vx=dx/length*speed,vz=dz/length*speed,vy=dy/length*speed,gravity=0.,x=cx+dx/length*.6,y=cy+dy/length*.6,z=cz+dz/length*.6,bounces=p["bounces"]+1,origin_x=cx,origin_y=cy,origin_z=cz)
                    self.emit("deflect",source=victim["id"],target=attacker["id"])
                    break
                base=p["damage"]
                if victim["block"] and facing:
                    base*=1-ITEMS.get(victim["shield"],{}).get("reduction",.52)
                self.damage(attacker,victim,base,zone_from_height(height),kind="projectile_hit",magic=p["magic"],learning_ticket=p.get('_learning'))
                self.learning.finish(p.get('_learning'),miss=True)
                consumed=True;break
            if not consumed:alive.append(p)
        self.projectiles=alive
