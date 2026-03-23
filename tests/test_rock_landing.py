#!/usr/bin/env python3
"""
Test script for the Rock-Landing power feature.

Powered pieces (encoded as alternate ASCII characters) can land on rocks,
destroying them. Normal pieces remain blocked by rocks.

Character mapping:
  A=powered Pawn, C=powered Knight, D=powered Bishop,
  T=powered Rook, X=powered Queen, Y=powered King
"""

import requests
import json

from helpers import BASE_URL


def test_moves(fen, square_from, expected_present=None, expected_absent=None, description=""):
    """Generic test: check that certain moves are/aren't available."""
    print(f"\n{'='*70}")
    print(f"Test: {description}")
    print(f"FEN: {fen}")
    print(f"{'='*70}")

    expected_present = expected_present or []
    expected_absent = expected_absent or []

    response = requests.post(f"{BASE_URL}/getmoves", json={"fen": fen})

    if response.status_code != 200:
        print(f"  ERROR: {response.status_code} {response.text}")
        return False

    data = response.json()
    moves_dict = data.get('moves', {})

    if square_from not in moves_dict:
        if expected_present:
            print(f"  ERROR: No moves found for piece at {square_from}")
            print(f"  Available squares: {list(moves_dict.keys())}")
            return False
        else:
            print(f"  OK: No moves at {square_from} (as expected)")
            return True

    piece_moves = moves_dict[square_from]
    print(f"  Moves from {square_from}: {piece_moves}")

    ok = True
    for dest in expected_present:
        move_str = f"{square_from}{dest}"
        if move_str in piece_moves:
            print(f"  OK: {move_str} present")
        else:
            print(f"  FAIL: {move_str} should be present but isn't")
            ok = False

    for dest in expected_absent:
        move_str = f"{square_from}{dest}"
        if move_str not in piece_moves:
            print(f"  OK: {move_str} absent")
        else:
            print(f"  FAIL: {move_str} should be absent but is present")
            ok = False

    if ok:
        print(f"  PASSED")
    return ok


def test_bestmove(fen, description, expected_move=None):
    """Test that bestmove works with powered pieces."""
    print(f"\n{'='*70}")
    print(f"Test: {description}")
    print(f"FEN: {fen}")
    print(f"{'='*70}")

    response = requests.post(f"{BASE_URL}/bestmove", json={
        "fen": fen,
        "maxdepth": 6,
        "top_n": 3
    })

    if response.status_code != 200:
        print(f"  ERROR: {response.status_code} {response.text}")
        return False

    data = response.json()
    best_moves = data.get('bestmoves', [])
    print(f"  Best moves: {best_moves}")

    if expected_move and best_moves:
        if best_moves[0][0] == expected_move:
            print(f"  OK: Best move is {expected_move}")
        else:
            print(f"  NOTE: Best move is {best_moves[0][0]}, expected {expected_move}")

    print(f"  PASSED")
    return True


