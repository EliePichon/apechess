# Ninja Knight (J/j)

**Type**: feature
**Priority**: high
**Scope**: medium (1-2 sessions)

## Problem

The game needs a new piece type that interacts with rocks in a novel way. Rocks currently block movement but the Ninja Knight introduces a "parkour" mechanic: bouncing off rocks to reach distant squares via chained knight-hops. This creates interesting tactical puzzles where rock placement becomes strategically meaningful for mobility.

## Solution

Add a new piece `J` (white) / `j` (black) that moves like a normal knight but can bounce off rocks. When a knight-hop lands on a rock, it must immediately make another knight-hop from that rock. The chain continues through rocks until the final destination is an empty square or capturable enemy piece. Rocks are **not destroyed** by bouncing.

### User Experience

- **FEN input**: Client sends `J`/`j` in FEN where Ninja Knights appear. Example: `RJBQKBJR` in the back rank.
- **Legal moves**: `/getmoves` returns multi-square path strings for bounce moves: `"b1d2f3"` means B1 hops to D2 (rock) then to F3. Normal hops remain 4-char: `"b1c3"`.
- **Player move**: Client submits the full path string (e.g., `"b1d2f3"`). Engine extracts origin + final destination.
- **CPU move**: `/turn` returns the full path string so the client can animate the bounce sequence.
- **Move string pattern**: `<origin><sq1>[<sq2>]...` — each segment is 2 chars. Length 4 = direct hop. Length 6+ = parkour. Intermediate squares are rocks.

### Technical Approach

#### Design Decisions
1. **Internal move format**: Flattened to standard `(origin, final_dest, "")` 3-tuple. No change to move contract.
2. **Rocks left intact**: Bouncing does not destroy rocks (unlike powered pieces).
3. **Captures**: Only at the final destination. Intermediate squares must be rocks.
4. **Piece system**: Separate type — NOT added to `POWERED_TO_BASE`. Same value (280) and PST as Knight.
5. **Path ambiguity**: If multiple bounce paths reach the same destination, engine picks any valid one. Board state is identical regardless.
6. **Max bounces**: Unlimited (naturally capped by board geometry).
7. **Cycles**: No revisiting squares — DFS tracks a visited set.

#### Implementation Touchpoints

**`sunfish.py`** — Core engine:
- `piece` dict: `"J": 280`
- `pst` dict: `pst["J"] = pst["N"]`
- `directions` dict: `"J"` gets same knight offsets as `"N"`
- `NON_SLIDERS`: add `"J"` → `frozenset("PNKACYJ")`
- New `NINJA_KNIGHTS = frozenset("J")`
- `gen_moves()`: dedicated branch for `p == "J"` — DFS through knight-hops, bouncing off rocks (`O`/`o`), yielding `(origin, final_dest, "")` for each reachable non-rock square
- New `Position._ninja_knight_dests(origin)`: DFS returning all reachable final destinations

**`engine.py`** — API layer:
- `player_pieces`: add `"J"` → `frozenset("PNBRQKACDTXYJ")`
- New `_reconstruct_bounce_path(board, origin, dest)`: BFS to find a valid bounce path for API output
- Move rendering: detect J moves and emit multi-square path strings
- CPU move output (`/turn`, `/bestmove`): intercept J moves to add path info

**`tools/uci.py`** — Move parsing:
- `parse_move`: if `len(move_str) > 5`, extract origin from first 2 chars and dest from last 2 chars (multi-hop Ninja Knight move). Standard 4-5 char moves unchanged.

**C extension** (`csrc/`):
- `_sunfish_core.h`: Add `J` to `IS_NON_SLIDER`, `get_directions` (maps to `KNIGHT_DIRS`), new `IS_NINJA_KNIGHT` lookup
- `_sunfish_core.c`: `gen_moves_internal` — add DFS bounce logic for `J`, identical to Python implementation. Uses stack-based DFS with `visited[120]` array.
- `tables.h`: Regenerate via `scripts/gen_tables.py` (J maps to knight PST index 1)

**`scripts/gen_tables.py`**: Add `"J": 1` to `PIECE_CHARS` mapping.

#### Move Generation Algorithm (DFS)

```
_ninja_knight_dests(origin):
    visited = {origin}
    stack = [origin]
    results = []
    while stack:
        sq = stack.pop()
        for d in KNIGHT_DIRECTIONS:
            dest = sq + d
            if dest in visited: skip
            q = board[dest]
            if space: skip
            if rock (O/o): mark visited, push to stack
            if empty or enemy (lowercase, not 'o'): mark visited, add to results
            if friendly (uppercase): skip
    return results
```

#### Path Reconstruction (BFS)

For API output, given `(origin, final_dest)`, BFS from origin through rocks using knight-hops to find a valid path. Returns `[origin, rock1, rock2, ..., dest]`. Rendered as concatenated algebraic squares.

#### Rotation/Swapcase

`J` ↔ `j` via `swapcase()` — works automatically. When black to move, `j` on the board becomes `J` after `Position.rotate()`, and gen_moves handles it. Rocks `O` ↔ `o` also swap correctly. The DFS checks for rocks using both cases (or a `ROCKS` set).

## Acceptance Criteria

- [ ] `J`/`j` recognized in FEN parsing (`from_fen` handles J/j)
- [ ] `J` moves like a normal knight when no rocks are adjacent
- [ ] `J` bounces off rocks: landing on a rock triggers another knight-hop
- [ ] Multi-bounce chains work (rock → rock → ... → empty/enemy)
- [ ] Rocks are NOT destroyed after bounce
- [ ] Captures only at final destination (not on intermediate rocks)
- [ ] Cycle prevention: visited squares cannot be revisited (no infinite loops)
- [ ] `/getmoves` returns multi-square path strings for bounce moves (e.g., `"b1d2f3"`)
- [ ] `/getmoves` returns 4-char strings for direct knight hops
- [ ] `/move` accepts multi-square path strings, correctly extracts origin and dest
- [ ] `/turn` returns multi-square path for CPU bounce moves
- [ ] Black Ninja Knight (`j`) works correctly after rotation
- [ ] C extension produces identical moves and node counts as Python
- [ ] Search works correctly with J (bestmove, eval)
- [ ] Engine falls back to pure Python gracefully if C ext not rebuilt

## Out of Scope

- Ninja Knight promotion (pawns do NOT promote to J)
- Powered Ninja Knight variant (no rock-destroying ninja knight)
- Bouncing off enemy pieces (only rocks trigger bounces)
- Client-side animation (this spec is engine-only)
- UCI protocol support for multi-square moves

## Open Questions

- None — all design decisions resolved during refinement.

## Related

- Rocks: `tests/test_rocks.py`, rock mechanics in `sunfish.py` gen_moves
- Powered pieces: `POWERED_TO_BASE` pattern in `sunfish.py` (J intentionally excluded)
- Rock landing: `tests/test_rock_landing.py` (similar but different mechanic)
