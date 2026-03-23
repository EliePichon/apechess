#!/usr/bin/env python3
"""
Comprehensive depth performance benchmark for the Sunfish chess engine.
Tests various maxdepth settings across different game phases.
"""

import requests
import time
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from helpers import BASE_URL

# Test positions for different game phases
TEST_POSITIONS = {
    "early_game_1": {
        "name": "Early Game - Italian Opening",
        "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"
    },
    "early_game_2": {
        "name": "Early Game - Queen's Gambit",
        "fen": "rnbqkb1r/ppp2ppp/4pn2/3p4/2PP4/2N2N2/PP2PPPP/R1BQKB1R b KQkq - 2 4"
    },
    "midgame_1": {
        "name": "Midgame - Complex Position",
        "fen": "r1bq1rk1/pp2bppp/2n1pn2/3p4/2PP4/1PN1PN2/PB2BPPP/R2QK2R w KQ - 2 9"
    },
    "midgame_2": {
        "name": "Midgame - Tactical",
        "fen": "r2qkb1r/ppp2ppp/2n1bn2/3p4/3P4/2NBPN2/PPP2PPP/R1BQK2R w KQkq - 1 7"
    },
    "endgame_1": {
        "name": "Endgame - Rook & Pawns",
        "fen": "8/5pk1/6p1/3R4/5P2/6P1/r5K1/8 w - - 0 1"
    },
    "endgame_2": {
        "name": "Endgame - Queen vs Rook",
        "fen": "8/8/4k3/8/8/3QK3/8/5r2 w - - 0 1"
    }
}

@dataclass
class BenchmarkResult:
    """Container for benchmark results."""
    game_phase: str
    position_name: str
    depth: int
    time_seconds: float
    best_move: str
    timed_out: bool
    error: Optional[str] = None


