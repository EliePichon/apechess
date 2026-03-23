#!/usr/bin/env python3
"""
Integration tests for Dream API: /turn endpoint and updated /move with grade/peek_next.
"""

import requests
import json

from helpers import BASE_URL, START_FEN, MIDDLEGAME_FEN, create_session, TestTracker

# Checkmate in 1: white Qh5 to f7 is checkmate (Scholar's mate setup)
# After Qf7, black king has no escape
MATE_IN_1_FEN = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"

# Stalemate: black king on a8, white queen on b6, white king on c8
# Black to move, no legal moves, not in check
STALEMATE_FEN = "k7/8/1Q6/8/8/8/8/2K5 b - - 0 1"

t = TestTracker()


def test_turn_basic():
    print("\n--- Test: /turn basic ---")
    sid = create_session()

    r = requests.post(f"{BASE_URL}/turn", json={
        "session_id": sid,
        "maxdepth": 4,
    })
    t.test("/turn returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("has move field", "move" in data, f"keys: {list(data.keys())}")
    t.test("move is a string", isinstance(data.get("move"), str))
    t.test("move is 4-5 chars", len(data.get("move", "")) in (4, 5), f"got '{data.get('move')}'")
    t.test("has eval field", "eval" in data)
    t.test("has check field", "check" in data)
    t.test("check is bool", isinstance(data.get("check"), bool))
    t.test("has game_over field", "game_over" in data)
    t.test("game_over is null for opening", data.get("game_over") is None, f"got {data.get('game_over')}")
    t.test("no next without peek_next", "next" not in data, f"keys: {list(data.keys())}")


def test_turn_with_peek():
    print("\n--- Test: /turn with peek_next ---")
    sid = create_session()

    r = requests.post(f"{BASE_URL}/turn", json={
        "session_id": sid,
        "maxdepth": 4,
        "peek_next": True,
        "peek_maxdepth": 4,
    })
    t.test("/turn with peek returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("has next block", "next" in data, f"keys: {list(data.keys())}")

    nxt = data.get("next", {})
    t.test("next has legal_moves", "legal_moves" in nxt, f"next keys: {list(nxt.keys())}")
    t.test("legal_moves is non-empty dict", isinstance(nxt.get("legal_moves"), dict) and len(nxt["legal_moves"]) > 0)
    t.test("next has check", "check" in nxt)
    t.test("next has clutchness", "clutchness" in nxt)
    t.test("clutchness is numeric", isinstance(nxt.get("clutchness"), (int, float, type(None))))
    t.test("next has best_eval", "best_eval" in nxt)

    # Verify legal_moves structure: {square: [move_str, ...]}
    first_sq = list(nxt["legal_moves"].keys())[0]
    moves = nxt["legal_moves"][first_sq]
    t.test("moves are list of strings", isinstance(moves, list) and isinstance(moves[0], str))


def test_turn_applies_move():
    print("\n--- Test: /turn applies move to session ---")
    sid = create_session()

    # Check ply before
    r = requests.get(f"{BASE_URL}/session/stats", params={"session_id": sid})
    ply_before = r.json()["ply"]

    # Computer plays
    requests.post(f"{BASE_URL}/turn", json={"session_id": sid, "maxdepth": 4})

    # Check ply after
    r = requests.get(f"{BASE_URL}/session/stats", params={"session_id": sid})
    ply_after = r.json()["ply"]
    t.test("ply incremented by 1", ply_after == ply_before + 1,
         f"before={ply_before}, after={ply_after}")


def test_turn_invalid_session():
    print("\n--- Test: /turn with invalid session ---")
    r = requests.post(f"{BASE_URL}/turn", json={
        "session_id": "nonexistent",
        "maxdepth": 4,
    })
    t.test("invalid session returns 404", r.status_code == 404, f"got {r.status_code}")


def test_turn_with_precision():
    print("\n--- Test: /turn with precision ---")
    sid = create_session()

    r = requests.post(f"{BASE_URL}/turn", json={
        "session_id": sid,
        "maxdepth": 4,
        "precision": 0.2,
    })
    t.test("/turn with precision returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("move returned", data.get("move") is not None)


def test_move_with_grade():
    print("\n--- Test: /move with grade ---")
    sid = create_session()

    r = requests.post(f"{BASE_URL}/move", json={
        "session_id": sid,
        "move": "e2e4",
        "grade": True,
    })
    t.test("/move with grade returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("status is ok", data.get("status") == "ok")
    t.test("has check field", "check" in data)
    t.test("has game_over field", "game_over" in data)
    t.test("has grade block", "grade" in data, f"keys: {list(data.keys())}")

    grade = data.get("grade", {})
    t.test("grade has player_eval", "player_eval" in grade)
    t.test("grade has best_eval", "best_eval" in grade)
    t.test("grade has best_move", "best_move" in grade)
    t.test("grade has accuracy", "accuracy" in grade)
    t.test("accuracy is 0-1", 0 <= grade.get("accuracy", -1) <= 1,
         f"got {grade.get('accuracy')}")
    t.test("player_eval is numeric", isinstance(grade.get("player_eval"), (int, float)))
    t.test("best_eval is numeric", isinstance(grade.get("best_eval"), (int, float)))


def test_move_with_peek():
    print("\n--- Test: /move with peek_next ---")
    sid = create_session()

    r = requests.post(f"{BASE_URL}/move", json={
        "session_id": sid,
        "move": "e2e4",
        "peek_next": True,
        "peek_maxdepth": 4,
    })
    t.test("/move with peek returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("has next block", "next" in data, f"keys: {list(data.keys())}")

    nxt = data.get("next", {})
    t.test("next has legal_moves", "legal_moves" in nxt)
    t.test("legal_moves is non-empty", len(nxt.get("legal_moves", {})) > 0)
    t.test("next has check", "check" in nxt)
    t.test("next has clutchness", "clutchness" in nxt)
    t.test("next has best_eval", "best_eval" in nxt)


def test_move_with_grade_and_peek():
    print("\n--- Test: /move with grade + peek_next ---")
    sid = create_session()

    r = requests.post(f"{BASE_URL}/move", json={
        "session_id": sid,
        "move": "e2e4",
        "grade": True,
        "peek_next": True,
        "peek_maxdepth": 4,
    })
    t.test("returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("has grade", "grade" in data)
    t.test("has next", "next" in data)
    t.test("has game_over", "game_over" in data)


def test_move_backward_compatible():
    print("\n--- Test: /move backward compatible (no grade/peek) ---")
    sid = create_session()

    r = requests.post(f"{BASE_URL}/move", json={
        "session_id": sid,
        "move": "e2e4",
    })
    t.test("returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("status is ok", data.get("status") == "ok")
    t.test("has check", "check" in data)
    # Legacy path: no game_over, no grade, no next
    t.test("no grade", "grade" not in data)
    t.test("no next", "next" not in data)


def test_game_over_checkmate():
    print("\n--- Test: game_over checkmate detection ---")
    # Use mate-in-1 position: Qh5f7 is checkmate
    sid = create_session(MATE_IN_1_FEN)

    # White plays Qh5f7 (checkmate)
    r = requests.post(f"{BASE_URL}/move", json={
        "session_id": sid,
        "move": "h5f7",
        "peek_next": True,
    })
    t.test("mating move returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("game_over is checkmate", data.get("game_over") == "checkmate",
         f"got {data.get('game_over')}")
    t.test("check is true", data.get("check") is True, f"got {data.get('check')}")
    t.test("no next on game_over", "next" not in data, f"keys: {list(data.keys())}")


def test_game_over_stalemate():
    print("\n--- Test: game_over stalemate detection ---")
    # Black to move, no legal moves, not in check
    sid = create_session(STALEMATE_FEN)

    # Use /turn to have the engine try to move for black
    # But black has no legal moves — should detect stalemate
    r = requests.post(f"{BASE_URL}/turn", json={
        "session_id": sid,
        "maxdepth": 4,
    })
    t.test("stalemate returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("game_over is stalemate", data.get("game_over") == "stalemate",
         f"got {data.get('game_over')}")
    t.test("move is null", data.get("move") is None, f"got {data.get('move')}")


def test_game_over_via_turn():
    print("\n--- Test: /turn detects checkmate after computer move ---")
    # Set up a position where white can deliver checkmate
    # Use mate-in-1 FEN, let the engine find Qf7#
    sid = create_session(MATE_IN_1_FEN)

    r = requests.post(f"{BASE_URL}/turn", json={
        "session_id": sid,
        "maxdepth": 6,
    })
    t.test("returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    # Engine should find the mating move
    t.test("move is h5f7", data.get("move") == "h5f7",
         f"got {data.get('move')}")
    t.test("game_over is checkmate", data.get("game_over") == "checkmate",
         f"got {data.get('game_over')}")


def test_full_dream_workflow():
    print("\n--- Test: full dream workflow ---")
    sid = create_session()

    # 1. Computer (white) plays first turn with peek
    r = requests.post(f"{BASE_URL}/turn", json={
        "session_id": sid,
        "maxdepth": 4,
        "peek_next": True,
        "peek_maxdepth": 4,
    })
    t.test("turn 1 returns 200", r.status_code == 200)
    data = r.json()
    t.test("turn 1 has move", data.get("move") is not None)
    t.test("turn 1 has next", "next" in data)
    nxt = data.get("next", {})
    t.test("turn 1 next has legal_moves", len(nxt.get("legal_moves", {})) > 0)

    # 2. Player (black) makes a move with grade + peek
    # Pick first legal move from next.legal_moves
    first_sq = list(nxt["legal_moves"].keys())[0]
    player_move = nxt["legal_moves"][first_sq][0]

    r = requests.post(f"{BASE_URL}/move", json={
        "session_id": sid,
        "move": player_move,
        "grade": True,
        "peek_next": True,
        "peek_maxdepth": 4,
    })
    t.test("player move returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("player move has grade", "grade" in data)
    t.test("player move has next", "next" in data)

    # 3. Computer (white) plays second turn with peek
    r = requests.post(f"{BASE_URL}/turn", json={
        "session_id": sid,
        "maxdepth": 4,
        "peek_next": True,
        "peek_maxdepth": 4,
    })
    t.test("turn 2 returns 200", r.status_code == 200)
    data = r.json()
    t.test("turn 2 has move", data.get("move") is not None)
    t.test("turn 2 game continues", data.get("game_over") is None)

    # Verify ply advanced correctly (1 initial + 3 moves = 4)
    r = requests.get(f"{BASE_URL}/session/stats", params={"session_id": sid})
    stats = r.json()
    t.test("ply is 4 after 3 moves", stats.get("ply") == 4,
         f"got {stats.get('ply')}")


def main():
    print("=" * 60)
    print("Dream API Tests (/turn + updated /move)")
    print("=" * 60)

    test_turn_basic()
    test_turn_with_peek()
    test_turn_applies_move()
    test_turn_invalid_session()
    test_turn_with_precision()
    test_move_with_grade()
    test_move_with_peek()
    test_move_with_grade_and_peek()
    test_move_backward_compatible()
    test_game_over_checkmate()
    test_game_over_stalemate()
    test_game_over_via_turn()
    test_full_dream_workflow()

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