def main():
    print("="*70)
    print("Testing Rock-Landing Power Feature")
    print("Powered pieces: A(Pawn) C(Knight) D(Bishop) T(Rook) X(Queen) Y(King)")
    print("Make sure the server is running on port 5500!")
    print("="*70)

    results = []

    # --- Powered Rook (T) ---

    # T at d2 with rock at d4: can reach d4 (landing on rock) but not d5+
    results.append(test_moves(
        fen="8/8/8/8/3O4/8/3T4/8 w - - 0 1",
        square_from="d2",
        expected_present=["d3", "d4"],
        expected_absent=["d5", "d6", "d7", "d8"],
        description="Powered Rook lands on rock but doesn't slide through"
    ))

    # Normal Rook at d2 still blocked by rock at d4
    results.append(test_moves(
        fen="8/8/8/8/3O4/8/3R4/8 w - - 0 1",
        square_from="d2",
        expected_present=["d3"],
        expected_absent=["d4", "d5"],
        description="Normal Rook still blocked by rock (regression check)"
    ))

    # --- Powered Bishop (D) ---

    # D at b2 with rock at d4: can reach d4 but not e5+
    results.append(test_moves(
        fen="8/8/8/8/3O4/8/1D6/8 w - - 0 1",
        square_from="b2",
        expected_present=["c3", "d4"],
        expected_absent=["e5", "f6"],
        description="Powered Bishop lands on rock diagonally but stops"
    ))

    # --- Powered Queen (X) ---

    # X at d2 with rock at d4: can reach d4 on file, stops there
    results.append(test_moves(
        fen="8/8/8/8/3O4/8/3X4/8 w - - 0 1",
        square_from="d2",
        expected_present=["d3", "d4"],
        expected_absent=["d5"],
        description="Powered Queen lands on rock vertically but stops"
    ))

    # --- Powered Knight (C) ---

    # Knight at d2 with rock at c4: powered knight can land on c4
    results.append(test_moves(
        fen="8/8/8/8/2O5/8/3C4/8 w - - 0 1",
        square_from="d2",
        expected_present=["c4", "e4", "f3", "f1", "b3", "b1"],
        description="Powered Knight lands on rock at c4"
    ))

    # Normal Knight at d2 with rock at c4: can't land on rock
    results.append(test_moves(
        fen="8/8/8/8/2O5/8/3N4/8 w - - 0 1",
        square_from="d2",
        expected_present=["e4", "f3", "f1", "b3", "b1"],
        expected_absent=["c4"],
        description="Normal Knight blocked from landing on rock at c4"
    ))

    # --- Powered Pawn (A) ---

    # Powered Pawn at d3 with rock at d4: can advance onto rock
    results.append(test_moves(
        fen="8/8/8/8/3O4/3A4/8/8 w - - 0 1",
        square_from="d3",
        expected_present=["d4"],
        description="Powered Pawn advances onto rock"
    ))

    # Normal Pawn at d3 with rock at d4: blocked
    results.append(test_moves(
        fen="8/8/8/8/3O4/3P4/8/8 w - - 0 1",
        square_from="d3",
        expected_absent=["d4"],
        description="Normal Pawn blocked by rock (regression check)"
    ))

    # --- Powered King (Y) ---

    # Powered King at e3 with rock at d4: can move onto rock
    results.append(test_moves(
        fen="8/8/8/8/3O4/4Y3/8/8 w - - 0 1",
        square_from="e3",
        expected_present=["d4", "e4", "d3", "f3", "d2", "e2", "f2", "f4"],
        description="Powered King can move onto rock"
    ))

    # --- Black powered pieces (swapcase correctness) ---

    # Black powered rook (t in FEN) at d7 with rock at d5: can land on rock
    results.append(test_moves(
        fen="8/3t4/8/3O4/8/8/8/k7 b - - 0 1",
        square_from="d7",
        expected_present=["d6", "d5"],
        expected_absent=["d4", "d3"],
        description="Black powered Rook lands on rock after rotation"
    ))

    # Black normal rook at d7 with rock at d5: still blocked
    results.append(test_moves(
        fen="8/3r4/8/3O4/8/8/8/k7 b - - 0 1",
        square_from="d7",
        expected_present=["d6"],
        expected_absent=["d5", "d4"],
        description="Black normal Rook blocked by rock (regression)"
    ))

    # --- Bestmove with powered pieces ---

    results.append(test_bestmove(
        fen="8/8/8/8/3O4/8/3T4/8 w - - 0 1",
        description="Bestmove works with powered Rook and rock"
    ))

    # --- Mixed powered and normal pieces ---

    results.append(test_moves(
        fen="8/8/8/8/3O4/8/2RT4/8 w - - 0 1",
        square_from="d2",
        expected_present=["d3", "d4"],
        expected_absent=["d5"],
        description="Powered Rook at d2 lands on rock (normal Rook at c2 coexists)"
    ))

    results.append(test_moves(
        fen="8/8/8/8/3O4/8/2RT4/8 w - - 0 1",
        square_from="c2",
        expected_present=["c3"],
        expected_absent=["c4"],  # no rock in c-file; just check normal rook works
        description="Normal Rook at c2 works normally alongside powered Rook"
    ))

    # --- Powered Pawn Promotion ---

    # Powered Pawn at a7 promotes to powered pieces (C/D/T/X)
    results.append(test_moves(
        fen="8/A7/8/8/8/8/8/8 w - - 0 1",
        square_from="a7",
        expected_present=["a8c", "a8d", "a8t", "a8x"],
        expected_absent=["a8n", "a8q"],
        description="Powered Pawn promotes to powered pieces (C/D/T/X)"
    ))

    # Normal Pawn at a7 promotes to normal pieces (N/B/R/Q)
    results.append(test_moves(
        fen="8/P7/8/8/8/8/8/8 w - - 0 1",
        square_from="a7",
        expected_present=["a8n", "a8b", "a8r", "a8q"],
        expected_absent=["a8c", "a8x"],
        description="Normal Pawn still promotes to normal pieces (regression)"
    ))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("\nALL TESTS PASSED!")
        return 0
    else:
        print(f"\n{total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
