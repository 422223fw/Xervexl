import json
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from pathlib import Path
from arena_features import SERVER_CAPACITY, WORLD_TYPES
BASE=len(WORLD_TYPES)
from server import Arena, Handler, ThreadingHTTPServer, password_hash

ROOT=Path(__file__).resolve().parents[1]


class CapacityTests(unittest.TestCase):
    def setUp(self):
        runtime=ROOT/'data'/'tests';runtime.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=runtime)
        self.arena=Arena(Path(self.temp.name)/'accounts.json',seed=8)
        self.credential=password_hash('synthetic-load-passphrase')
        self.tokens=[]

    def tearDown(self):self.temp.cleanup()

    def account(self):
        # Real registered-user/session structures; reuse one synthetic hash to
        # keep capacity checks focused on allocation rather than 200 PBKDF runs.
        name=f'LoadPlayer{len(self.tokens):03d}'
        user=self.arena.account(name,name.lower()+'@example.com')
        user['password']=self.credential;self.arena.users[name.lower()]=user
        token=self.arena.session(user)['token'];self.tokens.append(token)
        return token

    def enter(self,token=None,world=0):
        token=token or self.account()
        route='/arena/join' if world is None else '/arena/world'
        return self.arena.request(route,{} if world is None else dict(world_id=world),token)

    def fill(self,count=100,world=0):
        return [self.enter(world=world) for _ in range(count)]

    def test_hundredth_player_opens_exactly_one_new_server_without_moving_existing_players(self):
        self.fill(99);before={f['id'] for f in self.arena.fighters.values() if not f['bot']}
        self.assertEqual(len(self.arena.worlds),BASE)
        self.enter()
        self.assertEqual(self.arena.populations()[0],100)
        self.assertEqual(len(self.arena.worlds),BASE+1)
        self.assertTrue(before.issubset(self.arena.fighters))
        spare=self.arena.worlds[BASE]
        self.assertEqual(spare['biome'],self.arena.worlds[0]['biome'])
        self.assertNotEqual(spare['seed'],self.arena.worlds[0]['seed'])
        self.assertNotEqual(spare['props'],self.arena.worlds[0]['props'])
        self.assertEqual(self.arena.populations()[BASE],0)

    def test_automatic_player_101_enters_new_server_and_gets_filler_bots(self):
        self.fill();result=self.enter(world=None)
        self.assertEqual(result['world']['id'],BASE)
        self.assertEqual(result['world']['humans'],1)
        self.assertEqual(result['world']['bots'],9)
        self.assertEqual(self.arena.populations()[0],100)
        self.assertEqual(len(self.arena.worlds),BASE+1)

    def test_explicit_join_to_full_server_reports_actual_destination(self):
        self.fill();result=self.enter(world=0)
        self.assertEqual(result['world']['id'],BASE)
        self.assertIn('full',result['message'])
        self.assertEqual(self.arena.fighters[result['player']]['world_id'],BASE)
        self.assertEqual(result['world']['capacity'],SERVER_CAPACITY)

    def test_two_hundred_players_create_a_third_instance_without_overbooking(self):
        self.fill(200)
        self.assertEqual(self.arena.populations()[0],100)
        self.assertEqual(self.arena.populations()[BASE],100)
        self.assertEqual(self.arena.populations()[BASE+1],0)
        self.assertEqual(len(self.arena.worlds),BASE+2)
        result=self.enter(world=None)
        self.assertEqual(result['world']['id'],BASE+1)
        self.assertTrue(all(n<=100 for n in self.arena.populations().values()))

    def test_rejoining_a_full_server_keeps_current_avatar_and_uses_no_extra_slot(self):
        self.fill();token=self.tokens[0]
        actor=self.arena.fighters[self.arena.sessions[token]['fighter']]
        actor.update(hp=37,stamina=24)
        for _ in range(3):
            result=self.enter(token,0)
            self.assertEqual(result['player'],actor['id'])
        self.assertEqual((actor['hp'],actor['stamina']),(37,24))
        self.assertEqual(self.arena.populations()[0],100)
        self.assertEqual(len(self.arena.worlds),BASE+1)

    def test_another_device_of_same_account_replaces_its_slot_in_full_server(self):
        self.fill();first=self.tokens[0];user=self.arena.sessions[first]['user']
        second=self.arena.session(user)['token']
        result=self.enter(second,0)
        self.assertEqual(result['world']['id'],0)
        self.assertEqual(self.arena.sessions[first]['fighter'],'')
        self.assertEqual(sum(not f['bot'] for f in self.arena.fighters.values()),100)
        self.assertEqual(len(self.arena.worlds),BASE+1)

    def test_departure_reopens_a_slot_and_reuses_existing_server(self):
        self.fill();self.arena.request('/arena/leave',{},self.tokens[0])
        result=self.enter(world=None)
        self.assertEqual(result['world']['id'],0)
        self.assertEqual(self.arena.populations()[0],100)
        self.assertEqual(len(self.arena.worlds),BASE+1)

    def test_bots_and_signed_in_home_accounts_do_not_consume_human_capacity(self):
        for _ in range(101):self.account()
        self.assertEqual(len(self.arena.worlds),BASE)
        info=self.arena.request('/servers',{})['worlds'][0]
        self.assertEqual((info['humans'],info['bots'],info['available']),(0,10,100))
        result=self.enter(self.tokens[0],0)
        self.assertEqual((result['world']['humans'],result['world']['bots']),(1,9))

    def test_expired_avatar_reopens_slot_while_account_remains_authenticated(self):
        self.fill();token=self.tokens[0]
        self.arena.sessions[token]['touched']=time.monotonic()-61
        self.arena.tick(.03)
        self.assertEqual(self.arena.populations()[0],99)
        self.assertTrue(self.arena.request('/auth/resume',{},token)['authenticated'])
        self.assertEqual(self.enter(world=None)['world']['id'],0)

    def test_invalid_move_leaves_current_avatar_and_client_cannot_raise_capacity(self):
        result=self.enter();token=self.tokens[0];original=result['player']
        for invalid in (None,False,'0',1.5,999,-1):
            with self.assertRaises(ValueError):self.arena.request('/arena/world',dict(world_id=invalid),token)
            self.assertEqual(self.arena.sessions[token]['fighter'],original)
            self.assertIn(original,self.arena.fighters)
        result=self.arena.request('/arena/world',dict(world_id=0,capacity=99999,server_capacity=99999),token)
        self.assertEqual(result['world']['capacity'],100)

    def test_moves_to_full_servers_keep_equipment_and_progress(self):
        self.fill();token=self.account();user=self.arena.sessions[token]['user']
        user.update(coins=1357,xp=1000,skill=41,inventory=['knife','arming'],weapon='arming')
        first=self.enter(token,1)
        moved=self.enter(token,0)
        self.assertEqual(moved['world']['id'],BASE)
        for key in ('coins','xp','skill','inventory','weapon'):self.assertEqual(moved['profile'][key],first['profile'][key])
        self.assertEqual(self.arena.populations()[1],0)

    def test_listing_is_live_metadata_and_does_not_leak_accounts(self):
        self.fill();result=self.arena.request('/servers',{})
        self.assertEqual(result['server_capacity'],100)
        self.assertEqual(len(result['worlds']),BASE+1)
        full=result['worlds'][0]
        self.assertTrue(full['full']);self.assertEqual(full['available'],0)
        self.assertFalse(result['worlds'][BASE]['full'])
        self.assertNotIn('props',full)
        text=json.dumps(result)
        for secret in ('password','email','LoadPlayer',self.tokens[0]):self.assertNotIn(secret,text)

    def test_overflow_instances_have_separate_combat_and_dropped_weapons(self):
        self.fill();result=self.enter();a=self.arena.fighters[self.arena.sessions[self.tokens[0]]['fighter']]
        b=self.arena.fighters[result['player']]
        a.update(x=0,z=0,spawn_safe=0,weapon='longsword',attack='left',yaw=0)
        b.update(x=0,z=1,spawn_safe=0,hp=100)
        self.arena.strike(a);self.assertEqual(b['hp'],100)
        self.arena.drop_weapon(a)
        drop=self.arena.drops[-1];drop.update(x=0,z=1,y=.06,age=1.2)
        self.assertFalse(self.arena.pickup_weapon(b))
        state=self.arena.request('/arena/state',{},self.tokens[-1])
        self.assertTrue(all(f['world_id']==BASE for f in state['fighters']))
        self.assertNotIn(drop,state['drops'])

    def test_concurrent_http_joins_at_99_do_not_overbook_or_duplicate_spares(self):
        self.fill(99);tokens=[self.account() for _ in range(8)]
        class TestHandler(Handler):pass
        TestHandler.arena=self.arena;TestHandler.limits={}
        http=ThreadingHTTPServer(('127.0.0.1',0),TestHandler)
        service=threading.Thread(target=http.serve_forever,daemon=True);service.start()
        def connect(token):
            connection=HTTPConnection('127.0.0.1',http.server_port,timeout=5)
            connection.request('POST','/arena/world',json.dumps(dict(world_id=0)),{'Authorization':'Bearer '+token,'Content-Type':'application/json'})
            response=connection.getresponse();body=json.loads(response.read());connection.close()
            self.assertEqual(response.status,200,body)
            return body['world']['id']
        try:
            with ThreadPoolExecutor(max_workers=8) as workers:destinations=list(workers.map(connect,tokens))
        finally:
            http.shutdown();http.server_close();service.join()
        self.assertEqual(destinations.count(0),1)
        self.assertEqual(destinations.count(BASE),7)
        self.assertEqual(len(self.arena.worlds),BASE+1)
        self.assertEqual(self.arena.populations()[0],100)
        self.assertEqual(self.arena.populations()[BASE],7)


if __name__=='__main__':unittest.main()
