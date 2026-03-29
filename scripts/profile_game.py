#!/usr/bin/env python3
"""
Standardized game scenario for py-spy profiling.

Plays 6 positions (opening, midgame, endgame) via HTTP at depth 12 with top_n=3,
generating sustained CPU load for flame graph sampling. Runs in ~30-60s.

Usage:
    python scripts/profile_game.py [--base-url URL] [--depth DEPTH]
"""

import argparse
import time
import requests

DEFAULT_BASE_URL = "http://localhost:5500"
DEFAULT_DEPTH = 12
TOP_N = 3

POSITIONS = [
    ("opening_start", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"),
    ("opening_italian", "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"),
    ("midgame_open", "r1bq1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 7"),
    ("midgame_tense", "r2qkb1r/pp2pppp/2n2n2/3p1b2/3P4/2N2N2/PPP1BPPP/R1BQK2R w KQkq - 4 6"),
    ("endgame_rook", "8/5pk1/6p1/8/3R4/6PP/5PK1/2r5 w - - 0 36"),
    ("endgame_queen", "6k1/5ppp/8/8/8/8/5PPP/3Q2K1 w - - 0 40"),
]


def run(base_url, depth):
    print(f"Profiling: {len(POSITIONS)} positions, depth={depth}, top_n={TOP_N}")
    print(f"Target: {base_url}\n")

    total_start = time.perf_counter()

    for name, fen in POSITIONS:
        print(f"  {name}...", end=" ", flush=True)
        t0 = time.perf_counter()

        r = requests.post(
            f"{base_url}/bestmove",
            json={
                "fen": fen,
                "maxdepth": depth,
                "top_n": TOP_N,
            },
        )
        r.raise_for_status()
        data = r.json()

        elapsed = time.perf_counter() - t0
        moves = [m[0] for m in data.get("bestmoves", [])]
        print(f"{elapsed:.1f}s  moves={moves}")

    total = time.perf_counter() - total_start
    print(f"\nDone in {total:.1f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Profiling workload for py-spy")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    args = parser.parse_args()
    run(args.base_url, args.depth)
