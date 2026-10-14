"""Seeded arena rooms, inventory, direction-sensitive guard, footing and ropes."""
import math
import random
import secrets
from collections import Counter
from rules import ITEMS,RANGED

SERVER_CAPACITY=100
WORLD_TYPES=(("Sunstone Court","desert"),("Oak Ruins","forest"),("Winter Keep","snow"),("Tidewatch Fort","coast"),("Ember Basin","volcanic"))


def wrap_angle(a):return (a+math.pi)%math.tau-math.pi


def make_world(identifier,template_id,world_seed,instance=1,overflow_of=None):
    name,biome=WORLD_TYPES[template_id];rng=random.Random(world_seed);props=[]
    count={"desert":18,"forest":24,"snow":16,"coast":20,"volcanic":22}[biome]
    for i in range(count):
        for attempt in range(100):
            a=rng.random()*math.tau;r=rng.uniform(9,30);x,z=math.sin(a)*r,math.cos(a)*r
            radius=rng.uniform(.65,1.2)
            if all(math.hypot(x-p['x'],z-p['z'])>radius+p['radius']+1.4 for p in props):break
        kind="tree" if biome=="forest" and i%2==0 else "ruin" if biome in ("desert","snow") and i%4==0 else "pillar" if i%3==0 else "rock"
        props.append(dict(x=x,z=z,radius=radius,height=rng.uniform(1.4,3.8) if kind!="tree" else rng.uniform(4,6),kind=kind))
    return dict(id=identifier,name=name,biome=biome,seed=world_seed,radius=38,props=props,
                template_id=template_id,instance=instance,server_number=identifier+1,capacity=SERVER_CAPACITY,overflow_of=overflow_of)


def make_worlds(seed):
    return [make_world(i,i,(seed+i*9176)%2**31) for i in range(len(WORLD_TYPES))]


