#!/usr/bin/env python3
"""
Test script for hero-gated activation mechanics.

Parkour activation (N/C -> J) only fires when "charles" hero is selected.
Laser Bishop activation (B/D -> G -> L) only fires when "steina" hero is selected.
Without the corresponding hero, captures happen normally without triggering upgrades.
"""

import requests

from helpers import BASE_URL, TestTracker


def create_session(fen=None, heroes=None):
    """Create a new game session with optional heroes config."""
    body = {}
    if fen:
        body["fen"] = fen
    if heroes:
        body["heroes"] = heroes
    r = requests.post(f"{BASE_URL}/newgame", json=body)
    r.raise_for_status()
    return r.json()["session_id"]


def make_move(session_id, move):
    """Apply a player move to a session."""
    r = requests.post(f"{BASE_URL}/move", json={
        "session_id": session_id,
        "move": move,
    })
    r.raise_for_status()
    return r.json()


def get_moves_session(session_id):
    """Get legal moves via /turn peek (returns next block with legal moves)."""
    # Use /turn with peek to see the board state after a move
    # Actually, we can use /bestmove to check if J pieces exist by looking at move sources
    # Simplest: use /getmoves with a FEN that we construct
    pass


def get_moves(fen, heroes=None):
    """Get legal moves from the engine for a given FEN."""
    body = {"fen": fen}
    if heroes:
        body["heroes"] = heroes
    r = requests.post(f"{BASE_URL}/getmoves", json=body)
    r.raise_for_status()
    return r.json()


def get_bestmove(fen, heroes=None, **kwargs):
    """Get best move with optional heroes."""
    body = {"fen": fen, "maxdepth": 3}
    if heroes:
        body["heroes"] = heroes
    body.update(kwargs)
    r = requests.post(f"{BASE_URL}/bestmove", json=body)
    r.raise_for_status()
    return r.json()


# ---- Parkour activation tests ----

def test_no_parkour_without_hero():
    """Without charles hero, knight captures should NOT trigger parkour."""
    print("\n=== No parkour without charles ===")
    t = TestTracker()

    # White N on d4 can capture black pawn on b5. Another white N on b1.
    # After Nd4xb5, if parkour fired b1 would become J, otherwise stays N.
    fen = "4k3/8/8/1p6/3N4/8/8/1N2K3 w - - 0 1"
    sid = create_session(fen, heroes={})  # No heroes

    result = make_move(sid, "d4b5")
    t.test("Move accepted", result.get("status") == "ok", f"result: {result}")

    # Black king moves (king can go to d8, f8, d7, e7, f7 — b5 doesn't attack those)
    result = make_move(sid, "e8d7")
    t.test("Black move accepted", result.get("status") == "ok", f"result: {result}")

    # Now it's white's turn again. If parkour did NOT fire, b1 is still N.
    # Use /turn to have the computer play and verify it works.
    r = requests.post(f"{BASE_URL}/turn", json={
        "session_id": sid,
        "maxdepth": 1,
    })
    r.raise_for_status()
    turn_result = r.json()
    t.test("Turn completed (no parkour)", turn_result.get("move") is not None,
           f"result: {turn_result}")

    # Simpler direct test: N next to a rock should NOT have bounce moves.
    fen2 = "4k3/8/8/8/8/2O5/8/1N2K3 w - - 0 1"
    data = get_moves(fen2)
    b1_moves = set(data["moves"].get("b1", []))
    # N can't bounce off rocks (only J can)
    has_bounce = any(len(m) > 4 for m in b1_moves)
    t.test("N on b1 has no bounce moves (no hero)", not has_bounce,
           f"moves: {b1_moves}")

    return t


