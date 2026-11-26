import unittest

from src.replay import replay


class ReplaySmokeTest(unittest.TestCase):
    def test_empty_feed(self):
        self.assertEqual(replay([]), [])

    def test_return_value_uses_a_separate_list(self):
        events = [{"id": "first", "when": 1, "payload": "first"}]
        self.assertIsNot(replay(events), events)
