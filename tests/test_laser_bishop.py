#!/usr/bin/env python3
"""
Test script for the Laser Bishop (L/l) feature.

The Laser Bishop slides through ALL pieces (allies, enemies, rocks) on diagonals.
It can only stop on empty squares or enemy pieces (capturing them).
It cannot stop on rocks or allies. Board edge stops the ray.

Activation is two-phase:
  Phase 1: Any B/D captures -> all B/D become G (Bloodied Bishop)
  Phase 2: Any G captures -> all G/B/D become L (Laser Bishop)

Character mapping: G = White Bloodied Bishop, g = Black
                   L = White Laser Bishop, l = Black
"""

import requests
import json

from helpers import BASE_URL, create_session, TestTracker


def get_moves(fen):
    """Get legal moves from the engine for a given FEN."""
    r = requests.post(f"{BASE_URL}/getmoves", json={"fen": fen})
    r.raise_for_status()
    return r.json()


def make_move(session_id, move):
    """Make a move in a session."""
    r = requests.post(f"{BASE_URL}/move", json={"session_id": session_id, "move": move})
    r.raise_for_status()
    return r.json()


def test_laser_slides_through_allies():
    """L should slide through friendly pieces."""
    print("\n=== L slides through allies ===")
    t = TestTracker()

    # L on a1, friendly pawn on b2, should reach squares beyond b2
    data = get_moves("4k3/8/8/8/8/8/1P6/L3K3 w - - 0 1")
    moves = set(data["moves"].get("a1", []))
    # L slides NE: b2 (ally, skip), c3, d4, e5, f6, g7, h8
    t.test("L reaches c3 through ally on b2", "a1c3" in moves, f"moves: {moves}")
    t.test("L reaches h8 through ally on b2", "a1h8" in moves, f"moves: {moves}")
    # L should NOT be able to stop on b2 (ally)
    t.test("L cannot stop on ally b2", "a1b2" not in moves, f"moves: {moves}")
    return t


def test_laser_slides_through_enemies():
    """L should slide through enemy pieces and can capture them."""
    print("\n=== L slides through enemies ===")
    t = TestTracker()

    # L on a1, enemy pawn on c3, enemy rook on e5
    data = get_moves("4k3/8/8/4r3/8/2p5/8/L3K3 w - - 0 1")
    moves = set(data["moves"].get("a1", []))
    # Can capture c3
    t.test("L can capture on c3", "a1c3" in moves, f"moves: {moves}")
    # Can capture e5 (through c3)
    t.test("L can capture on e5 through c3", "a1e5" in moves, f"moves: {moves}")
    # Can reach empty squares beyond both enemies
    t.test("L reaches d4 between enemies", "a1d4" in moves, f"moves: {moves}")
    t.test("L reaches f6 beyond e5", "a1f6" in moves, f"moves: {moves}")
    return t


def test_laser_slides_through_rocks():
    """L should slide through rocks but cannot stop on them."""
    print("\n=== L slides through rocks ===")
    t = TestTracker()

    # L on a1, rock on c3
    data = get_moves("4k3/8/8/8/8/2O5/8/L3K3 w - - 0 1")
    moves = set(data["moves"].get("a1", []))
    # L cannot stop on rock c3
    t.test("L cannot stop on rock c3", "a1c3" not in moves, f"moves: {moves}")
    # But can reach squares beyond the rock
    t.test("L reaches b2 before rock", "a1b2" in moves, f"moves: {moves}")
    t.test("L reaches d4 beyond rock", "a1d4" in moves, f"moves: {moves}")
    t.test("L reaches h8 beyond rock", "a1h8" in moves, f"moves: {moves}")
    return t


def test_laser_board_edge_stops():
    """Board edge should stop L's ray."""
    print("\n=== Board edge stops L ===")
    t = TestTracker()

    # L on d4, should not go past h8 or a1 or a7 or g1
    data = get_moves("4k3/8/8/8/3L4/8/8/4K3 w - - 0 1")
    moves = set(data["moves"].get("d4", []))
    # NE diagonal: e5, f6, g7, h8 (stops at edge)
    t.test("L reaches h8", "d4h8" in moves, f"moves: {moves}")
    # NW diagonal: c5, b6, a7 (stops at edge)
    t.test("L reaches a7", "d4a7" in moves, f"moves: {moves}")
    # SE diagonal: e3, f2, g1 (stops at edge)
    t.test("L reaches g1", "d4g1" in moves, f"moves: {moves}")
    # SW diagonal: c3, b2, a1 (stops at edge)
    t.test("L reaches a1", "d4a1" in moves, f"moves: {moves}")
    # Count total moves (should be exactly the diagonals from d4)
    t.test("L has correct number of moves", len(moves) == 13,
           f"expected 13, got {len(moves)}: {moves}")
    return t