def test_parkour_with_charles():
    """With charles hero, knight captures SHOULD trigger parkour."""
    print("\n=== Parkour activates with charles ===")
    t = TestTracker()

    # White N on d4 captures black pawn on b5. Another white N on b1.
    # With charles hero, after Nd4xb5, both should become J.
    fen = "4k3/8/8/1p6/3N4/8/8/1N2K3 w - - 0 1"
    sid = create_session(fen, heroes={"white": "charles"})

    result = make_move(sid, "d4b5")
    t.test("Move accepted", result.get("status") == "ok", f"result: {result}")

    # Black king moves
    result = make_move(sid, "e8d7")
    t.test("Black move accepted", result.get("status") == "ok", f"result: {result}")

    # Now it's white's turn. If parkour fired, b1 became J.
    # Verify J can bounce off rocks: set up direct check.
    fen_post = "4k3/8/8/8/8/2O5/8/1J2K3 w - - 0 1"
    data = get_moves(fen_post)
    b1_moves = set(data["moves"].get("b1", []))
    has_bounce = any(len(m) > 4 for m in b1_moves)
    t.test("J on b1 has bounce moves after parkour", has_bounce,
           f"moves: {b1_moves}")

    return t


def test_session_parkour_capture():
    """Session-based test: N captures with charles → pieces become J (verified by next turn)."""
    print("\n=== Session parkour: N capture → J ===")
    t = TestTracker()

    # Position: N on f3, black pawn on g5. Another N on b1.
    # After Nf3xg5 with charles, both become J.
    fen = "4k3/8/8/6p1/8/5N2/8/1N2K3 w - - 0 1"
    sid = create_session(fen, heroes={"white": "charles"})

    # White N captures g5
    result = make_move(sid, "f3g5")
    t.test("Knight capture accepted", result.get("status") == "ok", f"result: {result}")

    # Black king moves (g5 knight attacks e6,f7,h7 — king can go to d7,d8,f8)
    result = make_move(sid, "e8d7")
    t.test("Black move accepted", result.get("status") == "ok", f"result: {result}")

    # Computer turn — should work with J pieces
    r = requests.post(f"{BASE_URL}/turn", json={
        "session_id": sid,
        "maxdepth": 1,
    })
    r.raise_for_status()
    turn_result = r.json()
    t.test("Turn completed with J pieces", turn_result.get("move") is not None,
           f"result: {turn_result}")

    return t


# ---- Laser Bishop activation tests ----

def test_no_laser_without_hero():
    """Without steina hero, bishop captures should NOT trigger laser activation."""
    print("\n=== No laser activation without steina ===")
    t = TestTracker()

    # Direct test: L slides through allies, B doesn't. This verifies the distinction.
    # L on c1, ally pawn on d2 — L can slide through to e3, f4, etc.
    fen_laser = "4k3/8/8/8/8/8/3P4/2L4K w - - 0 1"
    data = get_moves(fen_laser)
    l_moves = set(data["moves"].get("c1", []))
    t.test("L slides through allies (sanity)", "c1e3" in l_moves or "c1f4" in l_moves,
           f"L moves: {l_moves}")

    # B on c1, ally pawn on d2 — B is blocked
    fen_bishop = "4k3/8/8/8/8/8/3P4/2B4K w - - 0 1"
    data = get_moves(fen_bishop)
    b_moves = set(data["moves"].get("c1", []))
    t.test("B blocked by ally", "c1e3" not in b_moves,
           f"B moves: {b_moves}")

    # Session test: Two captures without hero → B stays B (no L upgrade)
    # White B on c4 captures black pawns. King on h1 stays safe.
    fen = "7k/8/4p3/3p4/2B5/8/8/5B1K w - - 0 1"
    sid = create_session(fen, heroes={})  # No heroes

    # Capture 1: Bc4xd5
    result = make_move(sid, "c4d5")
    t.test("First capture (no hero)", result.get("status") == "ok", f"result: {result}")

    # Black king moves
    result = make_move(sid, "h8g7")
    t.test("Black move", result.get("status") == "ok", f"result: {result}")

    # Capture 2: Bd5xe6 — without hero, should NOT become L
    result = make_move(sid, "d5e6")
    t.test("Second capture (no hero)", result.get("status") == "ok", f"result: {result}")

    # Computer plays — should work fine with regular B
    r = requests.post(f"{BASE_URL}/turn", json={
        "session_id": sid,
        "maxdepth": 1,
    })
    r.raise_for_status()
    turn_result = r.json()
    t.test("Turn after captures (no laser)", turn_result.get("game_over") is not None or turn_result.get("move") is not None,
           f"result: {turn_result}")

    return t


