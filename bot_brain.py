"""Bounded 2-5 step combat forecasts with visible-threat tactical reactions."""
import math
from rules import ITEMS,RANGED,TARGET_HEIGHTS,MOVES,grip_risk_multiplier
from bot_learning import context, ATTACKS


class BotBrain:
    def target_for(self,f,enemies):
        def score(a):
            distance=math.hypot(a['x']-f['x'],a['z']-f['z'])
            finish_weight=5 if f['hp']<f['max_hp']*.45 else 2
            return distance+finish_weight*a['hp']/a['max_hp']+(25 if a['spawn_safe']>0 else 0)-(.7 if a['id']==f.get('target_id') else 0)
        return min(enemies,key=score)

    def plan_bot(self,bot,opponent):
        own,enemy=ITEMS[bot['weapon']],ITEMS[opponent['weapon']]
        ranged=own['family'] in RANGED;enemy_ranged=enemy['family'] in RANGED
        actions=('advance','retreat','strafe_l','strafe_r','block','left','right','overhead','thrust','disarm','dodge')
        if ranged:actions=('advance','retreat','strafe_l','strafe_r','thrust','dodge')
        distance=math.hypot(opponent['x']-bot['x'],opponent['z']-bot['z'])
        learning_key=context(bot,opponent)
        threat=opponent['windup']>0
        armour=ITEMS.get(opponent['armour'],{}).get('reduction',0)
        helmet=ITEMS.get(opponent['helmet'],{}).get('reduction',0)
        impact=max(1-armour,1.45*(1-helmet)) if bot['depth']>=4 else 1-armour
        crowd=sum(a is not opponent and a is not bot and a['dead']<=0 and self.same_world(bot,a) and math.hypot(a['x']-bot['x'],a['z']-bot['z'])<3 for a in self.fighters.values())
        beam=[(0.,distance,bot['hp'],opponent['hp'],bot['stamina'],'',bot['cooldown'],opponent['cooldown'],opponent['stamina'])]
        nodes=0
        for ply in range(bot['depth']):
            candidates=[]
            for previous,dist,hp,ehp,stamina,first,cd,ecd,estamina in beam:
                for action in actions:
                    nodes+=1;d,h,e,st,es=dist,hp,ehp,stamina,estamina
                    own_cd,enemy_cd=max(0.,cd-.24),max(0.,ecd-.24)
                    if action=='advance':d=max(.85,d-1.05)
                    elif action=='retreat':d+=.85
                    elif action.startswith('strafe'):d+=.06
                    elif action=='dodge':
                        if st<24:continue
                        st-=24;d+=.75
                    bonus=0
                    if action in ('left','right','overhead','thrust','disarm'):
                        cost=10 if ranged else MOVES[action]['cost']
                        if st<cost or own_cd>0:continue
                        st-=cost;reach=own['reach']+(.35 if action=='thrust' and not ranged else 0)
                        if d<reach:
                            if action=='disarm':
                                if enemy['family'] in ('blade','spear','axe','mace') and es<25 and enemy_cd>.1 and not opponent['block'] and d<=1.8 and self.clock>=opponent['grip_test_after']:
                                    bonus=24*.08*grip_risk_multiplier(opponent['grip_upgrades'])
                            else:
                                damage=own['damage']*(1.2 if action=='overhead' else .85 if action=='thrust' and not ranged else 1)*impact
                                if ranged:damage*=max(.25,1-d/(own['reach']*1.5))*(.55 if math.hypot(opponent['move_x'],opponent['move_z'])>2 else 1)
                                elif opponent['block']:
                                    expected={'left':'right','right':'left','overhead':'up','thrust':'centre'}[action]
                                    if opponent['guard_dir']==expected:damage=0
                                    else:damage*=.65
                                e-=min(75.,damage)
                        own_cd=max(MOVES[action]['windup']+MOVES[action]['follow']+.02,own['cooldown']+(.18 if action=='overhead' else 0))
                    if e<=0:h=bot['max_hp'];st=100
                    elif enemy_cd<=0 and d<enemy['reach']+.2 and es>=10:
                        incoming=enemy['damage']*(1.25 if threat and ply==0 else .6)
                        if enemy_ranged:incoming*=max(.3,1-d/(enemy['reach']*1.4))
                        if action=='block' and bot['weapon']!='fists':incoming*=.25 if enemy_ranged else .05
                        elif action=='dodge':incoming*=.08
                        elif action.startswith('strafe'):incoming*=.5
                        incoming*=1-ITEMS.get(bot['armour'],{}).get('reduction',0)
                        h-=incoming;enemy_cd=enemy['cooldown'];es-=12
                    else:d=max(.8,d-.5)
                    h-=crowd*(.6 if action in ('block','dodge') else 2.)
                    st=min(100.,st+(2 if action=='block' else 4));es=min(100.,es+4)
                    preferred=min(12.,own['reach']*.55) if ranged else own['reach']*.76
                    gain=(ehp-e)*1.5-(hp-h)*1.35+bonus+(dist-d)*(0 if ranged else 1.2)
                    if action=='block' and not threat:gain-=3
                    if action=='retreat' and bot['hp']>bot['max_hp']*.4:gain-=1
                    score=previous+gain*(.76**ply)-abs(d-preferred)*.35-max(0,20-st)*.08
                    if h<=0:score-=220
                    if e<=0:score+=160
                    if action=='advance':score+=.3*(.76**ply)
                    if ply==0:score+=self.learning.bias(learning_key,action)
                    candidates.append((score,d,h,e,st,first or action,own_cd,enemy_cd,es))
            candidates.sort(reverse=True,key=lambda a:a[0]);beam=candidates[:10]
        bot['plan_nodes']=nodes
        if not beam:return 'advance'
        # Explore only nearby tactical choices, never arbitrary suicidal moves.
        options=list(dict.fromkeys(b[5] for b in beam if b[0]>=beam[0][0]-6))
        if len(options)>1 and self.rng.random()<.035:return self.rng.choice(options)
        return beam[0][5]

    def steer_bot(self,f,move):
        mx,mz=move;length=math.hypot(mx,mz)
        if length<.01:return [0.,0.]
        mx,mz=mx/length,mz/length
        for p in self.world_for(f)['props']:
            dx,dz=p['x']-f['x'],p['z']-f['z'];ahead=dx*mx+dz*mz
            side=dx*mz-dz*mx
            if 0<ahead<2.3 and abs(side)<p['radius']+.65:
                direction=-1 if side>0 else 1
                return [mx*.25+mz*direction*.95,mz*.25-mx*direction*.95]
        return [mx,mz]

    def bot_input(self,f):
        mode_input=self.mode_bot_input(f)
        if mode_input is not None:return mode_input
        drops=[d for d in self.drops if d['world_id']==f['world_id']]
        if f['weapon']=='fists' and drops:
            drop=min(drops,key=lambda d:math.hypot(d['x']-f['x'],d['z']-f['z']))
            yaw=math.atan2(drop['x']-f['x'],drop['z']-f['z'])
            return dict(move=self.steer_bot(f,[math.sin(yaw),math.cos(yaw)]),yaw=yaw,pickup=True)
        cached=getattr(self,'_bot_enemies',None)
        enemies=[a for a in cached.get((f['world_id'],f.get('team',-1)),[]) if a is not f and a['dead']<=0] if cached is not None else [a for a in self.fighters.values() if a['dead']<=0 and self.can_fight(f,a)]
        if not enemies:return {}
        target=self.fighters.get(f.get('target_id',''))
        if cached is None or self.clock>=f.get('target_at',0) or not target or target['dead']>0 or not self.can_fight(f,target):
            target=self.target_for(f,enemies);f['target_at']=self.clock+.15
        new_target=target['id']!=f.get('target_id');f['target_id']=target['id']
        memory=f.setdefault('bot_memory',{})
        observation=(target['id'],target['attack_id'])
        if observation!=memory.get('observed'):
            memory.update(observed=observation,seen_at=self.clock)
            if target['attack'] in ('left','right','overhead','thrust'):
                habits=memory.setdefault('habits',{});habits[target['attack']]=habits.get(target['attack'],0)+1
        if (new_target or self.clock>=f['plan_at']) and (getattr(self,'_planning_slots',None) is None or f['id'] in self._planning_slots):
            f['action']=self.plan_bot(f,target);f['plan_at']=self.clock+.18+(5-f['depth'])*.05
        yaw=math.atan2(target['x']-f['x'],target['z']-f['z']);action=f['action']
        mx,mz=math.sin(yaw),math.cos(yaw)
        if action=='retreat':mx,mz=-mx,-mz
        elif action=='strafe_l':mx,mz=-mz,mx
        elif action=='strafe_r':mx,mz=mz,-mx
        elif action not in ('advance','dodge'):mx,mz=0,0
        attack=action if action in ('left','right','overhead','thrust','disarm') else ''
        ranged=ITEMS[f['weapon']]['family'] in RANGED
        if attack and target['block'] and not ranged and attack!='disarm' and f['depth']>=3:
            attack='overhead' if target['guard_dir']=='centre' else 'left' if target['guard_dir'] in ('up','left') else 'right'
        if ranged:
            speed=ITEMS[f['weapon']].get('speed',23);travel=math.hypot(target['x']-f['x'],target['z']-f['z'])/speed
            lead=.45+.12*(f['depth']-2)
            yaw=math.atan2(target['x']+target['move_x']*travel*lead-f['x'],target['z']+target['move_z']*travel*lead-f['z'])
        threatening=[a for a in enemies if a['windup']>0 and a['spawn_safe']<=0 and math.hypot(a['x']-f['x'],a['z']-f['z'])<ITEMS[a['weapon']]['reach']+.4 and ITEMS[a['weapon']]['family'] not in RANGED]
        block=action=='block' and f['weapon']!='fists';guard='centre'
        if threatening:
            danger=min(threatening,key=lambda a:a['windup'])
            stamp=(danger['id'],danger['attack_id'])
            if memory.get('threat')!=stamp:memory.update(threat=stamp,threat_seen=self.clock)
            ready=self.clock-memory['threat_seen']>={2:.24,3:.18,4:.12,5:.085}[f['depth']]
            if ready and f['weapon']!='fists':
                block=True;attack='';mx=mz=0
                yaw=math.atan2(danger['x']-f['x'],danger['z']-f['z'])
                guard={'left':'right','right':'left','overhead':'up'}.get(danger['attack'],'centre')
            elif not f['block']:block=False
        elif block:
            habits=memory.get('habits',{});likely=max(habits,key=habits.get) if habits else 'thrust'
            guard={'left':'right','right':'left','overhead':'up'}.get(likely,'centre')
        dodge=action=='dodge' and not f['last_dodge']
        for p in self.projectiles:
            if p['world_id']!=f['world_id'] or p['owner']==f['id']:continue
            vx,vz=p['vx'],p['vz'];speed2=vx*vx+vz*vz
            if speed2<.1:continue
            t=((f['x']-p['x'])*vx+(f['z']-p['z'])*vz)/speed2
            if 0<t<.16+f['depth']*.035 and math.hypot(p['x']+vx*t-f['x'],p['z']+vz*t-f['z'])<.65:
                if f['stamina']>=24 and not f['last_dodge']:
                    length=math.sqrt(speed2);mx,mz=-vz/length,vx/length;dodge=True;block=False;attack=''
                    memory['dodge_move']=[mx,mz]
                break
        if f['dodge']>0 and 'dodge_move' in memory:mx,mz=memory['dodge_move']
        if f['last_attack']:attack=''
        zone='body'
        if f['depth']>=4:
            head=1.45*(1-ITEMS.get(target['helmet'],{}).get('reduction',0));body=1-ITEMS.get(target['armour'],{}).get('reduction',0)
            zone='legs' if target['balance']<25 else 'head' if head>body else 'body'
        pitch=0.
        if ranged:
            item=ITEMS[f['weapon']];travel=max(.1,math.hypot(target['x']-f['x'],target['z']-f['z'])/item.get('speed',23))
            desired=(TARGET_HEIGHTS[zone]-1.35+.5*item.get('gravity',0)*travel*travel)/travel
            pitch=max(-.8,min(.8,((TARGET_HEIGHTS[zone]-1.35)*2-desired)/(item.get('speed',23)*.15)))
        executed='block' if block else 'dodge' if dodge and f['stamina']>=24 else attack if attack else action if action not in ATTACKS else ''
        self.learning_decision(f,executed,target)
        return dict(move=self.steer_bot(f,[mx,mz]),yaw=yaw,attack=attack,block=block,guard_dir=guard,dodge=dodge,jump=False,
                    aim_zone=zone,aim_pitch=pitch,cast=bool(f['spell']) and f['hp']<f['max_hp']*.45)
