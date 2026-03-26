# Performance Audit — Sunfish Engine

**Date:** 2026-03-26
**Method:** cProfile on CPython, midgame position, depth 8 (645K nodes, 108s)
**Position:** `r1bq1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 7`

## Profile Summary

| Function | Time (s) | % of total | Calls | Notes |
|---|---|---|---|---|
| `gen_moves()` | 41.6 | **39.8%** | 19.7M | Scans 120 chars to find ~16 pieces |
| `value()` | 16.9 | **16.1%** | 19.8M | PST lookups + capture scoring |
| `str.isupper()` | 10.9 | 10.4% | 102M | Driven by gen_moves board scan |
| `genexpr` (sort) | 7.0 | 6.7% | 19.7M | Generator wrapping in sorted() |
| `str.isspace()` | 4.7 | 4.5% | 44.6M | Board boundary detection |
| `sorted()` | 4.0 | 3.8% | 541K | Move ordering per bound() call |
| `str.islower()` | 3.4 | 3.3% | 28.7M | Capture/stop detection |
| `Move.__new__` | 3.1 | 3.0% | 21.6M | namedtuple allocation overhead |
| `hasattr()` | 2.2 | 2.1% | 19.8M | Precision check in value() |
| `abs()` | 2.0 | 2.0% | 20.7M | Castling distance checks |

Total function calls: **313M** for 645K search nodes.

## Findings

### 1. `gen_moves()` board scan — 39.8% of runtime

The engine iterates all 120 characters of the board string on every `gen_moves()` call. Only ~16 are movable uppercase pieces. The remaining 104 iterations (padding, dots, lowercase) are filtered by `if not p.isupper() or p == 'O'` — but the Python loop overhead for those 104 no-ops is massive at 19.7M invocations.

**Quick win:** Pre-filter with a generator expression that runs the scan in C:
```python
pieces = [(i, p) for i, p in enumerate(self.board) if p.isupper() and p != 'O']
for i, p in pieces:
    ...
```

**Full fix:** Maintain a piece-list on the Position object, updated incrementally in `move()` and `rotate()`. Eliminates the scan entirely.

| Approach | Estimated speedup | Complexity |
|---|---|---|
| Pre-filter genexpr | 4-6% overall | Low |
| Incremental piece-list | 15-20% overall | Medium-High |

---

### 2. `hasattr()` / `setattr()` in hot loop — 2.3% of runtime

`bound()` calls `setattr(pos, 'searcher', self)` on every entry (645K times). Then `value()` calls `hasattr(self, 'searcher')` on every evaluation (19.8M times). This is a workaround for passing the precision parameter through the search tree.

**Fix:** Use a module-level `_precision` variable instead. Zero-cost when precision is 0 (the common case).

| Metric | Before | After |
|---|---|---|
| `hasattr` calls | 19.8M | 0 |
| `setattr` calls | 645K | 0 |
| Saved time | ~2.4s | — |

---

### 3. `Move` namedtuple allocation — 3.0% of runtime

`Move.__new__` is called 21.6M times. The namedtuple constructor validates arguments and creates a new object each time. Plain tuples are ~3x faster to construct.

**Fix:** Replace `Move(i, j, prom)` with `(i, j, prom)`. All hot-path code already uses unpacking (`i, j, prom = move`). Only non-hot paths (engine.py, server.py) use `.i`/`.j`/`.prom` attribute access and need updating.

---

### 4. `flip_coord()` function call overhead — 0.2%

2.3M calls to a one-liner (`return 119 - i`). Each has Python function-call overhead (~80ns).

**Fix:** Inline `119 - i` at the 3 call sites in `value()`.

---

### 5. `put` lambda redefined per `move()` — 0.5%

`put = lambda board, i, p: board[:i] + p + board[i + 1:]` is recreated 634K times. Python allocates a new function object each time.

**Fix:** Hoist to module-level function.

---

## Benefit/Complexity Matrix

| # | Optimization | Speedup | Effort | Risk |
|---|---|---|---|---|
| 1 | Remove hasattr/setattr | ~2-3% | 15 min | None |
| 2 | Inline flip_coord | ~0.3% | 5 min | None |
| 3 | Module-level put | ~0.5% | 5 min | None |
| 4 | Plain tuples for Move | ~3% | 30 min | Low |
| 5 | Pre-filter gen_moves | ~4-6% | 1 hr | Low |
| | **Combined estimate** | **~10-12%** | **~2 hr** | |

### Not recommended now

- **Bytearray board**: Would replace immutable string ops with O(1) mutations (~40-50% speedup) but requires rewriting the core Position class, adding undo-move, and Zobrist hashing. A multi-day project.

---

## Implemented Results

**Benchmark:** 6 positions (opening/midgame/endgame), depth 8, CPython 3.x, `scripts/benchmark.py`

| Metric | Before | After | Change |
|---|---|---|---|
| Total time | 169.35s | 130.75s | **-22.8%** |
| NPS (nodes/sec) | 17,759 | 23,002 | **+29.5%** |
| Node count | 3,007,556 | 3,007,556 | Identical |
| Moves produced | Same | Same | Identical |
| Tests passing | 156/156 | 156/156 | All pass |

**What was implemented (Steps 1-4):**
1. Replaced `hasattr()`/`setattr()` with module-level `_precision` variable
2. Inlined `flip_coord()` calls in `value()` (3 sites)
3. Hoisted `put` lambda to module-level `_put()` function
4. Replaced `Move` namedtuple with plain tuples in hot paths

**What was tested but reverted (Step 5):**
- Pre-filtering pieces via generator expression in `gen_moves()` — no measurable improvement on CPython due to generator overhead offsetting the filtering benefit.

## Methodology Notes

- cProfile adds ~10-15% overhead to all calls, so absolute times are inflated. Ratios between functions are accurate.
- Node count (645K for midgame_open) and search behavior are unaffected by profiling — the same search tree is explored.
- All implemented optimizations are behavior-preserving: same moves, same evaluations, same search tree.
- Benchmark script: `scripts/benchmark.py` — runs engine directly (no HTTP), uses `time.perf_counter()`.
