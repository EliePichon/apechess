#!/usr/bin/env python3
"""
Node count invariance test: C extension must produce identical node counts
to the Python implementation at all search depths.

This is the definitive correctness gate for the C extension. If node counts
diverge, the C implementation has a bug (likely move ordering or missing moves).

Usage:
    python -m pytest tests/test_node_invariance.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sunfish
from tools import uci

uci.sunfish = sunfish

import _sunfish_core

# Get the original Python gen_moves
if hasattr(sunfish, "_py_gen_moves"):
    py_gen_moves = sunfish._py_gen_moves
else:
    py_gen_moves = sunfish.Position.gen_moves


def _c_gen_moves(self):
    return _sunfish_core.gen_moves(self.board, self.wc, self.bc, self.ep, self.kp)


POSITIONS = [
    ("opening_start", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"),
    ("opening_italian", "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"),
    ("midgame_open", "r1bq1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 7"),
    ("midgame_tense", "r2qkb1r/pp2pppp/2n2n2/3p1b2/3P4/2N2N2/PPP1BPPP/R1BQK2R w KQkq - 4 6"),
    ("endgame_rook", "8/5pk1/6p1/8/3R4/6PP/5PK1/2r5 w - - 0 36"),
    ("endgame_queen", "6k1/5ppp/8/8/8/8/5PPP/3Q2K1 w - - 0 40"),
]

DEPTH = 6


def _search_nodes(fen, gen_moves_fn, depth):
    """Run search to given depth with the specified gen_moves, return node count."""
    sunfish.Position.gen_moves = gen_moves_fn
    parts = fen.split()
    pos = uci.from_fen(*parts)
    hist = [pos]
    searcher = sunfish.Searcher()
    for d, gamma, score, move in searcher.search(hist):
        if d >= depth:
            return searcher.nodes
    return searcher.nodes


def test_node_invariance_opening_start():
    py = _search_nodes(POSITIONS[0][1], py_gen_moves, DEPTH)
    c = _search_nodes(POSITIONS[0][1], _c_gen_moves, DEPTH)
    assert py == c, f"opening_start: Python={py}, C={c}"


def test_node_invariance_opening_italian():
    py = _search_nodes(POSITIONS[1][1], py_gen_moves, DEPTH)
    c = _search_nodes(POSITIONS[1][1], _c_gen_moves, DEPTH)
    assert py == c, f"opening_italian: Python={py}, C={c}"


def test_node_invariance_midgame_open():
    py = _search_nodes(POSITIONS[2][1], py_gen_moves, DEPTH)
    c = _search_nodes(POSITIONS[2][1], _c_gen_moves, DEPTH)
    assert py == c, f"midgame_open: Python={py}, C={c}"


def test_node_invariance_midgame_tense():
    py = _search_nodes(POSITIONS[3][1], py_gen_moves, DEPTH)
    c = _search_nodes(POSITIONS[3][1], _c_gen_moves, DEPTH)
    assert py == c, f"midgame_tense: Python={py}, C={c}"


def test_node_invariance_endgame_rook():
    py = _search_nodes(POSITIONS[4][1], py_gen_moves, DEPTH)
    c = _search_nodes(POSITIONS[4][1], _c_gen_moves, DEPTH)
    assert py == c, f"endgame_rook: Python={py}, C={c}"


def test_node_invariance_endgame_queen():
    py = _search_nodes(POSITIONS[5][1], py_gen_moves, DEPTH)
    c = _search_nodes(POSITIONS[5][1], _c_gen_moves, DEPTH)
    assert py == c, f"endgame_queen: Python={py}, C={c}"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
