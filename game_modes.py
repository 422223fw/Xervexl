"""Authoritative rounds, squads, reviving and a bounded world/rule workshop."""
import json
import math
import re
import secrets
from pathlib import Path
from rules import ITEMS, PERSISTENT

MODES = [
    dict(id='squads100',name='Last Squad / 100',players=100,team_size=4,revives=True,survival=True,goal=0),
    dict(id='solo100',name='Last Fighter / 100',players=100,team_size=1,revives=False,survival=True,goal=0),
    dict(id='duos100',name='Last Duo / 100',players=100,team_size=2,revives=True,survival=True,goal=0),
    dict(id='squads40',name='Squad Skirmish / 40',players=40,team_size=4,revives=True,survival=True,goal=0),
    dict(id='clash20',name='Clash / 10 vs 10',players=20,team_size=10,revives=False,survival=False,goal=25),
    dict(id='duel',name='Duel / First to 3',players=2,team_size=1,revives=False,survival=False,goal=3),
    dict(id='blades',name='Blade Brawl / First to 12',players=16,team_size=1,revives=False,survival=False,goal=12,loadout='arming'),
    dict(id='archers',name='Archer Squads / 24',players=24,team_size=4,revives=True,survival=True,goal=0,loadout='bow'),
]
WIN_REWARD=dict(xp=650,coins=350,skill=25)


def parse_script(text):
    if not isinstance(text,str) or len(text)>4096:raise ValueError('Rule code must be at most 4096 characters.')
    result=[]
    for line_no,line in enumerate(text.splitlines(),1):
        line=line.strip()
        if not line or line.startswith('#'):continue
        match=re.fullmatch(r'on (start|kill|down|revive|win)(?: if (head|low_health))? (heal|stamina|score|xp|coins|weapon) ([A-Za-z0-9_]+)',line)
        if not match:raise ValueError(f'Code line {line_no}: use on EVENT [if head|low_health] ACTION VALUE.')
        event,condition,action,value=match.groups()
        if action=='weapon':
            if value not in ITEMS or ITEMS[value].get('kind','weapon')!='weapon':raise ValueError(f'Code line {line_no}: unknown weapon.')
        elif not value.isdigit() or not 0<=int(value)<=1000:raise ValueError(f'Code line {line_no}: value must be 0 to 1000.')
        result.append((event,condition,action,value))
        if len(result)>48:raise ValueError('Use at most 48 event instructions.')
    return result


