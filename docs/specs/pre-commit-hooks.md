# Pre-Commit Hooks with Unit Tests

**Type**: feature
**Priority**: medium
**Scope**: small (< 1 session)

## Problem

There are no automated quality gates before commits. A developer can push broken code (syntax errors, failing unit tests) without any warning. This slows down iteration — bugs caught later in Docker integration tests or code review could have been caught instantly at commit time.

## Solution

Add pre-commit hooks using the `pre-commit` framework that run **ruff** (lint + format check) and the existing **unit tests** before every commit.

### User Experience

1. Developer runs `make setup-hooks` once after cloning (installs pre-commit + ruff, activates the git hook)
2. On every `git commit`:
   - Ruff checks staged `.py` files for lint errors (~100ms)
   - Ruff checks formatting (~100ms)
   - Unit tests run (`tests/test_search_best_moves.py`) (~2-3s)
3. If anything fails, commit is blocked with a clear error message
4. Developer can also run `make lint` manually at any time

Integration tests (Docker-dependent) are **not** included in the hook — they're too slow and require infrastructure. Only fast, local checks run.

### Technical Approach

**New files:**

- **`.pre-commit-config.yaml`** — Hook definitions:
  - `ruff` (lint): check for errors/warnings (E, F, W rules)
  - `ruff-format`: check formatting (no auto-fix on commit, just fail)
  - Local hook: `python tests/test_search_best_moves.py` for unit tests

- **`pyproject.toml`** — Ruff configuration:
  - Line length: 120 (matches current codebase style)
  - Rules: E (pycodestyle errors), F (pyflakes), W (pycodestyle warnings)
  - Ignore: E501 (line length — too noisy for existing code), W291, W292, W293 (whitespace — let formatter handle)
  - Exclude: `.git`, `__pycache__`, `profiles/`

- **`requirements-dev.txt`** — Dev dependencies:
  - `pre-commit`
  - `ruff`

**Modified files:**

- **`Makefile`** — New targets:
  - `make setup-hooks`: `pip install -r requirements-dev.txt && pre-commit install`
  - `make lint`: `ruff check .`
  - `make format`: `ruff format .`
  - `make format-check`: `ruff format --check .`

## Acceptance Criteria

- [ ] `make setup-hooks` installs pre-commit and activates the git hook
- [ ] `git commit` triggers ruff lint + format check + unit tests
- [ ] Commit is blocked if any check fails
- [ ] `make lint` runs ruff standalone
- [ ] `make format` auto-formats code
- [ ] All checks pass on the current codebase (no false positives blocking work)
- [ ] Hook runs in < 5 seconds total

## Out of Scope

- Integration tests in the hook (require Docker)
- Auto-fixing on commit (format check only — developers fix manually or run `make format`)
- CI/CD pipeline setup
- New unit tests (existing `test_search_best_moves.py` only)

## Open Questions

- Should we add `ruff` to the main `requirements.txt` or keep it dev-only? (Recommendation: dev-only in `requirements-dev.txt`)
- Any specific lint rules to enable beyond the basics (E, F, W)?

## Related

- `tests/test_search_best_moves.py` — the unit test that will run in the hook
- `Makefile` — existing build/test targets
