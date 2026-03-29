#!/usr/bin/env python3
"""
Session vs Stateless performance benchmark.
Compares TP-reuse (session mode) against cold-start (stateless mode)
over a ~20-move self-play game.
"""

import requests

from helpers import BASE_URL, create_session

MAX_MOVES = 20
MAXDEPTH = 6


def session_run():
    """Phase 1: Engine plays itself via /turn with persistent session (TP reuse)."""
    print("Phase 1: Session run (TP reuse)...")
    sid = create_session()
    moves = []
    times = []

    for i in range(MAX_MOVES):
        r = requests.post(f"{BASE_URL}/turn", json={"session_id": sid, "maxdepth": MAXDEPTH})
        r.raise_for_status()
        data = r.json()
        elapsed = r.elapsed.total_seconds()

        moves.append(data["move"])
        times.append(elapsed)
        print(f"  Move {i + 1}: {data['move']} ({elapsed:.3f}s)", flush=True)

        if data.get("game_over"):
            print(f"  Game over: {data['game_over']}")
            break

    return moves, times


def stateless_run(moves):
    """Phase 2: Replay each position with a fresh session (cold TP)."""
    print(f"\nPhase 2: Stateless run (cold TP, {len(moves)} positions)...")
    times = []

    for i in range(len(moves)):
        try:
            # Fresh session for each position
            sid = create_session()

            # Replay moves 0..i-1 to reach the position before move i
            for prev_move in moves[:i]:
                r = requests.post(
                    f"{BASE_URL}/move",
                    json={
                        "session_id": sid,
                        "move": prev_move,
                    },
                )
                r.raise_for_status()

            # Now search from this position with a cold TP — time this call only
            r = requests.post(
                f"{BASE_URL}/bestmove",
                json={
                    "session_id": sid,
                    "maxdepth": MAXDEPTH,
                },
            )
            r.raise_for_status()
            elapsed = r.elapsed.total_seconds()
            times.append(elapsed)
            print(f"  Move {i + 1}: {elapsed:.3f}s", flush=True)
        except (requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
            print(f"  Move {i + 1}: FAILED ({e.__class__.__name__})")
            print(f"  Server disconnected — stopping stateless run at move {i + 1}")
            break

    return times


def print_results(session_times, stateless_times):
    """Phase 3: Print comparison table."""
    n = min(len(session_times), len(stateless_times))
    if n == 0:
        print("\nNo data to compare.")
        return
    session_total = sum(session_times[:n])
    stateless_total = sum(stateless_times[:n])

    print(f"\n{'=' * 70}")
    print("SESSION vs STATELESS BENCHMARK")
    print(f"{'=' * 70}")
    print(f"Depth: {MAXDEPTH} | Moves: {n} | Starting position: standard")
    print(f"{'=' * 70}")
    print(f"")
    print(f"{'Move':<6}{'Session (s)':<14}{'Stateless (s)':<16}{'Delta (s)':<12}{'Speedup':<10}")
    print(f"{'-' * 70}")

    for i in range(n):
        s = session_times[i]
        st = stateless_times[i]
        delta = st - s
        speedup = st / s if s > 0 else float("inf")
        speedup_str = f"{speedup:.2f}x"
        print(f"{i + 1:<6}{s:<14.3f}{st:<16.3f}{delta:<+12.3f}{speedup_str:<10}")

    print(f"{'-' * 70}")
    total_delta = stateless_total - session_total
    total_speedup = stateless_total / session_total if session_total > 0 else float("inf")
    total_speedup_str = f"{total_speedup:.2f}x"
    print(f"{'Total':<6}{session_total:<14.3f}{stateless_total:<16.3f}{total_delta:<+12.3f}{total_speedup_str:<10}")
    print(f"{'=' * 70}")


def main():
    # Server connectivity check
    try:
        requests.get(f"{BASE_URL}/")
    except requests.exceptions.ConnectionError:
        print("\nError: Could not connect to server.")
        print(f"  Make sure the server is running: make up")
        return

    moves, session_times = session_run()
    stateless_times = stateless_run(moves)
    print_results(session_times, stateless_times)
    print("\nBenchmark complete!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user.")
