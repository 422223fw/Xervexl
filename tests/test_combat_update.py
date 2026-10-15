import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rules import xp_for_level,level_for_xp,ITEMS
from server import Arena

ROOT=Path(__file__).resolve().parents[1]


class RankRulesTests(unittest.TestCase):
    def test_requested_costs_are_additional_xp_for_each_rank(self):
        self.assertEqual([xp_for_level(n) for n in range(1,7)],[0,79,316,1264,6004,34444])
        for rank in range(3,101):
            self.assertEqual(xp_for_level(rank)-xp_for_level(rank-1),rank*(xp_for_level(rank-1)-xp_for_level(rank-2)))

    def test_every_rank_boundary_uses_exact_integer_arithmetic(self):
        for rank in (2,3,4,5,20,100,2000):
            threshold=xp_for_level(rank)
            self.assertEqual(level_for_xp(threshold-1),rank-1)
            self.assertEqual(level_for_xp(threshold),rank)
            self.assertEqual(level_for_xp(threshold+1),rank)


class AccountGateTests(unittest.TestCase):
    def setUp(self):
        runtime=ROOT/'data'/'tests';runtime.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=runtime);self.path=Path(self.temp.name)/'accounts.json'
        self.arena=Arena(self.path,seed=8)

    def tearDown(self):self.temp.cleanup()

    def register(self):return self.arena.request('/auth/register',dict(username='Fighter',email='fighter@example.com',password='test-passphrase'))

    def test_unauthenticated_and_guest_sessions_cannot_enter_any_world(self):
        self.assertTrue(self.arena.request('/health',{})['account_required'])
        with self.assertRaisesRegex(ValueError,'Sign up'):self.arena.request('/auth/guest',{})
        for route in ('/arena/join','/arena/world','/arena/state'):
            with self.assertRaises(ValueError):self.arena.request(route,{})
        token=self.arena.session(self.arena.account('Guest-test'),True)['token']
        for route in ('/arena/join','/arena/world','/arena/state'):
            with self.assertRaisesRegex(ValueError,'registered account'):self.arena.request(route,{},token)
        with self.assertRaises(ValueError):self.arena.join(self.arena.sessions[token])
        self.assertTrue(all(f['bot'] for f in self.arena.fighters.values()))

    def test_registered_account_can_play_and_logout_prevents_reentry(self):
        token=self.register()['token'];result=self.arena.request('/arena/join',{},token)
        self.assertEqual(result['profile']['level_cost_xp'],79)
        self.assertTrue(result['player'])
        self.assertEqual(self.arena.request('/arena/state',{},token)['humans'],1)
        self.arena.request('/auth/logout',{},token)
        with self.assertRaises(ValueError):self.arena.request('/arena/join',{},token)

    def test_legacy_migration_preserves_earned_rank_and_runs_once(self):
        old=self.arena.account('Legacy','legacy@example.com','test-passphrase');old.pop('progression_version')
        old.update(xp=1000,skill=42,coins=1234,inventory=['knife','arming'],weapon='arming')
        self.path.write_text(json.dumps({'legacy':old}),encoding='utf-8')
        migrated=Arena(self.path,seed=8);user=migrated.users['legacy']
        self.assertEqual(user['xp'],2054);self.assertEqual(level_for_xp(user['xp']),4)
        for key in ('password','email','username','skill','coins','inventory','weapon'):self.assertEqual(user[key],old[key])
        self.assertEqual(len(list(self.path.parent.glob('accounts.pre-progression-*.bak'))),1)
        again=Arena(self.path,seed=8)
        self.assertEqual(again.users['legacy']['xp'],2054)
        self.assertEqual(len(list(self.path.parent.glob('accounts.pre-progression-*.bak'))),1)

    def test_huge_xp_survives_storage_profiles_leaderboards_and_arena_json(self):
        token=self.register()['token'];user=self.arena.sessions[token]['user']
        value=xp_for_level(2000)+7;user['xp']=value;self.arena.save()
        restored=Arena(self.path,seed=8)
        self.assertEqual(restored.users['fighter']['xp'],value)
        self.assertEqual(self.arena.profile(user)['xp'],str(value))
        self.assertEqual(self.arena.profile(user)['level'],2000)
        self.assertEqual(self.arena.profile(user)['level_progress_xp'],7)
        self.assertEqual(self.arena.profile(user)['level_cost_xp'],str(xp_for_level(2001)-xp_for_level(2000)))
        self.assertEqual(self.arena.leaderboards()['xp'][0]['xp'],str(value))
        pid=self.arena.request('/arena/join',{},token)['player']
        state=self.arena.request('/arena/state',{},token)
        actor=next(f for f in state['fighters'] if f['id']==pid)
        self.assertEqual(actor['xp'],str(value));self.assertEqual(actor['level'],2000)
        self.assertEqual(json.loads(json.dumps(state))['profile']['xp'],str(value))

    def test_atomic_save_retries_a_transient_windows_file_lock(self):
        self.register();replace=Path.replace;calls=[]
        def locked_once(source,target):
            calls.append(source)
            if len(calls)==1:raise PermissionError('Transient sharing violation')
            return replace(source,target)
        self.arena.users['fighter']['coins']=345
        with patch.object(Path,'replace',locked_once),patch('server.time.sleep'):
            self.arena.save()
        self.assertEqual(len(calls),2)
        self.assertEqual(json.loads(self.path.read_text())['fighter']['coins'],345)


