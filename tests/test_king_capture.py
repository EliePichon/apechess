#!/usr/bin/env python3
"""
Integration tests for king capture as a game-over condition.

In modified rule variants (e.g., double turns), a king can end up capturable
without the defending side having had a chance to move. The engine should
handle this: capture the king and report game_over: "king_captured".
"""

import requests

from helpers import BASE_URL, create_session, TestTracker

# White queen on d7 can capture black king on e8.
# Simulates a double-turn scenario where the king is left en prise.
KING_CAPTURABLE_FEN = "4k3/3Q4/8/8/8/8/8/4K3 w - - 0 1"

# Same idea but black to move: black queen on d2 can capture white king on e1.
KING_CAPTURABLE_BLACK_FEN = "4k3/8/8/8/8/8/3q4/4K3 b - - 0 1"

# Normal checkmate position (scholar's mate setup) — should still work as checkmate.
MATE_IN_1_FEN = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"

t = TestTracker()


def test_king_capture_via_move():
    """Player manually captures the opponent's king via /move."""
    print("\n--- Test: king capture via /move ---")
    sid = create_session(KING_CAPTURABLE_FEN)

    r = requests.post(
        f"{BASE_URL}/move",
        json={
            "session_id": sid,
            "move": "d7e8",
            "peek_next": True,
        },
    )
    t.test("king capture returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("game_over is king_captured", data.get("game_over") == "king_captured", f"got {data.get('game_over')}")
    t.test("check is false (game over)", data.get("check") is False, f"got {data.get('check')}")
    t.test("no next on game_over", "next" not in data, f"keys: {list(data.keys())}")


def test_king_capture_via_turn():
    """Engine (AI) captures the opponent's king via /turn."""
    print("\n--- Test: king capture via /turn ---")
    sid = create_session(KING_CAPTURABLE_FEN)

    r = requests.post(
        f"{BASE_URL}/turn",
        json={
            "session_id": sid,
            "maxdepth": 4,
        },
    )
    t.test("turn returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("game_over is king_captured", data.get("game_over") == "king_captured", f"got {data.get('game_over')}")
    t.test("move captures king", data.get("move") is not None, f"got {data.get('move')}")
    t.test("check is false", data.get("check") is False, f"got {data.get('check')}")


def test_king_capture_black_to_move():
    """Black captures white king — verifies coordinate flipping works."""
    print("\n--- Test: king capture by black via /turn ---")
    sid = create_session(KING_CAPTURABLE_BLACK_FEN)

    r = requests.post(
        f"{BASE_URL}/turn",
        json={
            "session_id": sid,
            "maxdepth": 4,
        },
    )
    t.test("turn returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("game_over is king_captured", data.get("game_over") == "king_captured", f"got {data.get('game_over')}")
    t.test("check is false", data.get("check") is False, f"got {data.get('check')}")


def test_checkmate_still_works():
    """Normal checkmate should still be detected as checkmate, not king_captured."""
    print("\n--- Test: checkmate regression ---")
    sid = create_session(MATE_IN_1_FEN)

    # White plays Qh5f7 (checkmate)
    r = requests.post(
        f"{BASE_URL}/move",
        json={
            "session_id": sid,
            "move": "h5f7",
            "peek_next": True,
        },
    )
    t.test("mating move returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("game_over is checkmate (not king_captured)", data.get("game_over") == "checkmate", f"got {data.get('game_over')}")
    t.test("check is true", data.get("check") is True, f"got {data.get('check')}")


def test_king_capture_via_legacy_move():
    """Legacy /move endpoint (without grade/peek_next) detects king capture."""
    print("\n--- Test: king capture via legacy /move ---")
    sid = create_session(KING_CAPTURABLE_FEN)

    r = requests.post(
        f"{BASE_URL}/move",
        json={
            "session_id": sid,
            "move": "d7e8",
        },
    )
    t.test("legacy move returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    t.test("game_over is king_captured", data.get("game_over") == "king_captured", f"got {data.get('game_over')}")
    t.test("check is false", data.get("check") is False, f"got {data.get('check')}")


if __name__ == "__main__":
    test_king_capture_via_move()
    test_king_capture_via_turn()
    test_king_capture_black_to_move()
    test_checkmate_still_works()
    test_king_capture_via_legacy_move()

    passed, failed = t.summary()
    print(f"\n{'='*40}")
    print(f"King capture tests: {passed} passed, {failed} failed")
    if failed:
        exit(1)
    print("All king capture tests passed!")
