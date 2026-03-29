#!/usr/bin/env python3
"""
Direct correctness tests for the C extension gen_moves implementation.

Compares C gen_moves output against Python gen_moves for various positions,
ensuring identical move lists in identical order.

Usage:
    python -m pytest tests/test_c_extension.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sunfish
from tools import uci

uci.sunfish = sunfish

# Import C extension directly
import _sunfish_core

# Get the original Python gen_moves (before monkey-patching)
if hasattr(sunfish, "_py_gen_moves"):
    py_gen_moves = sunfish._py_gen_moves
else:
    py_gen_moves = sunfish.Position.gen_moves


def compare_gen_moves(fen, label=""):
    """Compare C and Python gen_moves for a FEN position. Returns (pass, detail)."""
    parts = fen.split()
    pos = uci.from_fen(*parts)

    py_moves = list(py_gen_moves(pos))
    c_moves = _sunfish_core.gen_moves(pos.board, pos.wc, pos.bc, pos.ep, pos.kp)

    if py_moves == c_moves:
        return True, f"{len(py_moves)} moves"

    detail = f"Python={len(py_moves)}, C={len(c_moves)}"
    for i, (pm, cm) in enumerate(zip(py_moves, c_moves)):
        if pm != cm:
            detail += f" | First diff at index {i}: Python={pm}, C={cm}"
            break

    py_set, c_set = set(py_moves), set(c_moves)
    if py_set - c_set:
        detail += f" | In Python only: {list(py_set - c_set)[:3]}"
    if c_set - py_set:
        detail += f" | In C only: {list(c_set - py_set)[:3]}"

    return False, detail


# --- Test cases ---


def test_starting_position():
    ok, detail = compare_gen_moves("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    assert ok, f"Starting position: {detail}"


def test_starting_position_black():
    ok, detail = compare_gen_moves("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1")
    assert ok, f"Starting position black to move: {detail}"


def test_midgame_open():
    ok, detail = compare_gen_moves("r1bq1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 7")
    assert ok, f"Midgame open: {detail}"


def test_midgame_tense():
    ok, detail = compare_gen_moves("r2qkb1r/pp2pppp/2n2n2/3p1b2/3P4/2N2N2/PPP1BPPP/R1BQK2R w KQkq - 4 6")
    assert ok, f"Midgame tense: {detail}"


def test_endgame_rook():
    ok, detail = compare_gen_moves("8/5pk1/6p1/8/3R4/6PP/5PK1/2r5 w - - 0 36")
    assert ok, f"Endgame rook: {detail}"


def test_endgame_queen():
    ok, detail = compare_gen_moves("6k1/5ppp/8/8/8/8/5PPP/3Q2K1 w - - 0 40")
    assert ok, f"Endgame queen: {detail}"


def test_castling_both_sides():
    ok, detail = compare_gen_moves("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1")
    assert ok, f"Castling both sides: {detail}"


def test_castling_kingside_only():
    ok, detail = compare_gen_moves("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w Kk - 0 1")
    assert ok, f"Castling kingside only: {detail}"


def test_castling_queenside_only():
    ok, detail = compare_gen_moves("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w Qq - 0 1")
    assert ok, f"Castling queenside only: {detail}"


def test_en_passant():
    ok, detail = compare_gen_moves("rnbqkbnr/pppp1ppp/8/4pP2/8/8/PPPPP1PP/RNBQKBNR w KQkq e6 0 3")
    assert ok, f"En passant: {detail}"


def test_promotion():
    ok, detail = compare_gen_moves("8/P7/8/8/8/8/8/K6k w - - 0 1")
    assert ok, f"Promotion: {detail}"


def test_promotion_with_capture():
    ok, detail = compare_gen_moves("1n6/P7/8/8/8/8/8/K6k w - - 0 1")
    assert ok, f"Promotion with capture: {detail}"


def test_rock_blocks_sliding():
    ok, detail = compare_gen_moves("rnbqkbnr/pppppppp/8/3O4/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    assert ok, f"Rock blocks sliding: {detail}"


def test_rock_blocks_pawn():
    ok, detail = compare_gen_moves("8/8/8/8/8/3O4/3P4/K6k w - - 0 1")
    assert ok, f"Rock blocks pawn: {detail}"


def test_knight_jumps_over_rock():
    ok, detail = compare_gen_moves("8/8/8/3O4/2N5/8/8/K6k w - - 0 1")
    assert ok, f"Knight jumps rock: {detail}"


def test_powered_knight_on_rock():
    ok, detail = compare_gen_moves("8/8/8/3O4/2C5/8/8/K6k w - - 0 1")
    assert ok, f"Powered knight on rock: {detail}"


def test_powered_pawn_on_rock():
    ok, detail = compare_gen_moves("8/8/8/3O4/3A4/8/8/K6k w - - 0 1")
    assert ok, f"Powered pawn on rock: {detail}"


def test_powered_rook_stops_on_rock():
    ok, detail = compare_gen_moves("8/8/8/3O4/8/8/8/T6K w - - 0 1")
    assert ok, f"Powered rook stops on rock: {detail}"


def test_powered_bishop_on_rock():
    ok, detail = compare_gen_moves("8/8/8/8/8/8/1D6/K6k w - - 0 1")
    assert ok, f"Powered bishop: {detail}"


def test_powered_queen_on_rock():
    ok, detail = compare_gen_moves("8/8/8/3O4/8/8/3X4/K6k w - - 0 1")
    assert ok, f"Powered queen on rock: {detail}"


def test_powered_king():
    ok, detail = compare_gen_moves("8/8/8/8/8/8/8/3Y3k w - - 0 1")
    assert ok, f"Powered king: {detail}"


def test_powered_pawn_promotion():
    ok, detail = compare_gen_moves("8/A7/8/8/8/8/8/K6k w - - 0 1")
    assert ok, f"Powered pawn promotion: {detail}"


def test_complex_position():
    """A complex position with many pieces and tactical possibilities."""
    ok, detail = compare_gen_moves(
        "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
    )
    assert ok, f"Complex position: {detail}"


def test_many_captures():
    ok, detail = compare_gen_moves("r1b1k1nr/ppppqppp/2n5/4p3/1bB1P3/2NP1N2/PPP2PPP/R1BQK2R w KQkq - 0 5")
    assert ok, f"Many captures: {detail}"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
