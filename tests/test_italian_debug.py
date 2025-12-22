#!/usr/bin/env python3
"""
Debug why Italian Opening position doesn't respect movetime.
"""

import requests
import time

BASE_URL = "http://localhost:5500"

# The problematic position
ITALIAN_FEN = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"

print("Testing Italian Opening with different movetimes...")
print(f"FEN: {ITALIAN_FEN}\n")

for movetime_ms in [2000, 4000, 7000, 10000]:
    print(f"\n{'='*60}")
    print(f"Testing movetime={movetime_ms}ms ({movetime_ms/1000}s)")
    print(f"{'='*60}")

    payload = {
        "fen": ITALIAN_FEN,
        "movetime": movetime_ms,
        "maxdepth": 25,
        "precision": 0.0
    }

    start = time.time()
    try:
        response = requests.post(
            f"{BASE_URL}/bestmove",
            json=payload,
            timeout=20  # Long timeout to see actual behavior
        )
        elapsed = time.time() - start

        print(f"Status: {response.status_code}")
        print(f"Actual time: {elapsed:.2f}s")

        if response.status_code == 200:
            data = response.json()
            print(f"Best move: {data.get('bestmoves', [[]])[0]}")
            print(f"Depth reached: {data.get('depth_reached', 'N/A')}")
            print(f"Check: {data.get('check', False)}")

            # Calculate overshoot
            expected = movetime_ms / 1000.0
            overshoot = elapsed - expected
            overshoot_pct = (overshoot / expected) * 100

            if overshoot > 0.5:  # More than 500ms over
                print(f"⚠️  OVERSHOOT: {overshoot:.2f}s ({overshoot_pct:.1f}% over budget)")
            else:
                print(f"✓ Within budget (+{overshoot:.2f}s)")
        else:
            print(f"Error: {response.text}")

    except requests.exceptions.Timeout:
        elapsed = time.time() - start
        print(f"✗ TIMEOUT after {elapsed:.2f}s")
    except Exception as e:
        print(f"✗ ERROR: {e}")

print("\n\nConclusion:")
print("If overshoot increases with movetime, the engine has a time management bug.")
print("Check server logs for depth progression: docker-compose logs | tail -50")
