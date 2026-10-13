import importlib.util
import math
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("arena_server",Path(__file__).resolve().parents[1]/"server.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ArenaTests(unittest.TestCase):
    def setUp(self):
        runtime = Path(__file__).resolve().parents[1]/"data"/"tests"
        runtime.mkdir(parents=True,exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=runtime)
        self.path = Path(self.temp.name)/"accounts.json"
        self.arena = mod.Arena(self.path, seed=7)

    def tearDown(self):
        self.temp.cleanup()

    def guest(self):
        token = self.arena.request("/auth/guest",{})["token"]
        pid = self.arena.request("/arena/join",{},token)["player"]
        return token,self.arena.fighters[pid]

    def pair(self):
        token,a = self.guest()
        _,b = self.guest()
        self.arena.fighters = {a["id"]:a,b["id"]:b}
        a.update(x=0,z=0,yaw=0,weapon="longsword",spawn_safe=0)
        b.update(x=0,z=2,yaw=math.pi,spawn_safe=0)
        return a,b

    def test_accounts_are_hashed_persistent_and_private(self):
        result=self.arena.request("/auth/register",dict(username="Tester",email="t@example.com",password="long-secret"))
        self.assertNotIn("long-secret",self.path.read_text())
        self.assertNotIn("password",result["profile"])
        restored=mod.Arena(self.path)
        login=restored.request("/auth/login",dict(username="tester",password="long-secret"))
        self.assertEqual(login["profile"]["inventory"],["knife"])
        with self.assertRaises(ValueError):
            restored.request("/auth/login",dict(username="tester",password="wrong"))

    def test_bots_fill_to_ten_and_depart_for_humans(self):
        self.assertEqual(len(self.arena.fighters),10)
        self.assertEqual({f["depth"] for f in self.arena.fighters.values()},{2,3,4,5})
        for _ in range(12): self.guest()
        self.assertEqual(len(self.arena.fighters),12)
        self.assertFalse(any(f["bot"] for f in self.arena.fighters.values()))

    def test_human_account_cannot_spawn_multiple_fighters(self):
        creds=dict(username="Single",email="s@example.com",password="long-secret")
        a=self.arena.request("/auth/register",creds)["token"]
        b=self.arena.request("/auth/login",creds)["token"]
        self.arena.request("/arena/join",{},a)
        self.arena.request("/arena/join",{},b)
        self.assertEqual(sum(not f["bot"] for f in self.arena.fighters.values()),1)

    def test_directed_strike_block_and_dodge(self):
        a,b=self.pair();a["attack"]="left"
        self.arena.strike(a);unblocked=100-b["hp"]
        self.assertGreater(unblocked,0)
        b.update(hp=100,block=True,shield="kite",stamina=100)
        self.arena.strike(a);self.assertLess(100-b["hp"],unblocked)
        b.update(hp=100,dodge=.2)
        self.arena.strike(a);self.assertEqual(b["hp"],100)
        b.update(dodge=0,block=False,z=-2)
        self.arena.strike(a);self.assertEqual(b["hp"],100)

    def test_buy_equip_and_persist(self):
        result=self.arena.request("/auth/register",dict(username="Buyer",email="b@example.com",password="long-secret"))
        token=result["token"]
        with self.assertRaises(ValueError): self.arena.request("/shop/buy",dict(item="plate"),token)
        self.arena.sessions[token]["user"]["coins"]=500
        result=self.arena.request("/shop/buy",dict(item="arming"),token)
        self.assertEqual(result["profile"]["coins"],320)
        result=self.arena.request("/shop/buy",dict(item="arming"),token)
        self.assertEqual(result["profile"]["coins"],320)
        self.assertEqual(mod.Arena(self.path).users["buyer"]["weapon"],"arming")

    def test_timed_parry_prevents_damage_and_staggers_attacker(self):
        a,b=self.pair();a["attack"]="left"
        b.update(block=True,block_since=self.arena.clock)
        self.arena.strike(a)
        self.assertEqual(b["hp"],100)
        self.assertGreaterEqual(a["cooldown"],.85)
        self.assertTrue(any(e["kind"]=="parry" for e in self.arena.events))
        self.assertEqual(a["weapon"],"fists")

    def test_client_cannot_teleport_or_forge_rewards(self):
        token,f=self.guest();f.update(x=0,z=30);old_x=f["x"]
        self.arena.request("/arena/state",dict(move=[9999,9999],yaw=0,x=999,hp=999,coins=99999),token)
        self.arena.tick(.03)
        self.assertLess(abs(f["x"]-old_x),.2)
        self.assertEqual(f["hp"],100)
        self.assertEqual(self.arena.sessions[token]["user"]["coins"],100)
        with self.assertRaises(ValueError): self.arena.request("/arena/state",dict(move=[float("nan"),0]),token)

    def test_stale_input_stops_movement(self):
        token,f=self.guest()
        f.update(x=0,z=30)
        self.arena.request("/arena/state",dict(move=[1,0]),token)
        self.arena.clock+=1
        before=f["x"]
        self.arena.tick(.03)
        self.assertAlmostEqual(f["x"],before)

    def test_bot_search_uses_each_requested_depth(self):
        a,b=self.pair();a.update(bot=True,depth=2)
        choices=[]
        for depth in (2,3,4,5):
            a["depth"]=depth
            choice=self.arena.plan_bot(a,b)
            self.assertIn(choice,("advance","retreat","strafe_l","strafe_r","block","left","overhead","thrust","dodge"))
            choices.append(choice)
        self.assertEqual(len(choices),4)

    def test_replanning_does_not_stall_combat(self):
        for _ in range(900): self.arena.tick(1/30)
        self.assertGreater(sum(f["attack_id"] for f in self.arena.fighters.values()),10)
        self.assertGreater(sum(f["kills"] for f in self.arena.fighters.values()),0)

    def test_kill_rewards_and_respawn(self):
        a,b=self.pair();a["attack"]="overhead";b["hp"]=1
        self.arena.strike(a)
        self.assertGreater(b["dead"],0)
        user=next(s["user"] for s in self.arena.sessions.values() if s["fighter"]==a["id"])
        self.assertEqual(user["coins"],145)
        self.arena.fighters={b["id"]:b}
        for _ in range(36): self.arena.tick(.1)
        self.assertEqual(b["dead"],0)
        self.assertEqual(b["hp"],100)

    def test_reset_code_expires_and_invalidates_sessions(self):
        result=self.arena.request("/auth/register",dict(username="Reset",email="r@example.com",password="long-secret"))
        token=result["token"]
        code="test-one-use-code"
        hashed=mod.hashlib.sha256(code.encode()).hexdigest()
        self.arena.resets[hashed]=("reset",mod.time.monotonic()+60)
        self.arena.request("/auth/reset",dict(code=code,password="new-secret"))
        self.assertNotIn(token,self.arena.sessions)
        with self.assertRaises(ValueError):self.arena.request("/auth/reset",dict(code=code,password="new-secret"))
        self.arena.request("/auth/login",dict(username="reset",password="new-secret"))
        self.arena.resets[hashed]=("reset",mod.time.monotonic()-1)
        with self.assertRaises(ValueError):self.arena.request("/auth/reset",dict(code=code,password="new-secret"))


if __name__=="__main__":unittest.main()
