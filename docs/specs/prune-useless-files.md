# Prune Useless Files

**Type**: refactor
**Priority**: low
**Scope**: small (< 1 session)

## Problem

The repo carries legacy files from the original Sunfish fork (NNUE engine, terminal UI, man page), stale investigation docs, and accidentally-tracked venv artifacts. These add clutter and confusion without serving the REST API project.

## Solution

Remove all files that are not referenced by the active codebase (server, engine, tests, CI pipelines, or deployment).

### Files Removed

**NNUE engine** (unused alternative engine + 16 pickle models):
- `sunfish_nnue.py`
- `nnue/` (entire directory)

**Stale docs** (post-mortem investigations and upstream artifacts):
- `docs/CONCURRENCY_FIX.md`
- `docs/ERROR_INVESTIGATION.md`
- `docs/PERFORMANCE_TESTING.md`
- `docs/old_comm_digram.md`
- `docs/sunfish.6`

**Legacy tools** (not used by CI or server):
- `tools/clean_draws.py`
- `tools/fancy.py`
- `tools/test.sh`

**Venv artifacts** (accidentally tracked):
- `pyvenv.cfg`

### Collateral Updates

- `.gitignore`: added `pyvenv.cfg` and `include/` to prevent re-tracking
- `README.md`: removed "Play against sunfish" section (referenced `tools/fancy.py`), NNUE section, and fixed stale `FRONTEND_GUIDE.md` reference to point at `API.md`
- `todo.md`: marked item as done

## Acceptance Criteria

- [x] All listed files removed from git tracking
- [x] `.gitignore` updated to prevent re-tracking venv artifacts
- [x] README.md has no dangling references to removed files
- [x] GitHub Actions CI (`tools/quick_tests.sh` + `tools/tester.py` + `tools/test_files/`) untouched
- [x] PyInstaller pipeline (`sunfish-server.spec`) untouched
- [ ] `make up && make test` passes

## Out of Scope

- Cleaning up `build/` and `dist/` directories (PyInstaller, still used)
- Removing `tools/tester.py`, `tools/quick_tests.sh`, `tools/test_files/` (used by GitHub Actions CI)
- Removing `API.md`, `TESTING.md`, `README.md` (still useful)
- Reorganizing remaining docs or tools
