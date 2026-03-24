#!/usr/bin/env python3
"""
Direct unit tests for _search_best_moves() — no HTTP server required.

These tests lock in the function's behavior before decomposing it into helpers
(refactoring plan item #6). Run with: python tests/test_search_best_moves.py
"""

import sys
import os

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sunfish
import tools.uci as uci
from engine import _search_best_moves, build_history

uci.sunfish = sunfish

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
MIDDLEGAME_FEN = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
STALEMATE_FEN = "k7/8/1Q6/8/8/8/8/2K5 b - - 0 1"
BLACK_TO_MOVE_FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"

passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  PASS  {name}")
        passed += 1
    else:
        print(f"  FAIL  {name} — {detail}")
        failed += 1


def make_searcher_and_hist(fen):
    """Create a Searcher and history from FEN."""
    searcher = sunfish.Searcher()
    searcher.precision = 0.0
    hist = build_history(fen)
    return searcher, hist


# ---- Test 1: Fast path (top_n=1) ----

def test_fast_path():
    print("\n--- Test: fast path (top_n=1) ---")
    searcher, hist = make_searcher_and_hist(START_FEN)
    result = _search_best_moves(searcher, hist, 0, 4, 1, [])

    check("returns dict", isinstance(result, dict))
    check("has bestmove", "bestmove" in result)
    check("bestmove is string", isinstance(result["bestmove"], str))
    check("bestmove is 4-5 chars", len(result["bestmove"]) in (4, 5),
          f"got '{result['bestmove']}' ({len(result['bestmove'])} chars)")
    check("has scored_moves", "scored_moves" in result)
    check("scored_moves has 1 entry", len(result["scored_moves"]) == 1,
          f"got {len(result['scored_moves'])}")
    check("scored_moves entry is (str, int)",
          len(result["scored_moves"]) > 0
          and isinstance(result["scored_moves"][0][0], str)
          and isinstance(result["scored_moves"][0][1], int))
    check("has depth_reached", "depth_reached" in result)
    check("depth_reached is int", isinstance(result["depth_reached"], int))
    check("clutchness is None for top_n=1", result.get("clutchness") is None,
          f"got {result.get('clutchness')}")


# ---- Test 2: Standard path (top_n=5) ----

def test_standard_path():
    print("\n--- Test: standard path (top_n=5) ---")
    searcher, hist = make_searcher_and_hist(START_FEN)
    result = _search_best_moves(searcher, hist, 0, 4, 5, [])

    check("returns dict", isinstance(result, dict))
    check("scored_moves has 5 entries", len(result["scored_moves"]) == 5,
          f"got {len(result['scored_moves'])}")

    # Check all entries are (str, int)
    all_valid = all(
        isinstance(m, str) and isinstance(s, (int, float))
        for m, s in result["scored_moves"]
    )
    check("all scored_moves are (str, number)", all_valid)

    # Check scores are descending
    scores = [s for _, s in result["scored_moves"]]
    check("scores are descending", scores == sorted(scores, reverse=True),
          f"got {scores}")

    check("clutchness is int", isinstance(result.get("clutchness"), int),
          f"got {type(result.get('clutchness'))}")


# ---- Test 3: Ignore squares ----

def test_ignore_squares():
    print("\n--- Test: ignore squares ---")
    searcher, hist = make_searcher_and_hist(START_FEN)
    result = _search_best_moves(searcher, hist, 0, 4, 5, ["g1", "b1"])

    check("returns dict", isinstance(result, dict))
    check("has scored_moves", len(result["scored_moves"]) > 0)

    # No move should start from g1 or b1
    for move_str, _ in result["scored_moves"]:
        from_sq = move_str[:2]
        check(f"move {move_str} not from ignored square",
              from_sq not in ("g1", "b1"),
              f"from {from_sq}")

    # bestmove should also not start from ignored squares
    best = result["bestmove"]
    check(f"bestmove {best} not from ignored square",
          best[:2] not in ("g1", "b1"),
          f"from {best[:2]}")


# ---- Test 4: No legal moves (stalemate) ----

def test_no_legal_moves():
    print("\n--- Test: no legal moves (stalemate) ---")
    searcher, hist = make_searcher_and_hist(STALEMATE_FEN)
    result = _search_best_moves(searcher, hist, 0, 4, 1, [])

    check("bestmove is (none)", result["bestmove"] == "(none)",
          f"got '{result['bestmove']}'")
    check("scored_moves is empty", result["scored_moves"] == [],
          f"got {result['scored_moves']}")


# ---- Test 5: Clutchness with top_n >= 2 ----

def test_clutchness():
    print("\n--- Test: clutchness computation ---")
    searcher, hist = make_searcher_and_hist(MIDDLEGAME_FEN)
    result = _search_best_moves(searcher, hist, 0, 5, 3, [])

    check("clutchness is not None for top_n=3",
          result.get("clutchness") is not None,
          f"got {result.get('clutchness')}")
    check("clutchness is int",
          isinstance(result.get("clutchness"), int),
          f"got type {type(result.get('clutchness'))}")
    check("clutchness >= 0", result.get("clutchness", -1) >= 0,
          f"got {result.get('clutchness')}")

    # Verify clutchness equals gap between top 2 scores
    if len(result["scored_moves"]) >= 2:
        gap = result["scored_moves"][0][1] - result["scored_moves"][1][1]
        check("clutchness matches score gap", result["clutchness"] == gap,
              f"clutchness={result['clutchness']}, gap={gap}")


# ---- Test 6: Black to move (POV flip) ----

def test_black_to_move():
    print("\n--- Test: black to move ---")
    searcher, hist = make_searcher_and_hist(BLACK_TO_MOVE_FEN)
    result = _search_best_moves(searcher, hist, 0, 4, 3, [])

    check("returns dict", isinstance(result, dict))
    check("bestmove is string", isinstance(result["bestmove"], str))
    check("bestmove is 4-5 chars", len(result["bestmove"]) in (4, 5),
          f"got '{result['bestmove']}' ({len(result['bestmove'])} chars)")

    # Black moves should be from ranks 7-8 area (pieces start there)
    best = result["bestmove"]
    from_sq = best[:2]
    from_rank = from_sq[1]
    check(f"black move {best} from rank 5-8",
          from_rank in "5678",
          f"from rank {from_rank}")

    check("scored_moves has entries", len(result["scored_moves"]) > 0)


# ---- Test 7: Return dict contract ----

def test_return_contract():
    print("\n--- Test: return dict contract ---")
    searcher, hist = make_searcher_and_hist(START_FEN)
    result = _search_best_moves(searcher, hist, 0, 4, 2, [])

    expected_keys = {"bestmove", "scored_moves", "depth_reached", "clutchness"}
    check("exact keys match", set(result.keys()) == expected_keys,
          f"got {set(result.keys())}")


def main():
    test_fast_path()
    test_standard_path()
    test_ignore_squares()
    test_no_legal_moves()
    test_clutchness()
    test_black_to_move()
    test_return_contract()

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'='*50}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
