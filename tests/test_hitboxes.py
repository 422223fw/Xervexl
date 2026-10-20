import copy
import math
import tempfile
import unittest
from pathlib import Path

import hitboxes as hb
from rules import ITEMS,MOVES
from server import Arena

ROOT=Path(__file__).resolve().parents[1]


class GeometryTests(unittest.TestCase):
    def test_oriented_box_intersection_is_not_a_distance_cone(self):
        basis=hb.axes(math.pi/4)
        self.assertIsNotNone(hb.segment_box((0,1,-2),(0,1,2),(0,1,0),basis,(.3,.4,.2)))
        self.assertIsNone(hb.segment_box((.8,1,-2),(.8,1,2),(0,1,0),basis,(.3,.4,.2)))
        self.assertIsNone(hb.segment_box((0,2,-2),(0,2,2),(0,1,0),basis,(.3,.4,.2)))

    def test_swept_capsules_include_endpoints_and_handle_parallel_segments(self):
        self.assertIsNotNone(hb.segment_capsule((-2,0,0),(2,0,0),(0,-1,0),(0,1,0),.1))
        self.assertIsNone(hb.segment_capsule((-2,0,.3),(2,0,.3),(0,-1,0),(0,1,0),.1))
        self.assertIsNotNone(hb.segment_capsule((0,0,.05),(0,0,.05),(0,0,0),(0,1,0),.1))
        self.assertEqual(hb.closest_segments((0,0,0),(1,0,0),(0,1,0),(1,1,0))[0],1)

    def test_exported_animation_is_dense_unit_length_and_has_all_guards(self):
        self.assertEqual(set(hb.DATA['guards']),{'left','right','up','centre'})
        for move in MOVES:
            exported=hb.DATA['moves'][move]
            self.assertAlmostEqual(exported['windup'],MOVES[move]['windup'])
            for samples in exported['aims'].values():
                self.assertEqual(len(samples),257)
                for p in samples:self.assertAlmostEqual(hb.dot(p[3:6],p[3:6]),1,places=5)


class HitboxCombatTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'data')
        self.g=Arena(Path(self.temp.name)/'accounts.json',seed=31)
        self.a=self.g.spawn('geometry-a','A');self.b=self.g.spawn('geometry-b','B')
        self.g.fighters={'geometry-a':self.a,'geometry-b':self.b};self.g.maintain_bots=lambda:None
        self.g.worlds[0]['props']=[];self.g.rng.random=lambda:1
        self.a.update(x=0,z=0,yaw=0,body_yaw=0,world_id=0,weapon='longsword',attack='left',attack_started=0,attack_windup=.24,attack_duration=.6,spawn_safe=0)
        self.b.update(x=0,z=2,yaw=math.pi,body_yaw=math.pi,world_id=0,weapon='arming',spawn_safe=0)
        self.base_a=copy.deepcopy(self.a);self.base_b=copy.deepcopy(self.b)

    def tearDown(self):self.temp.cleanup()

    def reset(self):
        self.a.clear();self.a.update(copy.deepcopy(self.base_a));self.b.clear();self.b.update(copy.deepcopy(self.base_b));self.g.clock=0;self.g.events=[]

    def test_nominal_weapon_reach_does_not_hurt_without_blade_contact(self):
        self.b['z']=2.9
        self.assertLess(self.b['z'],ITEMS['longsword']['reach'])
        self.g.strike(self.a);self.assertEqual(self.b['hp'],100)

    def test_lateral_empty_space_inside_the_old_arc_is_a_miss(self):
        self.b.update(x=2.1,z=1.9)
        self.assertLess(math.atan2(self.b['x'],self.b['z']),MOVES['left']['arc'])
        self.g.strike(self.a);self.assertEqual(self.b['hp'],100)

    def test_all_four_matching_directions_intercept_short_and_long_blades(self):
        for weapon in ('knife','arming','longsword'):
            for attack,guard in (('left','right'),('right','left'),('overhead','up'),('thrust','centre')):
                self.reset();self.a['attack']=attack
                self.a.update(attack_windup=MOVES[attack]['windup'],attack_duration=MOVES[attack]['windup']+MOVES[attack]['follow'])
                self.b.update(weapon=weapon,block=True,guard_dir=guard,block_since=0)
                self.g.strike(self.a)
                self.assertEqual(self.b['hp'],100,(weapon,attack,guard))
                self.assertTrue(any(e['kind']=='parry' for e in self.g.events),(weapon,attack))

    def test_centre_guard_cannot_block_a_horizontal_cut(self):
        self.b.update(block=True,guard_dir='centre',block_since=0)
        self.g.strike(self.a)
        self.assertLess(self.b['hp'],100);self.assertEqual(self.b['parries'],0)

    def test_live_guard_contacts_survive_rotated_views_and_different_tick_sizes(self):
        for yaw in (0,.7,2.6,4.8):
            for dt in (.016,.03,.10):
                for attack,guard in (('left','right'),('right','left'),('overhead','up'),('thrust','centre')):
                    self.reset()
                    self.a.update(yaw=yaw,body_yaw=yaw,attack='',windup=0,cooldown=0)
                    self.b.update(x=math.sin(yaw)*2,z=math.cos(yaw)*2,yaw=yaw+math.pi,body_yaw=yaw+math.pi,block=True,guard_dir=guard,block_since=-10)
                    for _ in range(100):
                        self.a.update(input=dict(attack=attack,yaw=yaw),last_input=self.g.clock)
                        self.b.update(input=dict(block=True,guard_dir=guard,yaw=yaw+math.pi),last_input=self.g.clock)
                        self.g.tick(dt)
                        if any(e['kind'] in ('hit','block','parry') for e in self.g.events):break
                    self.assertEqual(self.b['hp'],100,(yaw,dt,attack))
                    self.assertTrue(any(e['kind']=='block' for e in self.g.events),(yaw,dt,attack))

    def test_matching_guard_looking_away_does_not_stop_a_blade(self):
        self.b.update(yaw=0,body_yaw=0,block=True,guard_dir='right',block_since=0)
        self.g.strike(self.a);self.assertLess(self.b['hp'],100)

    def test_torso_hit_cannot_be_declared_a_headshot_by_the_client(self):
        self.a['aim_zone']='body';self.g.strike(self.a)
        hit=next(e for e in self.g.events if e['kind']=='hit')
        self.assertIn(hit['zone'],('body','arms'))
        self.assertEqual(len(hit['point']),3)

    def test_arrow_can_pass_between_actual_legs_instead_of_hitting_a_capsule(self):
        shapes,_=hb.body_shapes(self.b,0)
        self.assertIsNone(hb.body_hit((0,.3,0),(0,.3,4),shapes,.025))
        self.a['weapon']='bow';self.g.shoot(self.a,ITEMS['bow'])
        self.g.projectiles[0].update(y=.3,vy=0,gravity=0)
        self.g.tick_objects(.2);self.assertEqual(self.b['hp'],100)
        self.assertEqual(len(self.g.projectiles),1)

    def test_head_torso_arms_and_legs_have_separate_shapes(self):
        shapes,_=hb.body_shapes(self.b,0)
        self.assertEqual({s[0] for s in shapes},{'head','body','arms','legs'})
        self.assertEqual(len(shapes),10)

    def test_held_blade_stops_a_physical_arrow_without_parry_farming(self):
        self.a['weapon']='bow';self.b.update(z=5,weapon='longsword',block=True,guard_dir='centre',block_since=-10)
        self.g.shoot(self.a,ITEMS['bow']);self.g.tick_objects(.25)
        self.assertEqual((self.b['hp'],self.b['parries'],self.b['xp'],self.b['stamina']),(100,0,0,100))
        self.assertEqual(self.g.projectiles,[])
        self.assertEqual(self.g.events[-1]['kind'],'block')

    def test_wrong_arrow_guard_does_not_reflect_or_grant_a_parry(self):
        self.a['weapon']='bow';self.b.update(z=5,weapon='longsword',block=True,guard_dir='right',block_since=0)
        self.g.shoot(self.a,ITEMS['bow']);self.g.tick_objects(.25)
        self.assertLess(self.b['hp'],100)
        self.assertEqual((self.b['parries'],self.b['xp']),(0,0))

    def test_jump_and_fall_move_the_actual_body_hitboxes(self):
        original=hb.body_shapes(self.b,0)[0][0][2]
        self.b['jump']=.275;raised=hb.body_shapes(self.b,0)[0][0][2]
        self.assertAlmostEqual(raised[1]-original[1],.65)
        self.b.update(jump=0,fall=.8);fallen=hb.body_shapes(self.b,0)[0][0][2]
        self.assertLess(fallen[1],.6)
        self.assertGreater(abs(fallen[2]-original[2]),1)

    def test_downed_geometry_matches_the_visible_fallen_pose(self):
        self.b['downed']=5;down=hb.body_shapes(self.b,0)
        self.b.update(downed=0,fall=.8,fall_duration=1.25)
        self.assertEqual(down,hb.body_shapes(self.b,0))

    def test_guard_changes_are_a_continuous_120_ms_animation(self):
        self.b.update(block=True,guard_dir='right',guard_changed=0,guard_from=hb.DATA['guards']['up'])
        start=hb.pose(self.b,0);middle=hb.pose(self.b,.06);end=hb.pose(self.b,.12)
        for actual,expected in zip(start,hb.DATA['guards']['up']):self.assertAlmostEqual(actual,expected)
        self.assertEqual(tuple(end),tuple(hb.DATA['guards']['right']))
        self.assertNotEqual(tuple(middle),tuple(start));self.assertNotEqual(tuple(middle),tuple(end))
        self.assertAlmostEqual(hb.dot(middle[3:6],middle[3:6]),1)

    def test_one_attack_hits_the_same_target_only_once_across_server_ticks(self):
        self.a.update(cooldown=.62,windup=.24)
        for _ in range(20):self.g.tick(.03)
        hits=[e for e in self.g.events if e['kind']=='hit' and e['target']==self.b['id']]
        self.assertEqual(len(hits),1)

    def test_empty_hands_have_no_invisible_sword_guard(self):
        self.b.update(weapon='fists',block=True,guard_dir='right',block_since=0)
        self.g.strike(self.a);self.assertLess(self.b['hp'],100)

    def test_full_block_does_not_spend_stamina_or_repeat_progress(self):
        self.b.update(block=True,guard_dir='right',block_since=-10,stamina=17)
        self.g.strike(self.a)
        self.assertEqual((self.b['hp'],self.b['stamina'],self.b['xp']),(100,17,0))

    def test_debug_boxes_are_server_derived_and_opt_in(self):
        user=self.g.account('BoxTester','boxes@example.com','test-passphrase');self.g.users['boxtester']=user
        token=self.g.session(user)['token'];self.g.sessions[token]['fighter']=self.a['id']
        normal=self.g.request('/arena/state',{},token);self.assertEqual(normal['hitboxes'],[])
        debug=self.g.request('/arena/state',{'debug_hitboxes':True,'guard_from':[999]*9,'guard_changed':-999},token)
        self.assertEqual(len(debug['hitboxes']),2)
        self.assertEqual(debug['hitboxes'][1]['shapes'],hb.body_shapes(self.b,self.g.clock)[0])
        self.assertEqual(self.a['guard_from'],[])

    def test_guard_direction_switch_cannot_restart_the_perfect_parry_timer(self):
        self.a.update(attack='',input=dict(block=True,guard_dir='up'),last_input=0)
        self.g.tick(.03);pressed=self.a['block_since']
        self.a.update(input=dict(block=True,guard_dir='right'),last_input=self.g.clock)
        self.g.tick(.03)
        self.assertEqual(self.a['block_since'],pressed)
        self.assertEqual(self.a['guard_changed'],self.g.clock)
        self.assertNotEqual(self.a['guard_from'],hb.DATA['guards']['right'])

    def test_walking_carry_and_block_handoff_preserve_the_world_blade(self):
        self.a.update(attack='',body_yaw=1.1,move_x=4.4,move_z=0,gait=.7)
        before=hb.weapon_segment(self.a,0);source=hb.guard_origin(self.a,0)
        self.a.update(block=True,guard_dir='right',guard_from=source,guard_changed=0)
        after=hb.weapon_segment(self.a,0)
        for p,q in zip(before,after):self.assertLess(hb.dot(hb.sub(p,q),hb.sub(p,q)),.000001)

    def test_live_guard_contact_finishes_the_cancelled_bot_learning_ticket(self):
        self.a.update(bot=True,depth=3,cooldown=.62,windup=.24)
        self.b.update(block=True,guard_dir='right',block_since=0,input=dict(block=True,guard_dir='right'),last_input=0)
        self.g.bot_input=lambda f:{}
        self.g.learning_attack(self.a);ticket=self.a['attack_learning']
        for _ in range(15):self.g.tick(.03)
        self.assertTrue(ticket['done'])
        self.assertLess(ticket['reward'],0)
        self.assertEqual(self.b['hp'],100)


if __name__=='__main__':unittest.main()
