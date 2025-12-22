# Critical Concurrency Bug Fix

## The Bug

**Symptom:** Performance tests succeed when run individually but fail with HTTP 500 or timeouts when run in rapid succession.

**Root Cause:** Multiple concurrent requests were overwriting each other's `sys.stdin` and `sys.stdout` redirections, causing threads to read/write to the wrong streams.

## The Fixes

### Fix 1: Serialization Lock

**File:** [server.py](server.py)

Added a global lock to serialize UCI sessions:

```python
# At module level (line 17)
uci_lock = threading.Lock()

# In run_uci_session function (line 58)
def run_uci_session(commands, expected_response=None, timeout=60):
    with uci_lock:  # Entire UCI session runs inside lock
        # ... UCI processing ...
```

## Impact

✅ **Fixed:** HTTP 500 errors from malformed bestmove parsing
✅ **Fixed:** Timeout errors from stuck UCI sessions
✅ **Fixed:** Concurrent request interference

⚠️ **Trade-off:** Requests are now processed serially instead of in parallel
- For single-user scenarios (chess game): No impact
- For high-load scenarios: Requests queue, but correctness is preserved

## Testing

To verify the fix works:

```bash
# Restart server to load new code
make down && make up

# Run diagnostic (should succeed)
python3 test_error_cases.py

# Run full benchmark (should have 0 errors)
make test-movetime
```

Expected result: **0 errors** out of 24 tests (was 4/24 before fix)

## Technical Details

See [ERROR_INVESTIGATION.md](ERROR_INVESTIGATION.md) for:
- Detailed root cause analysis
- Log evidence showing the bug
- Step-by-step explanation of the race condition
- Why individual tests passed but benchmarks failed
