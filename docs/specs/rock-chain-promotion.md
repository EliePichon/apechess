# Rock-Chain Early Promotion

**Type**: feature
**Priority**: high
**Scope**: small (< 1 session)

## Problem

When rocks occupy the last rank, pawns in those files can never promote — they're permanently blocked. This removes a core chess mechanic (promotion) from files with rocks on rank 8, making those pawns strategically useless.

## Solution

Allow pawns to promote early when a continuous chain of rocks connects their destination square to rank 8 in the same file.

### Rules (from white's perspective)

- Rank 8 always allows promotion (unchanged).
- If rank 8 has a rock, the pawn can promote on rank 7.
- If ranks 8 AND 7 both have rocks, the pawn can promote on rank 6.
- The chain must be continuous from rank 8 downward. A rock on rank 7 without rank 8 does NOT enable promotion on rank 6.
- Applies to both **forward advances** and **diagonal captures**.
- Both regular pawns (P → N/B/R/Q) and powered pawns (A → C/D/T/X) benefit.
- Rocks remain intact — the pawn stops on the first non-rock square below the chain.

### Technical Approach

Add a helper function `is_promotion_sq(board, j)` that replaces the current `A8 <= j <= H8` check. The helper walks north from `j` toward rank 8, verifying each intermediate square is a rock.

Must be implemented in both Python (`sunfish.py`) and C (`csrc/_sunfish_core.c`) to maintain node-count invariance. Three call sites in each: `gen_moves`, `move`, `value`.

## Acceptance Criteria

- [ ] Pawn promotes on rank 7 when rank 8 same file has a rock
- [ ] Pawn promotes on rank 6 when ranks 8+7 same file have rocks (chain of 2)
- [ ] Pawn does NOT promote on rank 6 when rank 7 has rock but rank 8 does not
- [ ] Diagonal captures into rock-chain squares trigger promotion
- [ ] Powered pawn (A) promotes to C/D/T/X via rock chain
- [ ] Black-to-move (rotated board) works correctly
- [ ] C and Python produce identical move lists for rock-chain positions
- [ ] Node count invariance tests pass
- [ ] All existing tests still pass

## Out of Scope

- Eval/PST changes for early promotion squares
- Any change to how rocks interact with other pieces
- UI/API changes (promotion choice is already part of the move format)

## Open Questions

None — all ambiguities resolved during refinement.

## Related

- `tests/test_rock_landing.py` — existing powered-pawn promotion tests
- `tests/test_c_extension.py` — C/Python parity tests
- CLAUDE.md "Rocks" and "Powered Pieces" sections
