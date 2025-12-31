# Performance Testing Guide

This document describes the performance testing infrastructure for the Sunfish chess engine.

## Available Test Suites

### 1. `test_depth_performance.py` - Depth-Limited Performance Analysis

Tests the engine with fixed depth limits to understand computational requirements.

**Parameters:**
- Depths: 8, 10, 12, 15
- Timeout: 15 seconds per test
- Precision: 0% (deterministic play)
- Positions: 6 total (2 early game, 2 midgame, 2 endgame)

**Usage:**
```bash
make test-depth
# or
python3 test_depth_performance.py
```

**Output:**
- Results table organized by game phase
- Average times by phase and depth
- Timeout frequency analysis
- Runtime: ~15-20 minutes

**Use Case:** Determine which depth settings work for different game phases and difficulty levels.

---

### 2. `test_movetime_performance.py` - Time-Limited Performance Analysis (NEW)

Tests the engine with time limits and tracks actual depth reached via iterative deepening.

**Parameters:**
- Max depth: 25 (limit, not target)
- Movetimes: 2s, 4s, 7s, 10s
- Precision: 0% (deterministic play)
- Positions: 6 total (2 early game, 2 midgame, 2 endgame)

**Usage:**
```bash
make test-movetime
# or
python3 test_movetime_performance.py
```

**Output:**
- Actual search time table
- **Depth reached table** (shows max depth achieved during iterative deepening)
- Time limit compliance analysis
- Average times by phase and movetime
- Runtime: ~5-10 minutes

**Use Case:**
- Configure time-based difficulty levels
- Understand depth/time tradeoffs
- Ensure engine respects time limits
- See how deep the engine can search in realistic time budgets

---

### 3. `test_performance.py` - Feature Overhead Benchmarks

Tests performance impact of different features (precision blur, top_n, ignore_squares).

**Usage:**
```bash
make test-perf
# or
python3 test_performance.py
```

**Output:**
- Baseline vs feature overhead comparison
- Overhead percentages and factors

---

### 4. Quick Depth Verification Test

Verifies that `depth_reached` is correctly returned in API responses.

**Usage:**
```bash
python3 test_depth_quick.py
```

## New Feature: Depth Tracking

### API Changes

The `/bestmove` endpoint now returns the actual depth reached during search:

**Request:**
```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "movetime": 3000,
  "maxdepth": 25,
  "precision": 0.0
}
```

**Response:**
```json
{
  "bestmoves": [["e2e4", 45]],
  "check": false,
  "depth_reached": 9
}
```

### Implementation Details

**UCI Protocol Update** ([tools/uci.py:251-256](tools/uci.py#L251-L256)):
- `final_depth` variable tracks maximum depth reached during iterative deepening
- Included in bestmove output: `bestmove e2e4 score 45 depth 9`

**Server Update** ([server.py:231-239](server.py#L231-L239)):
- Parses `depth` field from UCI response
- Includes `depth_reached` in JSON response (if available)

### Benefits

1. **Performance Insights**: See how deep the engine searches in given time
2. **Difficulty Calibration**: Match AI strength to actual search depth
3. **Time Budget Analysis**: Understand depth/time tradeoffs for different positions
4. **Debug Tool**: Verify iterative deepening is working correctly

## Interpreting Results

### Depth-Limited Tests (test_depth_performance.py)

- **Early Game**: Usually completes faster (fewer pieces, simpler positions)
- **Midgame**: Slowest phase (most complex positions)
- **Endgame**: Fast again (fewer pieces, simpler tactics)
- **Timeouts**: Indicate depth is too high for time budget

**Example interpretation:**
```
Depth 8:  1-2s   (Good for fast/easy AI)
Depth 10: 3-5s   (Good for medium AI)
Depth 12: 8-12s  (Good for hard AI)
Depth 15: Often timeouts (very hard/analysis mode)
```

### Time-Limited Tests (test_movetime_performance.py)

- **Compliance %**: How often engine finishes within time limit
- **Depth Reached**: Shows actual search quality achieved
- **Phase Differences**: Endgames reach deeper than midgames

**Example interpretation:**
```
2s movetime  → depth 6-7  (Quick/beginner AI)
4s movetime  → depth 7-9  (Medium AI)
7s movetime  → depth 9-11 (Hard AI)
10s movetime → depth 10-13 (Expert AI)
```

### Recommended Settings by Difficulty

Based on test results, configure difficulty levels:

| Level      | Method         | Setting              | Expected Depth | Time Budget |
|------------|----------------|----------------------|----------------|-------------|
| Beginner   | movetime       | 2000ms               | 6-7            | 2s          |
| Easy       | movetime       | 4000ms               | 7-9            | 4s          |
| Medium     | maxdepth       | 8                    | 8              | 1-3s        |
| Hard       | movetime       | 7000ms               | 9-11           | 7s          |
| Expert     | maxdepth       | 10                   | 10             | 3-8s        |
| Master     | movetime       | 10000ms              | 10-13          | 10s         |
| Analysis   | maxdepth       | 12-15                | 12-15          | 5-20s       |

Add `precision` parameter for additional fine-tuning:
- `precision: 0.0` - Full strength (use above settings)
- `precision: 0.1` - Slight weakening (~10% score variation)
- `precision: 0.2` - Moderate weakening (~20% score variation)
- `precision: 0.3` - Significant weakening (~30% score variation)

## Running All Tests

To run the complete test suite:

```bash
# Start server
make up

# Run all performance tests (takes ~25-35 minutes total)
make test-perf     # ~2 minutes
make test-movetime # ~5-10 minutes
make test-depth    # ~15-20 minutes

# Quick verification
python3 test_depth_quick.py
```

## Server Logs

To see detailed search progress during tests:

```bash
make logs
```

This shows:
- UCI commands received
- Search depth progress
- Node counts
- Time elapsed
- Best move selection

## Notes

- All tests use **0% precision blur** for consistent, deterministic results
- Tests measure **actual search time** (not including network overhead)
- **Endgame positions** generally allow deeper search in less time
- **Midgame positions** are most computationally expensive
- Time compliance includes **+500ms tolerance** for overhead
- Docker container may add slight overhead vs native execution
