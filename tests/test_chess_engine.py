"""Tests for chess_engine.py. Run from the repository root:  python3 -m unittest discover -s tests -v"""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chess_engine import (BLACK, FILES, START_FEN, WHITE, Position, best_move, perft,  # noqa: E402
                          square_name)


def sq(name):
    return FILES.index(name[0]) + 8 * (int(name[1]) - 1)


def find(pos, uci):
    """The legal move written like 'e2e4' (or 'e7e8q' for promotions)."""
    fr, to = sq(uci[:2]), sq(uci[2:4])
    return next(m for m in pos.legal_moves() if m[0] == fr and m[1] == to)


def play(pos, *ucis):
    sans = []
    for u in ucis:
        m = find(pos, u)
        sans.append(pos.san(m))
        pos.push(m)
    return sans


class PerftTests(unittest.TestCase):
    """Leaf-node counts published for these positions; any rule bug changes them."""

    CASES = {
        "start position": (START_FEN, [20, 400, 8902]),
        "kiwipete (castling, pins)": (
            "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", [48, 2039, 97862]),
        "en passant and pins": ("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", [14, 191, 2812, 43238]),
        "promotions": (
            "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1", [6, 264, 9467]),
        "promotion with check": ("rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8", [44, 1486, 62379]),
    }

    def test_perft(self):
        for name, (fen, counts) in self.CASES.items():
            pos = Position(fen)
            for depth, expected in enumerate(counts, 1):
                with self.subTest(position=name, depth=depth):
                    self.assertEqual(perft(pos, depth), expected)
            self.assertEqual(pos.to_fen(), Position(fen).to_fen(), "make/undo must restore the position")


class NotationTests(unittest.TestCase):
    def test_opening_and_castling(self):
        pos = Position()
        sans = play(pos, "e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5", "e1g1")
        self.assertEqual(sans, ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "O-O"])

    def test_disambiguation(self):
        pos = Position("4k3/8/8/8/8/8/4K3/R6R w - - 0 1")
        names = {pos.san(m) for m in pos.legal_moves()}
        self.assertTrue({"Rad1", "Rhd1", "Ra8+"} <= names)
        pos = Position("4k3/8/8/8/R7/8/8/R3K3 w - - 0 1")
        names = {pos.san(m) for m in pos.legal_moves()}
        self.assertTrue({"R4a2", "R1a2"} <= names)

    def test_promotion_and_en_passant(self):
        pos = Position("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
        self.assertIn("a8=Q+", {pos.san(m) for m in pos.legal_moves()})
        pos = Position("rnbqkbnr/ppp1pppp/8/8/3pP3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 3")
        self.assertIn("dxe3", {pos.san(m) for m in pos.legal_moves()})

    def test_square_names(self):
        self.assertEqual([square_name(0), square_name(7), square_name(63)], ["a1", "h1", "h8"])


class GameEndTests(unittest.TestCase):
    def test_fools_mate(self):
        pos = Position()
        sans = play(pos, "f2f3", "e7e5", "g2g4", "d8h4")
        self.assertEqual(sans[-1], "Qh4#")
        self.assertEqual(pos.outcome(), ("checkmate", BLACK))

    def test_stalemate(self):
        self.assertEqual(Position("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1").outcome(), ("stalemate", 0))

    def test_insufficient_material(self):
        self.assertEqual(Position("8/8/4k3/8/8/3K4/8/6B1 w - - 0 1").outcome()[0], "insufficient material")

    def test_fifty_move_rule(self):
        self.assertEqual(Position("8/8/4k3/8/8/3K4/8/6R1 w - - 100 80").outcome()[0], "fifty-move rule")

    def test_threefold_repetition_and_undo(self):
        pos = Position("4k3/8/8/8/8/8/8/R3K3 w - - 0 1")
        for move in [(0, 1, 0), (60, 59, 0), (1, 0, 0), (59, 60, 0)] * 2:
            pos.push(move)
        self.assertEqual(pos.outcome()[0], "threefold repetition")
        for _ in range(8):
            pos.pop()
        self.assertIsNone(pos.outcome())

    def test_cannot_castle_through_check(self):
        pos = Position("4k3/8/8/8/8/5r2/8/4K2R w K - 0 1")  # f1 is attacked by the rook on f3
        self.assertNotIn((4, 6, 0), pos.legal_moves())


class AITests(unittest.TestCase):
    def test_finds_mate_in_one(self):
        for level in (2, 3):
            pos = Position("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1")
            self.assertEqual(pos.san(best_move(pos, level)), "Ra8#")

    def test_takes_a_hanging_queen_at_every_level(self):
        for level in (1, 2, 3):
            for seed in range(5):
                pos = Position("4k3/8/8/3q4/8/2N5/8/4K3 w - - 0 1")
                move = best_move(pos, level, random.Random(seed))
                self.assertEqual(pos.san(move).rstrip("+"), "Nxd5")

    def test_search_leaves_the_position_unchanged(self):
        pos = Position("r1bq1rk1/pp2bppp/2n1pn2/2pp4/3P1B2/2PBPN2/PP1N1PPP/R2QK2R w KQ - 0 8")
        before = pos.to_fen()
        for level in (1, 2, 3):
            move = best_move(pos, level)
            self.assertIn(move, pos.legal_moves())
            self.assertEqual((pos.to_fen(), len(pos.stack)), (before, 0))

    def test_plays_a_legal_game_against_random_moves(self):
        rng = random.Random(7)
        pos = Position()
        for _ in range(80):
            legal = pos.legal_moves()
            if pos.outcome(legal):
                break
            move = rng.choice(legal) if pos.turn == BLACK else best_move(pos, 2, rng)
            self.assertIn(move, legal)
            pos.push(move)


if __name__ == "__main__":
    unittest.main()
