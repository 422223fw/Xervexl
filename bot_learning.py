"""Online contextual action values learned from authoritative combat outcomes.

The tactical forecast remains the prior. This small, bounded model supplies a
confidence-weighted correction; it never changes reflex limits or fighter stats.
No names, account identifiers, inputs or passwords are stored here.
"""
import json
import math
import shutil
import time
from pathlib import Path
from rules import ITEMS, RANGED

ACTIONS = ('advance', 'retreat', 'strafe_l', 'strafe_r', 'block', 'left',
           'right', 'overhead', 'thrust', 'disarm', 'dodge')
ATTACKS = ('left', 'right', 'overhead', 'thrust', 'disarm')


def context(bot, opponent):
    own, enemy = ITEMS[bot['weapon']], ITEMS[opponent['weapon']]
    distance = math.hypot(opponent['x']-bot['x'], opponent['z']-bot['z'])
    reach = min(12., own['reach']*.55) if own['family'] in RANGED else own['reach']
    band = 'close' if distance < reach*.75 else 'reach' if distance < reach+.4 else 'far'
    guard = opponent['guard_dir'] if opponent['block'] else 'open'
    threat = 'windup' if opponent['windup'] > 0 else 'recover' if opponent['cooldown'] > .15 else 'ready'
    return '|'.join((str(bot['depth']), own['family'], enemy['family'], band, guard, threat,
                     'hurt' if bot['hp'] < bot['max_hp']*.4 else 'healthy',
                     'tired' if bot['stamina'] < 30 else 'fresh'))


class BotLearning:
    VERSION = 1
    MAX_CONTEXTS = 4096

    def __init__(self, path):
        self.path = Path(path)
        self.values = {}
        self.updates = 0
        self.dirty = False
        self.last_save = 0.
        self.save_error = ''
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text('utf-8'))
            if data.get('version') != self.VERSION:
                raise ValueError('Unsupported bot learning version')
            updates = data['updates']
            if type(updates) is not int or updates < 0:
                raise ValueError('Invalid update count')
            rows = data['values']
            if not isinstance(rows, dict) or len(rows) > self.MAX_CONTEXTS:
                raise ValueError('Invalid learning table')
            for key, row in rows.items():
                if not isinstance(key, str) or len(key) > 120 or len(key.split('|')) != 8 or not isinstance(row, dict):
                    raise ValueError('Invalid combat context')
                for action, stat in row.items():
                    if action not in ACTIONS or set(stat) != {'count', 'mean', 'seen'}:
                        raise ValueError('Invalid action statistic')
                    if type(stat['count']) is not int or not 1 <= stat['count'] <= 1_000_000_000:
                        raise ValueError('Invalid sample count')
                    if type(stat['seen']) is not int or not 0 <= stat['seen'] <= updates:
                        raise ValueError('Invalid sample age')
                    if not isinstance(stat['mean'], (int, float)) or not math.isfinite(stat['mean']) or abs(stat['mean']) > 60:
                        raise ValueError('Invalid learned value')
            self.values, self.updates = rows, updates
        except (ValueError, KeyError, TypeError, AttributeError):
            # Keep the original file for recovery instead of silently destroying it.
            backup = self.path.with_name(self.path.name+f'.invalid-{time.time_ns()}.bak')
            shutil.copy2(self.path, backup)
            self.dirty = True
            print('Bot learning data was invalid; a private recovery backup was saved.', flush=True)

    def bias(self, key, action):
        stat = self.values.get(key, {}).get(action)
        if not stat:
            return 0.
        return max(-18., min(18., stat['mean'])) * stat['count']/(stat['count']+6)

    def observe(self, key, action, reward):
        if action not in ACTIONS or not math.isfinite(reward):
            return
        if key not in self.values and len(self.values) >= self.MAX_CONTEXTS:
            oldest = min(self.values, key=lambda k: max(s['seen'] for s in self.values[k].values()))
            del self.values[oldest]
        row = self.values.setdefault(key, {})
        stat = row.setdefault(action, dict(count=0, mean=0., seen=0))
        stat['count'] = min(1_000_000_000, stat['count']+1)
        alpha = max(.04, 1/min(25, stat['count']))
        stat['mean'] += alpha*(max(-60., min(60., reward))-stat['mean'])
        self.updates += 1
        stat['seen'] = self.updates
        self.dirty = True

    def finish(self, ticket, miss=False):
        if not ticket or ticket['done']:
            return
        ticket['done'] = True
        if miss and not ticket['contact']:
            ticket['reward'] -= 4
        self.observe(ticket['key'], ticket['action'], ticket['reward'])

    def save(self, now=0., force=False):
        if not self.dirty or not force and now-self.last_save < 5.:
            return
        temporary = self.path.with_suffix('.tmp')
        try:
            temporary.write_text(json.dumps(dict(version=self.VERSION, updates=self.updates,
                                                 values=self.values), separators=(',', ':')), 'utf-8')
            for attempt in range(6):
                try:
                    temporary.replace(self.path)
                    break
                except PermissionError:
                    if attempt == 5:
                        raise
                    time.sleep(.02*(attempt+1))
        except OSError as error:
            # A failed checkpoint must not crash the combat loop or erase memory.
            self.save_error = type(error).__name__
            return
        self.save_error = ''
        self.last_save = now
        self.dirty = False