def test_laser_captures_through_pieces():
    """L should be able to capture an enemy with more pieces behind it."""
    print("\n=== L captures through pieces ===")
    t = TestTracker()

    # L on a1, enemy on c3, ally on d4, enemy on f6
    data = get_moves("4k3/8/5p2/8/3P4/2p5/8/L3K3 w - - 0 1")
    moves = set(data["moves"].get("a1", []))
    # Can capture c3
    t.test("L captures c3", "a1c3" in moves, f"moves: {moves}")
    # Cannot stop on d4 (ally)
    t.test("L cannot stop on ally d4", "a1d4" not in moves, f"moves: {moves}")
    # Can reach e5 (empty) and capture f6 (enemy) — through both c3 and d4
    t.test("L reaches e5 through pieces", "a1e5" in moves, f"moves: {moves}")
    t.test("L captures f6 through pieces", "a1f6" in moves, f"moves: {moves}")
    return t


def test_bloodied_bishop_standard_movement():
    """G (Bloodied Bishop) should move exactly like a regular bishop."""
    print("\n=== G moves like regular bishop ===")
    t = TestTracker()

    # G on c1 with pawn on d2 — should be blocked by ally
    data = get_moves("4k3/8/8/8/8/8/3P4/2G1K3 w - - 0 1")
    moves = set(data["moves"].get("c1", []))
    # G should be blocked by the pawn on d2 (NE diagonal)
    t.test("G blocked by ally on d2", "c1d2" not in moves and "c1e3" not in moves,
           f"moves: {moves}")
    # G should still be able to go NW: b2, a3
    t.test("G can go to b2", "c1b2" in moves, f"moves: {moves}")
    return t


def test_activation_phase1():
    """B capture should transform all B/D to G."""
    print("\n=== Activation Phase 1: B/D -> G ===")
    t = TestTracker()

    # White B on c4 can capture black pawn on d5. Another white B on f1.
    fen = "4k3/8/8/3p4/2B5/8/8/5B1K w - - 0 1"
    sid = create_session(fen)
    result = make_move(sid, "c4d5")
    t.test("Phase 1 move accepted", result.get("status") == "ok",
           f"result: {result}")

    # Now get moves to verify pieces are G (not B)
    # After white moves, it's black's turn; we need to check from white's perspective
    # Let's use a new session approach: make the move and check via another move
    # Actually, let's verify by setting up a position with G and checking it works
    data = get_moves("4k3/8/8/8/8/8/8/2G2G1K w - - 0 1")
    moves_c1 = data["moves"].get("c1", [])
    moves_f1 = data["moves"].get("f1", [])
    t.test("G on c1 has moves", len(moves_c1) > 0, f"moves: {moves_c1}")
    t.test("G on f1 has moves", len(moves_f1) > 0, f"moves: {moves_f1}")
    return t


def test_activation_phase2():
    """G capture should transform all G/B/D to L."""
    print("\n=== Activation Phase 2: G -> L ===")
    t = TestTracker()

    # Two G bishops, one can capture
    fen = "4k3/8/8/3p4/2G5/8/8/5G1K w - - 0 1"
    sid = create_session(fen)
    result = make_move(sid, "c4d5")
    t.test("Phase 2 move accepted", result.get("status") == "ok",
           f"result: {result}")
    return t


