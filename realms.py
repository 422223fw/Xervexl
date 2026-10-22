"""Persistent friends-only survival worlds, crafting, mining and creatures."""
import copy
import json
import math
import secrets
from pathlib import Path
import voxel_world as vox
from social import atomic_json
from rules import ITEMS,WEAPONS,GEAR,SPELLS,level_for_xp,xp_for_level

RECIPES={i['id']:dict(wood=max(2,i['damage']//5),iron=max(0,(i['damage']-18)//4)) for i in WEAPONS if i['id']!='fists' and i['family'] not in ('rope',)}
RECIPES.update(knife=dict(wood=2,stone=2),pickaxe=dict(wood=4,stone=3),bow=dict(wood=8,fiber=10),longbow=dict(wood=12,fiber=14),crossbow=dict(wood=10,iron=12,fiber=5),slingshot=dict(wood=3,fiber=5),glass=dict(stone=2),iron=dict(iron_ore=2))
for name in ('stormblade','frostsabre','sunblade','moonbow','emberstaff'):RECIPES[name]['crystal']=12
for item in GEAR+SPELLS:
    if item.get('kind') in ('shield','armour','helmet','spell'):
        RECIPES[item['id']]=dict(wood=8,iron=8 if item['price']<3000 else 20)
        if item['price']>=8000:RECIPES[item['id']]['crystal']=16
DEFAULT_SETTINGS=dict(mobs=True,bots=False,pvp=False,friends_build=True)


class Realms:
    def setup_realms(self):
        self.realms_path=self.path.with_name(self.path.stem+'.realms.json')
        self.realm_directory=self.path.parent/(self.path.stem+'.realms')
        self.realms=json.loads(self.realms_path.read_text('utf-8')) if self.realms_path.exists() else {}
        self.realm_dirty=set();self.realm_saved_at=0.
        for identifier,r in self.realms.items():
            saved=self.realm_directory/(identifier+'.json')
            r['record']=json.loads(saved.read_text('utf-8'))
            self.attach_realm(identifier,r)

    def attach_realm(self,identifier,r):
        r['room']=len(self.worlds)
        self.worlds.append(dict(id=r['room'],realm_id=identifier,name=r['name'],biome='survival',seed=r['record']['seed'],props=[],radius=524288,
                               template_id=0,instance=1,server_number=r['room']+1,capacity=100,overflow_of=None))

    def is_realm(self,f):return bool(f and 0<=f.get('world_id',-1)<len(self.worlds) and self.worlds[f['world_id']].get('realm_id'))
    def realm_for(self,f):return self.realms[self.worlds[f['world_id']]['realm_id']] if self.is_realm(f) else None
    def realm_access(self,r,name):return bool(r and (r['owner']==name.lower() or self.friends_with(r['owner'],name)))

    def save_realms_index(self):atomic_json(self.realms_path,{k:{n:v for n,v in r.items() if n not in ('record','room')} for k,r in self.realms.items()})
    def save_realm(self,identifier):
        atomic_json(self.realm_directory/(identifier+'.json'),self.realms[identifier]['record']);self.realm_dirty.discard(identifier)

    def realm_list(self,s):
        me=s['user']['username'].lower()
        return [dict(id=i,name=r['name'],owner=self.users.get(r['owner'],{}).get('username',r['owner']),mine=r['owner']==me,settings=r['settings'],
                     online=sum(not f['bot'] and f['world_id']==r['room'] for f in self.fighters.values())) for i,r in self.realms.items() if self.realm_access(r,me)]

    def create_realm(self,s,body):
        name=body.get('name','')
        if not isinstance(name,str) or not 3<=len(name.strip())<=40:raise ValueError('World name: 3 to 40 characters.')
        settings={k:body.get(k,v) for k,v in DEFAULT_SETTINGS.items()}
        if any(type(v) is not bool for v in settings.values()):raise ValueError('World settings must be on or off.')
        identifier='realm-'+secrets.token_hex(8);seed=secrets.randbelow(2**24)
        self.realms[identifier]=dict(name=name.strip(),owner=s['user']['username'].lower(),settings=settings,
                                    record=dict(seed=seed,revision=0,edits={},players={}))
        try:self.save_realm(identifier);self.save_realms_index()
        except OSError:self.realms.pop(identifier,None);raise
        self.attach_realm(identifier,self.realms[identifier])
        return dict(realms=self.realm_list(s),created_realm=identifier,message='World created. Confirmed friends can join.')

    def configure_realm(self,s,body):
        r=self.realms.get(body.get('id'))
        if not r or r['owner']!=s['user']['username'].lower():raise ValueError('Only the world owner can change its settings.')
        settings=dict(r['settings'])
        for k in DEFAULT_SETTINGS:
            if k in body:
                if type(body[k]) is not bool:raise ValueError('World settings must be on or off.')
                settings[k]=body[k]
        previous=r['settings'];r['settings']=settings
        try:self.save_realms_index()
        except OSError:r['settings']=previous;raise
        return dict(realms=self.realm_list(s),message='World settings saved.')

    def realm_player(self,f):
        r=self.realm_for(f)
        return r['record']['players'].get(f['name'].lower()) if r and not f['bot'] else None

    def realm_checkpoint(self,f):
        state=self.realm_player(f)
        if state is None:return
        state.update(x=f['x'],y=f.get('y',0),z=f['z'],weapon=f['weapon'],slots=f['realm_slots'])
        state.update({k:f[k] for k in ('shield','armour','helmet','spell')})
        state.update({k:f[k] for k in ('xp','skill','coins','kills','deaths')})
        self.realm_dirty.add(self.worlds[f['world_id']]['realm_id'])

    def join_realm(self,s,body):
        identifier=body.get('id');r=self.realms.get(identifier);me=s['user']['username'].lower()
        if not self.realm_access(r,me):raise ValueError('Only the owner and confirmed friends may join this world.')
        if sum(not f['bot'] and f['world_id']==r['room'] for f in self.fighters.values())>=100:raise ValueError('This world has 100 players.')
        current=self.fighters.get(s['fighter'])
        if current and current['world_id']==r['room']:return self.realm_join_result(s,current)
        self.realm_checkpoint(current)
        for other in self.sessions.values():
            if other['user'] is s['user']:
                old=self.fighters.get(other['fighter']);self.realm_checkpoint(old);self.fighters.pop(other['fighter'],None);other['fighter']=''
        pid='p-'+secrets.token_hex(5);f=self.spawn(pid,s['user']['username']);f['world_id']=r['room']
        state=r['record']['players'].setdefault(me,dict(resources={},inventory=['fists'],slots=['fists','','','',''],weapon='fists',x=0,z=0))
        x,z=state.get('x',0),state.get('z',0);y=vox.floor_at(r['record'],x,z,state.get('y',20)+2)
        weapon=state['weapon'] if state['weapon'] in state['inventory'] else 'fists'
        f.update(x=x,y=y,z=z,vy=0.,realm_grounded=True,weapon=weapon,loadout_weapon=weapon,realm_slots=list(state['slots']),
                 level=1,xp=0,skill=0,coins=0,health_upgrades=0,stability_upgrades=0,grip_upgrades=0,max_hp=100.,hp=100.)
        f.update({k:state.get(k,'') for k in ('shield','armour','helmet','spell')})
        f.update({k:state.get(k,0) for k in ('xp','skill','coins','kills','deaths')});f['level']=level_for_xp(f['xp'])
        s['fighter']=pid;self.realm_checkpoint(f);self.save_realm(identifier)
        return self.realm_join_result(s,f)

    def realm_profile(self,s,f):
        state=self.realm_player(f);virtual=dict(s['user']);virtual.update({k:f[k] for k in ('xp','skill','coins','kills','deaths','health_upgrades','grip_upgrades','stability_upgrades')});p=self.profile(virtual)
        p.update(inventory=list(state['inventory']),weapon=f['weapon'],weapon_slots=list(f['realm_slots']),
                 max_hp=100,realm=True,resources=dict(state['resources']))
        p.update({k:f[k] for k in ('shield','armour','helmet','spell')})
        return p

    def session_profile(self,s):
        f=self.fighters.get(s['fighter'])
        return self.realm_profile(s,f) if self.is_realm(f) else self.profile(s['user'])

    def flush_realms(self):
        for f in self.fighters.values():self.realm_checkpoint(f)
        for identifier in list(self.realm_dirty):self.save_realm(identifier)

    def learning_close(self):
        self.flush_realms();super().learning_close()

    def realm_join_result(self,s,f):
        return dict(player=f['id'],profile=self.realm_profile(s,f),world=self.world_info(f['world_id']),worlds=self.world_catalog(),realms=self.realm_list(s))

    def realm_inventory(self,s,route,body):
        f=self.fighters.get(s['fighter']);state=self.realm_player(f)
        if state is None or not self.realm_access(self.realm_for(f),f['name']):raise ValueError('Join an accessible survival world first.')
        if f['dead']>0 or f['disarmed']>0 or f['fall']>0:raise ValueError('Recover before switching weapons.')
        slot=body.get('slot')
        if type(slot) is not int or not 0<=slot<5:raise ValueError('Select a slot from 1 to 5.')
        if route=='/inventory/assign':
            item=body.get('item')
            if item not in state['inventory'] or ITEMS.get(item,{}).get('kind','weapon')!='weapon':raise ValueError('Craft that weapon first.')
            f['realm_slots'][slot]=item
        else:
            weapon=f['realm_slots'][slot]
            if not weapon:raise ValueError('That slot is empty.')
            self.cancel_attack(f,.3);f['weapon']=f['loadout_weapon']=weapon
        self.realm_checkpoint(f);self.save_realm(self.worlds[f['world_id']]['realm_id'])
        return dict(profile=self.realm_profile(s,f))

    def realm_craft(self,s,body):
        f=self.fighters.get(s['fighter']);state=self.realm_player(f);item=body.get('item')
        if state is None or not self.realm_access(self.realm_for(f),f['name']) or not isinstance(item,str) or item not in RECIPES:raise ValueError('Choose an available crafting recipe in your world.')
        if f['dead']>0 or f['fall']>0:raise ValueError('Wait until you recover.')
        recipe=RECIPES[item]
        if item in ITEMS and item in state['inventory']:raise ValueError('You already crafted that weapon.')
        if any(state['resources'].get(k,0)<v for k,v in recipe.items()):raise ValueError('Gather the required materials first.')
        before=copy.deepcopy(state)
        for k,v in recipe.items():state['resources'][k]-=v
        if item in ITEMS:
            state['inventory'].append(item)
            kind=ITEMS[item].get('kind','weapon')
            if kind=='weapon':
                if '' in f['realm_slots']:f['realm_slots'][f['realm_slots'].index('')]=item
                f['weapon']=f['loadout_weapon']=item;self.cancel_attack(f,.3)
            else:f[kind]=item
        else:state['resources'][item]=state['resources'].get(item,0)+1
        self.realm_checkpoint(f)
        try:self.save_realm(self.worlds[f['world_id']]['realm_id'])
        except OSError:
            state.clear();state.update(before);f['realm_slots']=list(before['slots']);f['weapon']=f['loadout_weapon']=before['weapon']
            f.update({k:before.get(k,'') for k in ('shield','armour','helmet','spell')});raise
        return dict(profile=self.realm_profile(s,f),message='Crafted '+item+'.')

    def realm_equip(self,s,body):
        f=self.fighters.get(s['fighter']);state=self.realm_player(f);item=body.get('item')
        if state is None or not self.realm_access(self.realm_for(f),f['name']) or not isinstance(item,str) or item not in state['inventory']:raise ValueError('Craft that equipment first.')
        if f['dead']>0 or f['fall']>0 or f['disarmed']>0:raise ValueError('Recover before equipping.')
        kind=ITEMS[item].get('kind','weapon');key='weapon' if kind=='weapon' else kind;previous=f[key];f[key]=item
        if kind=='weapon':f['loadout_weapon']=item;self.cancel_attack(f,.3)
        self.realm_checkpoint(f)
        try:self.save_realm(self.worlds[f['world_id']]['realm_id'])
        except OSError:f[key]=previous;self.realm_checkpoint(f);raise
        return dict(profile=self.realm_profile(s,f),message='Equipped '+item+'.')

    def realm_can_build(self,f):
        r=self.realm_for(f)
        return bool(r and not f['bot'] and self.realm_access(r,f['name']) and (r['owner']==f['name'].lower() or r['settings']['friends_build']))

    def realm_aim(self,f):
        r=self.realm_for(f);pitch=f.get('aim_pitch',0);yaw=f['yaw']
        return vox.ray(r['record'],(f['x'],self.lift(f)+1.84,f['z']),(math.sin(yaw)*math.cos(pitch),-math.sin(pitch),math.cos(yaw)*math.cos(pitch))) if r else None

    def realm_build_tick(self,f,inp,dt):
        f['mine_progress']=0.
        if not self.is_realm(f) or f['bot']:return
        building=inp.get('build_mode',False);f['build_mode']=building
        if not building or not self.realm_can_build(f) or f['dead']>0 or f['fall']>0:
            f['mine_target']=None;f['last_place']=bool(inp.get('place'));return
        hit=self.realm_aim(f);f['aim_block']=hit
        if not hit:f['mine_target']=None;f['last_place']=bool(inp.get('place'));return
        r=self.realm_for(f);state=self.realm_player(f);cell=hit['cell'];key=','.join(map(str,cell));material=hit['block']['material']
        if inp.get('mine') and material!='bedrock':
            if f.get('mine_target')!=cell:f['mine_target']=cell;f['mine_elapsed']=0.;f['mining_started']=self.clock
            f['mine_elapsed']=f.get('mine_elapsed',0)+dt
            seconds=vox.HARDNESS.get(material,1.)*(.55 if f['weapon']=='pickaxe' else 1.7 if material in ('stone','iron_ore','iron','crystal') else 1)
            f['mine_progress']=min(1,f['mine_elapsed']/seconds)
            if f['mine_progress']>=1:
                before=copy.deepcopy(r['record'])
                record=r['record'];record['edits'][key]=None;record['revision']+=1
                loot='fiber' if material=='leaves' else 'dirt' if material=='grass' else material
                state['resources'][loot]=state['resources'].get(loot,0)+1
                self.realm_checkpoint(f)
                try:self.save_realm(self.worlds[f['world_id']]['realm_id'])
                except OSError:r['record']=before;f['mine_target']=None;raise
                self.emit('mine',source=f['id'],point=hit['point'],material=material);f['mine_target']=None
        else:f['mine_target']=None
        if inp.get('place') and not f.get('last_place') and hit['adjacent']:
            target=hit['adjacent'];kind=inp.get('build_material','wood');shape=inp.get('build_shape','cube');rotation=inp.get('build_rotation',0)
            if kind in vox.MATERIALS and shape in vox.SHAPES and state['resources'].get(kind,0)>0 and not vox.block(r['record'],*target):
                tx,ty,tz=((n+.5)*vox.CELL for n in target)
                occupied=any(a['world_id']==f['world_id'] and a['dead']<=0 and abs(a['x']-tx)<.6 and abs(a['z']-tz)<.6 and a.get('y',0)<ty+.25 and a.get('y',0)+2>ty-.25 for a in self.fighters.values())
                if not occupied:
                    before=copy.deepcopy(r['record'])
                    r['record']['edits'][','.join(map(str,target))]=dict(material=kind,shape=shape,rotation=rotation%4)
                    r['record']['revision']+=1;state['resources'][kind]-=1
                    self.realm_checkpoint(f)
                    try:self.save_realm(self.worlds[f['world_id']]['realm_id'])
                    except OSError:r['record']=before;raise
                    self.emit('build',source=f['id'],point=(tx,ty,tz),material=kind)
        f['last_place']=bool(inp.get('place'))

    def realm_move(self,f,old_x,old_z,dt):
        r=self.realm_for(f)
        if not r:return
        record=r['record'];feet=f.get('y',2.5)+math.sin((.55-f['jump'])/.55*math.pi)*.65 if f['jump']>0 else f.get('y',2.5)
        blocked=any(vox.solid(record,f['x']+x,feet+y,f['z']+z) for x,z in ((-.22,-.22),(-.22,.22),(.22,-.22),(.22,.22)) for y in (.54,1.1,1.65))
        if blocked:f['x'],f['z']=old_x,old_z;f['move_x']=f['move_z']=0.
        surface=max(vox.floor_at(record,f['x']+x,f['z']+z,feet+.53) for x,z in ((-.18,-.18),(-.18,.18),(.18,-.18),(.18,.18)))
        if surface>=f.get('y',2.5)-.03 and surface<=feet+.53:
            f['y']=surface;f['vy']=0.;f['realm_grounded']=True
        else:
            f['vy']=max(-25.,f.get('vy',0)-9.8*dt);f['y']=max(surface,f.get('y',2.5)+f['vy']*dt)
            f['realm_grounded']=f['y']<=surface+.01
        self.realm_checkpoint(f)

    def realm_trace(self,world_id,start,end):
        world=self.worlds[world_id]
        if not world.get('realm_id'):return None
        delta=tuple(b-a for a,b in zip(start,end));distance=math.sqrt(sum(v*v for v in delta))
        return vox.ray(self.realms[world['realm_id']]['record'],start,delta,distance) if distance>1e-6 else None

    def drop_floor(self,d):
        world=self.worlds[d['world_id']]
        return vox.floor_at(self.realms[world['realm_id']]['record'],d['x'],d['z'],d['y']+.2)+.06 if world.get('realm_id') else .06

    def realm_snapshot(self,f):
        r=self.realm_for(f)
        if not r:return {}
        cx,cz=int(f['x']/vox.CELL),int(f['z']/vox.CELL)
        edits={k:v for k,v in r['record']['edits'].items() if abs(int(k.split(',')[0])-cx)<=64 and abs(int(k.split(',')[2])-cz)<=64}
        state=self.realm_player(f)
        return dict(id=self.worlds[f['world_id']]['realm_id'],seed=r['record']['seed'],revision=r['record']['revision'],edits=edits,settings=r['settings'],
                    owner=r['owner'],can_build=self.realm_can_build(f),resources=dict(state['resources']) if state else {},recipes=RECIPES,
                    build_mode=f.get('build_mode',False),mine_progress=f.get('mine_progress',0),aim_block=f.get('aim_block'))

    def tick_realms(self):
        active={f['world_id'] for f in self.fighters.values() if not f['bot'] and self.is_realm(f)}
        for r in self.realms.values():
            bots=[f for f in self.fighters.values() if f['world_id']==r['room'] and f['bot']]
            wanted_kinds=(['raider','revenant','golem','raider','revenant','golem'] if r['settings']['mobs'] else [])+(['sparring']*4 if r['settings']['bots'] else []) if r['room'] in active else []
            for f in list(bots):
                if f.get('mob_kind') not in wanted_kinds:self.fighters.pop(f['id'],None);bots.remove(f)
                else:wanted_kinds.remove(f['mob_kind'])
            for kind in wanted_kinds:
                self.bot_serial+=1;f=self.spawn('creature-'+secrets.token_hex(5),'Wandering '+('raider' if len(bots)%3==0 else 'revenant' if len(bots)%3==1 else 'golem'),True,2+len(bots)%4)
                f.update(world_id=r['room'],mob_kind=kind,x=f['x']*1.5,z=f['z']*1.5,name='Sparring fighter' if kind=='sparring' else 'Wild '+kind)
                rank=1+len(bots);f.update(y=vox.floor_at(r['record'],f['x'],f['z'],30),level=rank,xp=xp_for_level(rank),spawn_safe=1.5)
                if kind!='sparring':
                    weapon={'raider':'axe','revenant':'knife','golem':'mace'}[kind];hp={'raider':100.,'revenant':80.,'golem':150.}[kind]
                    f.update(weapon=weapon,loadout_weapon=weapon,hp=hp,max_hp=hp,armour='',helmet='',shield='',spell='')
                bots.append(f)
        if self.clock-self.realm_saved_at>=2:
            for i in list(self.realm_dirty):self.save_realm(i)
            self.realm_saved_at=self.clock
