import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from bot_learning import BotLearning, context
from server import Arena

ROOT = Path(__file__).resolve().parents[1]


class CombatFixture(unittest.TestCase):
    def setUp(self):
        runtime = ROOT/'data'/'tests'
        runtime.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=runtime)
        self.path = Path(self.temp.name)/'accounts.json'
        self.arena = Arena(self.path, seed=5)
        self.a = self.arena.spawn('learner', 'Learner', True, 3)
        self.b = self.arena.spawn('target', 'Target')
        self.a.update(x=0, z=0, yaw=0, world_id=0, weapon='longsword', hp=100,
                      spawn_safe=0, armour='', shield='', helmet='', stamina=100)
        self.b.update(x=0, z=2, yaw=math.pi, world_id=0, spawn_safe=0)
        self.arena.fighters = {self.a['id']: self.a, self.b['id']: self.b}
        self.arena.worlds[0]['props'] = []
        self.arena.maintain_bots = lambda: None
        self.arena.rng.random = lambda: 1. # Disable exploration for choice comparisons.

    def tearDown(self):
        self.temp.cleanup()

    def attack(self, move='left'):
        self.a['attack'] = move
        self.arena.learning_attack(self.a)
        return self.a.get('attack_learning')


class LearningTests(CombatFixture):

    def test_real_hit_and_miss_change_learned_action_values(self):
        key = context(self.a, self.b)
        self.attack('left');self.arena.strike(self.a)
        self.assertGreater(self.arena.learning.bias(key, 'left'), 0)
        self.b['z'] = 8
        key = context(self.a, self.b)
        self.attack('thrust');self.arena.strike(self.a)
        self.assertLess(self.arena.learning.bias(key, 'thrust'), 0)
        self.assertEqual(self.arena.learning.updates, 2)

    def test_fighting_feedback_changes_the_next_forecast_choice(self):
        # The opponent repeatedly counters the initially preferred overhead.
        # This is actual strike/parry feedback, not manually seeded weights.
        before = self.arena.plan_bot(self.a, self.b)
        self.assertEqual(before, 'overhead')
        key = context(self.a, self.b)
        for _ in range(24):
            self.a.update(weapon='longsword', hp=100, stamina=100, dead=0, disarmed=0, cooldown=0)
            self.b.update(hp=100, dead=0, block=False, cooldown=0)
            self.attack('overhead')
            self.b.update(block=True, guard_dir='up', block_since=self.arena.clock)
            self.arena.strike(self.a)
            self.a.update(weapon='longsword', disarmed=0, cooldown=0)
            self.b.update(hp=100, dead=0, block=False)
            self.attack('left');self.arena.strike(self.a)
            self.b.update(hp=100, dead=0, block=False, cooldown=0)
        self.assertLess(self.arena.learning.bias(key, 'overhead'), 0)
        self.assertGreater(self.arena.learning.bias(key, 'left'), 0)
        self.assertNotEqual(self.arena.plan_bot(self.a, self.b), before)

    def test_learning_persists_without_account_data_or_identifiers(self):
        key = context(self.a, self.b)
        self.attack();self.arena.strike(self.a)
        self.arena.learning_close()
        restored = Arena(self.path, seed=5)
        self.assertEqual(restored.learning.values, self.arena.learning.values)
        self.assertEqual(restored.learning.bias(key, 'left'), self.arena.learning.bias(key, 'left'))
        stored = restored.learning.path.read_text()
        for private in ('Learner', 'Target', 'learner', 'password', 'email', 'username'):
            self.assertNotIn(private, stored)
        self.assertEqual(json.loads(self.path.read_text()), {})

    def test_memory_shares_tactics_only_with_matching_combat_context(self):
        self.attack();self.arena.strike(self.a)
        same = context(self.a, self.b)
        self.assertGreater(self.arena.learning.bias(same, 'left'), 0)
        self.a['depth'] = 2
        self.assertEqual(self.arena.learning.bias(context(self.a, self.b), 'left'), 0)
        self.a['depth'] = 3;self.b.update(block=True, guard_dir='up')
        self.assertEqual(self.arena.learning.bias(context(self.a, self.b), 'left'), 0)

    def test_idle_guard_cannot_farm_positive_learning_rewards(self):
        self.arena.learning_decision(self.a, 'block', self.b)
        self.a['block'] = True
        self.arena.clock = 1
        self.arena.learning_tick()
        self.assertEqual(self.arena.learning.bias(context(self.a, self.b), 'block'), 0)

    def test_actual_guard_learns_from_absorbing_an_attack(self):
        self.b['z'] = 1.3
        key = context(self.a, self.b)
        self.arena.learning_decision(self.a, 'block', self.b)
        self.a.update(block=True, guard_dir='centre', block_since=-10)
        self.b['attack'] = 'left';self.arena.strike(self.b)
        self.arena.clock = 1;self.arena.learning_tick()
        self.assertEqual(self.a['hp'], 100)
        self.assertGreater(self.arena.learning.bias(key, 'block'), 0)

    def test_death_teaches_the_cost_of_committing_to_an_attack(self):
        key = context(self.a, self.b)
        self.attack('thrust')
        self.a['hp'] = 1
        self.arena.damage(self.b, self.a, 20, 'body')
        self.assertLess(self.arena.learning.bias(key, 'thrust'), 0)
        self.assertTrue(self.a['attack_learning']['done'])

    def test_entry_grace_and_other_worlds_do_not_supply_attack_rewards(self):
        self.a['spawn_safe'] = 1
        self.attack();self.arena.strike(self.a)
        self.assertEqual(self.arena.learning.updates, 0)
        self.a['spawn_safe'] = 0;self.b['world_id'] = 1
        self.attack();self.arena.strike(self.a)
        self.assertEqual(self.arena.learning.updates, 0)

    def test_projectile_is_credited_to_its_original_shot_after_another_action(self):
        self.a['weapon'] = 'crossbow';self.b['z'] = 4
        key = context(self.a, self.b)
        shot = self.attack('thrust');self.arena.strike(self.a)
        self.assertFalse(shot['done'])
        self.arena.learning_decision(self.a, 'retreat', self.b)
        self.a['attack_learning'] = None
        for _ in range(10):self.arena.tick_objects(.02)
        self.assertTrue(shot['done'])
        self.assertGreater(self.arena.learning.bias(key, 'thrust'), 0)
        self.assertEqual(self.a['decision_learning']['reward'], 0)

    def test_expired_projectile_counts_as_a_miss_once(self):
        self.a['weapon'] = 'bow';self.b['z'] = 10
        key = context(self.a, self.b)
        shot = self.attack('thrust');self.arena.strike(self.a)
        self.arena.tick_objects(5)
        self.assertTrue(shot['done'])
        self.assertLess(self.arena.learning.bias(key, 'thrust'), 0)
        self.arena.tick_objects(5)
        self.assertEqual(self.arena.learning.updates, 1)

    def test_shutdown_does_not_teach_that_an_unfinished_shot_missed(self):
        self.a['weapon'] = 'bow';self.b['z'] = 10
        self.attack('thrust');self.arena.strike(self.a)
        self.arena.learning_close()
        self.assertEqual(self.arena.learning.updates, 0)

    def test_magic_ward_does_not_credit_a_block_that_did_not_stop_damage(self):
        key = context(self.a, self.b)
        self.arena.learning_decision(self.a, 'block', self.b)
        self.a.update(block=True, ward=80)
        self.arena.damage(self.b, self.a, 20, 'body')
        self.arena.clock = 1;self.arena.learning_tick()
        self.assertEqual(self.arena.learning.bias(key, 'block'), 0)

    def test_checkpoint_retries_a_file_lock_and_preserves_unsaved_memory(self):
        self.attack();self.arena.strike(self.a)
        with patch.object(Path, 'replace', side_effect=PermissionError('locked')), patch('bot_learning.time.sleep'):
            self.arena.learning.save(force=True)
        self.assertTrue(self.arena.learning.dirty)
        self.assertEqual(self.arena.learning.save_error, 'PermissionError')
        self.arena.learning.save(force=True)
        self.assertFalse(self.arena.learning.dirty)
        self.assertEqual(BotLearning(self.arena.learning.path).updates, 1)

    def test_corrupt_memory_is_backed_up_before_recovery(self):
        path = self.arena.learning.path
        path.write_text('{broken', encoding='utf-8')
        recovered = BotLearning(path)
        backups = list(path.parent.glob(path.name+'.invalid-*.bak'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), '{broken')
        self.assertEqual(recovered.values, {})

    def test_table_and_correction_are_bounded_and_new_feedback_can_reverse_a_habit(self):
        model = self.arena.learning;model.MAX_CONTEXTS = 3
        key = context(self.a, self.b)
        for _ in range(50):model.observe(key, 'left', 60)
        self.assertLessEqual(model.bias(key, 'left'), 18)
        for _ in range(60):model.observe(key, 'left', -60)
        self.assertLess(model.bias(key, 'left'), 0)
        for i in range(8):model.observe(key+str(i), 'block', 0)
        self.assertEqual(len(model.values), 3)

    def test_reflected_arrow_teaches_the_shooter_about_a_failed_shot(self):
        self.a['weapon'] = 'crossbow';self.b['z'] = 4
        key = context(self.a, self.b)
        shot = self.attack('thrust');self.arena.strike(self.a)
        self.b.update(block=True, block_since=self.arena.clock)
        for _ in range(10):self.arena.tick_objects(.02)
        self.assertTrue(shot['done'])
        self.assertLess(self.arena.learning.bias(key, 'thrust'), 0)
        self.assertEqual(self.arena.learning.updates, 1)

    def test_live_self_play_produces_persistent_training_without_registered_players(self):
        arena = Arena(self.path, seed=4)
        for _ in range(900):arena.tick(1/30)
        arena.learning_close()
        self.assertGreater(arena.learning.updates, 100)
        self.assertGreater(len(arena.learning.values), 10)
        self.assertTrue(any(stat['mean'] > 0 for row in arena.learning.values.values() for stat in row.values()))
        self.assertTrue(any(stat['mean'] < 0 for row in arena.learning.values.values() for stat in row.values()))
        restored = Arena(self.path, seed=7)
        self.assertEqual(restored.learning.values, arena.learning.values)
        self.assertFalse(restored.users)