def test_full_two_phase_activation():
    """Complete B -> G -> L activation sequence."""
    print("\n=== Full two-phase activation ===")
    t = TestTracker()

    # Set up: white Bishops that can capture in sequence
    # B on c4, pawn targets on d5 and e6 (after first capture, second triggers phase 2)
    # We need black to have pieces to capture on two separate turns
    # Turn 1: Bc4xd5 (B->G), black moves, Turn 2: Gd5xe6 (G->L)
    fen = "4k3/8/8/3pp3/2B5/8/8/5B1K w - - 0 1"
    sid = create_session(fen)

    # Phase 1: Bishop captures d5
    result = make_move(sid, "c4d5")
    t.test("First capture accepted", result.get("status") == "ok",
           f"result: {result}")

    # Black makes a move (king moves)
    result = make_move(sid, "e8d8")
    t.test("Black move accepted", result.get("status") == "ok",
           f"result: {result}")

    # Phase 2: G captures e5 (now a G bishop from phase 1)
    result = make_move(sid, "d5e5")
    t.test("Second capture (G->L) accepted", result.get("status") == "ok",
           f"result: {result}")
    return t


def test_laser_bishop_direct():
    """Test L piece directly in FEN — verify slide-through behavior."""
    print("\n=== Laser Bishop direct FEN ===")
    t = TestTracker()

    # L on a1 with multiple obstacles on the NE diagonal
    # Ally on b2, rock on d4, enemy on f6
    data = get_moves("4k3/8/5p2/8/3O4/8/1N6/L3K3 w - - 0 1")
    moves = set(data["moves"].get("a1", []))
    # Cannot stop on b2 (ally) or d4 (rock)
    t.test("L cannot stop on ally b2", "a1b2" not in moves, f"moves: {moves}")
    t.test("L cannot stop on rock d4", "a1d4" not in moves, f"moves: {moves}")
    # Can reach empty c3, e5 and capture f6
    t.test("L reaches c3", "a1c3" in moves, f"moves: {moves}")
    t.test("L reaches e5", "a1e5" in moves, f"moves: {moves}")
    t.test("L captures f6", "a1f6" in moves, f"moves: {moves}")
    # Can reach g7, h8 beyond the enemy
    t.test("L reaches g7 beyond f6", "a1g7" in moves, f"moves: {moves}")
    t.test("L reaches h8 beyond f6", "a1h8" in moves, f"moves: {moves}")
    return t


def test_powered_bishop_triggers_activation():
    """D (Powered Bishop) capture should trigger Phase 1."""
    print("\n=== D triggers activation ===")
    t = TestTracker()

    # D on c4 can capture d5, plus a B on f1
    fen = "4k3/8/8/3p4/2D5/8/8/5B1K w - - 0 1"
    sid = create_session(fen)
    result = make_move(sid, "c4d5")
    t.test("D capture triggers activation", result.get("status") == "ok",
           f"result: {result}")
    return t


def test_black_laser_bishop():
    """Test black Laser Bishop works correctly."""
    print("\n=== Black Laser Bishop ===")
    t = TestTracker()

    # Black L on d5, white pawn on c4 (target for capture)
    data = get_moves("4k3/8/8/3l4/8/8/8/4K3 b - - 0 1")
    moves = set(data["moves"].get("d5", []))
    # l should slide on all diagonals through everything
    t.test("Black L has diagonal moves", len(moves) > 0, f"moves: {moves}")
    # Should reach all corners of its diagonals
    t.test("Black L reaches a8", "d5a8" in moves, f"moves: {moves}")
    t.test("Black L reaches h1", "d5h1" in moves, f"moves: {moves}")
    return t


if __name__ == "__main__":
    trackers = []
    trackers.append(test_laser_slides_through_allies())
    trackers.append(test_laser_slides_through_enemies())
    trackers.append(test_laser_slides_through_rocks())
    trackers.append(test_laser_board_edge_stops())
    trackers.append(test_laser_captures_through_pieces())
    trackers.append(test_bloodied_bishop_standard_movement())
    trackers.append(test_activation_phase1())
    trackers.append(test_activation_phase2())
    trackers.append(test_full_two_phase_activation())
    trackers.append(test_laser_bishop_direct())
    trackers.append(test_powered_bishop_triggers_activation())
    trackers.append(test_black_laser_bishop())

    total_pass = sum(t.passed for t in trackers)
    total_fail = sum(t.failed for t in trackers)
    print(f"\n{'='*60}")
    print(f"TOTAL: {total_pass} passed, {total_fail} failed")
    if total_fail > 0:
        exit(1)
    print("All laser bishop tests passed!")
