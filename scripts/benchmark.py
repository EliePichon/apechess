#!/usr/bin/env python3
"""
Direct engine benchmark for measuring optimization impact.

Runs the same 6 positions as profile_game.py but calls the engine directly
(no HTTP overhead). Reports per-position timing, nodes, and nodes/sec.

Usage:
    python scripts/benchmark.py [--depth DEPTH]
"""

import argparse
import sys
import time

sys.path.insert(0, ".")

import sunfish
from tools import uci

uci.sunfish = sunfish

DEFAULT_DEPTH = 8

POSITIONS = [
    ("opening_start",   "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"),
    ("opening_italian", "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"),
    ("midgame_open",    "r1bq1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 7"),
    ("midgame_tense",   "r2qkb1r/pp2pppp/2n2n2/3p1b2/3P4/2N2N2/PPP1BPPP/R1BQK2R w KQkq - 4 6"),
    ("endgame_rook",    "8/5pk1/6p1/8/3R4/6PP/5PK1/2r5 w - - 0 36"),
    ("endgame_queen",   "6k1/5ppp/8/8/8/8/5PPP/3Q2K1 w - - 0 40"),
]


def run_position(name, fen, depth):
    pos = uci.from_fen(*fen.split())
    hist = [pos]

    searcher = sunfish.Searcher()

    t0 = time.perf_counter()
    best_move = None
    for d, gamma, score, move in searcher.search(hist):
        if d >= depth:
            best_move = move
            break
    elapsed = time.perf_counter() - t0
    nodes = searcher.nodes
    nps = int(nodes / elapsed) if elapsed > 0 else 0

    return elapsed, nodes, nps, best_move


def main():
    parser = argparse.ArgumentParser(description="Direct engine benchmark")
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    args = parser.parse_args()

    print(f"Benchmark: {len(POSITIONS)} positions, depth={args.depth}")
    print(f"{'Position':<20} {'Time':>8} {'Nodes':>10} {'NPS':>10} {'Move':>8}")
    print("-" * 60)

    total_time = 0
    total_nodes = 0

    for name, fen in POSITIONS:
        elapsed, nodes, nps, move = run_position(name, fen, args.depth)
        total_time += elapsed
        total_nodes += nodes
        move_str = sunfish.render(move[0]) + sunfish.render(move[1]) if move else "?"
        print(f"{name:<20} {elapsed:>7.2f}s {nodes:>10,} {nps:>10,} {move_str:>8}")

    total_nps = int(total_nodes / total_time) if total_time > 0 else 0
    print("-" * 60)
    print(f"{'TOTAL':<20} {total_time:>7.2f}s {total_nodes:>10,} {total_nps:>10,}")


if __name__ == "__main__":
    main()
