import math
import tempfile
import unittest
from pathlib import Path
from server import Arena

ROOT=Path(__file__).resolve().parents[1]


class PickupTests(unittest.TestCase):
    def setUp(self):
        runtime=ROOT/'data'/'tests';runtime.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=runtime)
        self.arena=Arena(Path(self.temp.name)/'accounts.json',seed=4)
        self.token=self.arena.request('/auth/register',dict(username='RecoverBlade',email='recover-blade@example.com',password='test-passphrase'))['token']
        self.player=self.arena.request('/arena/join',{},self.token)['player']
        self.a=self.arena.fighters[self.player]
        self.b=self.arena.spawn('opponent','Opponent')
        self.a.update(x=0,z=0,yaw=0,world_id=0,spawn_safe=0)
        self.b.update(x=0,z=2,yaw=math.pi,world_id=0,spawn_safe=0)
        self.arena.fighters={self.a['id']:self.a,self.b['id']:self.b};self.arena.maintain_bots=lambda:None
        self.arena.worlds[0]['props']=[]

    def tearDown(self):self.temp.cleanup()

    def landed(self,f,weapon='knife',x=0,z=0):
        f['weapon']=weapon;self.arena.drop_weapon(f)
        drop=self.arena.drops[-1];drop.update(x=x,z=z,y=.06,vy=0,vx=0,vz=0,age=1.1)
        return drop

    def input(self,**values):
        self.arena.request('/arena/state',values,self.token)

    def test_held_pickup_recovers_own_sword_after_disarm_cooldown(self):
        self.a['weapon']='longsword';self.arena.drop_weapon(self.a,self.b)
        drop=self.arena.drops[-1];drop.update(x=0,z=0,y=.06,vy=0,vx=0,vz=0,age=1.1)
        self.input(pickup=True);self.arena.tick(.03)
        self.assertEqual(self.a['weapon'],'fists')
        for _ in range(40):self.input(pickup=True);self.arena.tick(.03)
        state=self.arena.request('/arena/state',{},self.token)
        actor=next(f for f in state['fighters'] if f['id']==self.player)
        self.assertEqual(actor['weapon'],'longsword')
        self.assertNotIn(drop,self.arena.drops)
        events=[e for e in self.arena.events if e['kind']=='pickup']
        self.assertEqual(len(events),1);self.assertTrue(events[0]['own'])

    def test_held_key_waits_for_actual_landing(self):
        self.arena.drop_weapon(self.a)
        self.input(pickup=True);self.arena.tick(.03)
        drop=self.arena.drops[-1]
        for _ in range(50):
            self.a.update(x=drop['x'],z=drop['z'])
            self.input(pickup=True);self.arena.tick(.03)
            if self.a['weapon']!='fists':break
            if drop['y']>.22:self.assertFalse(self.arena.pickup_hint(self.a))
        self.assertEqual(self.a['weapon'],'knife')
        self.assertLessEqual(drop['y'],.22)

    def test_own_weapon_is_preferred_to_a_closer_foreign_one(self):
        own=self.landed(self.a,'arming',x=1.2)
        other=self.landed(self.b,'sabre',x=.2)
        self.a['disarmed']=0
        self.assertEqual(self.arena.pickup_hint(self.a)['id'],own['id'])
        self.assertTrue(self.arena.pickup_weapon(self.a))
        self.assertEqual(self.a['weapon'],'arming');self.assertIn(other,self.arena.drops)

    def test_a_successful_hold_does_not_keep_swapping_weapons(self):
        own=self.landed(self.a,'knife',x=.4)
        other=self.landed(self.b,'sabre',x=.1)
        self.a['disarmed']=0
        for _ in range(30):self.input(pickup=True);self.arena.tick(.03)
        self.assertEqual(self.a['weapon'],'knife');self.assertIn(other,self.arena.drops)
        self.input();self.arena.tick(.03)
        self.input(pickup=True);self.arena.tick(.03)
        self.assertEqual(self.a['weapon'],'sabre')
        self.assertNotIn(own,self.arena.drops)

    def test_waiting_for_a_weapon_to_come_into_range_retries(self):
        self.landed(self.a,x=3)
        self.a['disarmed']=0
        self.input(pickup=True);self.arena.tick(.03)
        self.assertEqual(self.a['weapon'],'fists')
        self.a['x']=2.5
        self.input(pickup=True);self.arena.tick(.03)
        self.assertEqual(self.a['weapon'],'knife')

    def test_hint_and_pickup_reject_other_world_airborne_expired_and_far_weapons(self):
        drop=self.landed(self.a)
        self.a['disarmed']=0
        for change in (dict(world_id=1),dict(y=1),dict(expires=-1),dict(x=4)):
            original=drop.copy();drop.update(change)
            self.assertFalse(self.arena.pickup_hint(self.a));self.assertFalse(self.arena.pickup_weapon(self.a))
            drop.update(original)

    def test_dead_or_fallen_fighter_cannot_pick_up(self):
        self.landed(self.a);self.a['disarmed']=0
        self.a['dead']=2
        self.assertFalse(self.arena.pickup_hint(self.a));self.assertFalse(self.arena.pickup_weapon(self.a))
        self.a.update(dead=0,fall=.8)
        self.assertFalse(self.arena.pickup_hint(self.a)['ready']);self.assertFalse(self.arena.pickup_weapon(self.a))

    def test_state_shows_waiting_hint_and_clears_it_after_pickup(self):
        drop=self.landed(self.a,'knife',x=.5)
        state=self.arena.request('/arena/state',{},self.token)
        self.assertEqual(state['pickup']['id'],drop['id']);self.assertTrue(state['pickup']['own'])
        self.assertFalse(state['pickup']['ready'])
        self.a['disarmed']=0;self.input(pickup=True);self.arena.tick(.03)
        self.assertEqual(self.arena.request('/arena/state',{},self.token)['pickup'],{})

    def test_borrowed_sword_never_changes_owned_inventory_or_currency(self):
        drop=self.landed(self.b,'greatsword')
        before=self.arena.profile(self.arena.sessions[self.token]['user'])
        self.input(pickup=True);self.arena.tick(.03)
        self.assertEqual(self.a['weapon'],'greatsword')
        after=self.arena.request('/me',{},self.token)['profile']
        for key in ('inventory','weapon_slots','coins','xp','skill'):self.assertEqual(after[key],before[key])
        self.assertNotIn(drop,self.arena.drops)

    def test_pickup_cancels_a_punch_instead_of_turning_it_into_a_sword_hit(self):
        self.landed(self.a,'longsword');self.a['disarmed']=0
        self.a.update(attack='left',windup=.03,queued_attack='right',queued_repeat=True)
        self.assertTrue(self.arena.pickup_weapon(self.a))
        self.assertEqual((self.a['attack'],self.a['windup'],self.a['queued_attack']),('',0,''))
        self.assertEqual(self.a['cooldown'],.3)


if __name__=='__main__':unittest.main()
