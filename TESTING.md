# Testing the top_n Implementation

## Starting the Server

Use Docker Compose to run the server:

```bash
docker-compose up
```

The server will be available at `http://localhost:5500`

## Running the Test Script

In a separate terminal:

```bash
python3 test_top_n.py
```

## Manual Testing with curl

### Test 1: Fast path (top_n=1)
```bash
curl -X POST http://localhost:5500/bestmove \
  -H "Content-Type: application/json" \
  -d '{
    "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "maxdepth": 6,
    "top_n": 1
  }'
```

Expected: Returns 1 move very quickly (same speed as before)

### Test 2: Multiple moves (top_n=5)
```bash
curl -X POST http://localhost:5500/bestmove \
  -H "Content-Type: application/json" \
  -d '{
    "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "maxdepth": 6,
    "top_n": 5
  }'
```

Expected: Returns 5 moves with properly evaluated scores (~10% slower)

### Test 3: Default behavior (top_n=10)
```bash
curl -X POST http://localhost:5500/bestmove \
  -H "Content-Type: application/json" \
  -d '{
    "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "maxdepth": 6
  }'
```

Expected: Returns 10 moves (default) with properly evaluated scores

## What to Look For

### Performance
- **top_n=1**: Should be as fast as the old implementation (fast path)
- **top_n=5-10**: Should add ~10-20% computation time
- **top_n=20**: Should add ~20-30% computation time

### Move Quality
The scores in `allmoves` should now be:
- Much more accurate than before (not just static eval)
- Consistent with the depth of search
- Properly ranked (higher scores = better moves)

### Example Response
```json
{
  "bestmove": "e2e4",
  "score": "23",
  "check": false,
  "allmoves": [
    ["e2e4", 23],
    ["d2d4", 20],
    ["g1f3", 18],
    ["b1c3", 15],
    ["c2c4", 12]
  ]
}
```

## Comparing Old vs New

### Old Implementation (Static Eval Only)
```json
"allmoves": [
  ["e2e4", 100],    // Just PST difference
  ["d2d4", 95],     // Not search-based
  ["g1f3", 85],     // May not reflect true strength
  ...30+ moves      // All moves returned
]
```

### New Implementation (TT + Shallow Search)
```json
"allmoves": [
  ["e2e4", 45],     // Search-based score
  ["d2d4", 42],     // TT or depth-3 search
  ["g1f3", 38],     // Reflects tactical strength
  ["b1c3", 35],     // Only top N returned
  ["c2c4", 32]
]
```

## Performance Benchmarks

Run this to compare performance:

```python
import requests
import time

def benchmark(top_n, runs=3):
    times = []
    for _ in range(runs):
        start = time.time()
        requests.post("http://localhost:5500/bestmove", json={
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "maxdepth": 6,
            "top_n": top_n
        })
        times.append(time.time() - start)
    return sum(times) / len(times)

print(f"top_n=1:  {benchmark(1):.2f}s (avg)")
print(f"top_n=5:  {benchmark(5):.2f}s (avg)")
print(f"top_n=10: {benchmark(10):.2f}s (avg)")
print(f"top_n=20: {benchmark(20):.2f}s (avg)")
```

## Troubleshooting

### Server not responding
```bash
# Check if container is running
docker ps

# Check server logs
docker-compose logs -f
```

### Unexpected scores
- Verify the FEN string is valid
- Check that moves history is correct if provided
- Ensure depth is reasonable (6-10 for testing)

### Slow performance
- Lower the `maxdepth` parameter
- Reduce `top_n` value
- Check system resources (Docker memory limits)
