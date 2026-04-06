# Laser Bishop (`L`/`l`)

**Type**: feature
**Priority**: high
**Scope**: medium (1-2 sessions)

## Problem

Bishops are currently the least exciting piece on the board. The Ninja Knight upgrade (J) adds a compelling power-up mechanic to Knights via captures. Bishops need an equivalent progression that rewards aggressive play and creates a late-game threat.

## Solution

A two-phase bishop upgrade triggered by cumulative bishop captures (any bishop on that side). After two captures, all bishops transform into **Laser Bishops** that slide through ALL pieces on diagonals — only stopping on empty squares or enemy pieces to capture.

### Piece Characters

| Char | Name | Role | Value | PST index |
|------|------|------|-------|-----------|
| `G`/`g` | Bloodied Bishop | Intermediate (after 1st capture) | 320 | 2 (shares B) |
| `L`/`l` | Laser Bishop | Final (after 2nd capture) | 950 | 8 (own) |

### User Experience

1. **First bishop capture**: Any B or D captures an enemy piece → all B/D on that side become `G` (Bloodied Bishop). G moves identically to a regular bishop. The transformation is a visual signal that the upgrade is halfway there.
2. **Second bishop capture**: Any G captures an enemy piece → all G/B/D on that side become `L` (Laser Bishop). L slides through everything on diagonals.
3. **Laser Bishop movement**:
   - Slides along diagonals (same 4 directions as B)
   - **Passes through** all pieces: allies, enemies, rocks — nothing blocks the ray except the board edge
   - **Can stop on**: empty squares or enemy pieces (capturing them)
   - **Cannot stop on**: rocks, allies, board padding
   - Can capture an enemy with more pieces behind it (keeps sliding past)
4. **Strategic impact**: +630 value per upgraded piece makes bishop captures increasingly attractive. Two bishops upgraded = +1260 total positional swing.

### Technical Approach

Follows the Ninja Knight (J) pattern exactly. The intermediate char `G` encodes the capture count in the board string itself — no extra state fields needed.

#### sunfish.py

- **Piece dicts**: `piece["G"] = 320`, `piece["L"] = 950`. PST for G = B's PST. PST for L = shifted from B by +630 (same pattern as J shifted from N).
- **Directions**: G and L both use `directions["B"]` (diagonals).
- **Constants**: `LASER_BISHOPS = frozenset("L")`. G and L are NOT in `NON_SLIDERS`, NOT in `POWERED_PIECES`, NOT in `POWERED_TO_BASE`.
- **gen_moves()**: New branch for `p == "L"` (after J branch). Slides through everything, only yields on empty/enemy. G falls through to standard sliding logic (same as B).
- **move()**: After parkour block, check `p in ("B", "D", "G")` capturing enemy:
  - If `p == "G"` or G already on board → Phase 2: all G/B/D → L
  - Else → Phase 1: all B/D → G
- **value()**: Phase 2 adds PST delta (L - source) for mover + all bystander G/B/D. Phase 1 has zero delta (G shares B's PST).

#### C extension

- **`_sunfish_core.h`**: Add `IS_BISHOP_FAMILY[128]` (B, D, G), `IS_LASER_BISHOP[128]` (L). Add G/L cases to `get_directions()`.
- **`_sunfish_core.c`**: Mirror Python logic in `gen_moves_internal` (L branch), `value_internal` (activation scoring), `move_and_rotate` (board transformation).
- **`gen_tables.py`**: Add L to `PIECE_ORDER` (index 8), add `"G": 2, "L": 8` to `PIECE_CHARS`.
- Regenerate `csrc/tables.h`.

#### engine.py

- Add G and L to `player_pieces` frozenset (two locations).
- No special move expansion needed (L moves are standard 4-char algebraic).

## Acceptance Criteria

- [ ] L slides through allies, enemies, and rocks on diagonals
- [ ] L cannot stop on rocks or ally squares
- [ ] L can capture enemy pieces with other pieces behind them
- [ ] Board edge stops L's ray
- [ ] Phase 1: B/D capture → all B/D become G
- [ ] Phase 2: G capture → all G/B/D become L
- [ ] D (powered bishop) captures count and D transforms
- [ ] Black side activation works (g → l via swapcase/rotate)
- [ ] value() scores Phase 2 upgrade correctly (+630 per piece)
- [ ] C extension produces identical moves/scores/transformations as Python
- [ ] Node count invariance maintained (test_node_invariance.py passes)
- [ ] G moves identically to regular bishop (blocked by pieces/rocks)
- [ ] Pawn promotion to B after Phase 1 → new B upgrades to L on next bishop capture

## Out of Scope

- Laser Bishop bouncing off edges / wrapping (separate backlog item)
- Powered Laser Bishop variant (L already passes through rocks)
- Custom FEN notation for G/L (standard FEN with G/L chars works)
- Interaction with explosive pawns or other unreleased features

## Open Questions

- Should G have a distinct PST shape (e.g., slightly more aggressive positioning)? Current plan: share B's PST for simplicity. Can tune later.

## Related

- [Ninja Knight spec](../specs/) — same activation pattern (reference implementation)
- Backlog: "Bishops through edges? or mirror?" — future extension of L
- `tests/test_ninja_knight.py` — test structure to mirror
