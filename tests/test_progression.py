import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path
from rules import (ITEMS,PERSISTENT,level_for_xp,xp_for_level,death_penalty)

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("progression_server",ROOT/"server.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ProgressionTests(unittest.TestCase):
    def setUp(self):
        (ROOT/"data"/"tests").mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/"data"/"tests")
        self.path=Path(self.temp.name)/"accounts.json"
        self.arena=mod.Arena(self.path,seed=9)
        self.tokens=[]
        for number in range(2):
            token=self.arena.request("/auth/register",dict(username="Fighter"+str(number),email=f"fighter{number}@example.com",password="test-passphrase"))["token"]
            self.arena.request("/arena/join",{},token);self.tokens.append(token)
        self.a=self.arena.fighters[self.arena.sessions[self.tokens[0]]["fighter"]]
        self.b=self.arena.fighters[self.arena.sessions[self.tokens[1]]["fighter"]]
        self.arena.fighters={self.a["id"]:self.a,self.b["id"]:self.b}
        self.a.update(x=0,z=0,yaw=0,spawn_safe=0,weapon="longsword",attack="left")
        self.b.update(x=0,z=2,yaw=math.pi,spawn_safe=0)

    def tearDown(self):self.temp.cleanup()

    def rank(self,f,level):f["xp"]=xp_for_level(level);f["level"]=level

    def test_kill_reward_uses_victim_rank_and_persists_profile(self):
        self.rank(self.b,7);self.b.update(hp=1,skill=80)
        self.arena.strike(self.a)
        profile=self.arena.request("/me",{},self.tokens[0])["profile"]
        self.assertEqual(profile["xp"],180)
        self.assertEqual(profile["skill"],7)
        self.assertEqual(profile["coins"],205)
        self.assertEqual(profile["level"],2)
        self.assertEqual(self.b["skill"],80-death_penalty(7,1))

    def test_lower_rank_killer_costs_more_skill(self):
        self.assertGreater(death_penalty(10,1),death_penalty(10,10))
        self.assertGreater(death_penalty(10,5),death_penalty(10,15))

    def test_elimination_refills_upgraded_health_and_stamina_in_client_state(self):
        self.a.update(hp=19.,stamina=3.,health_upgrades=4,max_hp=180.)
        self.b["hp"]=1
        self.arena.strike(self.a)
        snapshot=self.arena.request("/arena/state",{},self.tokens[0])
        fighter=next(f for f in snapshot["fighters"] if f["id"]==self.a["id"])
        self.assertEqual((fighter["hp"],fighter["stamina"],fighter["max_hp"]),(180,100,180))
        self.assertEqual(self.a["kills"],1)

    def test_nonlethal_hit_does_not_refill_the_attacker(self):
        self.a.update(hp=19.,stamina=3.)
        self.arena.strike(self.a)
        self.assertGreater(self.b["hp"],0)
        self.assertLess(self.b["hp"],100)
        self.assertEqual((self.a["hp"],self.a["stamina"]),(19,3))

    def test_posthumous_projectile_elimination_does_not_revive_dead_shooter(self):
        self.a["weapon"]="bow";self.b.update(z=5,hp=1)
        self.arena.shoot(self.a,ITEMS["bow"])
        self.a.update(dead=2.,hp=0.,stamina=12.)
        self.arena.tick_objects(.3)
        self.assertEqual(self.a["kills"],1)
        self.assertEqual((self.a["dead"],self.a["hp"],self.a["stamina"]),(2,0,12))

    def test_perfect_parry_costs_zero_stamina_and_earns_progress(self):
        self.rank(self.a,6)
        self.b.update(block=True,block_since=self.arena.clock,stamina=0)
        self.arena.strike(self.a)
        self.assertEqual(self.b["stamina"],0)
        self.assertEqual(self.b["hp"],100)
        self.assertEqual(self.b["xp"],130)
        self.assertEqual(self.b["skill"],5)
        self.assertEqual(self.a["weapon"],"fists")
        self.assertEqual(self.b["parries"],1)

    def test_disarm_earns_progress_loses_victim_skill_and_spawns_weapon(self):
        self.rank(self.b,5);self.b.update(stamina=20,skill=50,weapon="sabre")
        self.a["attack"]="disarm"
        self.arena.strike(self.a)
        self.assertEqual(self.b["weapon"],"fists")
        self.assertEqual(self.arena.drops[0]["weapon"],"sabre")
        self.assertEqual(self.a["xp"],75)
        self.assertEqual(self.a["skill"],2)
        self.assertEqual(self.b["skill"],43)
        self.arena.strike(self.a)
        self.assertEqual(self.a["xp"],75,"Cannot score another disarm against empty hands")

    def test_drop_pickup_does_not_grant_permanent_ownership(self):
        self.b.update(skill=9,weapon="greatsword")
        self.arena.drop_weapon(self.b)
        self.assertEqual(self.b["skill"],9,"Voluntary drop is not a skill penalty")
        for _ in range(40):self.arena.tick_objects(1/30)
        drop=self.arena.drops[0];self.a.update(x=drop["x"],z=drop["z"])
        self.assertTrue(self.arena.pickup_weapon(self.a))
        self.assertEqual(self.a["weapon"],"greatsword")
        self.assertNotIn("greatsword",self.arena.sessions[self.tokens[0]]["user"]["inventory"])

    def test_hit_region_changes_damage_and_no_full_health_one_shot(self):
        self.a["weapon"]="knife";self.b["z"]=1.2;losses={}
        for zone in ("head","body","legs"):
            self.a["aim_zone"]=zone;self.b["hp"]=100
            self.arena.strike(self.a);losses[zone]=100-self.b["hp"]
        self.assertGreater(losses["head"],losses["body"])
        self.assertGreater(losses["body"],losses["legs"])
        self.a.update(weapon="sunblade",attack="overhead",aim_zone="head");self.b["hp"]=100
        self.arena.strike(self.a)
        self.assertGreaterEqual(self.b["hp"],25)

    def test_helmet_protects_head(self):
        self.a["aim_zone"]="head";self.arena.strike(self.a);normal=100-self.b["hp"]
        self.b.update(hp=100,helmet="steelhelm")
        self.arena.strike(self.a)
        self.assertLess(100-self.b["hp"],normal)

    def test_arrow_sweep_hits_instead_of_tunnelling(self):
        self.a["weapon"]="bow";self.b["z"]=5
        self.arena.shoot(self.a,ITEMS["bow"])
        self.arena.tick_objects(.3)
        self.assertLess(self.b["hp"],100)
        self.assertEqual(len(self.arena.projectiles),0)

    def test_arrow_can_be_deflected_and_credit_changes_owner(self):
        self.a.update(weapon="bow",hp=1);self.b.update(z=5,weapon="longsword",block=True,block_since=self.arena.clock,hp=32,stamina=18)
        before=self.b["stamina"]
        self.arena.shoot(self.a,ITEMS["bow"]);self.arena.tick_objects(.25)
        self.assertEqual(self.b["hp"],32)
        self.assertEqual(self.b["stamina"],before)
        self.assertEqual(self.arena.projectiles[0]["owner"],self.b["id"])
        self.assertGreater(self.b["xp"],0)
        self.arena.tick_objects(.3)
        self.assertGreater(self.a["dead"],0)
        self.assertEqual(self.b["kills"],1)
        self.assertEqual((self.b["hp"],self.b["stamina"]),(100,100))

    def test_ordinary_shield_block_reduces_projectile_damage(self):
        self.a["weapon"]="crossbow";self.b.update(z=5,block=True,block_since=-999,shield="kite")
        self.arena.shoot(self.a,ITEMS["crossbow"]);self.arena.tick_objects(.2)
        self.assertGreater(self.b["hp"],85)
        self.assertLess(self.b["hp"],100)

    def test_health_upgrades_are_expensive_repeatable_and_survive_respawn(self):
        user=self.arena.sessions[self.tokens[0]]["user"];user["coins"]=self.a["coins"]=60000
        result=self.arena.request("/shop/buy",dict(item="health"),self.tokens[0])["profile"]
        self.assertEqual(result["coins"],48000)
        self.assertEqual(result["max_hp"],120)
        self.assertEqual(result["health_upgrade_price"],48000)
        result=self.arena.request("/shop/buy",dict(item="health"),self.tokens[0])["profile"]
        self.assertEqual(result["coins"],0)
        self.assertEqual(result["max_hp"],140)
        self.a.update(dead=.01,hp=0)
        self.arena.tick(.02)
        self.assertEqual(self.a["hp"],140)

    def test_shop_and_combat_do_not_restore_spent_money(self):
        user=self.arena.sessions[self.tokens[0]]["user"];user["coins"]=self.a["coins"]=500
        self.arena.request("/shop/buy",dict(item="arming"),self.tokens[0])
        self.arena.grant(self.a,xp=10)
        self.assertEqual(user["coins"],320)

    def test_spell_cooldown_stamina_and_healing(self):
        self.a.update(spell="heal",hp=50)
        self.assertTrue(self.arena.cast_spell(self.a))
        self.assertEqual(self.a["hp"],75)
        self.assertEqual(self.a["stamina"],60)
        self.assertFalse(self.arena.cast_spell(self.a))
        self.assertEqual(self.a["hp"],75)

    def test_frost_projectile_slows_after_real_hit(self):
        self.a.update(spell="frostbolt");self.b["z"]=4
        self.assertTrue(self.arena.cast_spell(self.a));self.arena.tick_objects(.25)
        self.assertGreater(self.b["slow"],0)

    def test_magical_blade_has_an_actual_combat_effect(self):
        self.a["weapon"]="stormblade";self.b["stamina"]=50
        self.arena.strike(self.a)
        self.assertEqual(self.b["stamina"],38)
        self.assertGreaterEqual(self.b["cooldown"],.18)

    def test_fire_damage_ticks_and_keeps_kill_credit(self):
        self.arena.maintain_bots=lambda:None
        self.a.update(hp=50.,stamina=10.)
        self.b["hp"]=8
        self.arena.damage(self.a,self.b,1,"body",magic="fire")
        for _ in range(32):self.arena.tick(.1)
        self.assertEqual(self.a["kills"],1)
        self.assertEqual((self.a["hp"],self.a["stamina"]),(100,100))
        self.assertGreater(self.b["dead"],0)
        self.assertTrue(any(e["kind"]=="burn" for e in self.arena.events))

    def test_leaderboards_include_bots_and_only_public_stats(self):
        self.arena.maintain_bots();self.arena.grant(self.a,skill=500)
        boards=self.arena.request("/leaderboards",{},self.tokens[0])["leaderboards"]
        self.assertEqual(set(boards),{"skill","level","xp","coins","kills"})
        self.assertEqual(boards["skill"][0]["username"],self.a["name"])
        self.assertTrue(any(row["bot"] for row in boards["level"]))
        self.assertNotIn("password",json.dumps(boards))
        self.assertNotIn("email",json.dumps(boards))

    def test_legacy_migration_backs_up_and_preserves_progress(self):
        old=self.arena.account("Legacy","l@example.com","long-secret")
        for key in ("xp","skill","parries","disarms","health_upgrades","helmet","spell"):old.pop(key)
        old.update(coins=5432,kills=12,inventory=["knife","sabre"],weapon="sabre")
        self.path.write_text(json.dumps({"legacy":old}),encoding="utf-8")
        restored=mod.Arena(self.path)
        backup=list(self.path.parent.glob("accounts.pre-progression-*.bak"))
        self.assertEqual(len(backup),1)
        self.assertEqual(json.loads(backup[0].read_text())["legacy"]["coins"],5432)
        user=restored.users["legacy"]
        self.assertEqual(user["coins"],5432);self.assertEqual(user["kills"],12);self.assertEqual(user["weapon"],"sabre")
        self.assertEqual(user["xp"],0)
        restored.request("/auth/login",dict(username="Legacy",password="long-secret"))

    def test_fake_progress_fields_are_ignored(self):
        self.arena.request("/arena/state",dict(xp=999999,skill=999999,coins=999999,level=99,max_hp=9999),self.tokens[0])
        self.assertEqual(self.a["xp"],0);self.assertEqual(self.a["skill"],0);self.assertEqual(self.a["max_hp"],100)


if __name__=="__main__":unittest.main()