class LearningCombat:
    def learning_context(self, f):
        enemies = [a for a in self.fighters.values() if a is not f and a['dead'] <= 0
                   and a['spawn_safe'] <= 0 and self.can_fight(f, a)]
        return context(f, self.target_for(f, enemies)) if enemies else None

    def learning_decision(self, f, action, opponent):
        previous = f.get('decision_learning')
        key = context(f, opponent)
        if previous and (previous['action'] != action or previous['key'] != key or self.clock-previous['started'] >= .8):
            self.learning.finish(previous)
            f['decision_learning'] = None
        if action not in ACTIONS or action in ATTACKS or f['spawn_safe'] > 0 or f['fall'] > 0 or opponent['spawn_safe'] > 0:
            return
        if not f.get('decision_learning'):
            f['decision_learning'] = dict(key=key, action=action, reward=0., started=self.clock, done=False, contact=False)

    def learning_attack(self, f):
        if not f['bot'] or f['spawn_safe'] > 0:
            return
        key = self.learning_context(f)
        if not key or f['attack'] not in ATTACKS:
            return
        self.learning.finish(f.get('decision_learning'))
        f['decision_learning'] = None
        f['attack_learning'] = dict(key=key, action=f['attack'], reward=0., started=self.clock,
                                    done=False, contact=False, projectile=False)

    @staticmethod
    def learning_reward(ticket, reward, contact=False):
        if ticket and not ticket['done']:
            ticket['reward'] += reward
            ticket['contact'] = ticket['contact'] or contact

    def learning_damage(self, attacker, victim, amount, ticket=None, blocked=False):
        if attacker['bot']:
            self.learning_reward(ticket, amount*.5, amount > 0)
        if victim['bot']:
            self.learning_reward(victim.get('decision_learning'), -amount*.6)
            # Damage taken during an attack teaches the cost of committing to it.
            self.learning_reward(victim.get('attack_learning'), -amount*.3)
        if victim['hp'] <= 0:
            self.learning_reward(ticket, 25, True)
            self.learning_reward(victim.get('decision_learning'), -25)
            self.learning_reward(victim.get('attack_learning'), -20)
            self.learning.finish(victim.get('decision_learning'))
            victim['decision_learning'] = None
            pending = victim.get('attack_learning')
            if pending and not pending['projectile']:
                self.learning.finish(pending, miss=True)
        elif blocked:
            self.learning_reward(victim.get('decision_learning'), 5, True)
            self.learning_reward(ticket, -2, True)

    def learning_event(self, kind, fields):
        if kind not in ('parry', 'disarm', 'deflect'):
            return
        source, target = self.fighters.get(fields.get('source')), self.fighters.get(fields.get('target'))
        if not source or not target or not self.same_world(source, target) or source['spawn_safe'] > 0 or target['spawn_safe'] > 0:
            return
        winner, loser = (target, source) if kind == 'parry' else (source, target)
        ticket = winner.get('attack_learning') if kind == 'disarm' and winner['attack'] == 'disarm' else winner.get('decision_learning')
        self.learning_reward(ticket, 10 if kind == 'parry' else 8 if kind == 'deflect' else 12, True)
        self.learning_reward(loser.get('decision_learning'), -12)
        if kind != 'deflect':
            self.learning_reward(loser.get('attack_learning'), -12, True)

    def learning_tick(self):
        for f in self.fighters.values():
            decision = f.get('decision_learning')
            if decision and (f['dead'] > 0 or self.clock-decision['started'] >= .8):
                self.learning.finish(decision)
                f['decision_learning'] = None
        self.learning.save(self.clock)

    def learning_close(self):
        for f in self.fighters.values():
            self.learning.finish(f.get('decision_learning'))
        for p in self.projectiles:
            ticket = p.get('_learning')
            # Stopping the server is not evidence that a flying shot missed.
            if ticket and (ticket['contact'] or ticket['reward']):
                self.learning.finish(ticket)
        self.learning.save(self.clock, force=True)
