import unittest
from bot_learning import BotBrain

class TestBotBias(unittest.TestCase):
    def setUp(self):
        self.bot = BotBrain()

    def test_bias_calculation(self):
        # Test the bias calculation logic
        # This is a simplified test, assuming a known context and action
        context_key = 'test_context'
        action = 'test_action'
        reward = 10
        self.bot.observe(context_key, action, reward)
        # Assuming the bias calculation is correct, we can check the resulting stat
        stat = self.bot.values.get(context_key, {}).get(action)
        self.assertIsNotNone(stat)
        self.assertTrue(stat['mean'] > 0)
        self.assertTrue(stat['count'] > 0)
