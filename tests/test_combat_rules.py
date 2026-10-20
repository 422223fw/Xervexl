import tempfile
import unittest
from pathlib import Path
from rules import ITEMS
from server import Arena

ROOT=Path(__file__).resolve().parents[1]


class FairCombatTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'data')
        self.g=Arena(Path(self.temp.name)/'accounts.json',seed=77)
        self.f=self.g.spawn('rules-a','A');self.v=self.g.spawn('rules-b','B')
        self.g.fighters={self.f['id']:self.f,self.v['id']:self.v};self.g.maintain_bots=lambda:None
        self.g.worlds[0]['props']=[];self.g.rng.random=lambda:1
        self.f.update(x=0,z=0,yaw=0,body_yaw=0,world_id=0,spawn_safe=0,weapon='longsword')
        self.v.update(x=0,z=2,yaw=3.14159265,body_yaw=3.14159265,world_id=0,spawn_safe=0)

    def tearDown(self):self.temp.cleanup()

    def tick(self,**inp):
        self.f.update(input=inp,last_input=self.g.clock)
        self.g.tick(.03)

    def test_block_cancels_damage_but_cannot_shorten_a_heavy_attack_recovery(self):
        self.tick(attack='spin');deadline=self.g.clock+self.f['cooldown'];spent=self.f['stamina']
        self.tick(block=True,guard_dir='right')
        self.assertEqual(self.f['attack'],'');self.assertTrue(self.f['block'])
        self.assertAlmostEqual(self.f['cooldown'],deadline-self.g.clock)
        self.assertLess(self.f['stamina']-spent,1)
        while self.g.clock+.03<deadline:
            self.tick(attack='left',easy_controls=True,auto_cut=True)
            self.assertEqual(self.f['attack_id'],1)
        self.assertEqual(self.v['hp'],100)
        for _ in range(3):self.tick(attack='left',easy_controls=True,auto_cut=True)
        self.assertEqual(self.f['attack_id'],2)

    def test_dodge_interrupts_an_existing_swing_and_clears_its_buffer(self):
        self.tick(attack='left');remaining=self.f['cooldown']
        self.f['queued_attack']='overhead'
        self.tick(dodge=True,attack='left',easy_controls=True,auto_cut=True)
        self.assertGreater(self.f['dodge'],0)
        self.assertEqual((self.f['attack'],self.f['queued_attack']),('',''))
        self.assertGreaterEqual(self.f['cooldown'],remaining-.03-.00001)
        for _ in range(8):self.tick(dodge=True,attack='left',easy_controls=True,auto_cut=True)
        self.assertEqual(self.v['hp'],100);self.assertEqual(self.f['attack_id'],1)

    def test_simultaneous_dodge_and_attack_only_evades_then_held_attack_resumes(self):
        self.tick(dodge=True,attack='left',easy_controls=True,auto_cut=True)
        self.assertEqual(self.f['attack_id'],0)
        for _ in range(8):self.tick(dodge=True,attack='left',easy_controls=True,auto_cut=True)
        self.assertEqual(self.f['attack_id'],0)
        for _ in range(8):self.tick(dodge=True,attack='left',easy_controls=True,auto_cut=True)
        self.assertGreater(self.f['attack_id'],0)

    def test_evading_cannot_create_melee_projectiles_or_spells(self):
        self.f.update(dodge=.2,attack='left',attack_windup=.24,attack_duration=.60)
        self.g.strike(self.f);self.assertEqual(self.v['hp'],100)
        self.f['weapon']='bow';self.g.shoot(self.f,ITEMS['bow'])
        self.f['spell']='firebolt';stamina=self.f['stamina']
        self.assertFalse(self.g.cast_spell(self.f));self.assertEqual(self.g.projectiles,[])
        self.assertEqual(self.f['stamina'],stamina)

    def test_protection_ends_on_a_legal_attack_but_not_blocking_or_exhausted_input(self):
        self.f['spawn_safe']=1.5
        self.tick(block=True,guard_dir='up');self.assertGreater(self.f['spawn_safe'],1)
        self.f['stamina']=0
        self.tick(attack='left');self.assertGreater(self.f['spawn_safe'],1)
        self.assertEqual(self.f['attack_id'],0)
        self.f['stamina']=100
        self.tick(attack='left',easy_controls=True,auto_cut=True)
        self.assertEqual(self.f['spawn_safe'],0);self.assertEqual(self.f['attack_id'],1)

    def test_valid_spell_ends_protection_and_pays_its_normal_cost(self):
        self.f.update(spawn_safe=1.5,spell='firebolt',stamina=100)
        self.assertTrue(self.g.cast_spell(self.f))
        self.assertEqual((self.f['spawn_safe'],self.f['stamina']),(0,75))
        self.assertEqual(len(self.g.projectiles),1)

    def test_rejected_spell_keeps_protection_and_does_not_charge_stamina(self):
        self.f.update(spawn_safe=1.5,spell='firebolt',stamina=100,spell_cd=2)
        self.assertFalse(self.g.cast_spell(self.f))
        self.assertEqual((self.f['spawn_safe'],self.f['stamina']),(1.5,100))

    def test_defensive_interrupt_finishes_the_bot_learning_ticket_once(self):
        for action in ({'block':True,'guard_dir':'right'},{'dodge':True}):
            self.f.update(bot=True,depth=3,attack='left',attack_started=self.g.clock,attack_windup=.24,attack_duration=.6,windup=.24,cooldown=.7,stamina=100,block=False,dodge=0,last_dodge=False)
            self.g.learning_attack(self.f);ticket=self.f['attack_learning']
            self.g.bot_input=lambda fighter:dict(action)
            self.g.tick(.03);self.assertTrue(ticket['done'])
            count=self.g.learning.updates
            self.g.tick(.03);self.assertEqual(count,self.g.learning.updates)


if __name__=='__main__':unittest.main()
