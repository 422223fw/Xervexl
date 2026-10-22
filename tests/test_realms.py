import copy
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from server import Arena
import voxel_world as vox


class RealmTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'accounts.json';self.arena=Arena(self.path,seed=7)
        self.alice=self.register('Alice');self.bob=self.register('Bob')
    def tearDown(self):self.arena.learning_close();self.temp.cleanup()
    def register(self,name):return self.arena.request('/auth/register',dict(username=name,email=name+'@example.com',password='long-secret-pass'))['token']
    def call(self,route,body=None,token=None):return self.arena.request(route,body or {},token or self.alice)
    def friends(self):
        self.call('/social/request',dict(username='Bob'));self.call('/social/respond',dict(username='Alice',accept=True),self.bob)
    def world(self,**settings):
        self.identifier=self.call('/realms/create',dict(name='Green Vale',**settings))['created_realm'];self.r=self.arena.realms[self.identifier]
        result=self.call('/realms/join',dict(id=self.identifier));self.f=self.arena.fighters[result['player']];return self.f
    def test_friendship_requires_recipient_acceptance_and_real_account(self):
        for name in ('Alice','not-an-account','Wandering raider'):
            with self.assertRaises(ValueError):self.call('/social/request',dict(username=name))
        self.call('/social/request',dict(username='Bob'));self.assertFalse(self.arena.friends_with('Alice','Bob'))
        with self.assertRaises(ValueError):self.call('/social/respond',dict(username='Bob',accept=True))
        self.call('/social/respond',dict(username='Alice',accept=True),self.bob)
        self.assertTrue(self.arena.friends_with('Bob','ALICE'));self.assertEqual(self.call('/social')['social']['friends'][0]['username'],'Bob')
    def test_private_world_hidden_until_friends_and_revocation_removes_access(self):
        self.world(mobs=False)
        self.assertEqual(self.call('/realms',token=self.bob)['realms'],[])
        with self.assertRaises(ValueError):self.call('/realms/join',dict(id=self.identifier),self.bob)
        with self.assertRaises(ValueError):self.call('/arena/world',dict(world_id=self.r['room']),self.bob)
        self.friends();joined=self.call('/realms/join',dict(id=self.identifier),self.bob)
        self.assertEqual(len(self.call('/realms',token=self.bob)['realms']),1)
        self.call('/social/remove',dict(username='Bob'))
        state=self.call('/arena/state',token=self.bob);self.assertEqual(state['player'],'');self.assertNotIn(joined['player'],self.arena.fighters)
        with self.assertRaises(ValueError):self.call('/realms/craft',dict(item='knife'),self.bob)
    def test_settings_owner_only_and_creatures_optional(self):
        self.world(mobs=False,bots=True);self.arena.tick(.03)
        local=[f for f in self.arena.fighters.values() if f['world_id']==self.r['room'] and f['bot']]
        self.assertEqual(len(local),4);self.assertEqual({f['mob_kind'] for f in local},{'sparring'})
        self.friends()
        with self.assertRaises(ValueError):self.call('/realms/settings',dict(id=self.identifier,mobs=True),self.bob)
        self.call('/realms/settings',dict(id=self.identifier,bots=False,mobs=True));self.arena.tick(.03)
        local=[f for f in self.arena.fighters.values() if f['world_id']==self.r['room'] and f['bot']]
        self.assertEqual(len(local),6);self.assertNotIn('sparring',{f['mob_kind'] for f in local})
    def test_crafting_uses_materials_isolates_arena_and_persists(self):
        self.world(mobs=False);u=copy.deepcopy(self.arena.users['alice']);state=self.arena.realm_player(self.f)
        self.assertEqual(state['inventory'],['fists'])
        with self.assertRaises(ValueError):self.call('/realms/craft',dict(item='pickaxe'))
        state['resources'].update(wood=8,stone=8);self.call('/realms/craft',dict(item='pickaxe'))
        self.assertEqual(self.f['weapon'],'pickaxe');self.assertEqual(state['resources']['wood'],4)
        self.arena.grant(self.f,xp=500,coins=500,skill=100)
        self.assertEqual(self.arena.users['alice'],u)
        with self.assertRaises(ValueError):self.call('/shop/buy',dict(item='arming'))
        self.call('/arena/leave');restored=Arena(self.path,seed=8)
        try:
            token=restored.request('/auth/login',dict(username='Alice',password='long-secret-pass'))['token']
            result=restored.request('/realms/join',dict(id=self.identifier),token)
            self.assertIn('pickaxe',result['profile']['inventory']);self.assertEqual(result['profile']['resources']['wood'],4)
        finally:restored.learning_close()
    def test_mining_requires_continuous_aim_gives_material_and_saves(self):
        self.world(mobs=False);hit=dict(cell=(0,4,2),adjacent=(0,5,2),block=dict(material='grass'),point=(0,2.5,1))
        with patch.object(self.arena,'realm_aim',return_value=hit):
            for _ in range(8):self.arena.realm_build_tick(self.f,dict(build_mode=True,mine=True),.1)
        self.assertIsNone(self.r['record']['edits']['0,4,2']);self.assertEqual(self.arena.realm_player(self.f)['resources']['dirt'],1)
        self.assertTrue((self.arena.realm_directory/(self.identifier+'.json')).exists())
    def test_mining_failed_save_rolls_back_block_and_loot(self):
        self.world(mobs=False);hit=dict(cell=(0,4,2),adjacent=(0,5,2),block=dict(material='grass'),point=(0,2.5,1))
        before=copy.deepcopy(self.r['record'])
        with patch.object(self.arena,'realm_aim',return_value=hit),patch.object(self.arena,'save_realm',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.arena.realm_build_tick(self.f,dict(build_mode=True,mine=True),1.)
        self.assertEqual(self.r['record'],before)
    def test_friend_build_and_pvp_are_independent_settings(self):
        self.world(mobs=False,friends_build=False);self.friends();pid=self.call('/realms/join',dict(id=self.identifier),self.bob)['player'];b=self.arena.fighters[pid]
        self.assertFalse(self.arena.realm_can_build(b));self.assertTrue(self.arena.realm_can_build(self.f));self.assertFalse(self.arena.can_fight(self.f,b))
        self.call('/realms/settings',dict(id=self.identifier,pvp=True,friends_build=True))
        self.assertTrue(self.arena.realm_can_build(b));self.assertTrue(self.arena.can_fight(self.f,b))
    def test_shapes_mining_ray_and_floor_agree(self):
        record=dict(seed=7,edits={'0,5,0':dict(material='wood',shape='slab',rotation=0)})
        self.assertAlmostEqual(vox.floor_at(record,.25,.25,4),2.75)
        self.assertTrue(vox.solid(record,.25,2.6,.25));self.assertFalse(vox.solid(record,.25,2.9,.25))
        hit=vox.ray(record,(.25,4,.25),(0,-1,0));self.assertEqual(hit['cell'],(0,5,0));self.assertNotEqual(hit['cell'],hit['adjacent'])
        record['edits']['0,5,0']['shape']='ramp'
        self.assertAlmostEqual(vox.floor_at(record,.1,.25,4),2.6)
    def test_world_room_is_never_used_as_arena_overflow(self):
        self.world(mobs=False);self.r['record']['edits']['0,4,0']=None
        for w in self.arena.world_catalog():self.assertNotEqual(w['id'],self.r['room'])
        for _ in range(20):self.assertNotEqual(self.arena.choose_world(),self.r['room'])
        for invalid in ('0',True,-1):
            with self.assertRaises(ValueError):self.arena.join(self.arena.sessions[self.alice],invalid,True)

    def test_placement_consumes_one_block_rejects_avatar_overlap_and_save_failure(self):
        self.world(mobs=False);self.arena.realm_player(self.f)['resources']['wood']=3
        hit=dict(cell=(0,4,4),adjacent=(0,5,4),block=dict(material='grass'),point=(0,2.5,2))
        inp=dict(build_mode=True,place=True,build_material='wood',build_shape='ramp',build_rotation=3)
        with patch.object(self.arena,'realm_aim',return_value=hit):
            self.arena.realm_build_tick(self.f,inp,.1);self.arena.realm_build_tick(self.f,inp,.1)
        self.assertEqual(self.r['record']['edits']['0,5,4']['rotation'],3);self.assertEqual(self.arena.realm_player(self.f)['resources']['wood'],2)
        self.f['last_place']=False;hit['adjacent']=(0,5,0)
        with patch.object(self.arena,'realm_aim',return_value=hit):self.arena.realm_build_tick(self.f,inp,.1)
        self.assertNotIn('0,5,0',self.r['record']['edits'])
        self.f['last_place']=False;hit['adjacent']=(1,5,4);before=copy.deepcopy(self.r['record'])
        with patch.object(self.arena,'realm_aim',return_value=hit),patch.object(self.arena,'save_realm',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.arena.realm_build_tick(self.f,inp,.1)
        self.assertEqual(self.r['record'],before)

    def test_walls_block_movement_and_mined_floor_allows_falling(self):
        self.world(mobs=False);self.f.update(x=0,z=0,y=2.5)
        for y in range(5,9):self.r['record']['edits'][f'1,{y},0']=dict(material='stone',shape='cube',rotation=0)
        self.f['x']=.45;self.arena.realm_move(self.f,0,0,.03);self.assertEqual(self.f['x'],0)
        for x in (-1,0):
            for z in (-1,0):self.r['record']['edits'][f'{x},4,{z}']=None
        for _ in range(10):self.arena.realm_move(self.f,0,0,.05)
        self.assertAlmostEqual(self.f['y'],2.)

    def test_world_trace_stops_at_terrain_and_dropped_blade_lands_above_ground(self):
        self.world(mobs=False);self.f.update(x=0,z=0,y=2.5,weapon='knife');self.arena.drop_weapon(self.f)
        self.assertGreater(self.arena.drops[-1]['y'],self.f['y'])
        for _ in range(50):self.arena.tick_objects(.04)
        drop=self.arena.drops[-1];self.assertAlmostEqual(drop['y'],2.56)
        self.assertIsNotNone(self.arena.realm_trace(self.r['room'],(0,4,0),(0,1,0)))
        self.assertIsNone(self.arena.realm_trace(self.r['room'],(0,4,0),(0,4,2)))

    def test_crafted_gear_equip_and_world_progress_do_not_leak_into_account(self):
        self.world(mobs=False);state=self.arena.realm_player(self.f);state['resources'].update(wood=30,iron=30)
        self.call('/realms/craft',dict(item='woodshield'));self.call('/realms/craft',dict(item='buckler'))
        self.call('/realms/equip',dict(item='woodshield'));self.assertEqual(self.f['shield'],'woodshield')
        self.arena.grant(self.f,xp=80,skill=3);self.arena.realm_checkpoint(self.f);self.arena.flush_realms()
        self.assertEqual(self.call('/me')['profile']['level'],2);self.assertEqual(self.arena.users['alice']['xp'],0)
        self.call('/arena/leave');self.call('/realms/join',dict(id=self.identifier));self.assertEqual(self.call('/me')['profile']['xp'],80)

    def test_creation_failed_save_leaves_no_broken_room(self):
        worlds=len(self.arena.worlds)
        with patch.object(self.arena,'save_realms_index',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.call('/realms/create',dict(name='No space'))
        self.assertFalse(self.arena.realms);self.assertEqual(len(self.arena.worlds),worlds)

    def test_failed_social_save_does_not_grant_unsaved_friend_access(self):
        self.call('/social/request',dict(username='Bob'))
        with patch('social.atomic_json',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.call('/social/respond',dict(username='Alice',accept=True),self.bob)
        self.assertFalse(self.arena.friends_with('Alice','Bob'));self.assertIn(['alice','bob'],self.arena.social['requests'])


if __name__=='__main__':unittest.main()
