import copy
import math
import tempfile
import unittest
from pathlib import Path

from rules import HEALTH_REGEN_RATE
from server import Arena

ROOT=Path(__file__).resolve().parents[1]


class HealthRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'data')
        self.arena=Arena(Path(self.temp.name)/'accounts.json',seed=37)
        self.user=self.arena.account('RecoveryTester','recovery@example.com','test-passphrase')
        self.arena.users['recoverytester']=self.user
        self.token=self.arena.session(self.user)['token']
        self.f=self.arena.fighters[self.arena.join(self.arena.sessions[self.token],0)]
        self.enemy=self.arena.spawn('regen-opponent','Opponent',True,3)
        self.f.update(world_id=0,x=0,z=0,yaw=0,spawn_safe=0,weapon='longsword')
        self.enemy.update(world_id=0,x=0,z=1.5,yaw=math.pi,spawn_safe=0)
        self.arena.fighters={self.f['id']:self.f,self.enemy['id']:self.enemy}
        self.arena.maintain_bots=lambda:None
        self.arena.bot_input=lambda f:{}

    def tearDown(self):self.temp.cleanup()

    def step(self,seconds,dt=.1):
        for _ in range(round(seconds/dt)):self.arena.tick(dt)

    def hurt(self,amount=20):self.arena.damage(self.enemy,self.f,amount,'body')

    def test_real_damage_waits_four_seconds_then_recovers_two_hp_per_second(self):
        self.hurt();self.assertEqual(self.f['hp'],80)
        self.step(4);self.assertAlmostEqual(self.f['hp'],80)
        self.step(3);self.assertAlmostEqual(self.f['hp'],86)
        self.assertEqual(self.f['regen_rate'],HEALTH_REGEN_RATE)

    def test_recovery_counts_only_the_portion_after_the_delay(self):
        self.f.update(hp=80,last_hurt=0)
        self.arena.clock=4.05
        self.arena.regenerate_health(self.f,.1)
        self.assertAlmostEqual(self.f['hp'],80.1)

    def test_tick_partition_does_not_change_recovered_health(self):
        results=[]
        for dt in (.05,.1,.25):
            self.arena.clock=0;self.f.update(hp=80,last_hurt=0)
            self.step(6,dt);results.append(self.f['hp'])
        for result in results:self.assertAlmostEqual(result,84)

    def test_another_hit_stops_active_recovery_and_restarts_delay(self):
        self.hurt();self.step(5);self.assertAlmostEqual(self.f['hp'],82)
        self.hurt(5);self.assertEqual(self.f['regen_rate'],0)
        hp=self.f['hp'];self.step(4);self.assertAlmostEqual(self.f['hp'],hp)
        self.step(1);self.assertAlmostEqual(self.f['hp'],hp+2)

    def test_held_guard_does_not_interrupt_recovery(self):
        self.f.update(hp=70,last_hurt=-10)
        self.enemy.update(attack='left',weapon='knife')
        self.f.update(block=True,block_since=-999,guard_dir='right')
        self.arena.strike(self.enemy)
        self.assertEqual(self.f['last_hurt'],-10)
        self.step(.5);self.assertAlmostEqual(self.f['hp'],71)

    def test_burning_prevents_recovery_and_real_burn_damage_delays_it(self):
        self.f.update(hp=60,last_hurt=-10,burn=1,burn_source=self.enemy['id'])
        self.step(.5)
        self.assertAlmostEqual(self.f['hp'],58.5)
        self.assertEqual(self.f['regen_rate'],0)
        self.assertAlmostEqual(self.f['last_hurt'],.5)

    def test_regeneration_stops_at_upgraded_maximum_without_changing_stats(self):
        self.f.update(hp=139.8,max_hp=140,health_upgrades=2,last_hurt=-10)
        before=copy.deepcopy(self.user)
        self.step(1)
        self.assertEqual((self.f['hp'],self.f['max_hp'],self.f['regen_rate']),(140,140,0))
        self.assertEqual(self.user,before)

    def test_dead_downed_eliminated_or_zero_hp_fighters_are_not_revived(self):
        for state in ({'dead':10},{'downed':10},{'eliminated':True},{'hp':0}):
            saved=copy.deepcopy(self.f)
            self.f.update(hp=10,last_hurt=-10,regen_rate=2);self.f.update(state)
            hp=self.f['hp'];self.arena.regenerate_health(self.f,1)
            self.assertEqual((self.f['hp'],self.f['regen_rate']),(hp,0),state)
            self.f.clear();self.f.update(saved)

    def test_kill_refills_entire_upgraded_health_and_stamina_immediately(self):
        self.f.update(hp=5,stamina=1,max_hp=160,health_upgrades=3,attack='left',last_hurt=self.arena.clock)
        self.enemy['hp']=1
        self.arena.strike(self.f)
        self.assertEqual((self.f['hp'],self.f['stamina'],self.f['regen_rate']),(160,100,0))
        self.assertEqual(self.f['kills'],1)

    def test_posthumous_and_downed_shooter_kills_do_not_revive_them(self):
        for state in ({'dead':2,'hp':0},{'downed':4,'hp':1}):
            saved=copy.deepcopy(self.f);self.f.update(**state)
            self.enemy.update(hp=0,dead=0);hp=self.f['hp']
            self.arena.finish_kill(self.f,self.enemy)
            self.assertEqual(self.f['hp'],hp)
            self.f.clear();self.f.update(saved)

    def test_bots_recover_at_the_same_rate_as_players(self):
        self.f.update(hp=50,last_hurt=-10);self.enemy.update(hp=50,last_hurt=-10)
        self.step(2)
        self.assertAlmostEqual(self.f['hp'],54);self.assertAlmostEqual(self.enemy['hp'],54)

    def test_state_reports_real_recovery_and_ignores_forged_values(self):
        self.f.update(hp=50,last_hurt=-10);self.step(.5)
        snapshot=self.arena.request('/arena/state',dict(hp=999,max_hp=999,regen_rate=999,last_hurt=-999),self.token)
        actor=next(f for f in snapshot['fighters'] if f['id']==self.f['id'])
        self.assertAlmostEqual(actor['hp'],51)
        self.assertEqual((actor['max_hp'],actor['regen_rate']),(100,2))
        self.assertEqual(self.f['last_hurt'],-10)

    def test_lobby_and_finished_rounds_do_not_regenerate(self):
        self.arena.request('/modes/join',dict(mode='squads100'),self.token)
        f=self.arena.fighters[self.arena.sessions[self.token]['fighter']]
        match=self.arena.match_for(f);f.update(hp=50,last_hurt=-10)
        for phase in ('countdown','finished'):
            match['phase']=phase;self.arena.regenerate_health(f,1)
            self.assertEqual((f['hp'],f['regen_rate']),(50,0))

    def test_survival_circle_damage_prevents_healing_and_is_not_cancelled(self):
        self.arena.request('/modes/join',dict(mode='squads100'),self.token)
        f=self.arena.fighters[self.arena.sessions[self.token]['fighter']]
        match=self.arena.match_for(f);match.update(phase='playing',started=0)
        f.update(x=37,z=0,hp=50,last_hurt=-10)
        self.arena.clock=10;self.arena.tick_modes(.1);self.arena.regenerate_health(f,.1)
        self.assertEqual((f['hp'],f['last_hurt'],f['regen_rate']),(49,10,0))

    def test_revive_starts_a_fresh_recovery_delay(self):
        self.arena.request('/modes/join',dict(mode='squads100'),self.token)
        f=self.arena.fighters[self.arena.sessions[self.token]['fighter']]
        match=self.arena.match_for(f);match.update(phase='playing',started=0)
        mate=next(a for a in self.arena.fighters.values() if a is not f and self.arena.allied(f,a))
        enemy=next(a for a in self.arena.fighters.values() if self.arena.can_fight(a,f))
        f.update(x=0,z=0,hp=1,spawn_safe=0);mate.update(x=.5,z=0)
        self.arena.mode_down(mate,enemy)
        f['input']={'revive':True,'move':[0,0]}
        for _ in range(31):
            self.arena.clock+=.1;f['last_input']=self.arena.clock;self.arena.tick_modes(.1)
        self.assertEqual(mate['downed'],0)
        self.assertAlmostEqual(mate['hp'],mate['max_hp']*.5)
        self.assertGreater(mate['last_hurt'],3)
        self.arena.regenerate_health(mate,.1)
        self.assertEqual(mate['regen_rate'],0)


if __name__=='__main__':unittest.main()
