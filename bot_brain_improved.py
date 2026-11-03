import math
from rules import ITEMS, RANGED, TARGET_HEIGHTS, MOVES, grip_risk_multiplier
from bot_learning import context, ATTACKS

class BotBrain:
    # Example of refactoring a method
    def target_for(self, f, enemies):
        def score(a):
            distance = math.hypot(a['x'] - f['x'], a['z'] - f['z'])
            finish_weight = 5 if f['hp'] < f['max_hp'] * 0.45 else 2
            return distance + finish_weight * a['hp'] / a['max_hp'] + (25 if a['spawn_safe'] > 0 else 0) - (0.7 if a['id'] == f.get('target_id') else 0)
        return min(enemies, key=score)

    # Additional methods would be refactored here