class EasyCombatTests(CombatFixture):
    def test_held_cut_alternates_and_respects_stamina_and_recovery(self):
        self.a['bot'] = False;self.b['z'] = 20
        self.a.update(input=dict(attack='left', easy_controls=True), last_input=0)
        started = []
        for _ in range(40):
            previous = self.a['attack_id'];self.a['last_input'] = self.arena.clock
            self.arena.tick(1/30)
            if self.a['attack_id'] != previous:started.append((self.arena.clock, self.a['attack']))
        self.assertGreaterEqual(len(started), 2)
        self.assertEqual([a[1] for a in started[:2]], ['left', 'right'])
        self.assertGreaterEqual(started[1][0]-started[0][0], .46)
        self.assertLess(self.a['stamina'], 100)

    def test_manual_mode_requires_a_new_click(self):
        self.a['bot'] = False;self.b['z'] = 20
        self.a.update(input=dict(attack='left'), last_input=0)
        for _ in range(40):
            self.a['last_input'] = self.arena.clock;self.arena.tick(1/30)
        self.assertEqual(self.a['attack_id'], 1)

    def test_releasing_a_held_cut_cancels_its_automatic_followup(self):
        self.a['bot'] = False;self.b['z'] = 20
        self.a.update(input=dict(attack='left', easy_controls=True), last_input=0)
        self.arena.tick(.03)
        while self.a['cooldown']>.19:
            self.a['last_input'] = self.arena.clock;self.arena.tick(.03)
        self.assertTrue(self.a['queued_repeat'])
        self.a.update(input=dict(easy_controls=True), last_input=self.arena.clock)
        self.arena.tick(.25)
        self.assertEqual(self.a['attack_id'], 1)
        self.assertEqual(self.a['queued_attack'], '')

    def test_auto_guard_only_uses_visible_facing_same_world_attacks(self):
        self.b.update(attack='overhead', windup=.26)
        self.assertEqual(self.arena.easy_guard(self.a), 'up')
        self.b.update(windup=0, input=dict(attack='overhead'))
        self.assertEqual(self.arena.easy_guard(self.a), 'centre')
        self.b['windup'] = .26;self.a['yaw'] = math.pi
        self.assertEqual(self.arena.easy_guard(self.a), 'centre')
        self.a['yaw'] = 0;self.b['world_id'] = 1
        self.assertEqual(self.arena.easy_guard(self.a), 'centre')

    def test_holding_auto_guard_does_not_refresh_perfect_parry_time(self):
        self.a['bot'] = False
        self.a.update(input=dict(block=True, easy_controls=True), last_input=0)
        self.b.update(attack='overhead', windup=.26)
        self.arena.tick(.03);pressed = self.a['block_since']
        self.b.update(attack='left', attack_started=1, windup=.18)
        self.a['last_input'] = self.arena.clock;self.arena.tick(.25)
        self.assertEqual(self.a['guard_dir'], 'right')
        self.assertEqual(self.a['block_since'], pressed)
        self.assertEqual(self.a['stamina'], 100)

    def test_block_cancels_held_combo_and_pending_cut(self):
        self.a['bot'] = False
        self.a.update(input=dict(attack='left', easy_controls=True), last_input=0)
        self.arena.tick(.03)
        self.a.update(input=dict(attack='left', block=True, easy_controls=True), last_input=self.arena.clock)
        self.arena.tick(.03)
        self.assertEqual((self.a['attack'], self.a['windup'], self.a['queued_attack']), ('', 0, ''))


if __name__ == '__main__':
    unittest.main()