class GameModes:
    def setup_modes(self):
        self.matches={}
        self.workshop_path=self.path.with_name(self.path.stem+'.workshop.json')
        self.blueprints=json.loads(self.workshop_path.read_text('utf-8')) if self.workshop_path.exists() else {}

    def mode_catalog(self):
        return [dict(m,ranked=True,description='Last surviving team wins' if m['survival'] else f"First team to {m['goal']} eliminations wins") for m in MODES]+[
            dict(v['mode'],ranked=False,description='Community world / match-only scripted rewards',owner=v['owner']) for v in self.blueprints.values()]

    def mode_config(self,identifier):
        found=next((m for m in MODES if m['id']==identifier),None)
        if found:return dict(found,ranked=True)
        if identifier in self.blueprints:return dict(self.blueprints[identifier]['mode'],ranked=False)
        raise ValueError('Unknown game mode.')

    def save_blueprint(self,s,body):
        from arena_features import WORLD_TYPES
        name=body.get('name','');props=body.get('props',[]);biome=body.get('biome',0)
        if not isinstance(name,str) or not 3<=len(name.strip())<=32:raise ValueError('Name your world with 3 to 32 characters.')
        if type(biome) is not int or not 0<=biome<len(WORLD_TYPES):raise ValueError('Choose a biome.')
        if not isinstance(props,list) or len(props)>80:raise ValueError('A world can contain at most 80 placed objects.')
        cleaned=[]
        for prop in props:
            if not isinstance(prop,dict) or prop.get('kind') not in ('tree','rock','ruin','pillar'):raise ValueError('Unknown world object.')
            values={k:prop.get(k) for k in ('x','z','radius','height')}
            if any(type(v) not in (int,float) or not math.isfinite(v) for v in values.values()):raise ValueError('Invalid object coordinates.')
            if math.hypot(values['x'],values['z'])>32 or not .5<=values['radius']<=3 or not 1<=values['height']<=8:raise ValueError('Object is outside the editor bounds.')
            if any(math.hypot(values['x']-p['x'],values['z']-p['z'])<values['radius']+p['radius']+.6 for p in cleaned):raise ValueError('Leave space between objects.')
            cleaned.append(dict(values,kind=prop['kind']))
        count=body.get('players',20);team=body.get('team_size',4)
        if type(count) is not int or count not in (8,20,40,100) or type(team) is not int or team not in (1,2,4,10) or count%team:raise ValueError('Choose a player count divisible by the team size.')
        code=body.get('code','');parse_script(code)
        identifier=body.get('id') or 'custom-'+secrets.token_hex(5)
        if not isinstance(identifier,str) or not re.fullmatch(r'custom-[0-9a-f]{10}',identifier):raise ValueError('Invalid world identifier.')
        owner=s['user']['username'].lower()
        if identifier in self.blueprints and self.blueprints[identifier]['owner']!=owner:raise ValueError('Only the creator can edit this world.')
        if identifier not in self.blueprints and sum(b['owner']==owner for b in self.blueprints.values())>=24:raise ValueError('You can save up to 24 worlds.')
        mode=dict(id=identifier,name=name.strip(),players=count,team_size=team,revives=team>1,survival=bool(body.get('survival',True)),goal=20)
        blueprint=dict(owner=owner,biome=biome,props=cleaned,code=code,mode=mode,revision=self.blueprints.get(identifier,{}).get('revision',0)+1)
        updated=dict(self.blueprints);updated[identifier]=blueprint
        temporary=self.workshop_path.with_suffix('.tmp');temporary.write_text(json.dumps(updated,indent=2),encoding='utf-8');temporary.replace(self.workshop_path)
        self.blueprints=updated
        return dict(saved_mode=identifier,modes=self.mode_catalog(),message='World and rule code saved. Custom rewards stay inside this match.')

    def match_for(self,f):return self.matches.get(f.get('world_id',-1))

    def allied(self,a,b):return self.same_world(a,b) and a.get('team',-1)>=0 and a.get('team')==b.get('team')

    def can_fight(self,a,b):
        if a is b or a['world_id']!=b['world_id'] or a.get('team',-1)>=0 and a.get('team')==b.get('team'):return False
        match=self.matches.get(a['world_id'])
        return not (a.get('downed',0)>0 or a.get('eliminated') or b.get('eliminated') or match and match['phase']!='playing')

    def prepare_bot_frame(self):
        self._bot_enemies=None;self._downed_allies=None
        if len(self.fighters)<=40:return
        rooms={};self._bot_enemies={};self._downed_allies={}
        for f in self.fighters.values():
            if f['dead']<=0 and not f.get('eliminated'):rooms.setdefault(f['world_id'],[]).append(f)
        for room,actors in rooms.items():
            for team in {f.get('team',-1) for f in actors}:
                self._bot_enemies[(room,team)]=[a for a in actors if team<0 or a.get('team',-1)!=team]
                self._downed_allies[(room,team)]=[a for a in actors if team>=0 and a.get('team')==team and a.get('downed',0)>0]

    def join_mode(self,s,identifier,biome=None):
        from arena_features import WORLD_TYPES,make_world
        mode=self.mode_config(identifier);current=self.fighters.get(s['fighter'])
        revision=self.blueprints.get(identifier,{}).get('revision',0)
        if current and self.match_for(current) and self.match_for(current)['mode']['id']==identifier and self.match_for(current).get('revision',0)==revision:return self.mode_join_result(s,current)
        if biome is not None and (type(biome) is not int or not 0<=biome<len(WORLD_TYPES)):raise ValueError('Unknown biome.')
        candidates=[m for m in self.matches.values() if m['mode']['id']==identifier and m.get('revision',0)==revision and m['phase'] in ('waiting','countdown')
                    and sum(not f['bot'] and f['world_id']==m['world_id'] for f in self.fighters.values())<mode['players']]
        if candidates:match=candidates[0]
        else:
            template=self.blueprints[identifier]['biome'] if identifier in self.blueprints else biome if biome is not None else self.rng.randrange(len(WORLD_TYPES))
            room=len(self.worlds);world=make_world(room,template,self.rng.randrange(2**31))
            world.update(mode_id=identifier,mode_name=mode['name'],capacity=mode['players'])
            if identifier in self.blueprints:world.update(name=mode['name'],props=[dict(p) for p in self.blueprints[identifier]['props']])
            self.worlds.append(world)
            match=dict(world_id=room,mode=mode,phase='waiting',roster={},scores={},paid=False,round_id='',ends_at=0,started=0,winner=-1,
                       revision=revision,script=parse_script(self.blueprints.get(identifier,{}).get('code','')))
            self.matches[room]=match
        room=match['world_id']
        humans=[f for f in self.fighters.values() if f['world_id']==room and not f['bot']]
        teams={i:sum(f.get('team')==i for f in humans) for i in range(mode['players']//mode['team_size'])}
        team=min((t for t,n in teams.items() if n<mode['team_size']),key=lambda t:(-teams[t],t))
        replacement=next((f for f in self.fighters.values() if f['world_id']==room and f['bot'] and f.get('team')==team),None)
        if replacement:self.fighters.pop(replacement['id'])
        pid=self.join(s,room,change_world=True);f=self.fighters[pid];f.update(team=team,downed=0.,eliminated=False,revive_progress=0.,reviver='',last_hurt=-999.,match_score=0,match_xp=0,match_coins=0)
        self.place_squad(f)
        if mode.get('loadout'):f['weapon']=f['loadout_weapon']=mode['loadout']
        if match['phase']=='waiting':self.start_countdown(match)
        self.fill_match(match)
        return self.mode_join_result(s,f)

    def mode_join_result(self,s,f):
        return dict(player=f['id'],profile=self.profile(s['user']),world=self.world_info(f['world_id']),worlds=self.world_catalog(),match=self.match_state(f['world_id']),message='Joined '+self.match_for(f)['mode']['name'])

    def place_squad(self,f):
        match=self.match_for(f);count=match['mode']['players']//match['mode']['team_size'];a=(f['team']+.5)*math.tau/count
        f.update(x=math.sin(a)*26+self.rng.uniform(-1,1),z=math.cos(a)*26+self.rng.uniform(-1,1),yaw=a+math.pi,body_yaw=a+math.pi)
        self.collision_props(f)

    def start_countdown(self,match):
        match.update(phase='countdown',ends_at=self.clock+12,round_id=secrets.token_hex(8),paid=False,winner=-1,scores={},roster={})
        for f in self.fighters.values():
            if f['world_id']==match['world_id']:f.update(match_score=0,match_xp=0,match_coins=0)
        self.fill_match(match)

    def fill_match(self,match):
        mode=match['mode'];room=match['world_id'];actors=[f for f in self.fighters.values() if f['world_id']==room]
        for team in range(mode['players']//mode['team_size']):
            for _ in range(mode['team_size']-sum(f.get('team')==team for f in actors)):
                self.bot_serial+=1;f=self.spawn('match-'+str(self.bot_serial),'Fighter '+str(self.bot_serial),True,2+self.bot_serial%4)
                f.update(world_id=room,team=team,downed=0.,eliminated=False,revive_progress=0.,reviver='',last_hurt=-999.,match_score=0,match_xp=0,match_coins=0,plan_at=self.clock+self.rng.random()*.3)
                if mode.get('loadout'):f['weapon']=f['loadout_weapon']=mode['loadout']
                self.place_squad(f);actors.append(f)

    def mode_down(self,victim,attacker):
        match=self.match_for(victim)
        if not match or not match['mode']['survival'] or not match['mode']['revives'] or victim.get('downed',0)>0:return False
        if not any(a is not victim and self.allied(a,victim) and a['dead']<=0 and a.get('downed',0)<=0 for a in self.fighters.values()):return False
        victim.update(hp=1.,downed=24.,down_hp=40.,downer=attacker['id'] if attacker else '',attack='',windup=0.,block=False,queued_attack='',burn=0.,revive_progress=0.,reviver='')
        self.emit('down',source=attacker['id'] if attacker else '',target=victim['id'])
        return True

    def mode_eliminated(self,victim,attacker):
        match=self.match_for(victim)
        if match:
            victim.update(downed=0.,revive_progress=0.,reviver='')
            if match['mode']['survival']:victim.update(eliminated=True,dead=99999.)
            if attacker:match['scores'][attacker.get('team',-1)]=match['scores'].get(attacker.get('team',-1),0)+1

    def revive_hint(self,f):
        if not f or not self.match_for(f) or f['dead']>0 or f.get('downed',0)>0:return {}
        near=[a for a in self.fighters.values() if self.allied(f,a) and a.get('downed',0)>0 and math.hypot(a['x']-f['x'],a['z']-f['z'])<2.2]
        if not near:return {}
        a=min(near,key=lambda a:math.hypot(a['x']-f['x'],a['z']-f['z']))
        return dict(id=a['id'],name=a['name'],progress=a.get('revive_progress',0)/3.,bleedout=a['downed'])

    def mode_bot_input(self,f):
        match=self.match_for(f)
        if not match:return None
        if match['phase']!='playing' or f.get('downed',0)>0 or f.get('eliminated'):return {}
        cached=getattr(self,'_downed_allies',None)
        allies=cached.get((f['world_id'],f['team']),[]) if cached is not None else [a for a in self.fighters.values() if self.allied(f,a) and a.get('downed',0)>0]
        if not allies:return None
        a=min(allies,key=lambda a:math.hypot(a['x']-f['x'],a['z']-f['z']))
        distance=math.hypot(a['x']-f['x'],a['z']-f['z'])
        foes=[e for e in self.fighters.values() if self.can_fight(f,e) and e['dead']<=0 and e.get('downed',0)<=0]
        danger=min((math.hypot(e['x']-f['x'],e['z']-f['z']) for e in foes),default=99)
        if distance>9 or danger<3 and a['downed']>5:return None
        yaw=math.atan2(a['x']-f['x'],a['z']-f['z'])
        return dict(move=self.steer_bot(f,[math.sin(yaw),math.cos(yaw)]) if distance>1.7 else [0,0],yaw=yaw,revive=distance<2.2)

    def script_event(self,event,actor,zone='body'):
        match=self.match_for(actor)
        if not match or match['mode']['ranked']:return
        for trigger,condition,action,value in match['script']:
            if trigger!=event or condition=='head' and zone!='head' or condition=='low_health' and actor['hp']>=actor['max_hp']*.4:continue
            if action=='weapon':actor['weapon']=actor['loadout_weapon']=value
            elif action=='heal' and actor['dead']<=0 and actor.get('downed',0)<=0:actor['hp']=min(actor['max_hp'],actor['hp']+int(value))
            elif action=='stamina':actor['stamina']=min(100,actor['stamina']+int(value))
            else:
                key={'score':'match_score','xp':'match_xp','coins':'match_coins'}.get(action)
                if key:actor[key]=min(1000000,actor.get(key,0)+int(value))

    def mode_win(self,match,team):
        if match['paid']:return
        match.update(paid=True,winner=team,phase='finished',ends_at=self.clock+18)
        reward=WIN_REWARD if match['mode']['ranked'] else dict(xp=0,coins=0,skill=0)
        for name,side in match['roster'].items():
            if side!=team or name not in self.users:continue
            user=self.users[name];actor=next((f for f in self.fighters.values() if not f['bot'] and f['name'].lower()==name),None)
            actor_match=self.match_for(actor) if actor else None
            if actor and (not actor_match or actor_match['mode']['ranked']):self.grant(actor,**reward)
            else:
                for k,v in reward.items():user[k]+=v
                self.save()
        for f in list(self.fighters.values()):
            if f['world_id']==match['world_id'] and f.get('team')==team:
                if f['bot']:self.grant(f,**reward)
                self.script_event('win',f)
        self.emit('victory',world_id=match['world_id'],team=team,mode=match['mode']['name'],**reward)

    def tick_modes(self,dt):
        for match in list(self.matches.values()):
            room=match['world_id'];actors=[f for f in self.fighters.values() if f['world_id']==room]
            humans=[f for f in actors if not f['bot']]
            if not humans:
                for f in actors:self.fighters.pop(f['id'],None)
                match.update(phase='waiting',roster={});continue
            if match['phase']=='countdown':
                if self.clock<match['ends_at']:continue
                match.update(phase='playing',started=self.clock,roster={f['name'].lower():f['team'] for f in humans})
                for f in actors:f['spawn_safe']=1.5;self.script_event('start',f)
            if match['phase']=='finished':
                if self.clock>=match['ends_at']:
                    for f in actors:
                        if f['bot']:self.fighters.pop(f['id'],None)
                        else:
                            f.update(hp=f['max_hp'],stamina=100.,dead=0.,eliminated=False,downed=0.,revive_progress=0.,attack='',windup=0.,burn=0.,fall=0.,spawn_safe=1.5,weapon=f['loadout_weapon'])
                            self.place_squad(f)
                    self.projectiles=[p for p in self.projectiles if p['world_id']!=room]
                    self.start_countdown(match)
                continue
            active=[f for f in actors if f['dead']<=0 and not f.get('eliminated')]
            channels={}
            for f in active:
                inp=f['input'] if not f['bot'] else f.get('mode_input',{})
                hint=self.revive_hint(f) if inp.get('revive') else {}
                if hint and not inp.get('attack') and not inp.get('block') and math.hypot(*inp.get('move',[0,0]))<.25 and self.clock-f.get('last_hurt',-999)>.25 and (f['bot'] or self.clock-f['last_input']<.5):channels.setdefault(hint['id'],f)
            for f in active:
                if f.get('downed',0)>0:
                    f['downed']=max(0,f['downed']-dt);rescuer=channels.get(f['id'])
                    if rescuer and self.clock-f.get('last_hurt',-999)>.25:
                        f['revive_progress']=f.get('revive_progress',0)+dt if f.get('reviver')==rescuer['id'] else dt;f['reviver']=rescuer['id']
                        if f['revive_progress']>=3:
                            f.update(downed=0.,hp=f['max_hp']*.5,stamina=50.,spawn_safe=1.,revive_progress=0.,reviver='',fall=0.,balance=50.,burn=0.)
                            self.grant(rescuer,xp=20,skill=1);self.script_event('revive',rescuer)
                            self.emit('revive',source=rescuer['id'],target=f['id']);continue
                    else:f.update(revive_progress=0.,reviver='')
                    upright=any(a.get('team')==f['team'] and a.get('downed',0)<=0 and a is not f for a in active)
                    if f['downed']<=0 or not upright:self.finish_kill(self.fighters.get(f.get('downer','')),f)
            if match['mode']['survival']:
                radius=max(3.,36-max(0,self.clock-match['started']-25)*.14)
                for f in active:
                    if f['dead']<=0 and math.hypot(f['x'],f['z'])>radius:
                        f['hp']-=dt*10
                        if f['hp']<=0:
                            if not self.mode_down(f,None):self.finish_kill(None,f)
                teams={f['team'] for f in actors if not f.get('eliminated') and f['dead']<=0 and f.get('downed',0)<=0}
                if len(teams)<=1:self.mode_win(match,next(iter(teams),-1))
            else:
                winners=[t for t,n in match['scores'].items() if n>=match['mode']['goal']]
                if winners:self.mode_win(match,winners[0])

    def match_state(self,room):
        match=self.matches.get(room)
        if not match:return {}
        actors=[f for f in self.fighters.values() if f['world_id']==room]
        mode=match['mode'];teams={f.get('team') for f in actors if not f.get('eliminated') and (not mode['survival'] or f['dead']<=0)}
        return dict(mode=mode['id'],name=mode['name'],phase=match['phase'],remaining=max(0,match['ends_at']-self.clock),team_size=mode['team_size'],
                    teams_left=len(teams),alive=sum(not f.get('eliminated') for f in actors),winner=match['winner'],ranked=mode['ranked'],scores=match['scores'],
                    zone_radius=max(3.,36-max(0,self.clock-match['started']-25)*.14) if mode['survival'] else 38,reward=WIN_REWARD if mode['ranked'] else {})
