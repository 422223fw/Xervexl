import json
import math
import tempfile
import unittest
from pathlib import Path
from server import Arena
from game_modes import parse_script, WIN_REWARD
from rules import MOVES

ROOT=Path(__file__).resolve().parents[1]


class ModeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'data');self.path=Path(self.temp.name)/'accounts.json'
        self.a=Arena(self.path,seed=42)
        self.user=self.a.account('SquadTester','squad@example.com','test-passphrase');self.a.users['squadtester']=self.user
        self.token=self.a.session(self.user)['token']

    def tearDown(self):self.temp.cleanup()

    def enter(self,mode='squads100'):
        result=self.a.request('/modes/join',dict(mode=mode),self.token)
        self.f=self.a.fighters[result['player']];self.m=self.a.match_for(self.f)
        self.actors=[f for f in self.a.fighters.values() if self.a.same_world(f,self.f)]
        return result

    def start(self):
        self.a.clock=self.m['ends_at']+.01;self.a.tick_modes(.03)
        for f in self.actors:f['spawn_safe']=0
        self.m['started']=self.a.clock

    def enemy(self):return next(f for f in self.actors if not self.a.allied(self.f,f))

    def friend(self):return next(f for f in self.actors if f is not self.f and self.a.allied(self.f,f))

    def test_squads_are_exactly_25_groups_of_four_with_99_bots(self):
        result=self.enter()
        self.assertEqual(result['match']['teams_left'],25);self.assertEqual(len(self.actors),100)
        self.assertEqual(sum(f['bot'] for f in self.actors),99)
        self.assertEqual([sum(f['team']==team for f in self.actors) for team in range(25)],[4]*25)

    def test_lobby_blocks_damage_and_live_round_does_not_admit_new_players(self):
        self.enter();enemy=self.enemy();self.f['spawn_safe']=enemy['spawn_safe']=0
        self.a.damage(self.f,enemy,50,'body');self.assertEqual(enemy['hp'],enemy['max_hp'])
        self.start();user=self.a.account('LateJoin','late@example.com','test-passphrase');self.a.users['latejoin']=user
        token=self.a.session(user)['token'];joined=self.a.request('/modes/join',dict(mode='squads100'),token)
        self.assertNotEqual(joined['world']['id'],self.f['world_id'])
        self.assertEqual(sum(f['world_id']==self.f['world_id'] for f in self.a.fighters.values()),100)

    def test_lobby_new_humans_replace_bots_and_share_a_squad(self):
        self.enter();user=self.a.account('TeamMate','team@example.com','test-passphrase');self.a.users['teammate']=user
        token=self.a.session(user)['token'];result=self.a.request('/modes/join',dict(mode='squads100'),token)
        mate=self.a.fighters[result['player']]
        self.assertTrue(self.a.allied(self.f,mate));self.assertEqual(sum(f['world_id']==self.f['world_id'] for f in self.a.fighters.values()),100)

    def test_friendly_damage_and_disarm_do_not_award_progress(self):
        self.enter();self.start();mate=self.friend();mate.update(x=0,z=1,yaw=math.pi,block=True,block_since=self.a.clock)
        self.f.update(x=0,z=0,yaw=0,weapon='longsword',attack='left')
        before=(self.f['xp'],mate['hp'],self.f['weapon'])
        self.a.damage(self.f,mate,100,'head');self.a.strike(self.f)
        self.assertEqual((self.f['xp'],mate['hp'],self.f['weapon']),before)

    def test_lethal_hit_downs_without_granting_an_elimination(self):
        self.enter();self.start();enemy=self.enemy();enemy['hp']=10;before=self.f['kills']
        self.a.damage(self.f,enemy,30,'body')
        self.assertGreater(enemy['downed'],0);self.assertEqual(enemy['dead'],0);self.assertEqual(self.f['kills'],before)
        self.assertEqual(enemy['hp'],1)

    def test_hold_revive_restores_half_health_without_stacking_helpers(self):
        self.enter();self.start();mate=self.friend();mate.update(x=self.f['x'],z=self.f['z']+.5,hp=1)
        self.a.mode_down(mate,self.enemy());self.f['input']={'revive':True,'move':[0,0]}
        helper=next(f for f in self.actors if f is not mate and f is not self.f and self.a.allied(f,self.f))
        helper.update(x=self.f['x'],z=self.f['z']-.5,mode_input={'revive':True,'move':[0,0]})
        for _ in range(20):
            self.a.clock+=.1;self.f['last_input']=self.a.clock;self.a.tick_modes(.1)
        self.assertGreater(mate['downed'],0)
        for _ in range(12):
            self.a.clock+=.1;self.f['last_input']=self.a.clock;self.a.tick_modes(.1)
        self.assertEqual(mate['downed'],0);self.assertEqual(mate['hp'],mate['max_hp']*.5)
        self.assertEqual(mate['spawn_safe'],1)

    def test_release_distance_and_damage_interrupt_reviving(self):
        self.enter();self.start();mate=self.friend();mate.update(x=self.f['x'],z=self.f['z']+.5)
        self.a.mode_down(mate,self.enemy());self.f['input']={'revive':True};self.f['last_input']=self.a.clock
        self.a.tick_modes(.5);self.assertGreater(mate['revive_progress'],0)
        self.f['input']={};self.a.tick_modes(.1);self.assertEqual(mate['revive_progress'],0)
        self.f['input']={'revive':True};self.f['last_hurt']=self.a.clock;self.a.tick_modes(.1);self.assertEqual(mate['revive_progress'],0)
        self.f.update(last_hurt=-999,x=self.f['x']+8);self.a.tick_modes(.1);self.assertEqual(mate['revive_progress'],0)

    def test_bots_try_to_rescue_nearby_allies(self):
        self.enter();self.start();rescuer=self.friend();rescuer.update(x=0,z=0)
        self.f.update(x=.5,z=0);self.a.mode_down(self.f,self.enemy())
        for e in self.actors:
            if not self.a.allied(e,rescuer):e.update(x=15,z=15)
        self.assertTrue(self.a.bot_input(rescuer)['revive'])

    def test_bleedout_and_team_wipe_prevent_respawn(self):
        self.enter();self.start();enemy=self.enemy();self.a.mode_down(enemy,self.f);enemy['downed']=.01
        self.a.tick_modes(.02);self.assertTrue(enemy['eliminated']);self.assertEqual(self.f['kills'],1)
        self.a.tick(.03);self.assertGreater(enemy['dead'],90000)

    def test_victory_grants_each_reward_once_and_survives_restart(self):
        self.enter();self.start()
        for e in self.actors:
            if e['team']!=self.f['team']:e.update(eliminated=True,dead=99999)
        before={k:self.user[k] for k in WIN_REWARD};self.a.tick_modes(.03);self.a.tick_modes(.03)
        self.assertEqual(self.m['phase'],'finished')
        self.a.mode_win(self.m,self.f['team'])
        for k,v in WIN_REWARD.items():self.assertEqual(self.user[k],before[k]+v)
        restored=Arena(self.path,seed=2)
        for k,v in WIN_REWARD.items():self.assertEqual(restored.users['squadtester'][k],before[k]+v)

    def test_respawn_modes_score_eliminations_and_finish_at_goal(self):
        self.enter('duel');self.start();enemy=self.enemy()
        for _ in range(3):
            enemy.update(hp=1,dead=0,spawn_safe=0);self.a.damage(self.f,enemy,10,'body');self.a.tick_modes(.03)
        self.assertEqual(self.m['phase'],'finished');self.assertEqual(self.m['winner'],self.f['team'])
        self.assertFalse(enemy.get('eliminated'))

    def test_custom_map_and_code_persist_and_cannot_mint_global_currency(self):
        body=dict(name='My Rule World',biome=6,players=8,team_size=4,props=[dict(kind='ruin',x=0,z=0,radius=1,height=3)],code='on start weapon bow\non kill coins 999\non kill if head heal 20\non win xp 1000')
        saved=self.a.request('/workshop/save',body,self.token);identifier=saved['saved_mode']
        self.assertEqual(Arena(self.path,seed=2).blueprints[identifier]['props'],body['props'])
        self.enter(identifier);self.start();self.assertEqual(self.f['weapon'],'bow')
        before=dict(self.user);self.a.script_event('kill',self.f,'head');self.a.grant(self.f,xp=999,coins=999,skill=999)
        self.assertEqual(self.f['match_coins'],999)
        for k in ('xp','coins','skill','inventory','weapon'):self.assertEqual(self.user[k],before[k])
        row=next(row for row in self.a.leaderboards()['coins'] if row['username']=='SquadTester')
        self.assertEqual(row['coins'],before['coins'])
        self.assertEqual(self.a.world_for(self.f)['props'],body['props'])

    def test_script_rejects_arbitrary_code_and_invalid_values(self):
        for code in ('import os','on kill heal -1','on win coins 100000','on kill weapon missing','on kill heal 1; exec(x)'):
            with self.assertRaises(ValueError):parse_script(code)
        self.assertEqual(len(parse_script('# comment\non revive if low_health heal 20')),1)

    def test_blueprint_validates_coordinates_and_creator(self):
        body=dict(name='Valid World',biome=0,players=8,team_size=4,props=[],code='on win score 100')
        identifier=self.a.request('/workshop/save',body,self.token)['saved_mode']
        body.update(id=identifier);user=self.a.account('OtherMaker','other@example.com','test-passphrase');self.a.users['othermaker']=user
        other=self.a.session(user)['token']
        with self.assertRaisesRegex(ValueError,'creator'):self.a.request('/workshop/save',body,other)
        body['props']=[dict(kind='rock',x=float('nan'),z=0,radius=1,height=3)]
        with self.assertRaises(ValueError):self.a.request('/workshop/save',body,self.token)

    def test_new_moves_and_slower_contact_are_authoritative(self):
        self.assertEqual(MOVES['left']['windup'],.24);self.assertEqual(MOVES['spin']['windup'],.46)
        self.assertTrue({'rising','reverse_spin','pommel','feint'}<=set(MOVES))
        a=self.a.spawn('motion-a','Motion');b=self.a.spawn('motion-b','Target');a.update(attack='feint',spawn_safe=0,x=0,z=0,yaw=0);b.update(spawn_safe=0,x=0,z=1)
        self.a.strike(a);self.assertEqual(b['hp'],100)

    def test_all_winning_human_members_are_paid_including_disconnected_members(self):
        self.enter();user=self.a.account('WinningMate','mate@example.com','test-passphrase');self.a.users['winningmate']=user
        token=self.a.session(user)['token'];r=self.a.request('/modes/join',dict(mode='squads100'),token)
        self.assertEqual(self.a.fighters[r['player']]['team'],self.f['team']);self.start()
        self.a.fighters.pop(r['player']);self.a.sessions[token]['fighter']=''
        self.a.mode_win(self.m,self.f['team']);self.a.mode_win(self.m,self.f['team'])
        self.assertEqual(user['xp'],650);self.assertEqual(user['coins'],450);self.assertEqual(user['skill'],25)

    def test_shared_bot_snapshots_keep_targets_hostile_and_eventually_plan_every_bot(self):
        self.enter();self.start()
        for _ in range(32):self.a.tick(1/30)
        bots=[f for f in self.actors if f['bot']]
        self.assertTrue(all(f.get('plan_nodes',0)>0 for f in bots))
        self.assertTrue(all(not self.a.allied(f,self.a.fighters[f['target_id']]) for f in bots if f.get('target_id') in self.a.fighters))

    def test_winner_playing_in_another_world_cannot_lose_the_award_on_next_sync(self):
        self.enter();user=self.a.account('MovingMate','moving@example.com','test-passphrase');self.a.users['movingmate']=user
        token=self.a.session(user)['token'];self.a.request('/modes/join',dict(mode='squads100'),token);self.start()
        moved=self.a.request('/arena/world',dict(world_id=0),token);actor=self.a.fighters[moved['player']]
        self.a.mode_win(self.m,self.f['team']);self.a.grant(actor,coins=1)
        self.assertEqual(user['coins'],451);self.assertEqual(user['xp'],650);self.assertEqual(actor['xp'],650)

    def test_editing_a_world_opens_its_new_geometry_and_keeps_running_rules_stable(self):
        body=dict(name='Editable Map',biome=0,players=8,team_size=4,props=[],code='on start weapon bow')
        identifier=self.a.request('/workshop/save',body,self.token)['saved_mode'];self.enter(identifier);self.start()
        old=self.f['world_id'];old_actor=self.f
        body.update(id=identifier,props=[dict(kind='ruin',x=10,z=0,radius=1,height=3)],code='on start weapon arming')
        self.a.request('/workshop/save',body,self.token);old_actor['weapon']='knife';self.a.script_event('start',old_actor)
        self.assertEqual(old_actor['weapon'],'bow')
        result=self.enter(identifier);self.assertNotEqual(result['world']['id'],old);self.start()
        self.assertEqual(self.f['weapon'],'arming');self.assertEqual(self.a.world_for(self.f)['props'],body['props'])


if __name__=='__main__':unittest.main()
