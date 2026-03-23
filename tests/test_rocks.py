#!/usr/bin/env python3
"""
Test script for the Rocks ('O') feature - immovable obstacles on the board.

Rocks are neutral pieces that:
- Block all pieces EXCEPT knights (knights jump over them)
- Cannot be moved or captured
- Are marked as 'O' in FEN notation
"""

import requests
import json

from helpers import BASE_URL

def test_rock_blocks_sliding_piece(fen, piece_name, square_from, blocked_squares, allowed_squares, description):
    """Test that rocks block sliding pieces (rook, bishop, queen)."""
    print(f"\n{'='*70}")
    print(f"Test: {description}")
    print(f"FEN: {fen}")
    print(f"{'='*70}")

    payload = {
        "fen": fen,
        "maxdepth": 4
    }

    response = requests.post(f"{BASE_URL}/getmoves", json=payload)

    if response.status_code == 200:
        data = response.json()
        moves_dict = data.get('moves', {})

        if square_from in moves_dict:
            piece_moves = moves_dict[square_from]
            print(f"\n✓ {piece_name} at {square_from} can move to: {piece_moves}")

            # Check that blocked squares are NOT in moves
            for blocked_sq in blocked_squares:
                blocked_move = f"{square_from}{blocked_sq}"
                if blocked_move in piece_moves:
                    print(f"✗ ERROR: {piece_name} should be blocked by rock, but {blocked_move} is in moves!")
                    return False
                else:
                    print(f"✓ Correctly blocked: {blocked_move} not in moves")

            # Check that allowed squares ARE in moves
            for allowed_sq in allowed_squares:
                allowed_move = f"{square_from}{allowed_sq}"
                if allowed_move not in piece_moves:
                    print(f"✗ ERROR: {piece_name} should be able to reach {allowed_sq}, but {allowed_move} is not in moves!")
                    return False
                else:
                    print(f"✓ Correctly allowed: {allowed_move} in moves")

            print(f"\n✓ Test PASSED: Rock correctly blocks {piece_name}")
            return True
        else:
            print(f"✗ ERROR: No moves found for {piece_name} at {square_from}")
            return False
    else:
        print(f"✗ Error: {response.status_code}")
        print(f"  {response.text}")
        return False


def test_knight_jumps_over_rock(fen, description):
    """Test that knights can jump over rocks."""
    print(f"\n{'='*70}")
    print(f"Test: {description}")
    print(f"FEN: {fen}")
    print(f"{'='*70}")

    payload = {
        "fen": fen,
        "maxdepth": 4
    }

    response = requests.post(f"{BASE_URL}/getmoves", json=payload)

    if response.status_code == 200:
        data = response.json()
        moves_dict = data.get('moves', {})

        # Expected knight moves from d2: c4, e4, f3, f1, b3, b1
        expected_destinations = ['c4', 'e4', 'f3', 'f1', 'b3', 'b1']

        if 'd2' in moves_dict:
            knight_moves = moves_dict['d2']
            print(f"\n✓ Knight at d2 can move to: {knight_moves}")

            all_present = True
            for dest in expected_destinations:
                move = f"d2{dest}"
                if move in knight_moves:
                    print(f"✓ Knight can jump to {dest}")
                else:
                    print(f"✗ ERROR: Knight should be able to jump to {dest}, but {move} not in moves!")
                    all_present = False

            if all_present:
                print(f"\n✓ Test PASSED: Knight can jump over rock at d4")
                return True
            else:
                return False
        else:
            print(f"✗ ERROR: No moves found for knight at d2")
            return False
    else:
        print(f"✗ Error: {response.status_code}")
        print(f"  {response.text}")
        return False


def test_rock_blocks_check(fen, description, should_be_in_check):
    """Test that rocks block check detection."""
    print(f"\n{'='*70}")
    print(f"Test: {description}")
    print(f"FEN: {fen}")
    print(f"Expected check: {should_be_in_check}")
    print(f"{'='*70}")

    payload = {
        "fen": fen
    }

    response = requests.post(f"{BASE_URL}/ischeck", json=payload)

    if response.status_code == 200:
        data = response.json()
        is_check = data.get('check', False)

        print(f"\n✓ Check status: {is_check}")

        if is_check == should_be_in_check:
            print(f"✓ Test PASSED: Check detection correct")
            return True
        else:
            print(f"✗ ERROR: Expected check={should_be_in_check}, got {is_check}")
            return False
    else:
        print(f"✗ Error: {response.status_code}")
        print(f"  {response.text}")
        return False