class TacticalBotTests(unittest.TestCase):
    def setUp(self):
        runtime=ROOT/'data'/'tests';runtime.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=runtime)
        self.arena=Arena(Path(self.temp.name)/'accounts.json',seed=11)
        self.a=self.arena.spawn('bot-tactical','Tactical',True,5)
        self.b=self.arena.spawn('target','Target')
        self.a.update(x=0,z=0,world_id=0,weapon='longsword',hp=100,spawn_safe=0,action='advance',plan_at=100,target_id='target')
        self.b.update(x=0,z=2,world_id=0,spawn_safe=0,yaw=math.pi)
        self.arena.fighters={self.a['id']:self.a,self.b['id']:self.b};self.arena.worlds[0]['props']=[]

    def tearDown(self):self.temp.cleanup()

    def test_visible_attack_reaction_has_delay_and_correct_guard(self):
        self.b.update(attack='left',attack_id=1,windup=.18)
        self.assertFalse(self.arena.bot_input(self.a)['block'])
        self.arena.clock=.10
        result=self.arena.bot_input(self.a)
        self.assertTrue(result['block']);self.assertEqual(result['guard_dir'],'right');self.assertEqual(result['attack'],'')

    def test_bot_does_not_read_unrevealed_human_attack_input(self):
        self.b['input']={'attack':'left'}
        result=self.arena.bot_input(self.a)
        self.assertFalse(result['block'])

    def test_lesser_depth_reacts_more_slowly(self):
        self.a['depth']=2;self.b.update(attack='overhead',attack_id=1,windup=.26)
        self.arena.bot_input(self.a);self.arena.clock=.13
        self.assertFalse(self.arena.bot_input(self.a)['block'])
        self.arena.clock=.25
        self.assertTrue(self.arena.bot_input(self.a)['block'])

    def test_ranged_bot_leads_a_moving_target(self):
        self.a.update(weapon='bow',action='thrust');self.b.update(z=8,move_x=3)
        result=self.arena.bot_input(self.a)
        self.assertGreater(result['yaw'],0)
        self.assertEqual(result['attack'],'thrust')
        self.assertTrue(math.isfinite(result['aim_pitch']))

    def test_bot_dodges_an_arrow_on_a_collision_course(self):
        self.b.update(z=6,weapon='bow');self.arena.shoot(self.b,ITEMS['bow'])
        result=self.arena.bot_input(self.a)
        self.assertTrue(result['dodge']);self.assertGreater(abs(result['move'][0]),.9)

    def test_bot_changes_cut_to_attack_the_exposed_guard_direction(self):
        self.a['action']='left';self.b.update(block=True,guard_dir='centre')
        self.assertEqual(self.arena.bot_input(self.a)['attack'],'overhead')
        self.b['guard_dir']='up'
        self.assertEqual(self.arena.bot_input(self.a)['attack'],'left')

    def test_bot_steers_around_a_solid_landmark(self):
        self.arena.worlds[0]['props']=[dict(x=0,z=1.3,radius=.8,height=2,kind='rock')]
        move=self.arena.bot_input(self.a)['move']
        self.assertGreater(abs(move[0]),.8)

    def test_wounded_bot_prefers_a_finishable_opponent(self):
        self.a['hp']=15
        weak=self.arena.spawn('weak','Weak');weak.update(x=0,z=2.8,world_id=0,hp=1,spawn_safe=0)
        self.assertEqual(self.arena.target_for(self.a,[self.b,weak])['id'],weak['id'])


class MoveTimingTests(unittest.TestCase):
    def setUp(self):
        runtime=ROOT/'data'/'tests';runtime.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=runtime);self.arena=Arena(Path(self.temp.name)/'accounts.json',seed=3)
        self.a=self.arena.spawn('motion-a','A');self.b=self.arena.spawn('motion-b','B')
        self.a.update(x=0,z=0,yaw=0,world_id=0,spawn_safe=0,last_input=0)
        self.b.update(x=0,z=1.3,world_id=0,spawn_safe=0)
        self.arena.fighters={self.a['id']:self.a,self.b['id']:self.b};self.arena.maintain_bots=lambda:None

    def tearDown(self):self.temp.cleanup()

    def input(self,**values):self.a['input']=values;self.a['last_input']=self.arena.clock

    def test_impact_occurs_at_the_reported_animation_contact_time(self):
        self.input(attack='left');self.arena.tick(.03)
        self.assertEqual(self.a['attack_windup'],.24)
        self.arena.tick(.20);self.assertEqual(self.b['hp'],100)
        self.arena.tick(.05);self.assertLess(self.b['hp'],100)

    def test_late_click_buffers_the_next_cut_and_block_clears_it(self):
        self.input(attack='left');self.arena.tick(.03)
        self.input();self.arena.tick(.45)
        self.input(attack='right');self.arena.tick(.04)
        self.assertEqual(self.a['queued_attack'],'right')
        self.input();self.arena.tick(.13);self.arena.tick(.015)
        self.assertEqual((self.a['attack_id'],self.a['attack']),(2,'right'))
        self.input(attack='left');self.arena.tick(.02)
        self.input(block=True);self.arena.tick(.02)
        self.assertEqual((self.a['queued_attack'],self.a['attack'],self.a['windup']),('','',0))

    def test_deliberate_spin_costs_more_and_can_hit_behind_the_fighter(self):
        self.b['z']=-1.3;self.input(attack='spin');self.arena.tick(.03)
        self.assertEqual(self.a['stamina'],70)
        self.arena.tick(.50)
        self.assertLess(self.b['hp'],100)

    def test_ranged_weapon_cannot_fire_a_spinning_cut(self):
        self.a['weapon']='bow';self.input(attack='spin');self.arena.tick(.03);self.arena.tick(.4)
        self.assertEqual(self.a['attack_id'],0)
        self.assertEqual(self.a['stamina'],100)
        self.assertEqual(self.arena.projectiles,[])


if __name__=='__main__':unittest.main()
