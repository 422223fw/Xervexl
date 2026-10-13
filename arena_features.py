"""Seeded arena rooms, inventory, direction-sensitive guard, footing and ropes."""
import math
import random
import secrets
from rules import ITEMS,RANGED


def wrap_angle(a):return (a+math.pi)%math.tau-math.pi


def make_worlds(seed):
    result=[]
    for index,(name,biome) in enumerate((("Sunstone Court","desert"),("Oak Ruins","forest"),("Winter Keep","snow"),("Tidewatch Fort","coast"),("Ember Basin","volcanic"))):
        world_seed=(seed+index*9176)%2**31;rng=random.Random(world_seed)
        props=[]
        for i in range(14):
            a=rng.random()*math.tau;r=rng.uniform(15,25)
            props.append(dict(x=math.sin(a)*r,z=math.cos(a)*r,radius=rng.uniform(.65,1.2),height=rng.uniform(1.2,3.1),kind="pillar" if i%3==0 else "rock"))
        result.append(dict(id=index,name=name,biome=biome,seed=world_seed,radius=38,props=props))
    return result


class ArenaFeatures:
    def setup_worlds(self,seed):
        self.worlds=make_worlds(seed if seed is not None else secrets.randbelow(2**31))
        self.default_world=0;self.ropes=[]

    def same_world(self,a,b):return a.get("world_id",0)==b.get("world_id",0)
    def world_for(self,f):return self.worlds[f.get("world_id",0)]

    def choose_world(self,exclude=None):
        humans=[f for f in self.fighters.values() if not f["bot"] and f["world_id"]!=exclude]
        if humans and exclude is None:return max(set(f["world_id"] for f in humans),key=lambda w:sum(f["world_id"]==w for f in humans))
        return self.rng.choice([w["id"] for w in self.worlds if w["id"]!=exclude])

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
        f.update(fall=1.25,fall_duration=1.25,attack="",windup=0.,block=False,jump=0.)
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
