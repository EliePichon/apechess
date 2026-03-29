#!/usr/bin/env python3
"""
Test the specific error cases from the movetime benchmark.
Helps diagnose why certain positions fail.
"""

import requests
import json

from helpers import BASE_URL

# The positions that failed in the benchmark
ERROR_CASES = [
    {
        "name": "Early Game - Italian Opening (7s timeout)",
        "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
        "movetime": 7000,
        "maxdepth": 25,
    },
    {
        "name": "Early Game - Queen's Gambit (10s 500 error)",
        "fen": "rnbqkb1r/ppp2ppp/4pn2/3p4/2PP4/2N2N2/PP2PPPP/R1BQKB1R b KQkq - 2 4",
        "movetime": 10000,
        "maxdepth": 25,
    },
    {
        "name": "Midgame - Complex Position (7s 500 error)",
        "fen": "r1bq1rk1/pp2bppp/2n1pn2/3p4/2PP4/1PN1PN2/PB2BPPP/R2QK2R w KQ - 2 9",
        "movetime": 7000,
        "maxdepth": 25,
    },
]


def test_position(test_case, verbose=True):
    """Test a single position and return detailed results."""
    print(f"\n{'=' * 80}")
    print(f"Testing: {test_case['name']}")
    print(f"{'=' * 80}")
    print(f"FEN: {test_case['fen']}")
    print(f"Movetime: {test_case['movetime']}ms")
    print(f"Maxdepth: {test_case['maxdepth']}")
    print()

    payload = {"fen": test_case["fen"], "movetime": test_case["movetime"], "maxdepth": test_case["maxdepth"], "precision": 0.0}

    try:
        print("Sending request...")
        response = requests.post(
            f"{BASE_URL}/bestmove",
            json=payload,
            timeout=(test_case["movetime"] / 1000.0) + 15,  # Extra buffer
        )

        print(f"Status code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✓ SUCCESS")
            print(f"Response: {json.dumps(data, indent=2)}")
            return "SUCCESS"
        else:
            print(f"✗ HTTP ERROR {response.status_code}")
            print(f"Response: {response.text}")
            return f"HTTP_{response.status_code}"

    except requests.exceptions.Timeout:
        print(f"✗ REQUEST TIMEOUT")
        return "TIMEOUT"

    except Exception as e:
        print(f"✗ EXCEPTION: {e}")
        return f"EXCEPTION: {e}"


def main():
    print("\n" + "=" * 80)
    print("ERROR CASE DIAGNOSTIC TEST")
    print("=" * 80)
    print(f"Testing {len(ERROR_CASES)} positions that failed in benchmark")
    print()

    results = []
    for test_case in ERROR_CASES:
        result = test_position(test_case)
        results.append({"name": test_case["name"], "result": result})

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    for r in results:
        print(f"{r['name']:<60} {r['result']}")

    success_count = sum(1 for r in results if r["result"] == "SUCCESS")
    print(f"\n{success_count}/{len(results)} tests passed")

    if success_count < len(results):
        print("\n⚠ Some tests failed. Check server logs for details:")
        print("  docker-compose logs -f")


if __name__ == "__main__":
    try:
        # Check server
        response = requests.get(f"{BASE_URL}/", timeout=2)
    except requests.exceptions.ConnectionError:
        print("\n✗ Error: Could not connect to server.")
        print(f"  Make sure the server is running: make up\n")
        exit(1)
    except:
        pass

    main()
