#!/usr/bin/env python3
"""
Test script for the ignore_squares parameter in the bestmove endpoint.
"""

import requests
import json

BASE_URL = "http://localhost:5500"

def test_ignore_squares(fen, ignore_squares, description):
    """Test the bestmove endpoint with ignore_squares parameter."""
    print(f"\n{'='*70}")
    print(f"Test: {description}")
    print(f"FEN: {fen}")
    print(f"Ignoring squares: {ignore_squares}")
    print(f"{'='*70}")

    # Test without ignoring squares
    payload_normal = {
        "fen": fen,
        "maxdepth": 4,
        "top_n": 5
    }

    response_normal = requests.post(f"{BASE_URL}/bestmove", json=payload_normal)

    if response_normal.status_code == 200:
        data_normal = response_normal.json()
        print(f"\n✓ Without ignore_squares:")
        print(f"  Best move: {data_normal.get('bestmove')}")
        print(f"  Top 5 moves:")
        for i, (move, score) in enumerate(data_normal.get('allmoves', [])[:5], 1):
            square_from = move[:2]
            print(f"    {i}. {move} (from {square_from}): {score}")
    else:
        print(f"✗ Error: {response_normal.status_code}")
        return

    # Test with ignoring squares
    payload_ignore = {
        "fen": fen,
        "maxdepth": 4,
        "top_n": 5,
        "ignore_squares": ignore_squares
    }

    response_ignore = requests.post(f"{BASE_URL}/bestmove", json=payload_ignore)

    if response_ignore.status_code == 200:
        data_ignore = response_ignore.json()
        print(f"\n✓ With ignore_squares {ignore_squares}:")
        print(f"  Best move: {data_ignore.get('bestmove')}")
        print(f"  Top 5 moves:")
        for i, (move, score) in enumerate(data_ignore.get('allmoves', [])[:5], 1):
            square_from = move[:2]
            print(f"    {i}. {move} (from {square_from}): {score}")

        # Verify that no moves start from ignored squares
        all_moves = data_ignore.get('allmoves', [])
        for move, score in all_moves:
            square_from = move[:2]
            if square_from in ignore_squares:
                print(f"\n✗ ERROR: Move {move} starts from ignored square {square_from}!")
                return

        print(f"\n✓ Verification: No moves from ignored squares found")
    else:
        print(f"✗ Error: {response_ignore.status_code}")
        print(f"  {response_ignore.text}")

def main():
    print("Testing ignore_squares parameter implementation")
    print("Make sure the server is running on port 5500!")

    start_pos = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    # Test 1: Ignore knight squares (g1, b1)
    test_ignore_squares(
        start_pos,
        ["g1", "b1"],
        "Starting position - ignore both knights"
    )

    # Test 2: Ignore all pawn squares
    test_ignore_squares(
        start_pos,
        ["a2", "b2", "c2", "d2", "e2", "f2", "g2", "h2"],
        "Starting position - ignore all pawns"
    )

    # Test 3: Complex middlegame position
    middlegame = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
    test_ignore_squares(
        middlegame,
        ["f3", "c4"],
        "Middlegame - ignore knight on f3 and bishop on c4"
    )

    # Test 4: Ignore best move square
    test_ignore_squares(
        start_pos,
        ["g1"],
        "Starting position - ignore likely best move (g1 knight)"
    )

    print("\n" + "="*70)
    print("All tests completed!")
    print("="*70)

if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("\n✗ Error: Could not connect to server.")
        print("  Make sure the Flask server is running: docker-compose up")
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
