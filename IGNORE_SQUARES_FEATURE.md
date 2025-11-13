# Ignore Squares Feature

## Overview

The `ignore_squares` parameter allows you to exclude specific pieces from being considered in the best move calculation.

## Use Cases

- **Training Mode**: Force players to develop other pieces
- **Puzzle Mode**: Create scenarios where only certain moves are allowed
- **Analysis**: Explore alternative strategies ("What if I can't use my queen?")
- **Game Variants**: Implement custom rules restricting piece movement

## API Usage

### Request Format

```json
{
  "fen": "<fen_string>",
  "maxdepth": 6,
  "ignore_squares": ["e2", "g1"]  // List of squares to ignore
}
```

### Example 1: Ignore Knights in Starting Position

```bash
curl -X POST http://localhost:5500/bestmove \
  -H "Content-Type: application/json" \
  -d '{
    "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "maxdepth": 6,
    "ignore_squares": ["g1", "b1"]
  }'
```

**Response**:
```json
{
  "bestmove": "d2d4",  // Best pawn move (knights ignored)
  "score": "33",
  "check": false,
  "allmoves": [
    ["d2d4", 33],
    ["e2e3", 22],
    ["d2d3", 13],
    ["f2f4", 11]
    // No g1f3 or b1c3
  ]
}
```

### Example 2: Ignore All Pawns

```bash
curl -X POST http://localhost:5500/bestmove \
  -H "Content-Type: application/json" \
  -d '{
    "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "maxdepth": 6,
    "ignore_squares": ["a2", "b2", "c2", "d2", "e2", "f2", "g2", "h2"]
  }'
```

**Response**:
```json
{
  "bestmove": "g1f3",  // Knight move (pawns ignored)
  "allmoves": [
    ["g1f3", 43],
    ["b1c3", 32],
    ["g1h3", 4],
    ["b1a3", 1]
  ]
}
```

### Example 3: Force Alternative Move

```bash
# Ignore the obvious best move to see alternatives
curl -X POST http://localhost:5500/bestmove \
  -H "Content-Type: application/json" \
  -d '{
    "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "maxdepth": 6,
    "ignore_squares": ["g1"],  // Ignore the best knight
    "top_n": 3
  }'
```

**Response**:
```json
{
  "bestmove": "d2d4",  // Next best move
  "allmoves": [
    ["d2d4", 33],
    ["b1c3", 32],
    ["e2e3", 22]
  ]
}
```

## Behavior

### What Gets Filtered

- **All moves** originating from specified squares
- Works with **any square** in algebraic notation (a1-h8)
- Case insensitive: "E2" and "e2" both work

### Automatic Best Move Override

If the engine's best move comes from an ignored square:
1. The move is excluded from `allmoves`
2. The `bestmove` field automatically shows the next best allowed move
3. Scoring is recalculated for remaining moves

### Performance

- **Minimal overhead**: Simple list filtering (~1ms)
- No impact on search depth or quality
- Works with all other parameters (`top_n`, `precision`, etc.)

## Edge Cases

### 1. All Moves Ignored

```json
{
  "ignore_squares": ["a2", "b2", ..., "h2", "g1", "b1"]  // All pieces
}
```

**Response**:
```json
{
  "bestmove": "(none)",
  "allmoves": []
}
```

### 2. Invalid Square Names

```json
{
  "ignore_squares": ["z9", "invalid"]  // Bad squares
}
```

**Behavior**: Logged as warning, invalid squares are skipped

### 3. Empty List

```json
{
  "ignore_squares": []  // No filtering
}
```

**Behavior**: Normal operation, no moves filtered

### 4. Black's Perspective

The feature automatically handles coordinate flipping for black's perspective.

## Combining with Other Features

### With `top_n`

```json
{
  "ignore_squares": ["e2"],
  "top_n": 5  // Get top 5 moves excluding e2
}
```

### With `precision` (Difficulty Adjustment)

```json
{
  "ignore_squares": ["d1"],  // Don't use queen
  "precision": 0.2  // Add some randomness
}
```

### With Move History

```json
{
  "fen": "...",
  "moves": "e2e4 e7e5",
  "ignore_squares": ["g1"]  // Ignore knight after some moves
}
```

## Testing

Run the test suite:

```bash
python3 test_ignore_squares.py
```

Expected output:
```
✓ Without ignore_squares: g1f3 is best
✓ With ignore_squares ['g1', 'b1']: d2d4 is best
✓ Verification: No moves from ignored squares found
```

## Implementation Details

### Flow

1. **API Layer** (server.py): Accept `ignore_squares` as JSON array
2. **UCI Layer** (uci.py): Convert to comma-separated string for UCI command
3. **Search Layer** (go_loop): Filter legal moves, override bestmove if needed

### Code Location

- API endpoint: `server.py:185`
- UCI parsing: `tools/uci.py:422-428`
- Move filtering: `tools/uci.py:88-118`
- Bestmove override: `tools/uci.py:212-250`

## Frontend Integration

```javascript
// Training mode: Force player to develop pieces other than knights
async function getTrainingMove(fen) {
  const response = await fetch('/bestmove', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      fen: fen,
      maxdepth: 6,
      ignore_squares: ['g1', 'b1'],  // Force pawn moves
      top_n: 3  // Show top 3 alternatives
    })
  });
  return await response.json();
}

// Puzzle mode: Only allow specific pieces to move
async function getPuzzleMove(fen, allowedSquares) {
  // Get all squares
  const allSquares = [];
  for (let file of 'abcdefgh') {
    for (let rank of '12345678') {
      allSquares.push(file + rank);
    }
  }

  // Ignore all except allowed squares
  const ignoreSquares = allSquares.filter(sq => !allowedSquares.includes(sq));

  const response = await fetch('/bestmove', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      fen: fen,
      maxdepth: 8,
      ignore_squares: ignoreSquares
    })
  });
  return await response.json();
}
```

## Limitations

1. **Filtering only at root**: Ignored pieces can still be used in opponent's responses
2. **No game-level persistence**: Must specify ignore_squares on every API call
3. **Square-based, not piece-based**: Can't ignore "all pawns" without listing them

## Future Enhancements

Potential improvements:
- Piece type filtering (e.g., "ignore all pawns")
- Color-based filtering (e.g., "ignore all white pieces on queenside")
- Complex rules (e.g., "ignore pieces that haven't moved yet")
