import json
import math
import tempfile
import unittest
from pathlib import Path
from arena_features import make_worlds
from rules import ITEMS
from server import Arena

ROOT=Path(__file__).resolve().parents[1]


class MotionTests(unittest.TestCase):
    def setUp(self):
        (ROOT/"data"/"tests").mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/"data"/"tests")
        self.path=Path(self.temp.name)/"accounts.json";self.arena=Arena(self.path,seed=17);self.tokens=[]
        for _ in range(2):
            token=self.arena.request("/auth/guest",{})["token"];self.arena.request("/arena/join",{},token);self.tokens.append(token)
        self.a=self.arena.fighters[self.arena.sessions[self.tokens[0]]["fighter"]]
        self.b=self.arena.fighters[self.arena.sessions[self.tokens[1]]["fighter"]]
        self.a.update(x=0,z=0,yaw=0,body_yaw=0,spawn_safe=0,weapon="longsword",attack="left",world_id=0)
        self.b.update(x=0,z=2,yaw=math.pi,spawn_safe=0,world_id=0)
        self.arena.fighters={self.a["id"]:self.a,self.b["id"]:self.b}
        self.arena.maintain_bots=lambda:None

    def tearDown(self):self.temp.cleanup()

    def test_new_registered_account_starts_at_exact_requested_values(self):
        result=self.arena.request("/auth/register",dict(username="NewFighter",email="new@example.com",password="test-passphrase"))
        p=result["profile"]
        self.assertEqual((p["level"],p["skill"],p["coins"],p["xp"]),(1,0,100,0))
        self.assertEqual(p["weapon_slots"],["knife","","","",""])
        self.assertFalse(p["guest"])

    def test_logout_invalidates_session_but_preserves_account(self):
        result=self.arena.request("/auth/register",dict(username="Returning",email="r@example.com",password="test-passphrase"))
        token=result["token"];user=self.arena.sessions[token]["user"];user.update(coins=777,xp=200,skill=12);self.arena.save()
        self.assertTrue(self.arena.request("/auth/logout",{},token)["logged_out"])
        with self.assertRaises(ValueError):self.arena.request("/me",{},token)
        p=self.arena.request("/auth/login",dict(username="Returning",password="test-passphrase"))["profile"]
        self.assertEqual((p["coins"],p["xp"],p["skill"],p["level"]),(777,200,12,2))

    def test_purchased_weapons_fill_and_switch_quick_slots(self):
        u=self.arena.sessions[self.tokens[0]]["user"];u["coins"]=self.a["coins"]=5000
        self.arena.request("/shop/buy",dict(item="arming"),self.tokens[0]);self.arena.request("/shop/buy",dict(item="bow"),self.tokens[0])
        self.assertEqual(u["weapon_slots"][:3],["knife","arming","bow"])
        self.arena.request("/inventory/switch",dict(slot=1),self.tokens[0])
        self.assertEqual(self.a["weapon"],"arming")
        self.arena.request("/inventory/switch",dict(slot=2),self.tokens[0])
        self.assertEqual(self.a["weapon"],"bow")
        with self.assertRaises(ValueError):self.arena.request("/inventory/assign",dict(slot=0,item="sunblade"),self.tokens[0])
        with self.assertRaises(ValueError):self.arena.request("/inventory/switch",dict(slot=4),self.tokens[0])

    def test_aligned_held_guard_neither_loses_health_nor_stamina(self):
        self.b.update(block=True,block_since=-999,guard_dir="right",stamina=80)
        self.arena.strike(self.a)
        self.assertEqual((self.b["hp"],self.b["stamina"]),(100,80))
        self.assertEqual(self.b["xp"],0,"Holding guard is not an XP farming event")

    def test_mismatched_guard_does_not_counter_disarm(self):
        self.b.update(block=True,block_since=self.arena.clock,guard_dir="up",stamina=80)
        self.arena.strike(self.a)
        self.assertLess(self.b["hp"],100)
        self.assertEqual(self.a["weapon"],"longsword")
        self.assertEqual(self.b["stamina"],80)

    def test_last_instant_directional_guard_disarms_full_stamina_attacker(self):
        self.b.update(block=True,block_since=self.arena.clock,guard_dir="right")
        self.arena.strike(self.a)
        self.assertEqual(self.a["weapon"],"fists")
        self.assertEqual(self.b["stamina"],100)
        self.assertGreater(self.b["xp"],0)

    def test_block_cancels_attack_windup_and_prevents_its_hit(self):
        self.a["attack"]="";self.a["input"]={"attack":"left","yaw":0};self.a["last_input"]=self.arena.clock
        self.arena.tick(.03);self.assertGreater(self.a["windup"],0)
        self.a["input"]={"block":True,"guard_dir":"right","yaw":0};self.a["last_input"]=self.arena.clock
        self.arena.tick(.03)
        self.assertTrue(self.a["block"]);self.assertEqual(self.a["windup"],0)
        for _ in range(10):self.arena.tick(.03)
        self.assertEqual(self.b["hp"],100)

    def test_body_and_gait_follow_movement_independently_of_look(self):
        self.a["attack"]="";self.a["input"]={"move":[1,0],"yaw":0};self.a["last_input"]=self.arena.clock
        self.arena.tick(.1)
        self.assertAlmostEqual(self.a["body_yaw"],math.pi/2)
        self.assertEqual(self.a["yaw"],0)
        self.assertGreater(self.a["gait"],0);self.assertGreater(self.a["move_x"],0)

    def test_rooms_are_separate_for_melee_and_state(self):
        self.b["world_id"]=3;self.arena.strike(self.a)
        self.assertEqual(self.b["hp"],100)
        snapshot=self.arena.request("/arena/state",{},self.tokens[0])
        self.assertTrue(all(f["world_id"]==0 for f in snapshot["fighters"]))
        self.assertEqual(snapshot["world"]["id"],0)

    def test_projectile_does_not_hit_a_fighter_in_another_world(self):
        self.a["weapon"]="bow";self.b.update(z=5,world_id=3)
        self.arena.shoot(self.a,ITEMS["bow"]);self.arena.tick_objects(.3)
        self.assertEqual(self.b["hp"],100)

    def test_second_arrow_reflection_returns_towards_previous_deflector(self):
        self.a["weapon"]="bow";self.b.update(z=5,block=True,block_since=self.arena.clock)
        self.arena.shoot(self.a,ITEMS["bow"]);self.arena.tick_objects(.25)
        arrow=self.arena.projectiles[0]
        self.assertLess(arrow["vz"],0)
        self.a.update(weapon="longsword",block=True,block_since=self.arena.clock)
        self.arena.tick_objects(.3)
        self.assertEqual((arrow["owner"],arrow["bounces"]),(self.a["id"],2))
        self.assertGreater(arrow["vz"],0)
        self.assertEqual((self.a["hp"],self.b["hp"]),(100,100))

    def test_change_world_keeps_progress_and_chooses_actual_other_arena(self):
        self.arena.grant(self.a,xp=250,skill=7,coins=44)
        before=self.arena.profile(self.arena.sessions[self.tokens[0]]["user"])
        result=self.arena.request("/arena/world",dict(world_id=4),self.tokens[0])
        self.assertEqual(result["world"]["biome"],"volcanic")
        for key in ("xp","skill","coins","inventory"):self.assertEqual(result["profile"][key],before[key])

    def test_world_generation_has_five_distinct_repeatable_biomes(self):
        worlds=make_worlds(42)
        self.assertEqual(len({w["biome"] for w in worlds}),5)
        self.assertEqual(worlds,make_worlds(42))
        self.assertNotEqual(worlds[0]["props"],make_worlds(43)[0]["props"])

    def test_bot_population_is_maintained_independently_in_each_active_world(self):
        self.b["world_id"]=3
        Arena.maintain_bots(self.arena)
        for world_id in (0,3):
            fighters=[f for f in self.arena.fighters.values() if f["world_id"]==world_id]
            self.assertEqual((len(fighters),sum(f["bot"] for f in fighters)),(10,9))
        self.arena.fighters.pop(self.b["id"])
        Arena.maintain_bots(self.arena)
        self.assertTrue(all(f["world_id"]==0 for f in self.arena.fighters.values()))

    def test_unarmed_bot_does_not_chase_another_worlds_dropped_weapon(self):
        self.a.update(bot=True,weapon="fists")
        self.b["world_id"]=3
        self.arena.drop_weapon(self.b)
        self.assertEqual(self.arena.bot_input(self.a),{})

    def test_saved_inventory_and_stability_survive_server_restart(self):
        result=self.arena.request("/auth/register",dict(username="Keeper",email="k@example.com",password="test-passphrase"))
        token=result["token"];u=self.arena.sessions[token]["user"];u["coins"]=100000
        self.arena.request("/shop/buy",dict(item="katana"),token)
        self.arena.request("/inventory/assign",dict(slot=3,item="katana"),token)
        self.arena.request("/shop/buy",dict(item="stability"),token)
        before=self.arena.profile(u)
        fresh=Arena(self.path,seed=17)
        after=fresh.request("/auth/login",dict(username="Keeper",password="test-passphrase"))["profile"]
        for key in ("coins","weapon","weapon_slots","inventory","stability_upgrades","xp","skill"):
            self.assertEqual(after[key],before[key])

    def test_stability_reduces_actual_knockdown_rate(self):
        def count(upgrades):
            self.b["stability_upgrades"]=upgrades;total=0
            for _ in range(300):
                self.b.update(fall=0,balance=0)
                self.arena.balanced_hit(self.b,20,"legs")
                total+=self.b["fall"]>0
            return total
        normal=count(0);improved=count(3)
        self.assertGreater(normal,150)
        self.assertLess(improved,normal/4)

    def test_footing_store_upgrade_is_expensive_and_changes_real_resistance(self):
        u=self.arena.sessions[self.tokens[0]]["user"];u["coins"]=self.a["coins"]=100000
        p=self.arena.request("/shop/buy",dict(item="stability"),self.tokens[0])["profile"]
        self.assertEqual(p["coins"],84000)
        self.assertEqual(p["stability_upgrades"],1)
        self.assertAlmostEqual(p["fall_resistance"],.6)
        self.assertEqual(p["stability_upgrade_price"],64000)

    def test_grappling_rope_moves_its_owner_towards_target(self):
        self.a["weapon"]="grappling_rope";self.b["z"]=5
        self.arena.fire_rope(self.a);self.assertEqual(len(self.arena.ropes),1)
        self.arena.clock+=.3;self.arena.tick_ropes(.2)
        self.assertGreater(self.a["z"],.5)
        self.assertEqual(self.b["hp"],100)

    def test_lasso_can_knock_down_and_pull_target(self):
        self.a["weapon"]="lasso";self.b["z"]=5;self.arena.rng.random=lambda:0.
        self.arena.fire_rope(self.a)
        self.assertGreater(self.b["fall"],0)
        self.arena.clock+=.3;self.arena.tick_ropes(.2)
        self.assertLess(self.b["z"],5)


if __name__=="__main__":unittest.main()
