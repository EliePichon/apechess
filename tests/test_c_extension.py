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


# --- Phase 2: value() and score_and_sort_moves() tests ---


def compare_value(fen, label=""):
    """Compare C and Python value() for all moves in a FEN position."""
    parts = fen.split()
    pos = uci.from_fen(*parts)
    py_gen = py_gen_moves if callable(py_gen_moves) else sunfish.Position.gen_moves
    moves = list(py_gen(pos))

    py_value = sunfish._py_value if hasattr(sunfish, "_py_value") else sunfish.Position.value

    for move in moves:
        pv = py_value(pos, move)
        cv = _sunfish_core.value(pos.board, pos.ep, pos.kp, move[0], move[1], move[2])
        if pv != cv:
            return False, f"move={move}, Python={pv}, C={cv}"
    return True, f"{len(moves)} moves"


def compare_score_and_sort(fen, label=""):
    """Compare C score_and_sort_moves vs Python sorted(value, gen_moves)."""
    parts = fen.split()
    pos = uci.from_fen(*parts)
    py_gen = py_gen_moves if callable(py_gen_moves) else sunfish.Position.gen_moves
    py_val = sunfish._py_value if hasattr(sunfish, "_py_value") else sunfish.Position.value

    moves = list(py_gen(pos))
    py_scored = sorted(((py_val(pos, m), m) for m in moves), reverse=True)
    c_scored = _sunfish_core.score_and_sort_moves(pos.board, pos.wc, pos.bc, pos.ep, pos.kp)

    if py_scored == c_scored:
        return True, f"{len(moves)} moves"

    detail = f"len: Python={len(py_scored)}, C={len(c_scored)}"
    for i, (p, c) in enumerate(zip(py_scored, c_scored)):
        if p != c:
            detail += f" | First diff at {i}: Python={p}, C={c}"
            break
    return False, detail


