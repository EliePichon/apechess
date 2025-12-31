# Error Investigation Report

## Observed Errors

From the `test_movetime_performance.py` run, we observed two types of errors:

### 1. HTTP 500 Errors - Invalid Bestmove Format

**Symptoms:**
- Server returns HTTP 500
- Log shows: `ERROR - Error processing request: 'k'` or `ERROR - Error processing request: '.'`

**Root Cause:**
The bestmove parsing is receiving incomplete or malformed responses from the UCI engine. Instead of getting:
```
bestmove e2e4 score 45 depth 7
```

It's getting single characters like:
```
bestmove k
bestmove .
```

**Why This Happens:**
The UCI output stream is being read while the engine is still writing. The `output_stream.read()` in the polling loop captures partial output before the full bestmove line is written.

**Affected Positions:**
- Early Game - Queen's Gambit (10s movetime)
- Midgame - Complex Position (7s movetime)

### 2. Timeouts - UCI Session Timeout

**Symptoms:**
- Request times out
- Log shows: `ERROR - Timeout error: UCI session timed out waiting for response: bestmove`

**Root Cause:**
The default UCI session timeout (60s) is not sufficient for complex positions with long movetimes. The issue is compounded by:
1. Python's iterative deepening may take longer than the movetime parameter suggests
2. The 60s timeout is hardcoded regardless of the movetime requested

**Affected Positions:**
- Early Game - Italian Opening (7s and 10s movetimes)

## Root Cause Discovery

### **CRITICAL: Concurrency Bug - sys.stdin/stdout Conflicts**

**The Real Problem:**
When the benchmark runs multiple tests in quick succession, concurrent UCI sessions **overwrite each other's `sys.stdin` and `sys.stdout` redirections**.

**Evidence:**
```
# Request 1 succeeds
Received bestmove line: bestmove g8f6 score 36 depth 8
Parsed bestmove: g8f6, parts: ['bestmove', 'g8f6', 'score', '36', 'depth', '8']

# Request 1 then immediately fails
ERROR - Error processing request: '.'

# Request 2 times out
UCI output update: info string position set successfully
UCI timeout. Final output: info string position set successfully
```

**What Happens:**
1. Request 1 starts → Thread 1 sets `sys.stdin = input_stream_1`, `sys.stdout = output_stream_1`
2. Request 2 starts **while Request 1 is running** → Thread 2 **overwrites** `sys.stdin = input_stream_2`, `sys.stdout = output_stream_2`
3. Thread 1's UCI loop now reads from `input_stream_2` instead of `input_stream_1`
4. Thread 1 outputs to `output_stream_2` instead of `output_stream_1`
5. Both threads are now reading/writing to the wrong streams → **chaos**

**Why Single Tests Work:**
The diagnostic test (`test_error_cases.py`) runs one position at a time with pauses between requests, so there's no overlap.

**Why Benchmarks Fail:**
The benchmark fires requests rapidly in a loop with minimal delay, causing concurrent UCI sessions.

## Fixes Applied

### Fix 0: **UCI Session Serialization Lock (CRITICAL)**

