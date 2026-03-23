#!/usr/bin/env python3
"""
Test script for the new top_n parameter in the bestmove endpoint.
"""

import requests
import json
import time

from helpers import BASE_URL

def test_bestmove_top_n(fen, top_n, description):
    """Test the bestmove endpoint with different top_n values."""
    print(f"\n{'='*60}")
    print(f"Test: {description}")
    print(f"FEN: {fen}")
    print(f"top_n: {top_n}")
    print(f"{'='*60}")

    payload = {
        "fen": fen,
        "maxdepth": 6,  # Use lower depth for faster testing
        "top_n": top_n
    }

    start_time = time.time()
    response = requests.post(f"{BASE_URL}/bestmove", json=payload)
    elapsed = time.time() - start_time

    if response.status_code == 200:
        data = response.json()
        print(f"✓ Success (took {elapsed:.2f}s)")
        print(f"  Best move: {data.get('bestmove')}")
        print(f"  Score: {data.get('score')}")
        print(f"  Check: {data.get('check')}")
        print(f"  All moves ({len(data.get('allmoves', []))}):")
        for i, (move, score) in enumerate(data.get('allmoves', [])[:10], 1):
            print(f"    {i}. {move}: {score}")
        if len(data.get('allmoves', [])) > 10:
            print(f"    ... and {len(data.get('allmoves', [])) - 10} more")
        return elapsed, len(data.get('allmoves', []))
    else:
        print(f"✗ Error: {response.status_code}")
        print(f"  {response.text}")
        return None, None

def main():
    print("Testing top_n parameter implementation")
    print("Make sure the server is running on port 5500!")

    # Test positions
    start_pos = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    middlegame = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"

    results = []

    # Test 1: top_n=1 (fast path)
    elapsed, num_moves = test_bestmove_top_n(start_pos, 1, "Fast path: top_n=1")
    if elapsed:
        results.append(("top_n=1", elapsed, num_moves))

    time.sleep(0.5)

    # Test 2: top_n=5
    elapsed, num_moves = test_bestmove_top_n(start_pos, 5, "Standard path: top_n=5")
    if elapsed:
        results.append(("top_n=5", elapsed, num_moves))

    time.sleep(0.5)

    # Test 3: top_n=10 (default)
    elapsed, num_moves = test_bestmove_top_n(start_pos, 10, "Standard path: top_n=10 (default)")
    if elapsed:
        results.append(("top_n=10", elapsed, num_moves))

    time.sleep(0.5)

    # Test 4: top_n=20
    elapsed, num_moves = test_bestmove_top_n(middlegame, 20, "Standard path: top_n=20 on middlegame")
    if elapsed:
        results.append(("top_n=20", elapsed, num_moves))

    # Print summary
    if results:
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"{'Configuration':<15} {'Time (s)':<12} {'Moves returned':<15}")
        print(f"{'-'*60}")
        for config, elapsed, num_moves in results:
            print(f"{config:<15} {elapsed:<12.2f} {num_moves:<15}")

        # Compare top_n=1 vs top_n=10
        if len(results) >= 3:
            time_1 = results[0][1]
            time_10 = results[2][1]
            overhead = ((time_10 - time_1) / time_1) * 100
            print(f"\nOverhead for top_n=10 vs top_n=1: {overhead:.1f}%")

if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("\n✗ Error: Could not connect to server.")
        print("  Make sure the Flask server is running: python server.py")
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