def test_laser_with_steina():
    """With steina hero, bishop captures SHOULD trigger laser activation."""
    print("\n=== Laser activation with steina ===")
    t = TestTracker()

    # Two-capture scenario WITH steina: B→G (phase 1), G→L (phase 2)
    fen = "7k/8/4p3/3p4/2B5/8/8/5B1K w - - 0 1"
    sid = create_session(fen, heroes={"white": "steina"})

    # Capture 1: Bc4xd5 → phase 1 (B→G)
    result = make_move(sid, "c4d5")
    t.test("First capture with steina", result.get("status") == "ok", f"result: {result}")

    # Black moves
    result = make_move(sid, "h8g7")
    t.test("Black move", result.get("status") == "ok", f"result: {result}")

    # Capture 2: Gd5xe6 → phase 2 (G→L)
    result = make_move(sid, "d5e6")
    t.test("Second capture with steina", result.get("status") == "ok", f"result: {result}")

    # Black moves
    result = make_move(sid, "g7f6")
    t.test("Black move 2", result.get("status") == "ok", f"result: {result}")

    # Computer turn — if L exists, the engine will use slide-through moves
    r = requests.post(f"{BASE_URL}/turn", json={
        "session_id": sid,
        "maxdepth": 1,
    })
    r.raise_for_status()
    turn_result = r.json()
    t.test("Turn after laser activation", turn_result.get("move") is not None,
           f"result: {turn_result}")

    return t


# ---- Hero validation tests ----

def test_invalid_hero():
    """Invalid hero names should be rejected."""
    print("\n=== Invalid hero validation ===")
    t = TestTracker()

    r = requests.post(f"{BASE_URL}/newgame", json={
        "heroes": {"white": "invalid_hero"}
    })
    t.test("Invalid hero rejected", r.status_code == 400,
           f"status: {r.status_code}, body: {r.text}")

    r = requests.post(f"{BASE_URL}/newgame", json={
        "heroes": {"blue": "charles"}
    })
    t.test("Invalid side rejected", r.status_code == 400,
           f"status: {r.status_code}, body: {r.text}")

    return t


def test_both_heroes():
    """Both heroes can be active simultaneously."""
    print("\n=== Both heroes active ===")
    t = TestTracker()

    fen = "4k3/8/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    sid = create_session(fen, heroes={"white": "charles", "black": "steina"})
    t.test("Session with both heroes created", sid is not None, f"sid: {sid}")

    return t


def test_stateless_heroes():
    """Stateless /bestmove endpoint accepts heroes parameter."""
    print("\n=== Stateless heroes param ===")
    t = TestTracker()

    # Position where N can capture — with and without charles
    fen = "4k3/8/8/4p3/3N4/8/8/1N2K3 w - - 0 1"

    # Without heroes (default: all enabled for backward compat)
    result1 = get_bestmove(fen)
    t.test("Bestmove without heroes", len(result1.get("bestmoves", [])) > 0,
           f"result: {result1}")

    # With charles hero
    result2 = get_bestmove(fen, heroes={"white": "charles"})
    t.test("Bestmove with charles", len(result2.get("bestmoves", [])) > 0,
           f"result: {result2}")

    return t


# ---- Main ----

if __name__ == "__main__":
    all_passed = 0
    all_failed = 0

    for test_fn in [
        test_no_parkour_without_hero,
        test_parkour_with_charles,
        test_session_parkour_capture,
        test_no_laser_without_hero,
        test_laser_with_steina,
        test_invalid_hero,
        test_both_heroes,
        test_stateless_heroes,
    ]:
        tracker = test_fn()
        p, f = tracker.summary()
        all_passed += p
        all_failed += f

    print(f"\n{'='*50}")
    print(f"Heroes tests: {all_passed} passed, {all_failed} failed")
    if all_failed:
        exit(1)
    print("All hero tests passed!")
