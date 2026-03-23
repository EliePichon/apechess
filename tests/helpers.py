"""
Shared test utilities for Sunfish integration tests.

Provides common constants, session helpers, and a lightweight test tracker
so individual test files don't need to duplicate boilerplate.
"""

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "http://localhost:5500"

# Common FEN positions used across multiple test files
START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
MIDDLEGAME_FEN = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
ITALIAN_FEN = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"


# ---------------------------------------------------------------------------
# Session helper
# ---------------------------------------------------------------------------

def create_session(fen=None):
    """Create a new game session, optionally from a FEN position."""
    body = {"fen": fen} if fen else {}
    r = requests.post(f"{BASE_URL}/newgame", json=body)
    r.raise_for_status()
    return r.json()["session_id"]


# ---------------------------------------------------------------------------
# Test tracker
# ---------------------------------------------------------------------------

class TestTracker:
    """Lightweight pass/fail counter for integration tests."""

    def __init__(self):
        self.passed = 0
        self.failed = 0

    def test(self, name, condition, detail=""):
        if condition:
            print(f"  PASS  {name}")
            self.passed += 1
        else:
            print(f"  FAIL  {name} — {detail}")
            self.failed += 1

    def summary(self):
        return self.passed, self.failed
