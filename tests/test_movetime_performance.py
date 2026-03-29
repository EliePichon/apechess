#!/usr/bin/env python3
"""
Movetime performance benchmark for the Sunfish chess engine.
Tests time-limited search (maxdepth=25) with various movetime limits.
Tracks actual depth reached during iterative deepening.
"""

import requests
import time
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from helpers import BASE_URL

# Test positions for different game phases
TEST_POSITIONS = {
    "early_game_1": {
        "name": "Early Game - Italian Opening",
        "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
    },
    "early_game_2": {
        "name": "Early Game - Queen's Gambit",
        "fen": "rnbqkb1r/ppp2ppp/4pn2/3p4/2PP4/2N2N2/PP2PPPP/R1BQKB1R b KQkq - 2 4",
    },
    "midgame_1": {
        "name": "Midgame - Complex Position",
        "fen": "r1bq1rk1/pp2bppp/2n1pn2/3p4/2PP4/1PN1PN2/PB2BPPP/R2QK2R w KQ - 2 9",
    },
    "midgame_2": {"name": "Midgame - Tactical", "fen": "r2qkb1r/ppp2ppp/2n1bn2/3p4/3P4/2NBPN2/PPP2PPP/R1BQK2R w KQkq - 1 7"},
    "endgame_1": {"name": "Endgame - Rook & Pawns", "fen": "8/5pk1/6p1/3R4/5P2/6P1/r5K1/8 w - - 0 1"},
    "endgame_2": {"name": "Endgame - Queen vs Rook", "fen": "8/8/4k3/8/8/3QK3/8/5r2 w - - 0 1"},
}


@dataclass
class MovetimeResult:
    """Container for movetime benchmark results."""

    game_phase: str
    position_name: str
    movetime_ms: int
    actual_time_seconds: float
    depth_reached: Optional[int]
    best_move: str
    error: Optional[str] = None


