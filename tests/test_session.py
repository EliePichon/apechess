#!/usr/bin/env python3
"""
Integration tests for session-based stateful engine, /evalmoves, and clutchness.
"""

import requests
import json
import time

from helpers import BASE_URL, START_FEN, MIDDLEGAME_FEN, TestTracker

t = TestTracker()


def test_newgame_returns_session_id():
    print("\n--- Test: /newgame returns session_id ---")
    r = requests.post(f"{BASE_URL}/newgame", json={})
    t.test("/newgame returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("response has session_id", "session_id" in data, f"keys: {list(data.keys())}")
    t.test("session_id is a string", isinstance(data.get("session_id"), str))
    t.test("session_id is non-empty", len(data.get("session_id", "")) > 0)
    return data.get("session_id")


def test_newgame_with_fen():
    print("\n--- Test: /newgame with custom FEN ---")
    r = requests.post(f"{BASE_URL}/newgame", json={"fen": MIDDLEGAME_FEN})
    t.test("/newgame with FEN returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("response has session_id", "session_id" in data)
    return data.get("session_id")


def test_bestmove_with_session():
    print("\n--- Test: /bestmove with session_id ---")
    # Create session
    r = requests.post(f"{BASE_URL}/newgame", json={})
    sid = r.json()["session_id"]

    # Get best move using session (no FEN needed)
    r = requests.post(f"{BASE_URL}/bestmove", json={
        "session_id": sid,
        "maxdepth": 4,
    })
    t.test("/bestmove with session returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("response has bestmoves", "bestmoves" in data, f"keys: {list(data.keys())}")
    t.test("bestmoves is non-empty", len(data.get("bestmoves", [])) > 0)
    t.test("response has check field", "check" in data)


def test_bestmove_stateless_unchanged():
    print("\n--- Test: stateless /bestmove still works ---")
    r = requests.post(f"{BASE_URL}/bestmove", json={
        "fen": START_FEN,
        "maxdepth": 4,
    })
    t.test("stateless /bestmove returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("response has bestmoves", "bestmoves" in data)
    t.test("bestmoves is non-empty", len(data.get("bestmoves", [])) > 0)


def test_bestmove_no_fen_no_session():
    print("\n--- Test: /bestmove without fen or session returns error ---")
    r = requests.post(f"{BASE_URL}/bestmove", json={"maxdepth": 4})
    t.test("returns 400", r.status_code == 400, f"got {r.status_code}")


def test_move_player_turn():
    print("\n--- Test: /move player turn ---")
    r = requests.post(f"{BASE_URL}/newgame", json={})
    sid = r.json()["session_id"]

    r = requests.post(f"{BASE_URL}/move", json={
        "session_id": sid,
        "move": "e2e4",
    })
    t.test("/move returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("status is ok", data.get("status") == "ok", f"got {data.get('status')}")
    t.test("has check field", "check" in data)
    t.test("no bestmoves on player turn", "bestmoves" not in data)


def test_move_computer_turn():
    print("\n--- Test: /move computer turn auto-computes bestmoves ---")
    r = requests.post(f"{BASE_URL}/newgame", json={})
    sid = r.json()["session_id"]

    # Player moves e2e4
    requests.post(f"{BASE_URL}/move", json={"session_id": sid, "move": "e2e4"})

    # Computer turn: black plays e7e5, engine auto-computes response
    r = requests.post(f"{BASE_URL}/move", json={
        "session_id": sid,
        "move": "e7e5",
        "computer_turn": True,
        "maxdepth": 4,
    })
    t.test("/move computer turn returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("status is ok", data.get("status") == "ok")
    t.test("has bestmoves", "bestmoves" in data, f"keys: {list(data.keys())}")
    t.test("bestmoves is non-empty", len(data.get("bestmoves", [])) > 0)
    t.test("has clutchness", "clutchness" in data)


def test_move_illegal():
    print("\n--- Test: /move with illegal move returns error ---")
    r = requests.post(f"{BASE_URL}/newgame", json={})
    sid = r.json()["session_id"]

    r = requests.post(f"{BASE_URL}/move", json={
        "session_id": sid,
        "move": "e1e5",  # Illegal: king can't move to e5 from start
    })
    t.test("illegal move returns 400", r.status_code == 400, f"got {r.status_code}")


def test_move_invalid_session():
    print("\n--- Test: /move with invalid session returns 404 ---")
    r = requests.post(f"{BASE_URL}/move", json={
        "session_id": "nonexistent",
        "move": "e2e4",
    })
    t.test("invalid session returns 404", r.status_code == 404, f"got {r.status_code}")


def test_fen_override():
    print("\n--- Test: FEN override re-syncs session ---")
    r = requests.post(f"{BASE_URL}/newgame", json={})
    sid = r.json()["session_id"]

    # Override session position to middlegame
    r = requests.post(f"{BASE_URL}/bestmove", json={
        "session_id": sid,
        "fen": MIDDLEGAME_FEN,
        "maxdepth": 4,
    })
    t.test("FEN override returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("returns valid bestmoves", len(data.get("bestmoves", [])) > 0)


def test_clutchness_on_bestmove():
    print("\n--- Test: clutchness on /bestmove ---")
    r = requests.post(f"{BASE_URL}/bestmove", json={
        "fen": MIDDLEGAME_FEN,
        "maxdepth": 6,
        "clutchness": True,
    })
    t.test("returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("has clutchness field", "clutchness" in data, f"keys: {list(data.keys())}")
    t.test("clutchness is numeric", isinstance(data.get("clutchness"), (int, float)),
         f"got {type(data.get('clutchness'))}")


def test_clutchness_not_present_without_flag():
    print("\n--- Test: no clutchness without flag ---")
    r = requests.post(f"{BASE_URL}/bestmove", json={
        "fen": START_FEN,
        "maxdepth": 4,
    })
    data = r.json()
    t.test("no clutchness field without flag", "clutchness" not in data,
         f"keys: {list(data.keys())}")


def test_evalmoves_stateless():
    print("\n--- Test: /evalmoves stateless ---")
    r = requests.post(f"{BASE_URL}/evalmoves", json={
        "fen": MIDDLEGAME_FEN,
        "maxdepth": 4,
    })
    t.test("/evalmoves returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("has moves field", "moves" in data, f"keys: {list(data.keys())}")
    t.test("moves is non-empty dict", isinstance(data.get("moves"), dict) and len(data["moves"]) > 0)
    t.test("has check field", "check" in data)
    t.test("has clutchness field", "clutchness" in data)

    # Check structure of move entries
    first_square = list(data["moves"].keys())[0]
    entries = data["moves"][first_square]
    t.test("move entries are lists", isinstance(entries, list) and len(entries) > 0)
    first_entry = entries[0]
    t.test("entry has move field", "move" in first_entry, f"keys: {list(first_entry.keys())}")
    t.test("entry has eval field", "eval" in first_entry, f"keys: {list(first_entry.keys())}")
    t.test("eval is numeric", isinstance(first_entry.get("eval"), (int, float)))


def test_evalmoves_with_session():
    print("\n--- Test: /evalmoves with session ---")
    r = requests.post(f"{BASE_URL}/newgame", json={"fen": MIDDLEGAME_FEN})
    sid = r.json()["session_id"]

    r = requests.post(f"{BASE_URL}/evalmoves", json={
        "session_id": sid,
        "maxdepth": 4,
    })
    t.test("/evalmoves with session returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("has moves field", "moves" in data)
    t.test("moves is non-empty", len(data.get("moves", {})) > 0)


def test_session_stats():
    print("\n--- Test: /session/stats ---")
    r = requests.post(f"{BASE_URL}/newgame", json={})
    sid = r.json()["session_id"]

    # Do a search to populate tp_move
    requests.post(f"{BASE_URL}/bestmove", json={
        "session_id": sid,
        "maxdepth": 4,
    })

    r = requests.get(f"{BASE_URL}/session/stats", params={"session_id": sid})
    t.test("/session/stats returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("has tp_move_size", "tp_move_size" in data)
    t.test("tp_move_size > 0 after search", data.get("tp_move_size", 0) > 0,
         f"got {data.get('tp_move_size')}")
    t.test("has ply", "ply" in data)


def test_session_stats_invalid():
    print("\n--- Test: /session/stats with invalid id ---")
    r = requests.get(f"{BASE_URL}/session/stats", params={"session_id": "bogus"})
    t.test("invalid session returns 404", r.status_code == 404, f"got {r.status_code}")


def test_session_isolation():
    print("\n--- Test: session isolation ---")
    # Create two sessions
    r1 = requests.post(f"{BASE_URL}/newgame", json={})
    sid1 = r1.json()["session_id"]
    r2 = requests.post(f"{BASE_URL}/newgame", json={})
    sid2 = r2.json()["session_id"]

    t.test("different session IDs", sid1 != sid2)

    # Apply move only to session 1
    requests.post(f"{BASE_URL}/move", json={"session_id": sid1, "move": "e2e4"})

    # Session 2 should still be at starting position — e2e4 should still be legal
    r = requests.post(f"{BASE_URL}/move", json={"session_id": sid2, "move": "e2e4"})
    t.test("session 2 unaffected by session 1 move", r.status_code == 200, f"got {r.status_code}")

    # Session 1 should be after e2e4 — e2e4 should now be illegal
    r = requests.post(f"{BASE_URL}/move", json={"session_id": sid1, "move": "e2e4"})
    t.test("session 1 position advanced (e2e4 now illegal)", r.status_code == 400,
         f"got {r.status_code}")


def test_full_game_workflow():
    print("\n--- Test: full game workflow ---")
    # 1. Create game
    r = requests.post(f"{BASE_URL}/newgame", json={})
    sid = r.json()["session_id"]
    t.test("game created", r.status_code == 200)

    # 2. Get evals for player
    r = requests.post(f"{BASE_URL}/evalmoves", json={
        "session_id": sid,
        "maxdepth": 4,
    })
    t.test("evalmoves works", r.status_code == 200)

    # 3. Player plays e2e4
    r = requests.post(f"{BASE_URL}/move", json={
        "session_id": sid,
        "move": "e2e4",
    })
    t.test("player move e2e4", r.status_code == 200)

    # 4. Computer plays (e7e5), auto-computes response
    r = requests.post(f"{BASE_URL}/move", json={
        "session_id": sid,
        "move": "e7e5",
        "computer_turn": True,
        "maxdepth": 4,
    })
    t.test("computer move e7e5 with auto-compute", r.status_code == 200)
    data = r.json()
    t.test("auto-computed bestmoves returned", len(data.get("bestmoves", [])) > 0)

    # 5. Get best move for next turn
    r = requests.post(f"{BASE_URL}/bestmove", json={
        "session_id": sid,
        "maxdepth": 4,
    })
    t.test("bestmove after moves", r.status_code == 200)
    data = r.json()
    t.test("valid bestmoves", len(data.get("bestmoves", [])) > 0)


def test_turn_fen_override():
    """Test that /turn accepts fen override to re-sync position before playing."""
    print("\n--- Test: /turn with FEN override ---")
    # Create session at starting position
    r = requests.post(f"{BASE_URL}/newgame", json={})
    sid = r.json()["session_id"]

    # Override to a position where it's black's turn (after 1.e4)
    after_e4_fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    r = requests.post(f"{BASE_URL}/turn", json={
        "session_id": sid,
        "fen": after_e4_fen,
        "maxdepth": 4,
    })
    t.test("/turn with fen override status 200", r.status_code == 200)
    data = r.json()
    t.test("/turn returned a move", data.get("move") is not None)
    t.test("/turn game_over is null", data.get("game_over") is None)


def test_turn_ply():
    """Test that /turn response includes ply field."""
    print("\n--- Test: /turn includes ply ---")
    r = requests.post(f"{BASE_URL}/newgame", json={})
    sid = r.json()["session_id"]

    r = requests.post(f"{BASE_URL}/turn", json={
        "session_id": sid,
        "maxdepth": 4,
    })
    t.test("/turn status 200", r.status_code == 200)
    data = r.json()
    t.test("/turn has ply field", "ply" in data)
    t.test("/turn ply is int", isinstance(data.get("ply"), int))
    # After engine plays 1 move from start, ply should be 2 (initial + after move)
    t.test("/turn ply is 2 after one move", data.get("ply") == 2)


def test_move_ply():
    """Test that /move response includes ply field."""
    print("\n--- Test: /move includes ply ---")
    r = requests.post(f"{BASE_URL}/newgame", json={})
    sid = r.json()["session_id"]

    r = requests.post(f"{BASE_URL}/move", json={
        "session_id": sid,
        "move": "e2e4",
    })
    t.test("/move status 200", r.status_code == 200)
    data = r.json()
    t.test("/move has ply field", "ply" in data)
    t.test("/move ply is 2 after one move", data.get("ply") == 2)


def main():
    print("=" * 60)
    print("Session / Stateful Engine Tests")
    print("=" * 60)

    test_newgame_returns_session_id()
    test_newgame_with_fen()
    test_bestmove_with_session()
    test_bestmove_stateless_unchanged()
    test_bestmove_no_fen_no_session()
    test_move_player_turn()
    test_move_computer_turn()
    test_move_illegal()
    test_move_invalid_session()
    test_fen_override()
    test_clutchness_on_bestmove()
    test_clutchness_not_present_without_flag()
    test_evalmoves_stateless()
    test_evalmoves_with_session()
    test_session_stats()
    test_session_stats_invalid()
    test_session_isolation()
    test_full_game_workflow()
    test_turn_fen_override()
    test_turn_ply()
    test_move_ply()

    print(f"\n{'=' * 60}")
    print(f"Results: {t.passed} passed, {t.failed} failed")
    print(f"{'=' * 60}")

    if t.failed > 0:
        exit(1)


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("\nError: Could not connect to server.")
        print("Make sure the server is running: make up")
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
