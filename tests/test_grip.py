import copy
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rules import grip_price, grip_risk_multiplier
from server import Arena

ROOT=Path(__file__).resolve().parents[1]


class GripTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'data')
        self.path=Path(self.temp.name)/'accounts.json'
        self.arena=Arena(self.path,seed=29)
        self.user=self.arena.account('GripTester','grip@example.com','test-passphrase')
        self.arena.users['griptester']=self.user
        self.token=self.arena.session(self.user)['token']
        self.a=self.arena.fighters[self.arena.join(self.arena.sessions[self.token])]
        self.b=self.arena.spawn('grip-opponent','Opponent')
        self.arena.fighters={self.a['id']:self.a,self.b['id']:self.b}
        self.arena.maintain_bots=lambda:None
        self.a.update(x=0,z=0,yaw=0,world_id=0,spawn_safe=0,weapon='longsword',attack='disarm')
        self.b.update(x=0,z=1.5,yaw=math.pi,world_id=0,spawn_safe=0,weapon='sabre',stamina=20,cooldown=.3,skill=50)

    def tearDown(self):self.temp.cleanup()

    def test_full_stamina_cannot_be_disarmed_even_with_the_best_roll(self):
        self.b['stamina']=100
        with patch.object(self.arena.rng,'random',return_value=0) as roll:
            self.arena.strike(self.a)
        roll.assert_not_called()
        self.assertEqual(self.b['weapon'],'sabre')
        self.assertEqual(self.arena.drops,[])

    def test_disarm_needs_exhaustion_recovery_close_range_and_alignment(self):
        for change in ({'stamina':25},{'cooldown':.1},{'block':True},{'windup':.2},{'z':1.81},{'x':.8}):
            saved=copy.deepcopy(self.b);self.b.update(change)
            with patch.object(self.arena.rng,'random',return_value=0) as roll:
                self.arena.strike(self.a)
            self.assertEqual(self.b['weapon'],'sabre',change);roll.assert_not_called()
            self.b.clear();self.b.update(saved)

    def test_failed_contact_has_no_drop_penalty_or_reward(self):
        before=[(f['xp'],f['skill'],f['disarms'],f['coins']) for f in (self.a,self.b)]
        with patch.object(self.arena.rng,'random',return_value=.08):self.arena.strike(self.a)
        self.assertEqual(self.b['weapon'],'sabre');self.assertEqual(self.arena.drops,[])
        self.assertEqual([(f['xp'],f['skill'],f['disarms'],f['coins']) for f in (self.a,self.b)],before)
        self.assertEqual(self.arena.events[-1]['kind'],'grip_hold')

    def test_eligible_attempt_rates_are_eight_four_and_two_percent(self):
        for upgrades,expected in ((0,80),(1,40),(2,20)):
            successes=0;self.b['grip_upgrades']=upgrades
            # Sweep the entire probability interval; no flaky random sample.
            for index in range(1000):
                self.b['grip_test_after']=0
                with patch.object(self.arena.rng,'random',return_value=(index+.5)/1000),patch.object(self.arena,'drop_weapon',return_value=True):
                    successes+=self.arena.try_disarm(self.a,self.b)
            self.assertEqual(successes,expected)

    def test_failed_attempts_cannot_be_spammed_by_another_opponent(self):
        with patch.object(self.arena.rng,'random',return_value=.9):self.arena.strike(self.a)
        other=self.arena.spawn('other-opponent','Other')
        other.update(x=0,z=0,yaw=0,world_id=0,weapon='longsword',spawn_safe=0)
        with patch.object(self.arena.rng,'random',return_value=0) as roll:
            self.assertFalse(self.arena.try_disarm(other,self.b));roll.assert_not_called()
            self.arena.clock=3
            self.assertTrue(self.arena.try_disarm(other,self.b))

    def test_successful_disarm_rewards_once_and_weapon_is_recoverable(self):
        with patch.object(self.arena.rng,'random',return_value=.01):self.arena.strike(self.a)
        self.assertEqual((self.b['weapon'],self.a['xp'],self.a['skill'],self.a['disarms'],self.b['skill']),('fists',35,1,1,47))
        self.assertFalse(self.arena.try_disarm(self.a,self.b));self.assertEqual(self.a['disarms'],1)
        for _ in range(40):self.arena.tick_objects(1/30)
        drop=self.arena.drops[0];self.b.update(x=drop['x'],z=drop['z'],disarmed=0)
        self.assertTrue(self.arena.pickup_weapon(self.b));self.assertEqual(self.b['weapon'],'sabre')

    def test_parry_remains_free_and_rewards_without_automatic_disarm(self):
        self.a.update(attack='left',stamina=100)
        self.b.update(block=True,block_since=self.arena.clock,stamina=0,guard_dir='right')
        with patch.object(self.arena.rng,'random',return_value=0) as roll:self.arena.strike(self.a)
        roll.assert_not_called()
        self.assertEqual((self.b['hp'],self.b['stamina'],self.b['xp'],self.b['parries']),(100,0,20,1))
        self.assertEqual(self.a['weapon'],'longsword');self.assertEqual(self.b['disarms'],0)

    def test_counter_disarm_requires_seventy_ms_and_exhaustion(self):
        self.arena.clock=1
        self.a.update(attack='left',stamina=20)
        self.b.update(block=True,block_since=.9,guard_dir='right')
        with patch.object(self.arena.rng,'random',return_value=0) as roll:self.arena.strike(self.a)
        roll.assert_not_called();self.assertEqual(self.a['weapon'],'longsword')
        self.b['block_since']=1
        with patch.object(self.arena.rng,'random',return_value=.039):self.arena.strike(self.a)
        self.assertEqual(self.a['weapon'],'fists');self.assertEqual(self.b['disarms'],1)

    def test_counter_chance_is_four_percent_and_grip_halves_it(self):
        self.a.update(attack='left',stamina=20)
        self.b.update(block=True,block_since=self.arena.clock,guard_dir='right')
        with patch.object(self.arena.rng,'random',return_value=.04):self.arena.strike(self.a)
        self.assertEqual(self.a['weapon'],'longsword')
        self.a.update(grip_upgrades=1,grip_test_after=0)
        with patch.object(self.arena.rng,'random',return_value=.03):self.arena.strike(self.a)
        self.assertEqual(self.a['weapon'],'longsword')
        self.a['grip_test_after']=0
        with patch.object(self.arena.rng,'random',return_value=.019):self.arena.strike(self.a)
        self.assertEqual(self.a['weapon'],'fists')

    def test_grip_does_not_prevent_voluntary_drop(self):
        self.a.update(grip_upgrades=10,skill=15)
        self.assertTrue(self.arena.drop_weapon(self.a))
        self.assertEqual((self.a['weapon'],self.a['skill']),('fists',15))
        self.assertEqual(self.arena.events[-1]['kind'],'drop')

    def test_safety_states_rooms_and_unarmed_attacks_cannot_disarm(self):
        for fighter,changes in ((self.a,({'dead':1},{'spawn_safe':1},{'downed':1},{'fall':1},{'disarmed':1},{'weapon':'fists'})),
                                (self.b,({'dead':1},{'spawn_safe':1},{'downed':1},{'fall':1},{'world_id':4},{'weapon':'bow'}))):
            for change in changes:
                saved=copy.deepcopy(fighter);fighter.update(change)
                with patch.object(self.arena.rng,'random',return_value=0) as roll:
                    self.assertFalse(self.arena.try_disarm(self.a,self.b),change);roll.assert_not_called()
                fighter.clear();fighter.update(saved)

    def test_shop_prices_repeat_and_immediately_affect_real_combat(self):
        self.user['coins']=self.a['coins']=20000
        profile=self.arena.request('/shop/buy',{'item':'grip','grip_upgrades':999,'price':0},self.token)['profile']
        self.assertEqual((profile['coins'],profile['grip_upgrades'],profile['grip_upgrade_price'],profile['disarm_risk_multiplier']),(16000,1,16000,.5))
        self.assertEqual(self.a['grip_upgrades'],1)
        self.a.update(stamina=20,cooldown=.3);self.b.update(block=False)
        with patch.object(self.arena.rng,'random',return_value=.05):self.assertFalse(self.arena.try_disarm(self.b,self.a))
        profile=self.arena.request('/shop/buy',{'item':'grip'},self.token)['profile']
        self.assertEqual((profile['coins'],profile['grip_upgrades'],profile['grip_upgrade_price']),(0,2,36000))
        self.arena.grant(self.a,xp=5)
        self.assertEqual((self.user['coins'],self.user['grip_upgrades']),(0,2))
        self.assertNotIn('grip',self.user['inventory'])

    def test_insufficient_funds_and_equip_cannot_change_grip(self):
        before=copy.deepcopy(self.user)
        for route in ('/shop/buy','/shop/equip'):
            with self.assertRaises(ValueError):self.arena.request(route,{'item':'grip','grip_upgrades':999},self.token)
        self.assertEqual(self.user,before)
        self.arena.request('/arena/state',{'grip_upgrades':999},self.token)
        self.assertEqual(self.a['grip_upgrades'],0)

    def test_grip_survives_respawn_world_change_and_remembered_login(self):
        self.user['coins']=self.a['coins']=4000
        self.arena.request('/shop/buy',{'item':'grip'},self.token)
        self.a.update(hp=0,dead=.01);self.arena.tick(.02)
        self.assertEqual(self.a['grip_upgrades'],1)
        self.arena.request('/arena/world',{'world_id':4},self.token)
        self.assertEqual(self.arena.fighters[self.arena.sessions[self.token]['fighter']]['grip_upgrades'],1)
        restored=Arena(self.path,seed=29)
        self.assertEqual(restored.request('/auth/resume',{},self.token)['profile']['grip_upgrades'],1)

    def test_old_accounts_are_backed_up_without_changing_existing_values(self):
        self.user.update(xp=12345,skill=37,coins=6789)
        self.user.pop('grip_upgrades');before=copy.deepcopy(self.arena.users);self.arena.save()
        original=self.path.read_bytes();restored=Arena(self.path,seed=29)
        backups=list(self.path.parent.glob('accounts.pre-grip-*.bak'))
        self.assertEqual(len(backups),1);self.assertEqual(backups[0].read_bytes(),original)
        self.assertEqual(restored.users,{key:dict(value,grip_upgrades=0) for key,value in before.items()})
        self.assertEqual(restored.request('/auth/resume',{},self.token)['profile']['grip_upgrades'],0)
        Arena(self.path,seed=29)
        self.assertEqual(len(list(self.path.parent.glob('accounts.pre-grip-*.bak'))),1)

    def test_bot_grip_and_prices_use_the_same_rules(self):
        for depth,grip in ((2,0),(3,0),(4,1),(5,2)):
            bot=self.arena.spawn('depth-'+str(depth),'Bot',True,depth)
            self.assertEqual(bot['grip_upgrades'],grip)
        self.assertEqual([grip_price(n) for n in range(3)],[4000,16000,36000])
        self.assertEqual([grip_risk_multiplier(n) for n in range(4)],[1,.5,.25,.125])


if __name__=='__main__':unittest.main()