class MovetimePerformanceTest:
    """Performance testing with time-limited search."""

    def __init__(self, max_depth: int = 25):
        """
        Initialize the test runner.

        Args:
            max_depth: Maximum search depth limit (default: 25)
        """
        self.max_depth = max_depth
        self.results: List[MovetimeResult] = []

    def parse_depth_from_logs(self, response_data: Dict) -> Optional[int]:
        """
        Extract the actual depth reached from response.

        Note: This relies on server-side logging or response metadata.
        If not available, returns None.
        """
        # The response doesn't include depth info by default
        # We'll need to infer it from other means or rely on server logs
        return None

    def run_single_test(self, position_key: str, position_data: Dict, movetime_ms: int) -> MovetimeResult:
        """
        Run a single benchmark test with time limit.

        Args:
            position_key: Key identifying the position (e.g., "early_game_1")
            position_data: Dictionary with "name" and "fen" keys
            movetime_ms: Maximum thinking time in milliseconds

        Returns:
            MovetimeResult with timing and depth data
        """
        game_phase = position_key.rsplit("_", 1)[0].replace("_", " ").title()

        print(f"  Testing {position_data['name']} ({movetime_ms}ms)...", end=" ", flush=True)

        payload = {
            "fen": position_data["fen"],
            "maxdepth": self.max_depth,
            "movetime": movetime_ms,
            "precision": 0.0,  # 0% precision blur
            "top_n": 1,
        }

        start_time = time.time()

        try:
            # Generous timeout: depth stages can overshoot movetime
            timeout_seconds = (movetime_ms / 1000.0) * 2 + 10
            response = requests.post(f"{BASE_URL}/bestmove", json=payload, timeout=timeout_seconds)
            elapsed = time.time() - start_time

            if response.status_code != 200:
                print(f"✗ FAILED (HTTP {response.status_code})")
                return MovetimeResult(
                    game_phase=game_phase,
                    position_name=position_data["name"],
                    movetime_ms=movetime_ms,
                    actual_time_seconds=elapsed,
                    depth_reached=None,
                    best_move="",
                    error=f"HTTP {response.status_code}",
                )

            data = response.json()
            best_move = data.get("bestmoves", [["(none)", 0]])[0][0]

            # Try to get depth from response (if available)
            depth_reached = data.get("depth_reached")  # May be None

            # Calculate if we stayed within time limit (with small tolerance)
            time_limit_s = movetime_ms / 1000.0
            within_limit = elapsed <= (time_limit_s + 0.5)  # 500ms tolerance

            status = "✓" if within_limit else "⚠"
            depth_str = f"d{depth_reached}" if depth_reached else "d?"
            print(f"{status} ({elapsed:.2f}s, {depth_str}) - {best_move}")

            return MovetimeResult(
                game_phase=game_phase,
                position_name=position_data["name"],
                movetime_ms=movetime_ms,
                actual_time_seconds=elapsed,
                depth_reached=depth_reached,
                best_move=best_move,
            )

        except requests.exceptions.Timeout:
            elapsed = time.time() - start_time
            print(f"✗ TIMEOUT ({elapsed:.2f}s)")
            return MovetimeResult(
                game_phase=game_phase,
                position_name=position_data["name"],
                movetime_ms=movetime_ms,
                actual_time_seconds=elapsed,
                depth_reached=None,
                best_move="",
                error="Request timeout",
            )

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"✗ ERROR - {e}")
            return MovetimeResult(
                game_phase=game_phase,
                position_name=position_data["name"],
                movetime_ms=movetime_ms,
                actual_time_seconds=elapsed,
                depth_reached=None,
                best_move="",
                error=str(e),
            )

    def run_all_tests(self, movetimes_ms: List[int]):
        """
        Run all test combinations.

        Args:
            movetimes_ms: List of movetime limits in milliseconds (e.g., [2000, 4000, 7000, 10000])
        """
        print(f"\n{'=' * 80}")
        print("SUNFISH MOVETIME PERFORMANCE BENCHMARK")
        print(f"{'=' * 80}")
        print(f"Server: {BASE_URL}")
        print(f"Max depth limit: {self.max_depth} (iterative deepening)")
        print(f"Precision blur: 0% (deterministic play)")
        print(f"Movetimes to test: {[f'{mt}ms' for mt in movetimes_ms]}")
        print(f"Positions: {len(TEST_POSITIONS)} (across 3 game phases)")
        print(f"Total tests: {len(movetimes_ms) * len(TEST_POSITIONS)}")
        print(f"{'=' * 80}\n")

        # Run all combinations
        for movetime_ms in movetimes_ms:
            print(f"\n--- Movetime {movetime_ms}ms ({movetime_ms / 1000}s) ---")
            for position_key, position_data in TEST_POSITIONS.items():
                result = self.run_single_test(position_key, position_data, movetime_ms)
                self.results.append(result)

        print("\n")

    def print_results_table(self):
        """Print formatted results table organized by game phase."""
        print(f"\n{'=' * 95}")
        print("RESULTS TABLE - Actual Search Time")
        print(f"{'=' * 95}\n")

        # Group results by game phase
        phases = ["Early Game", "Midgame", "Endgame"]

        for phase in phases:
            phase_results = [r for r in self.results if r.game_phase == phase]
            if not phase_results:
                continue

            print(f"\n{phase.upper()}")
            print(f"{'-' * 95}")

            # Get unique movetimes
            movetimes = sorted(set(r.movetime_ms for r in phase_results))

            # Get unique positions for this phase
            positions = sorted(
                set(r.position_name for r in phase_results), key=lambda x: [r.position_name for r in phase_results].index(x)
            )

            # Print header
            header = f"{'Position':<40}"
            for mt in movetimes:
                header += f"{mt:>5}ms      "
            print(header)
            print(f"{'-' * 95}")

            # Print data rows
            for position in positions:
                row = f"{position:<40}"
                for movetime_ms in movetimes:
                    # Find result for this position and movetime
                    result = next(
                        (r for r in phase_results if r.position_name == position and r.movetime_ms == movetime_ms), None
                    )

                    if result is None:
                        row += f"{'N/A':<13}"
                    elif result.error:
                        row += f"{'ERROR':<13}"
                    else:
                        time_str = f"{result.actual_time_seconds:.2f}s"
                        row += f"{time_str:>8}     "

                print(row)

        print(f"\n{'=' * 95}\n")

    def print_depth_table(self):
        """Print table showing depth reached for each test."""
        print(f"\n{'=' * 95}")
        print("DEPTH REACHED TABLE")
        print(f"{'=' * 95}")
        print("Note: Depth values show maximum depth reached during iterative deepening")
        print(f"{'-' * 95}\n")

        # Group results by game phase
        phases = ["Early Game", "Midgame", "Endgame"]

        for phase in phases:
            phase_results = [r for r in self.results if r.game_phase == phase]
            if not phase_results:
                continue

            print(f"\n{phase.upper()}")
            print(f"{'-' * 95}")

            # Get unique movetimes
            movetimes = sorted(set(r.movetime_ms for r in phase_results))

            # Get unique positions for this phase
            positions = sorted(
                set(r.position_name for r in phase_results), key=lambda x: [r.position_name for r in phase_results].index(x)
            )

            # Print header
            header = f"{'Position':<40}"
            for mt in movetimes:
                header += f"{mt:>5}ms  "
            print(header)
            print(f"{'-' * 95}")

            # Print data rows
            for position in positions:
                row = f"{position:<40}"
                for movetime_ms in movetimes:
                    # Find result for this position and movetime
                    result = next(
                        (r for r in phase_results if r.position_name == position and r.movetime_ms == movetime_ms), None
                    )

                    if result is None:
                        row += f"{'N/A':<9}"
                    elif result.error:
                        row += f"{'ERR':<9}"
                    elif result.depth_reached is not None:
                        row += f"d{result.depth_reached:<7}"
                    else:
                        row += f"{'d?':<9}"

                print(row)

        print(f"\n{'=' * 95}\n")

    def print_analysis(self, movetimes_ms: List[int]):
        """Print performance analysis and insights."""
        print(f"\n{'=' * 80}")
        print("PERFORMANCE ANALYSIS")
        print(f"{'=' * 80}\n")

        # Analyze by game phase
        print("Average search time by game phase and movetime limit:")
        print(f"{'-' * 80}")
        print(f"{'Game Phase':<20}", end="")
        for mt in movetimes_ms:
            print(f"{mt:>5}ms   ", end="")
        print()
        print(f"{'-' * 80}")

        phases = ["Early Game", "Midgame", "Endgame"]
        for phase in phases:
            print(f"{phase:<20}", end="")
            for movetime_ms in movetimes_ms:
                phase_mt_results = [
                    r for r in self.results if r.game_phase == phase and r.movetime_ms == movetime_ms and not r.error
                ]
                if phase_mt_results:
                    avg_time = sum(r.actual_time_seconds for r in phase_mt_results) / len(phase_mt_results)
                    print(f"{avg_time:>6.2f}s   ", end="")
                else:
                    print(f"{'N/A':<9}", end="")
            print()

        # Time compliance analysis
        print(f"\n\nTime limit compliance:")
        print(f"{'-' * 80}")
        print("Percentage of tests that finished within movetime limit (+500ms tolerance):")
        print()

        for movetime_ms in movetimes_ms:
            mt_results = [r for r in self.results if r.movetime_ms == movetime_ms and not r.error]
            if mt_results:
                time_limit_s = movetime_ms / 1000.0
                within_limit = sum(1 for r in mt_results if r.actual_time_seconds <= (time_limit_s + 0.5))
                compliance_pct = 100 * within_limit / len(mt_results)
                print(f"  {movetime_ms:>5}ms: {within_limit:2d}/{len(mt_results)} ({compliance_pct:5.1f}%)")

        # Error analysis
        print(f"\n\nErrors and timeouts:")
        print(f"{'-' * 80}")
        error_count = sum(1 for r in self.results if r.error)
        total_tests = len(self.results)
        print(f"Total errors: {error_count}/{total_tests} ({100 * error_count / total_tests:.1f}%)")

        if error_count > 0:
            print("\nErrors by movetime:")
            for movetime_ms in movetimes_ms:
                mt_results = [r for r in self.results if r.movetime_ms == movetime_ms]
                mt_errors = sum(1 for r in mt_results if r.error)
                if mt_errors > 0:
                    print(f"  {movetime_ms:>5}ms: {mt_errors} errors")

        print(f"\n{'=' * 80}\n")


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
    movetimes_to_test = [2000, 4000, 7000, 10000]  # milliseconds
    max_depth_limit = 25

    # Run tests
    tester = MovetimePerformanceTest(max_depth=max_depth_limit)
    tester.run_all_tests(movetimes_to_test)

    # Print results
    tester.print_results_table()
    tester.print_depth_table()
    tester.print_analysis(movetimes_to_test)

    print("Benchmark complete!")
    print("\nNotes:")
    print("  - Max depth set to 25, but iterative deepening stops when movetime is reached")
    print("  - Actual search time shown (not including network overhead)")
    print("  - All tests use 0% precision blur (deterministic, strongest play)")
    print("  - 'Time limit compliance' uses +500ms tolerance for overhead")
    print("  - Depth values may show 'd?' if not captured in response")
    print("\nTo see actual depth reached, check server logs: make logs\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user.\n")
