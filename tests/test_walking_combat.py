import copy
import math
import tempfile
import unittest
from pathlib import Path

from rules import MOVES
from server import Arena

ROOT=Path(__file__).resolve().parents[1]


class WalkingCombatTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'data')
        self.arena=Arena(Path(self.temp.name)/'accounts.json',seed=61)
        self.user=self.arena.account('WalkingTester','walking@example.com','test-passphrase')
        self.arena.users['walkingtester']=self.user
        self.token=self.arena.session(self.user)['token']
        self.f=self.arena.fighters[self.arena.join(self.arena.sessions[self.token],0)]
        self.f.update(x=0,z=0,yaw=0,spawn_safe=0,weapon='longsword')
        self.arena.fighters={self.f['id']:self.f};self.arena.maintain_bots=lambda:None

    def tearDown(self):self.temp.cleanup()

    def input(self,side=0,forward=0,yaw=0,**extra):
        body=dict(move=[math.cos(yaw)*side+math.sin(yaw)*forward,-math.sin(yaw)*side+math.cos(yaw)*forward],
                  yaw=yaw,attack='left',easy_controls=True,auto_cut=True)
        body.update(extra);self.arena.request('/arena/state',body,self.token)

    def test_held_primary_attack_follows_all_nine_directions_at_rotated_yaws(self):
        original=copy.deepcopy(self.f)
        for yaw in (0,math.pi/2,math.pi,-math.pi/2,.73):
            for side in (-1,0,1):
                for forward in (-1,0,1):
                    self.f.clear();self.f.update(copy.deepcopy(original))
                    self.input(side,forward,yaw);self.arena.tick(.03)
                    expected='left' if side<0 else 'right' if side>0 else 'overhead' if forward>0 else 'thrust' if forward<0 else 'left'
                    self.assertEqual(self.f['attack'],expected,(side,forward,yaw))
                    self.assertEqual(self.f['attack_windup'],MOVES[expected]['windup'])
                    self.assertEqual(self.f['stamina'],100-MOVES[expected]['cost'])

    def test_current_swing_keeps_its_direction_until_the_next_move(self):
        self.input(side=-1);self.arena.tick(.03)
        self.input(side=1);self.arena.tick(.03)
        self.assertEqual(self.f['attack'],'left')
        for _ in range(23):self.input(side=1);self.arena.tick(.03)
        self.assertEqual((self.f['attack'],self.f['attack_id']),('right',2))

    def test_buffered_followup_uses_direction_when_it_actually_starts(self):
        self.input(side=-1);self.arena.tick(.03)
        while self.f['cooldown']>.18:self.input(side=-1);self.arena.tick(.03)
        self.assertTrue(self.f['queued_repeat'])
        while self.f['attack_id']==1:self.input(forward=-1);self.arena.tick(.03)
        self.assertEqual(self.f['attack'],'thrust')

    def test_holding_forward_or_backward_repeats_with_the_right_cost_and_timing(self):
        for forward,expected in ((1,'overhead'),(-1,'thrust')):
            self.f.update(attack='',cooldown=0,windup=0,last_attack=False,stamina=100,attack_id=0)
            started=[]
            for _ in range(60):
                previous=self.f['attack_id'];self.input(forward=forward);self.arena.tick(.03)
                if self.f['attack_id']!=previous:started.append((self.arena.clock,self.f['attack']))
            self.assertGreaterEqual(len(started),2)
            self.assertTrue(all(move==expected for _,move in started))
            self.assertGreaterEqual(started[1][0]-started[0][0],MOVES[expected]['windup']+MOVES[expected]['follow'])

    def test_explicit_attack_shortcuts_override_movement_and_do_not_auto_repeat(self):
        for move in ('overhead','thrust','spin','reverse_spin','disarm'):
            self.f.update(attack='',cooldown=0,windup=0,last_attack=False,stamina=100,attack_id=0,queued_attack='')
            for _ in range(45):self.input(side=1,attack=move,auto_cut=False);self.arena.tick(.03)
            self.assertEqual(self.f['attack_id'],1,move)

    def test_block_cancels_the_swing_and_queued_direction(self):
        self.input(forward=1);self.arena.tick(.03)
        self.input(side=1,block=True);self.arena.tick(.03)
        self.assertEqual((self.f['attack'],self.f['queued_attack'],self.f['windup']),('','',0))
        self.assertTrue(self.f['block'])

    def test_releasing_primary_cancels_queued_followup(self):
        self.input(forward=1);self.arena.tick(.03)
        while self.f['cooldown']>.18:self.input(forward=1);self.arena.tick(.03)
        self.assertTrue(self.f['queued_repeat'])
        for _ in range(12):self.input(forward=1,attack='',auto_cut=False);self.arena.tick(.03)
        self.assertEqual((self.f['attack_id'],self.f['queued_attack']),(1,''))

    def test_manual_guard_mode_preserves_explicit_direction_and_clicks(self):
        for _ in range(40):self.input(side=1,attack='left',easy_controls=False);self.arena.tick(.03)
        self.assertEqual(self.f['attack_id'],1)

    def test_bows_keep_their_standard_shot_and_do_not_turn_into_sword_moves(self):
        self.f['weapon']='bow';self.input(forward=1,attack='overhead');self.arena.tick(.03)
        self.assertEqual((self.f['attack'],self.f['attack_windup'],self.f['stamina']),('left',MOVES['left']['windup'],90))

    def test_auto_cut_flag_cannot_turn_special_attacks_into_a_repeat(self):
        for _ in range(45):self.input(side=1,attack='spin',auto_cut=True);self.arena.tick(.03)
        self.assertFalse(self.f['input']['auto_cut']);self.assertEqual(self.f['attack_id'],1)


if __name__=='__main__':unittest.main()
