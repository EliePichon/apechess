# Sunfish Tests

## Test Suites

| Test | Command | Duration | Purpose |
|------|---------|----------|---------|
| **Feature Tests** | `make test` | ~1 min | Validate top_n and ignore_squares features |
| **Performance** | `make test-perf` | ~2 min | Measure feature overhead |
| **Depth Analysis** | `make test-depth` | 15-20 min | Test fixed depth limits (8,10,12,15) |
| **Movetime Analysis** | `make test-movetime` | 5-10 min | Test time-limited search (2s,4s,7s,10s) |

## Quick Start

```bash
# Start server
make up

# Run all feature tests
make test

# Run performance analysis
make test-movetime
```

## Test Files

- `test_top_n.py` - Validates multi-move ranking
- `test_ignore_squares.py` - Validates piece filtering
- `test_performance.py` - Measures overhead of features
- `test_depth_performance.py` - Depth vs time analysis
- `test_movetime_performance.py` - Time-limited search analysis
- `test_error_cases.py` - Diagnostic tool for failures
- `test_italian_debug.py` - Debug Italian Opening position
- `test_depth_quick.py` - Quick depth tracking verification

## Documentation

See [docs/PERFORMANCE_TESTING.md](../docs/PERFORMANCE_TESTING.md) for detailed analysis and recommendations.