def test_value_starting():
    ok, detail = compare_value("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    assert ok, f"value starting: {detail}"


def test_value_midgame():
    ok, detail = compare_value("r1bq1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 7")
    assert ok, f"value midgame: {detail}"


def test_value_castling():
    ok, detail = compare_value("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1")
    assert ok, f"value castling: {detail}"


def test_value_en_passant():
    ok, detail = compare_value("rnbqkbnr/pppp1ppp/8/4pP2/8/8/PPPPP1PP/RNBQKBNR w KQkq e6 0 3")
    assert ok, f"value en passant: {detail}"


def test_value_promotion():
    ok, detail = compare_value("8/P7/8/8/8/8/8/K6k w - - 0 1")
    assert ok, f"value promotion: {detail}"


def test_value_endgame():
    ok, detail = compare_value("8/5pk1/6p1/8/3R4/6PP/5PK1/2r5 w - - 0 36")
    assert ok, f"value endgame: {detail}"


def test_score_and_sort_starting():
    ok, detail = compare_score_and_sort("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    assert ok, f"score_and_sort starting: {detail}"


def test_score_and_sort_midgame():
    ok, detail = compare_score_and_sort("r1bq1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 7")
    assert ok, f"score_and_sort midgame: {detail}"


def test_score_and_sort_castling():
    ok, detail = compare_score_and_sort("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1")
    assert ok, f"score_and_sort castling: {detail}"


def test_score_and_sort_promotion():
    ok, detail = compare_score_and_sort("8/P7/8/8/8/8/8/K6k w - - 0 1")
    assert ok, f"score_and_sort promotion: {detail}"


def test_score_and_sort_captures():
    ok, detail = compare_score_and_sort("r1b1k1nr/ppppqppp/2n5/4p3/1bB1P3/2NP1N2/PPP2PPP/R1BQK2R w KQkq - 0 5")
    assert ok, f"score_and_sort captures: {detail}"


def test_score_and_sort_black_to_move():
    ok, detail = compare_score_and_sort("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1")
    assert ok, f"score_and_sort black to move: {detail}"


# --- Phase 3: move() and rotate() tests ---


def compare_move(fen, label=""):
    """Compare C and Python move() for all moves in a FEN position."""
    parts = fen.split()
    pos = uci.from_fen(*parts)
    py_gen = py_gen_moves if callable(py_gen_moves) else sunfish.Position.gen_moves
    py_move_fn = sunfish._py_move if hasattr(sunfish, "_py_move") else sunfish.Position.move
    moves = list(py_gen(pos))

    for move in moves:
        py_moved = py_move_fn(pos, move)
        c_result = _sunfish_core.move_and_rotate(
            pos.board, pos.score, pos.wc, pos.bc, pos.ep, pos.kp,
            move[0], move[1], move[2])
        c_moved = sunfish.Position(*c_result)
        if py_moved != c_moved:
            detail = f"move={move}"
            for f in ["board", "score", "wc", "bc", "ep", "kp"]:
                pv, cv = getattr(py_moved, f), getattr(c_moved, f)
                if pv != cv:
                    detail += f", {f}: Py={repr(pv)[:40]}, C={repr(cv)[:40]}"
            return False, detail
    return True, f"{len(moves)} moves"


def compare_rotate(fen, nullmove=False, label=""):
    """Compare C and Python rotate() for a position."""
    parts = fen.split()
    pos = uci.from_fen(*parts)
    py_rotate_fn = sunfish._py_rotate if hasattr(sunfish, "_py_rotate") else sunfish.Position.rotate
    py_rot = py_rotate_fn(pos, nullmove=nullmove)
    c_result = _sunfish_core.rotate(
        pos.board, pos.score, pos.wc, pos.bc, pos.ep, pos.kp, nullmove)
    c_rot = sunfish.Position(*c_result)
    if py_rot == c_rot:
        return True, "match"
    detail = ""
    for f in ["board", "score", "wc", "bc", "ep", "kp"]:
        pv, cv = getattr(py_rot, f), getattr(c_rot, f)
        if pv != cv:
            detail += f"{f}: Py={repr(pv)[:40]}, C={repr(cv)[:40]}; "
    return False, detail


def test_move_starting():
    ok, detail = compare_move("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    assert ok, f"move starting: {detail}"


def test_move_castling():
    ok, detail = compare_move("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1")
    assert ok, f"move castling: {detail}"


def test_move_en_passant():
    ok, detail = compare_move("rnbqkbnr/pppp1ppp/8/4pP2/8/8/PPPPP1PP/RNBQKBNR w KQkq e6 0 3")
    assert ok, f"move en passant: {detail}"


def test_move_promotion():
    ok, detail = compare_move("8/P7/8/8/8/8/8/K6k w - - 0 1")
    assert ok, f"move promotion: {detail}"


def test_move_midgame():
    ok, detail = compare_move("r1bq1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 7")
    assert ok, f"move midgame: {detail}"


def test_move_black_to_move():
    ok, detail = compare_move("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1")
    assert ok, f"move black to move: {detail}"


def test_move_rocks():
    ok, detail = compare_move("8/8/8/3O4/2C5/8/8/K6k w - - 0 1")
    assert ok, f"move rocks: {detail}"


def test_rotate_starting():
    ok, detail = compare_rotate("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    assert ok, f"rotate starting: {detail}"


def test_rotate_with_ep():
    ok, detail = compare_rotate("rnbqkbnr/pppp1ppp/8/4pP2/8/8/PPPPP1PP/RNBQKBNR w KQkq e6 0 3")
    assert ok, f"rotate with ep: {detail}"


def test_rotate_nullmove():
    ok, detail = compare_rotate("rnbqkbnr/pppp1ppp/8/4pP2/8/8/PPPPP1PP/RNBQKBNR w KQkq e6 0 3", nullmove=True)
    assert ok, f"rotate nullmove: {detail}"


# --- Ninja Knight tests ---


def test_ninja_knight_basic():
    """Ninja Knight with no rocks moves like a normal knight."""
    ok, detail = compare_gen_moves("8/8/8/8/4J3/8/8/4K3 w - - 0 1")
    assert ok, f"Ninja Knight basic: {detail}"


def test_ninja_knight_single_bounce():
    """Ninja Knight bounces off a single rock."""
    ok, detail = compare_gen_moves("4k3/8/8/8/8/2O5/8/1J2K3 w - - 0 1")
    assert ok, f"Ninja Knight single bounce: {detail}"


def test_ninja_knight_multi_bounce():
    """Ninja Knight bounces through multiple rocks."""
    ok, detail = compare_gen_moves("4k3/8/8/8/3O4/1O6/8/J3K3 w - - 0 1")
    assert ok, f"Ninja Knight multi bounce: {detail}"


def test_ninja_knight_with_pieces():
    """Ninja Knight with various pieces on the board."""
    ok, detail = compare_gen_moves("4k3/8/8/4p3/3O4/2O5/8/1J2K3 w - - 0 1")
    assert ok, f"Ninja Knight with pieces: {detail}"


def test_ninja_knight_cycle_rocks():
    """Rocks in mutual knight-hop range don't cause issues."""
    ok, detail = compare_gen_moves("8/8/8/O7/8/1O6/8/J3K3 w - - 0 1")
    assert ok, f"Ninja Knight cycle rocks: {detail}"


def test_ninja_knight_black():
    """Black Ninja Knight after rotation."""
    ok, detail = compare_gen_moves("4k3/8/8/4j3/8/3O4/8/4K3 b - - 0 1")
    assert ok, f"Black Ninja Knight: {detail}"


def test_ninja_knight_dense_rocks():
    """Ninja Knight with many rocks on the board."""
    ok, detail = compare_gen_moves("4k3/8/2O1O3/1O3O2/4J3/1O3O2/2O1O3/4K3 w - - 0 1")
    assert ok, f"Ninja Knight dense rocks: {detail}"


# --- Parkour activation tests ---


def test_parkour_value_knight_capture():
    """value() includes parkour bonus when N captures."""
    ok, detail = compare_value("rnbqkbnr/pppppppp/8/8/8/2p5/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    assert ok, f"Parkour value knight capture: {detail}"


def test_parkour_value_with_bystanders():
    """value() parkour bonus accounts for multiple N/C pieces on the board."""
    # Two knights + a powered knight, one can capture
    ok, detail = compare_value("4k3/8/8/8/2p5/8/N1N5/4K1C1 w - - 0 1")
    assert ok, f"Parkour value bystanders: {detail}"


def test_parkour_move_knight_capture():
    """move_and_rotate() upgrades all N to J after knight capture."""
    ok, detail = compare_move("rnbqkbnr/pppppppp/8/8/8/2p5/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    assert ok, f"Parkour move knight capture: {detail}"


def test_parkour_move_powered_knight_capture():
    """move_and_rotate() upgrades all N/C to J after powered knight (C) capture."""
    ok, detail = compare_move("4k3/8/8/8/2p5/8/8/4K1CN w - - 0 1")
    assert ok, f"Parkour move powered knight: {detail}"


def test_parkour_move_no_activation_on_non_capture():
    """N moving to empty square does not trigger parkour."""
    ok, detail = compare_move("4k3/8/8/8/8/8/8/1N2K3 w - - 0 1")
    assert ok, f"Parkour no activation non-capture: {detail}"


def test_parkour_score_and_sort_with_capture():
    """score_and_sort includes parkour bonus for knight captures."""
    ok, detail = compare_score_and_sort("4k3/8/8/8/2p5/8/N1N5/4K3 w - - 0 1")
    assert ok, f"Parkour score_and_sort: {detail}"


# --- Laser Bishop (L/G) tests ---


def test_laser_bishop_basic():
    """gen_moves for Laser Bishop on open board."""
    ok, detail = compare_gen_moves("4k3/8/8/8/3L4/8/8/4K3 w - - 0 1")
    assert ok, f"Laser Bishop basic: {detail}"


def test_laser_bishop_through_allies():
    """L slides through friendly pieces."""
    ok, detail = compare_gen_moves("4k3/8/8/8/3L4/8/1P6/4K3 w - - 0 1")
    assert ok, f"Laser through allies: {detail}"


def test_laser_bishop_through_enemies():
    """L slides through enemy pieces, can capture them."""
    ok, detail = compare_gen_moves("4k3/8/5p2/8/3L4/2p5/8/4K3 w - - 0 1")
    assert ok, f"Laser through enemies: {detail}"


def test_laser_bishop_through_rocks():
    """L slides through rocks, cannot stop on them."""
    ok, detail = compare_gen_moves("4k3/8/8/4O3/3L4/2O5/8/4K3 w - - 0 1")
    assert ok, f"Laser through rocks: {detail}"


def test_laser_bishop_dense():
    """L with many pieces on diagonals."""
    ok, detail = compare_gen_moves("4k3/8/5p2/4N3/3L4/2O5/1p6/4K3 w - - 0 1")
    assert ok, f"Laser dense: {detail}"


def test_bloodied_bishop_gen_moves():
    """G moves like a regular bishop (blocked normally)."""
    ok, detail = compare_gen_moves("4k3/8/8/8/3G4/8/8/4K3 w - - 0 1")
    assert ok, f"Bloodied Bishop gen_moves: {detail}"


def test_bloodied_bishop_blocked():
    """G is blocked by allies like a normal bishop."""
    ok, detail = compare_gen_moves("4k3/8/8/8/3G4/4P3/8/4K3 w - - 0 1")
    assert ok, f"Bloodied Bishop blocked: {detail}"


def test_laser_value_phase2():
    """value() includes phase 2 bonus when G captures."""
    ok, detail = compare_value("4k3/8/8/3p4/2G5/8/8/5G1K w - - 0 1")
    assert ok, f"Laser value phase 2: {detail}"


def test_laser_value_phase1():
    """value() for phase 1 (B capture, no score delta for B->G)."""
    ok, detail = compare_value("4k3/8/8/3p4/2B5/8/8/5B1K w - - 0 1")
    assert ok, f"Laser value phase 1: {detail}"


def test_laser_value_with_bystanders():
    """value() phase 2 bonus accounts for multiple G pieces."""
    ok, detail = compare_value("4k3/8/8/3p4/2G5/8/G7/4K1G1 w - - 0 1")
    assert ok, f"Laser value bystanders: {detail}"


def test_laser_move_phase1():
    """move_and_rotate() transforms B/D -> G after first bishop capture."""
    ok, detail = compare_move("4k3/8/8/3p4/2B5/8/8/5B1K w - - 0 1")
    assert ok, f"Laser move phase 1: {detail}"


def test_laser_move_phase2():
    """move_and_rotate() transforms G -> L after second bishop capture."""
    ok, detail = compare_move("4k3/8/8/3p4/2G5/8/8/5G1K w - - 0 1")
    assert ok, f"Laser move phase 2: {detail}"


def test_laser_move_powered_bishop():
    """move_and_rotate() D capture triggers phase 1."""
    ok, detail = compare_move("4k3/8/8/3p4/2D5/8/8/5B1K w - - 0 1")
    assert ok, f"Laser move powered bishop: {detail}"


def test_laser_move_no_activation_non_capture():
    """G moving to empty square does not trigger phase 2."""
    ok, detail = compare_move("4k3/8/8/8/2G5/8/8/5G1K w - - 0 1")
    assert ok, f"Laser no activation non-capture: {detail}"


def test_laser_score_and_sort_phase2():
    """score_and_sort includes laser bonus for G captures."""
    ok, detail = compare_score_and_sort("4k3/8/8/3p4/2G5/8/G7/4K3 w - - 0 1")
    assert ok, f"Laser score_and_sort: {detail}"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
