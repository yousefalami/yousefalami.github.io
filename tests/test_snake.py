"""Tests for the Snake rules and score history in game.py.
Run from the repository root:  python3 -m unittest discover -s tests -v"""
import json
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from game import (BONUS_EVERY, BONUS_LIFETIME, BONUS_POINTS, LOG_LIMIT, NAME_MAX, SnakeGame,  # noqa: E402
                  add_entry, parse_log, rank_of, top_scores)


class SnakeRulesTests(unittest.TestCase):
    def test_start_state(self):
        g = SnakeGame(rng=random.Random(1))
        self.assertEqual(g.snake[0], (10, 10))
        self.assertNotIn(g.food, g.snake)
        self.assertEqual((g.score, g.level, g.tick_ms), (0, 1, 140))

    def test_cannot_reverse_into_the_neck(self):
        g = SnakeGame()
        g.turn("left")
        self.assertFalse(g.queue)
        g.turn("up")
        g.step()
        self.assertEqual((g.snake[0], g.direction), ((10, 9), "up"))

    def test_walls_kill_but_wrap_mode_continues(self):
        g = SnakeGame()
        g.snake = [(19, 5), (18, 5), (17, 5)]
        g.step()
        self.assertFalse(g.alive)
        self.assertEqual(g.event, "die")
        w = SnakeGame(wrap=True, rng=random.Random(3))
        w.snake, w.food = [(19, 5), (18, 5), (17, 5)], (0, 9)
        w.step()
        self.assertTrue(w.alive)
        self.assertEqual(w.snake[0], (0, 5))

    def test_hitting_itself_kills(self):
        g = SnakeGame(rng=random.Random(2))
        g.snake, g.direction, g.food = [(5, 5), (5, 6), (6, 6), (6, 5), (6, 4), (5, 4)], "up", (0, 0)
        g.turn("right")
        g.step()
        self.assertFalse(g.alive)

    def test_may_move_into_the_cell_the_tail_just_left(self):
        g = SnakeGame()
        g.snake, g.direction, g.food = [(5, 5), (5, 6), (4, 6), (4, 5)], "up", (0, 0)
        g.turn("left")
        g.step()
        self.assertTrue(g.alive)

    def test_eating_grows_scores_and_spawns_bonus(self):
        g = SnakeGame(rng=random.Random(4))
        for _ in range(BONUS_EVERY):
            hx, hy = g.snake[0]
            g.food = (hx + 1, hy)
            length = len(g.snake)
            g.step()
            self.assertEqual((g.event, len(g.snake)), ("eat", length + 1))
        self.assertEqual(g.score, BONUS_EVERY)
        self.assertIsNotNone(g.bonus)
        self.assertEqual(g.level, 2)
        hx, hy = g.snake[0]
        g.bonus, before = (hx + 1, hy), g.score
        g.step()
        self.assertEqual((g.event, g.score, g.bonus), ("bonus", before + BONUS_POINTS, None))

    def test_bonus_expires(self):
        g = SnakeGame(rng=random.Random(5))
        g.bonus, g.bonus_left = (0, 0), 2
        g.step()
        g.step()
        self.assertIsNone(g.bonus)
        self.assertGreater(BONUS_LIFETIME, 0)

    def test_filling_the_board_wins(self):
        g = SnakeGame(cols=4, rows=1, rng=random.Random(0))
        self.assertEqual(g.food, (3, 0))
        g.step()
        self.assertTrue(g.won)
        self.assertEqual((g.event, g.alive), ("win", False))

    def test_speed_increases_with_score_but_has_a_floor(self):
        g = SnakeGame()
        g.score = 10
        self.assertEqual(g.tick_ms, 120)
        g.score = 500
        self.assertEqual(g.tick_ms, 60)


class ScoreHistoryTests(unittest.TestCase):
    def test_ranking_and_ties(self):
        log, entries = [], []
        for name, score, mode, ts in [("Ali", 10, "walls", 1), ("Sara", 10, "walls", 2),
                                      ("  ", 7, "walls", 3), ("Bob", 50, "wrap", 4), ("x" * 40, 12, "walls", 5)]:
            log, entry = add_entry(log, name, score, mode, ts)
            entries.append(entry)
        self.assertEqual([e["name"] for e in top_scores(log, "walls")], ["x" * NAME_MAX, "Ali", "Sara", "Player"])
        self.assertEqual(rank_of(log, entries[1]), 3)   # the earlier of two equal scores ranks higher
        self.assertEqual(rank_of(log, entries[3]), 1)   # modes are ranked separately
        self.assertEqual(len(top_scores(log, "walls", 2)), 2)

    def test_log_is_capped(self):
        log = []
        for i in range(LOG_LIMIT + 30):
            log, _ = add_entry(log, "p", 1, "walls", i)
        self.assertEqual((len(log), log[0]["ts"]), (LOG_LIMIT, 30))

    def test_saved_log_round_trip_and_bad_data(self):
        log, _ = add_entry([], "Ali", 5, "wrap", 12.0)
        self.assertEqual(parse_log(json.dumps(log)), log)
        for junk in ("not json", '{"a": 1}', None, ""):
            self.assertEqual(parse_log(junk), [])
        cleaned = parse_log('[{"name": "A", "score": "3", "mode": "zzz", "ts": 1}, {"bad": 1}, 5]')
        self.assertEqual(cleaned, [{"name": "A", "score": 3, "mode": "walls", "ts": 1.0}])


if __name__ == "__main__":
    unittest.main()
