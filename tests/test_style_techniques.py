import copy
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from appearance import DEFAULT_APPEARANCE
from server import Arena
from rules import xp_for_level,MOVES
from techniques import technique

class StyleTechniquesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'accounts.json';self.arena=Arena(self.path,seed=17)
        self.u=self.arena.account('Stylist','style@example.com','long-test-password');self.arena.users['stylist']=self.u;self.arena.save()
        self.token=self.arena.session(self.u)['token'];self.f=self.arena.fighters[self.arena.join(self.arena.sessions[self.token],0)]
        self.arena.fighters={self.f['id']:self.f};self.arena.maintain_bots=lambda:None;self.f.update(x=0,z=0,spawn_safe=0)
    def tearDown(self):self.arena.learning_close();self.temp.cleanup()
    def call(self,route,body=None):return self.arena.request(route,body or {},self.token)
    def rank(self,rank):self.u['xp']=self.f['xp']=xp_for_level(rank);self.f['level']=rank
    def tick(self,**body):self.call('/arena/state',body);self.arena.tick(.03)
    def test_defaults_do_not_rewrite_existing_accounts(self):
        before=self.path.read_bytes();p=self.call('/me')['profile']
        self.assertEqual(p['appearance'],DEFAULT_APPEARANCE);self.assertEqual(p['technique_count'],0);self.assertEqual(p['next_technique']['rank'],2)
        self.assertEqual(self.path.read_bytes(),before)
    def test_skin_cape_saved_shared_and_survives_restart(self):
        self.call('/appearance/save',dict(appearance=dict(cloth=[.2,.5,.8],cape=dict(style='split',pattern='sun',length=1.3))))
        p=self.call('/arena/state');actor=next(f for f in p['fighters'] if f['id']==self.f['id'])
        self.assertEqual(actor['appearance']['cape']['style'],'split');self.assertEqual(actor['appearance']['cloth'],[.2,.5,.8])
        restored=Arena(self.path)
        try:self.assertEqual(restored.users['stylist']['appearance'],self.u['appearance'])
        finally:restored.learning_close()
    def test_cosmetic_validation_cannot_change_stats_or_accept_nonfinite_colours(self):
        before=copy.deepcopy(self.u)
        for value in (dict(hp=999),dict(cloth=[1,0]),dict(cloth=[True,0,0]),dict(cloth=[math.nan,0,0]),dict(cape=dict(length=10)),dict(cape=dict(style='flying')),dict(cape=dict(damage=999))):
            with self.assertRaises(ValueError):self.call('/appearance/save',dict(appearance=value))
        self.assertEqual(self.u,before)
    def test_failed_cosmetic_save_keeps_previous_appearance_and_actor(self):
        before=copy.deepcopy(self.f['appearance'])
        with patch.object(self.arena,'save',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.call('/appearance/save',dict(appearance=dict(cape=dict(style='long'))))
        self.assertNotIn('appearance',self.u);self.assertEqual(self.f['appearance'],before)
    def test_unique_technique_at_every_rank_without_finite_cap(self):
        combinations=[tuple(technique(rank)['moves']) for rank in range(2,10002)]
        self.assertEqual(len(combinations),len(set(combinations)))
        for rank in (2,10,11,100,10000000):self.assertTrue(all(move in MOVES for move in technique(rank)['moves']))
    def test_rank_unlocks_and_future_preview_are_server_authoritative(self):
        for invalid in (1,2,True,'2',-1,99):
            with self.assertRaises(ValueError):self.call('/techniques/select',dict(rank=invalid))
        with self.assertRaises(ValueError):self.call('/arena/state',dict(technique_rank=2))
        self.arena.grant(self.f,xp=79)
        self.assertEqual(self.f['level'],2);self.assertEqual(self.call('/me')['profile']['technique_count'],1)
        self.assertTrue(any(e['kind']=='technique_unlock' for e in self.arena.events))
        rows=self.call('/techniques')['techniques']['items'];self.assertTrue(rows[0]['unlocked']);self.assertFalse(rows[1]['unlocked'])
        self.call('/techniques/select',dict(rank=2));self.assertEqual(self.u['selected_technique'],2)
    def test_combo_has_real_separate_swings_and_normal_cost_no_hold_repeat(self):
        self.rank(2);started=[];self.f['stamina']=100
        for _ in range(120):
            before=self.f['attack_id'];self.tick(technique_rank=2)
            if self.f['attack_id']!=before:started.append((self.arena.clock,self.f['attack'],self.f['stamina']))
        self.assertEqual([v[1] for v in started],['feint','thrust'])
        self.assertEqual(started[0][2],94);self.assertGreaterEqual(started[1][0]-started[0][0],.34)
        self.assertEqual(self.f['attack_id'],2)
    def test_block_and_dodge_cancel_chain_but_preserve_spent_stamina(self):
        self.rank(3);self.tick(technique_rank=3);spent=self.f['stamina'];self.tick(block=True)
        self.assertEqual(self.f['technique_rank'],0);self.assertEqual(self.f['attack'],'');self.assertLess(self.f['stamina'],100)
        for _ in range(40):self.tick()
        self.tick(technique_rank=3);self.tick(dodge=True)
        self.assertEqual(self.f['technique_rank'],0);self.assertEqual(self.f['attack'],'');self.assertGreater(self.f['dodge'],0)
    def test_manual_cut_overrides_pending_combo_and_ranged_cannot_start_one(self):
        self.rank(3);self.tick(technique_rank=3);self.tick(attack='thrust')
        self.assertEqual(self.f['technique_rank'],0)
        self.f.update(weapon='bow',cooldown=0,last_technique=False,attack='',windup=0,queued_attack='')
        before=self.f['attack_id'];self.tick(technique_rank=3);self.assertEqual(self.f['attack_id'],before)
    def test_survival_uses_local_rank_and_shares_account_cosmetics(self):
        self.rank(4);identifier=self.call('/realms/create',dict(name='Style World',mobs=False))['created_realm']
        result=self.call('/realms/join',dict(id=identifier));self.f=self.arena.fighters[result['player']]
        self.assertEqual(result['profile']['technique_count'],0)
        with self.assertRaises(ValueError):self.call('/techniques/select',dict(rank=4))
        self.call('/appearance/save',dict(appearance=dict(cape=dict(style='short'))))
        self.assertEqual(self.f['appearance']['cape']['style'],'short');self.assertEqual(self.u['xp'],xp_for_level(4))

if __name__=='__main__':unittest.main()
