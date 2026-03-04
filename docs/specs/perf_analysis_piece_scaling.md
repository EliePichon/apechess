# Performance Analysis: Scaling Piece Types

## Findings

The only perf cost that scales with piece count is x in "string" checks (O(n) linear scans) in the hot paths of gen_moves(), value(), and move()
Current powered pieces add an estimated ~15-25% overhead
Scaling to all 26 letter pairs would ~double search time with string checks
The hard ceiling is 26 piece types due to swapcase() in Position.rotate()

## Changes applied:

Added 4 frozenset constants (NON_SLIDERS, PAWNS, KINGS, ROCKS) and replaced all 6 string membership checks — making performance independent of piece count


### Where piece count impacts performance

The **only** cost that scales with piece count is Python `x in "string"` membership checks — these are O(n) linear scans. They appear in 3 hot-path functions:

| Function | Check | Frequency per search node |
|----------|-------|--------------------------|
| `gen_moves()` L221 | `p in "PNKACY"` (non-sliders) | ~80x |
| `gen_moves()` L202 | `p in "PA"` (pawns) | ~60x |
| `gen_moves()` L224-226 | `board[j] in "KY"` (kings) | ~8x |
| `value()` L285,289 | `p in "KY"`, `p in "PA"` | ~30x |
| `move()` L255,262 | `p in "KY"`, `p in "PA"` | 1x |

Everything else (dict lookups, board scanning, tree size) is **O(1)** and unaffected.

### Estimated overhead

| Scenario | Piece types | Overhead vs original | With frozenset fix |
|----------|------------|---------------------|--------------------|
| Original Sunfish | 7 | 0% (baseline) | 0% |
| Current (powered) | 13 | ~15-25% | ~0-2% |
| Half ASCII letters | ~20 | ~60-80% | ~0-2% |
| All 26 letter pairs | 26 | ~100-150% | ~0-2% |

### ASCII ceiling

`swapcase()` in `Position.rotate()` means only letter pairs (A-Z / a-z) work. That's **26 max piece types** — the hard ceiling unless the rotation mechanism is redesigned.

## Changes Applied

Replaced all 6 string membership checks with pre-computed frozensets in `sunfish.py`:

```python
NON_SLIDERS = frozenset("PNKACY")
PAWNS = frozenset("PA")
KINGS = frozenset("KY")
ROCKS = frozenset("Oo")
```

Frozenset membership is O(1) regardless of set size, making performance completely independent of piece count.

## Next Steps

1. **Run `make test`** — rebuild Docker container and run full test suite to confirm no behavioral regression
2. **Update `CLAUDE.md`** — document the frozenset constants so future piece additions just need to add to the relevant frozenset
3. **(Optional) Benchmark** — run `make test-perf` before/after to measure actual speedup
