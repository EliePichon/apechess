#!/usr/bin/env python3
"""
Performance benchmark for the bestmove endpoint.
Tests different configurations to measure impact of various parameters.
"""

import requests
import timeit
import statistics
from typing import Dict, List, Tuple

from helpers import BASE_URL

# Test position (middlegame position with tactical complexity)
TEST_FEN = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"


class PerformanceTest:
    """Runner for performance benchmarks."""

    def __init__(self, fen: str = TEST_FEN, iterations: int = 1):
        self.fen = fen
        self.iterations = iterations
        self.results = []

    def run_request(self, config: Dict) -> float:
        """Execute a single request and return response time."""
        payload = {"fen": self.fen, **config}
        response = requests.post(f"{BASE_URL}/bestmove", json=payload)

        if response.status_code != 200:
            raise Exception(f"Request failed: {response.status_code} - {response.text}")

        return response.elapsed.total_seconds()

    def benchmark(self, name: str, config: Dict) -> Tuple[float, float, float]:
        """
        Run benchmark for a configuration.
        Returns (mean, stdev, min) in seconds.
        """
        print(f"  Running: {name}...", end=" ", flush=True)

        # Warmup request
        try:
            self.run_request(config)
        except Exception as e:
            print(f"FAILED - {e}")
            return (None, None, None)

        # Timed runs
        times = []
        for _ in range(self.iterations):
            try:
                elapsed = self.run_request(config)
                times.append(elapsed)
            except Exception as e:
                print(f"FAILED - {e}")
                return (None, None, None)

        mean = statistics.mean(times)
        stdev = statistics.stdev(times) if len(times) > 1 else 0
        min_time = min(times)

        print(f"✓ ({mean:.3f}s avg)")

        return (mean, stdev, min_time)

    def run_all(self):
        """Run all benchmark configurations."""
        print(f"\n{'=' * 70}")
        print("SUNFISH PERFORMANCE BENCHMARK")
        print(f"{'=' * 70}")
        print(f"Test FEN: {self.fen}")
        print(f"Iterations per test: {self.iterations}")
        print(f"Server: {BASE_URL}")
        print(f"{'=' * 70}\n")

        # Define test configurations
        configs = [
            # Baseline: Fast path (top_n=1, no precision)
            {"name": "Baseline (top_n=1, no precision)", "config": {"maxdepth": 6, "top_n": 1}},
            # With precision blur
            {"name": "With precision blur (0.15)", "config": {"maxdepth": 6, "top_n": 1, "precision": 0.15}},
            # Multiple moves (top_n=15)
            {"name": "Multi-move (top_n=15, no precision)", "config": {"maxdepth": 6, "top_n": 15}},
            # Multiple moves with precision
            {"name": "Multi-move (top_n=15, precision=0.15)", "config": {"maxdepth": 6, "top_n": 15, "precision": 0.15}},
            # Smaller multi-move set
            {"name": "Multi-move (top_n=5, no precision)", "config": {"maxdepth": 6, "top_n": 5}},
            # With ignore_squares
            {"name": "With ignore_squares (2 pieces)", "config": {"maxdepth": 6, "top_n": 1, "ignore_squares": ["f3", "c4"]}},
        ]

        # Run benchmarks
        for test in configs:
            mean, stdev, min_time = self.benchmark(test["name"], test["config"])
            self.results.append({"name": test["name"], "config": test["config"], "mean": mean, "stdev": stdev, "min": min_time})

        # Print results table
        self.print_results()

    def print_results(self):
        """Print formatted results table."""
        print(f"\n{'=' * 70}")
        print("RESULTS")
        print(f"{'=' * 70}")
        print(f"{'Configuration':<45} {'Mean':<12} {'StdDev':<12} {'Min':<10}")
        print(f"{'-' * 70}")

        baseline = None
        for i, result in enumerate(self.results):
            if result["mean"] is None:
                print(f"{result['name']:<45} {'FAILED':<12}")
                continue

            mean_str = f"{result['mean']:.3f}s"
            stdev_str = f"±{result['stdev']:.3f}s"
            min_str = f"{result['min']:.3f}s"

            print(f"{result['name']:<45} {mean_str:<12} {stdev_str:<12} {min_str:<10}")

            # Store baseline for comparison
            if i == 0:
                baseline = result["mean"]

        # Print overhead analysis
        if baseline is not None:
            print(f"\n{'=' * 70}")
            print("OVERHEAD ANALYSIS (vs Baseline)")
            print(f"{'=' * 70}")
            print(f"{'Configuration':<45} {'Overhead':<15} {'Factor':<10}")
            print(f"{'-' * 70}")

            for result in self.results[1:]:  # Skip baseline
                if result["mean"] is None:
                    continue

                overhead = result["mean"] - baseline
                overhead_pct = (overhead / baseline) * 100
                factor = result["mean"] / baseline

                overhead_str = f"+{overhead:.3f}s ({overhead_pct:+.1f}%)"
                factor_str = f"{factor:.2f}x"

                print(f"{result['name']:<45} {overhead_str:<15} {factor_str:<10}")

        print(f"{'=' * 70}\n")


def main():
    """Main entry point."""
    try:
        # Check if server is running
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 404:
            # 404 is fine, means Flask is running but no root route
            pass
    except requests.exceptions.ConnectionError:
        print("\n✗ Error: Could not connect to server.")
        print(f"  Make sure the server is running: make up")
        print(f"  Or manually: docker-compose up\n")
        return

    # Run benchmarks
    tester = PerformanceTest(iterations=5)
    tester.run_all()

    print("Benchmark complete!")
    print("\nTip: Run 'make logs' to see server-side performance data\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user.")