class DepthPerformanceTest:
    """Performance testing across different depths and game phases."""

    def __init__(self, max_movetime: int = 15000):
        """
        Initialize the test runner.

        Args:
            max_movetime: Maximum time in milliseconds (default: 15000ms = 15s)
        """
        self.max_movetime = max_movetime
        self.results: List[BenchmarkResult] = []

    def run_single_test(
        self,
        position_key: str,
        position_data: Dict,
        depth: int
    ) -> BenchmarkResult:
        """
        Run a single benchmark test.

        Args:
            position_key: Key identifying the position (e.g., "early_game_1")
            position_data: Dictionary with "name" and "fen" keys
            depth: Search depth to use

        Returns:
            BenchmarkResult with timing and move data
        """
        game_phase = position_key.rsplit('_', 1)[0].replace('_', ' ').title()

        print(f"  Testing {position_data['name']} at depth {depth}...", end=" ", flush=True)

        payload = {
            "fen": position_data["fen"],
            "maxdepth": depth,
            "movetime": self.max_movetime,
            "precision": 0.0,  # 0% precision blur
            "top_n": 1
        }

        start_time = time.time()

        try:
            response = requests.post(f"{BASE_URL}/bestmove", json=payload, timeout=20)
            elapsed = time.time() - start_time

            if response.status_code != 200:
                print(f"✗ FAILED (HTTP {response.status_code})")
                return BenchmarkResult(
                    game_phase=game_phase,
                    position_name=position_data["name"],
                    depth=depth,
                    time_seconds=0,
                    best_move="",
                    timed_out=False,
                    error=f"HTTP {response.status_code}"
                )

            data = response.json()
            best_move = data.get("bestmoves", [["(none)", 0]])[0][0]
            timed_out = elapsed >= (self.max_movetime / 1000.0)

            status = "⏱ TIMEOUT" if timed_out else "✓"
            print(f"{status} ({elapsed:.2f}s) - {best_move}")

            return BenchmarkResult(
                game_phase=game_phase,
                position_name=position_data["name"],
                depth=depth,
                time_seconds=elapsed,
                best_move=best_move,
                timed_out=timed_out
            )

        except requests.exceptions.Timeout:
            elapsed = time.time() - start_time
            print(f"✗ TIMEOUT ({elapsed:.2f}s)")
            return BenchmarkResult(
                game_phase=game_phase,
                position_name=position_data["name"],
                depth=depth,
                time_seconds=elapsed,
                best_move="",
                timed_out=True,
                error="Request timeout"
            )

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"✗ ERROR - {e}")
            return BenchmarkResult(
                game_phase=game_phase,
                position_name=position_data["name"],
                depth=depth,
                time_seconds=elapsed,
                best_move="",
                timed_out=False,
                error=str(e)
            )

    def run_all_tests(self, depths: List[int]):
        """
        Run all test combinations.

        Args:
            depths: List of search depths to test (e.g., [8, 10, 12, 15])
        """
        print(f"\n{'='*80}")
        print("SUNFISH DEPTH PERFORMANCE BENCHMARK")
        print(f"{'='*80}")
        print(f"Server: {BASE_URL}")
        print(f"Max movetime: {self.max_movetime}ms ({self.max_movetime/1000}s)")
        print(f"Precision blur: 0% (deterministic play)")
        print(f"Depths to test: {depths}")
        print(f"Positions: {len(TEST_POSITIONS)} (across 3 game phases)")
        print(f"Total tests: {len(depths) * len(TEST_POSITIONS)}")
        print(f"{'='*80}\n")

        # Run all combinations
        for depth in depths:
            print(f"\n--- Depth {depth} ---")
            for position_key, position_data in TEST_POSITIONS.items():
                result = self.run_single_test(position_key, position_data, depth)
                self.results.append(result)

        print("\n")

    def print_results_table(self):
        """Print formatted results table organized by game phase."""
        print(f"\n{'='*80}")
        print("RESULTS TABLE")
        print(f"{'='*80}\n")

        # Group results by game phase
        phases = ["Early Game", "Midgame", "Endgame"]

        for phase in phases:
            phase_results = [r for r in self.results if r.game_phase == phase]
            if not phase_results:
                continue

            print(f"\n{phase.upper()}")
            print(f"{'-'*80}")

            # Get unique depths
            depths = sorted(set(r.depth for r in phase_results))

            # Get unique positions for this phase
            positions = sorted(set(r.position_name for r in phase_results),
                             key=lambda x: [r.position_name for r in phase_results].index(x))

            # Print header
            header = f"{'Position':<40}"
            for depth in depths:
                header += f"Depth {depth:2d}    "
            print(header)
            print(f"{'-'*80}")

            # Print data rows
            for position in positions:
                row = f"{position:<40}"
                for depth in depths:
                    # Find result for this position and depth
                    result = next(
                        (r for r in phase_results
                         if r.position_name == position and r.depth == depth),
                        None
                    )

                    if result is None:
                        row += f"{'N/A':<12}"
                    elif result.error:
                        row += f"{'ERROR':<12}"
                    elif result.timed_out:
                        row += f"{'>15.00s':<12}"
                    else:
                        row += f"{result.time_seconds:>6.2f}s    "

                print(row)

        print(f"\n{'='*80}\n")

    def print_analysis(self, depths: List[int]):
        """Print performance analysis and insights."""
        print(f"\n{'='*80}")
        print("PERFORMANCE ANALYSIS")
        print(f"{'='*80}\n")

        # Analyze by game phase
        print("Average time by game phase and depth:")
        print(f"{'-'*80}")
        print(f"{'Game Phase':<20}", end="")
        for depth in depths:
            print(f"Depth {depth:2d}    ", end="")
        print()
        print(f"{'-'*80}")

        phases = ["Early Game", "Midgame", "Endgame"]
        for phase in phases:
            print(f"{phase:<20}", end="")
            for depth in depths:
                phase_depth_results = [
                    r for r in self.results
                    if r.game_phase == phase and r.depth == depth and not r.error
                ]
                if phase_depth_results:
                    avg_time = sum(r.time_seconds for r in phase_depth_results) / len(phase_depth_results)
                    if any(r.timed_out for r in phase_depth_results):
                        print(f"{'>15.00s':<12}", end="")
                    else:
                        print(f"{avg_time:>6.2f}s    ", end="")
                else:
                    print(f"{'N/A':<12}", end="")
            print()

        # Timeout analysis
        print(f"\n\nTimeout occurrences:")
        print(f"{'-'*80}")
        timeout_count = sum(1 for r in self.results if r.timed_out)
        total_tests = len(self.results)
        print(f"Total timeouts: {timeout_count}/{total_tests} ({100*timeout_count/total_tests:.1f}%)")

        if timeout_count > 0:
            print("\nTimeouts by depth:")
            for depth in depths:
                depth_results = [r for r in self.results if r.depth == depth]
                depth_timeouts = sum(1 for r in depth_results if r.timed_out)
                print(f"  Depth {depth:2d}: {depth_timeouts}/{len(depth_results)} timeouts")

        print(f"\n{'='*80}\n")


def main():
    """Main entry point."""
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/", timeout=2)
    except requests.exceptions.ConnectionError:
        print("\n✗ Error: Could not connect to server.")
        print(f"  Make sure the server is running on {BASE_URL}")
        print(f"  Run: make up\n")
        return
    except requests.exceptions.Timeout:
        pass  # Timeout on root is fine

    # Configure test parameters
    depths_to_test = [8, 10, 12, 15]
    max_movetime_ms = 15000  # 15 seconds

    # Run tests
    tester = DepthPerformanceTest(max_movetime=max_movetime_ms)
    tester.run_all_tests(depths_to_test)

    # Print results
    tester.print_results_table()
    tester.print_analysis(depths_to_test)

    print("Benchmark complete!")
    print("\nNotes:")
    print("  - Times shown are actual search times (not including network overhead)")
    print("  - '>15.00s' indicates the search hit the timeout limit")
    print("  - All tests use 0% precision blur (deterministic, strongest play)")
    print("  - Depth 15+ may timeout frequently in complex positions\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user.\n")