class ArenaFeatures:
    def setup_worlds(self,seed):
        self.worlds=make_worlds(seed if seed is not None else secrets.randbelow(2**31))
        self.default_world=0;self.ropes=[]

    def same_world(self,a,b):return a.get("world_id",0)==b.get("world_id",0)
    def world_for(self,f):return self.worlds[f.get("world_id",0)]

    def populations(self,ignore=()):
        return Counter(f['world_id'] for f in self.fighters.values() if not f['bot'] and f['id'] not in ignore)

    def world_info(self,world_id):
        world=self.worlds[world_id];humans=self.populations()[world_id]
        bots=sum(f['bot'] and f['world_id']==world_id for f in self.fighters.values())
        return dict(world,humans=humans,bots=bots,full=humans>=SERVER_CAPACITY,available=max(0,SERVER_CAPACITY-humans))

    def world_catalog(self):
        humans=self.populations();bots=Counter(f['world_id'] for f in self.fighters.values() if f['bot'])
        # Listing metadata stays small; geometry is sent only for the joined room.
        return [dict({k:v for k,v in w.items() if k!='props'},humans=humans[w['id']],bots=bots[w['id']],
                     full=humans[w['id']]>=SERVER_CAPACITY,available=max(0,SERVER_CAPACITY-humans[w['id']])) for w in self.worlds]

    def create_world(self,source_id):
        source=self.worlds[source_id];template=source['template_id']
        instance=1+max(w['instance'] for w in self.worlds if w['template_id']==template)
        used={w['seed'] for w in self.worlds};seed=self.rng.randrange(2**31)
        while seed in used:seed=self.rng.randrange(2**31)
        world=make_world(len(self.worlds),template,seed,instance,source_id)
        self.worlds.append(world)
        return world['id']

    def ensure_spare(self,world_id):
        counts=self.populations()
        if counts[world_id]<SERVER_CAPACITY:return
        template=self.worlds[world_id]['template_id']
        if not any(w['template_id']==template and counts[w['id']]<SERVER_CAPACITY for w in self.worlds):
            self.create_world(world_id)

    def available_world(self,requested,ignore=()):
        if type(requested) is not int or not 0<=requested<len(self.worlds):raise ValueError('Unknown server.')
        counts=self.populations(ignore)
        if counts[requested]<SERVER_CAPACITY:return requested
        template=self.worlds[requested]['template_id']
        candidates=[w['id'] for w in self.worlds if w['template_id']==template and counts[w['id']]<SERVER_CAPACITY]
        return max(candidates,key=lambda w:(counts[w],-w)) if candidates else self.create_world(requested)

    def choose_world(self,exclude=None,ignore=()):
        counts=self.populations(ignore)
        available=[w['id'] for w in self.worlds if w['id']!=exclude and counts[w['id']]<SERVER_CAPACITY]
        if not available:return self.create_world(exclude if exclude is not None else self.default_world)
        if exclude is None:
            populated=[w for w in available if counts[w]>0]
            if populated:return max(populated,key=lambda w:(counts[w],-w))
            overflow=[w for w in available if self.worlds[w]['overflow_of'] is not None and counts[self.worlds[w]['overflow_of']]>=SERVER_CAPACITY]
            if overflow:return min(overflow)
        return self.rng.choice(available)

    def inventory_assign(self,s,slot,item):
        if not isinstance(slot,int) or not 0<=slot<5:raise ValueError("Choose a slot from 1 to 5.")
        u=s["user"]
        if item and (item not in u["inventory"] or item not in ITEMS or ITEMS[item].get("kind","weapon")!="weapon"):
            raise ValueError("Only purchased weapons may be assigned.")
        for i,value in enumerate(u["weapon_slots"]):
            if value==item and item:u["weapon_slots"][i]=""
        u["weapon_slots"][slot]=item
        if not s["guest"]:self.save()
        return dict(profile=self.profile(u),message="Quick-slot updated.")

    def inventory_switch(self,s,slot):
        if not isinstance(slot,int) or not 0<=slot<5:raise ValueError("Choose a slot from 1 to 5.")
        u=s["user"];item=u["weapon_slots"][slot]
        if not item or item not in u["inventory"]:raise ValueError("This weapon slot is empty.")
        f=self.fighters.get(s["fighter"])
        if f and (f["disarmed"]>0 or f["fall"]>0):raise ValueError("Recover your footing before changing weapon.")
        u["weapon"]=item
        if f:f.update(weapon=item,loadout_weapon=item,attack="",windup=0.,cooldown=.28)
        if not s["guest"]:self.save()
        return dict(profile=self.profile(u))

    def guard_matches(self,attacker,defender):
        direction={"left":"right","right":"left","overhead":"up","thrust":"centre","disarm":"centre"}.get(attacker["attack"],"centre")
        guard=defender.get("guard_dir","centre")
        # A centred guard covers the neutral crossing; explicit side guards counter side cuts.
        return guard==direction or (guard=="centre" and attacker["attack"] in ("left","right","thrust","disarm"))

    def balanced_hit(self,victim,damage,zone):
        if victim["dead"]>0 or damage<=0:return
        victim["balance"]-=min(45.,damage*.8+(12 if zone=="legs" else 0))
        if victim["balance"]<=0:
            chance=max(.03,.75*.4**victim["stability_upgrades"])
            victim["balance"]=35.
            if self.rng.random()<chance:self.knock_down(victim)

    def knock_down(self,f):
        if f["dead"]>0 or f["spawn_safe"]>0:return
        f.update(fall=1.25,fall_duration=1.25,attack="",windup=0.,block=False,jump=0.,queued_attack="")
        self.emit("fall",target=f["id"])

    def collision_props(self,f):
        for p in self.world_for(f)["props"]:
            dx,dz=f["x"]-p["x"],f["z"]-p["z"];distance=math.hypot(dx,dz);radius=p["radius"]+.4
            if .001<distance<radius:f["x"]=p["x"]+dx/distance*radius;f["z"]=p["z"]+dz/distance*radius

    def fire_rope(self,f):
        item=ITEMS[f["weapon"]];targets=[]
        for other in self.fighters.values():
            if other is f or not self.same_world(f,other) or other["dead"]>0 or other["spawn_safe"]>0:continue
            dx,dz=other["x"]-f["x"],other["z"]-f["z"];distance=math.hypot(dx,dz)
            if distance<item["reach"] and abs(wrap_angle(math.atan2(dx,dz)-f["yaw"]))<.2:targets.append((distance,other))
        if targets:
            target=min(targets,key=lambda x:x[0])[1]
            if target["block"] and abs(wrap_angle(math.atan2(f["x"]-target["x"],f["z"]-target["z"])-target["yaw"]))<.7:return
            self.ropes.append(dict(id=secrets.token_hex(5),owner=f["id"],target=target["id"],x=target["x"],y=1.1,z=target["z"],
                world_id=f["world_id"],kind=f["weapon"],created=self.clock,expires=self.clock+1.6))
            if f["weapon"]=="lasso" and self.rng.random()<max(.03,.7*.4**target["stability_upgrades"]):self.knock_down(target)
        elif f["weapon"]=="grappling_rope":
            anchors=[p for p in self.world_for(f)["props"] if math.hypot(p["x"]-f["x"],p["z"]-f["z"])<item["reach"] and abs(wrap_angle(math.atan2(p["x"]-f["x"],p["z"]-f["z"])-f["yaw"]))<.22]
            if anchors:
                p=min(anchors,key=lambda p:math.hypot(p["x"]-f["x"],p["z"]-f["z"]))
                self.ropes.append(dict(id=secrets.token_hex(5),owner=f["id"],target="",x=p["x"],y=p["height"],z=p["z"],
                    world_id=f["world_id"],kind=f["weapon"],created=self.clock,expires=self.clock+1.6))

    def tick_ropes(self,dt):
        active=[]
        for rope in self.ropes:
            owner=self.fighters.get(rope["owner"]);target=self.fighters.get(rope["target"])
            if not owner or owner["dead"]>0 or self.clock>rope["expires"] or owner["world_id"]!=rope["world_id"]:continue
            if target:
                if target["dead"]>0 or not self.same_world(owner,target):continue
                rope.update(x=target["x"],z=target["z"])
            if self.clock-rope["created"]>.25:
                moving=target if target and rope["kind"]=="lasso" else owner
                tx,tz=(owner["x"],owner["z"]) if moving is target else (rope["x"],rope["z"])
                dx,dz=tx-moving["x"],tz-moving["z"];distance=math.hypot(dx,dz)
                if distance>1.8:moving["x"]+=dx/distance*4*dt;moving["z"]+=dz/distance*4*dt;self.collision_props(moving)
            active.append(rope)
        self.ropes=active