def test_bestmove_with_rocks(fen, description):
    """Test that bestmove calculation works with rocks."""
    print(f"\n{'='*70}")
    print(f"Test: {description}")
    print(f"FEN: {fen}")
    print(f"{'='*70}")

    payload = {
        "fen": fen,
        "maxdepth": 6,
        "top_n": 3
    }

    response = requests.post(f"{BASE_URL}/bestmove", json=payload)

    if response.status_code == 200:
        data = response.json()
        best_moves = data.get('bestmoves', [])

        print(f"\n✓ Best moves calculated successfully:")
        for i, (move, score) in enumerate(best_moves, 1):
            print(f"  {i}. {move}: {score}")

        print(f"\n✓ Test PASSED: Bestmove works with rocks")
        return True
    else:
        print(f"✗ Error: {response.status_code}")
        print(f"  {response.text}")
        return False


def main():
    print("="*70)
    print("Testing Rocks ('O') Feature Implementation")
    print("Make sure the server is running on port 5500!")
    print("="*70)

    results = []

    # Test Case 1: Rock blocks rook
    results.append(test_rock_blocks_sliding_piece(
        fen="8/8/8/8/3O4/8/3R4/8 w - - 0 1",
        piece_name="Rook",
        square_from="d2",
        blocked_squares=["d5", "d6", "d7", "d8"],
        allowed_squares=["d3"],
        description="Rock at d4 blocks rook at d2"
    ))

    # Test Case 2: Knight jumps over rock
    results.append(test_knight_jumps_over_rock(
        fen="8/8/8/8/3O4/8/3N4/8 w - - 0 1",
        description="Knight at d2 can jump over rock at d4"
    ))

    # Test Case 3: Rock blocks bishop diagonal
    results.append(test_rock_blocks_sliding_piece(
        fen="8/8/8/8/3O4/8/1B6/8 w - - 0 1",
        piece_name="Bishop",
        square_from="b2",
        blocked_squares=["d4", "e5", "f6", "g7", "h8"],
        allowed_squares=["c3"],
        description="Rock at d4 blocks bishop at b2 on diagonal"
    ))

    # Test Case 4: Multiple rocks block queen
    results.append(test_rock_blocks_sliding_piece(
        fen="8/2O1O3/8/8/8/8/3Q4/8 w - - 0 1",
        piece_name="Queen",
        square_from="d2",
        blocked_squares=["c7", "c8", "e7", "e8"],
        allowed_squares=["d3", "d4", "d5", "d6", "c3", "e3"],
        description="Multiple rocks at c7 and e7 block queen at d2"
    ))

    # Test Case 5: Rock blocks pawn double move
    results.append(test_rock_blocks_sliding_piece(
        fen="8/8/8/8/3O4/8/3P4/8 w - - 0 1",
        piece_name="Pawn",
        square_from="d2",
        blocked_squares=["d4", "d5"],
        allowed_squares=["d3"],
        description="Rock at d4 blocks pawn double move from d2"
    ))

    # Test Case 6: Rock blocks check
    results.append(test_rock_blocks_check(
        fen="8/8/8/3k4/3O4/8/3R4/8 b - - 0 1",
        description="Rock at d4 blocks rook check on king at d5",
        should_be_in_check=False
    ))

    # Test Case 7: Bestmove calculation with rocks
    results.append(test_bestmove_with_rocks(
        fen="8/8/8/8/3O4/2n5/3N4/8 w - - 0 1",
        description="Calculate bestmove in position with rock at d4"
    ))

    # Test Case 8: Lowercase 'o' rocks (black rocks) should not be capturable by white pieces
    # This is the exact bug from todo.md: FEN with lowercase 'o' rocks
    results.append(test_rock_blocks_sliding_piece(
        fen="1k3p2/8/1o1pp3/8/3o1P2/4KB2/3P2P1/8 w - - 0 1",
        piece_name="King",
        square_from="e3",
        blocked_squares=["d4"],  # Rock at d4 should NOT be capturable
        allowed_squares=["e4", "e2", "d3", "f2"],
        description="Lowercase rock at d4 is not capturable by king at e3"
    ))

    # Test Case 9: Black to move - rocks should block after rotation (O becomes o via swapcase)
    results.append(test_rock_blocks_sliding_piece(
        fen="8/3r4/8/3O4/8/8/8/k7 b - - 0 1",
        piece_name="d7",
        square_from="d7",
        blocked_squares=["d4", "d3", "d2", "d1"],
        allowed_squares=["d6"],
        description="Rock at d5 blocks black rook at d7 after rotation"
    ))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("\n✓ ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
