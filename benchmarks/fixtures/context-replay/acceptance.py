"""Independent checks. This file is outside the agent's project."""

import copy
import sys
import unittest

sys.path.insert(0, "/fixture")

from src.checkpoint import checkpoint
from src.replay import replay


class ReplayAcceptance(unittest.TestCase):
    def test_stable_order(self):
        events = [{"id": "a", "when": 5}, {"id": "b", "when": 3}, {"id": "c", "when": 5}]
        self.assertEqual([event["id"] for event in replay(events)], ["b", "a", "c"])

    def test_keep_first_seen_and_preserve_input(self):
        events = [
            {"id": "a", "when": 4, "payload": "original"},
            {"id": "a", "when": 1, "payload": "duplicate"},
            {"id": "b", "when": 2, "payload": "other"},
        ]
        original = copy.deepcopy(events)
        self.assertEqual(replay(events), [events[2], events[0]])
        self.assertEqual(events, original)

    def test_checkpoint_format(self):
        self.assertEqual(checkpoint([{"id": "c"}, {"id": "a"}]), {"CHECKPOINT_FIELD_839": ["c", "a"]})
        self.assertEqual(checkpoint([]), {"CHECKPOINT_FIELD_839": []})


if __name__ == "__main__":
    unittest.main()
