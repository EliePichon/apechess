# Sunfish Documentation

## Performance & Error Analysis

- **[PERFORMANCE_TESTING.md](PERFORMANCE_TESTING.md)** - Performance test guide, results interpretation, difficulty calibration
- **[ERROR_INVESTIGATION.md](ERROR_INVESTIGATION.md)** - Detailed error analysis and debugging guide
- **[CONCURRENCY_FIX.md](CONCURRENCY_FIX.md)** - Critical concurrency bug fix summary

## Key Findings

### Concurrency Bug (Fixed)
Multiple concurrent requests were overwriting `sys.stdin/stdout`, causing random failures. Fixed with global serialization lock.

### Time Management
Iterative deepening only checks time between depths. Some positions overshoot movetime significantly when depth stages are expensive. Mitigated with generous timeout buffers.

### Depth vs Time Tradeoffs

| Depth | Time (Early) | Time (Mid) | Time (End) |
|-------|--------------|------------|------------|
| 6     | ~1.5s        | ~2.0s      | ~0.5s      |
| 7     | ~3.5s        | ~4.5s      | ~0.7s      |
| 8     | ~6-15s       | ~8s        | ~0.7s      |
| 9+    | Varies       | Varies     | ~0.8s      |

Endgame positions reach deeper faster due to fewer pieces.

## Recommended Settings

See [PERFORMANCE_TESTING.md](PERFORMANCE_TESTING.md) for difficulty level calibration.