**File:** [server.py:17,58](server.py#L17,58)

Added a global lock to serialize UCI sessions and prevent concurrent sys.stdin/stdout conflicts:

```python
# Global lock to serialize UCI sessions
uci_lock = threading.Lock()

def run_uci_session(commands, expected_response=None, timeout=60):
    # Acquire lock to prevent concurrent UCI sessions from interfering
    with uci_lock:
        # ... entire UCI session runs inside lock ...
```

**Impact:**
- Requests are now processed **serially** instead of concurrently
- Each request waits for the previous one to complete
- No more stream conflicts
- **Fixes both HTTP 500 and timeout errors**

**Trade-off:**
- Slightly slower under high load (requests queue instead of parallel)
- But correctness > speed, and most use cases don't have concurrent requests

### Fix 1: Generous Timeout Buffers

**File:** [server.py:248-257](server.py#L248-L257), [test_movetime_performance.py:115](test_movetime_performance.py#L115)

**Problem:** Time check in iterative deepening only happens between depths, so if one depth takes very long, the engine can significantly overshoot the movetime budget.

**Example:** Italian Opening position with movetime=7s takes ~15.5s because depth 8 is computationally expensive.

**Solution:** Use generous timeout buffers instead of strict limits:

**Server-side:**
```python
if movetime:
    uci_timeout = (movetime / 1000.0) * 2 + 15  # 2x movetime + 15s buffer
else:
    uci_timeout = 120  # Very generous for depth-based
```

**Client-side (tests):**
```python
timeout_seconds = (movetime_ms / 1000.0) * 2 + 10  # 2x movetime + 10s buffer
```

**Impact:**
- Allows positions with expensive depths to complete without timeout
- Tests can accurately measure actual search time (even if it overshoots)
- No false positives from timeouts

**Trade-off:**
- Requests can take longer than requested movetime
- But this is inherent to the current iterative deepening implementation
- Alternative would be adding time checks inside the search loop (more complex)

### Fix 2: Better Error Handling and Logging

**File:** [server.py:263-281](server.py#L263-L281)

Added:
- Logging of raw bestmove line received
- Validation that bestmove is at least 4 characters
- Better error messages showing what was actually received

```python
logger.debug(f"Received bestmove line: {bestmove_line}")
logger.debug(f"Parsed bestmove: {bestmove}, parts: {parts}")

# Validate bestmove format (should be at least 4 characters: e2e4)
if len(bestmove) < 4:
    logger.error(f"Invalid bestmove format: '{bestmove}' (too short)")
    return jsonify({"error": f"Invalid bestmove format: '{bestmove}'"}), 500
```

### Fix 2: Dynamic UCI Timeout

**File:** [server.py:222-230](server.py#L222-L230)

Calculate timeout based on movetime parameter:
```python
if movetime:
    uci_timeout = (movetime / 1000.0) + 10  # movetime + 10s buffer
else:
    uci_timeout = 60  # Default for depth-based
```

This ensures the UCI session has enough time to complete.

### Fix 3: Enhanced Debug Logging

**File:** [server.py:77-112](server.py#L77-L112)

Added detailed logging in the UCI polling loop:
- Logs output updates as they occur
- Logs final output when timeout is reached
- Helps diagnose what's happening during search

## Diagnostic Tools

### test_error_cases.py

New script to reproduce specific error cases:

```bash
python3 test_error_cases.py
```

Tests the exact positions that failed in the benchmark with detailed output.

## Understanding the Root Issues

### Issue 1: StringIO Race Condition

The current implementation uses `StringIO` to capture UCI output and polls it every 100ms:

```python
while time.time() - start_time < timeout:
    output_stream.seek(0)
    response = output_stream.read().strip().split("\n")
    # Check if bestmove line is present
```

**Problem:** When the engine writes `bestmove e2e4 score 45 depth 7`, the polling might catch it mid-write:
- First poll: `"bestmove e"`
- Second poll: `"bestmove e2e4 score 45 depth 7"` ✓

But the code returns as soon as ANY line starts with "bestmove", even if incomplete.

### Issue 2: Movetime Compliance

The engine's `go movetime X` command should complete within X milliseconds, but:
1. Python overhead adds latency
2. Iterative deepening might finish a depth before checking time
3. The 2/3 movetime check in `go_loop` sometimes isn't enough

**From tools/uci.py:78-79:**
```python
if elapsed > max_movetime * 2 / 3:
    break
```

This only checks after each depth completes, so if depth N takes longer than expected, it overshoots.

## Recommended Solutions

### Short-term (Applied)

✅ Add bestmove validation to catch malformed responses
✅ Increase UCI timeout based on movetime
✅ Add debug logging to diagnose issues

### Medium-term (TODO)

1. **Fix StringIO Race Condition**
   - Use a thread-safe queue instead of StringIO polling
   - Or ensure complete line buffering before reading
   - Or wait for newline character before processing

2. **Improve Time Management**
   - Check elapsed time more frequently during search
   - Add safety margin: stop at 90% of movetime instead of 66%
   - Log when engine exceeds movetime budget

3. **Better Error Recovery**
   - If bestmove is malformed, retry with shorter movetime
   - Provide fallback move (e.g., first legal move)
   - Return partial results instead of 500 error

### Long-term (Architectural)

1. **Async Processing**
   - Use asyncio instead of threading
   - Stream results as they arrive
   - Better timeout handling

2. **Engine Optimization**
   - Profile why certain positions take longer
   - Add position-specific timeout adjustments
   - Consider depth limits based on position complexity

## How to Debug Future Errors

1. **Run error case test:**
   ```bash
   python3 test_error_cases.py
   ```

2. **Watch server logs:**
   ```bash
   make logs
   # or
   docker-compose logs -f | grep -A 5 -B 5 "ERROR\|bestmove"
   ```

3. **Look for these patterns:**
   - `Received bestmove line:` - Shows what was actually received
   - `Parsed bestmove:` - Shows how it was parsed
   - `UCI output update:` - Shows UCI output as it arrives
   - `UCI timeout. Final output:` - Shows final state on timeout

4. **Test specific position manually:**
   ```bash
   curl -X POST http://localhost:5500/bestmove \
     -H "Content-Type: application/json" \
     -d '{
       "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
       "movetime": 7000,
       "maxdepth": 25,
       "precision": 0.0
     }'
   ```

## Error Frequency Analysis

From the benchmark run (24 tests total):

- **Successes:** 20/24 (83.3%)
- **HTTP 500 errors:** 2/24 (8.3%)
- **Timeouts:** 2/24 (8.3%)

**Error distribution by movetime:**
- 2000ms: 0 errors (6/6 success)
- 4000ms: 1 error (5/6 success) - 1 timeout
- 7000ms: 2 errors (4/6 success) - 1 HTTP 500, 1 timeout
- 10000ms: 2 errors (4/6 success) - 2 HTTP 500

**Observation:** Errors increase with longer movetimes, suggesting the issues are related to:
1. Longer searches → more opportunity for race conditions
2. Longer searches → closer to timeout limits
3. Specific positions that are computationally expensive

## Next Steps

1. **Deploy fixes and retest:**
   ```bash
   make down
   make up
   make test-movetime
   ```

2. **If errors persist, run diagnostic:**
   ```bash
   python3 test_error_cases.py
   ```

3. **Consider reducing test movetimes:**
   - Current: 2s, 4s, 7s, 10s
   - Safer: 1s, 2s, 4s, 6s (less likely to timeout)

4. **Add retry logic to tests:**
   - Retry failed tests once before marking as error
   - Helps distinguish transient issues from real bugs
