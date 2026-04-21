# Open-Source Release Preparation

**Type**: refactor
**Priority**: medium
**Scope**: medium (1-2 sessions)

## Problem

The repo is going to be mirrored to a new **public GitHub repo** as a portfolio showcase. The private GitLab repo continues business-as-usual; only a cleaned snapshot is published externally.

Today the history contains material unsuitable for a public audience:
- Internal backlog file (`todo.md`) with half-baked ideas and AI prompts
- Obsolete CI pipelines coupled to private infrastructure (`.gitlab-ci.yml` references `EliePichon/apechess-desktop` + `GITHUB_PAT`)
- Editor/IDE personal config (`.vscode/`)
- Upstream-era GitHub workflow that no longer matches the test suite (`.github/workflows/python-app.yml`)
- Unused PyInstaller spec (`sunfish-server.spec`)
- ~30+ commits with `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>` trailers and a "🤖 Generated with Claude Code" footer
- Commit timestamps clustered in weekday office hours, which is not the impression the author wants to give on a personal portfolio

## Solution

Produce a cleaned, public-ready mirror of the repository in a separate directory. Never modify the live working tree or private GitLab remote.

### User Experience

Viewer lands on `github.com/EliePichon/<repo>`, sees:
- A clean commit log with crisp messages, no AI co-author trailers, no internal references to sister projects
- Timestamps that read like a side-project worked on evenings and weekends
- Only source, tests, docs, and a recognized `CLAUDE.md` developer guide — no internal backlog, no dead CI, no personal IDE config
- A `README.md` that explains what the project is (already good as of `master`)

### Technical Approach

All work happens in a **separate mirror clone**. The private GitLab remote is never touched.

#### 1. Safety & setup

```bash
# From /Users/eliepichon/Workspace/
git -C sunfish bundle create sunfish-prerewrite-$(date +%Y%m%d).bundle --all
git clone --no-local --mirror sunfish sunfish-public.git
cd sunfish-public.git
pip install git-filter-repo   # if not already installed
```

The bundle is a local safety net — restorable via `git clone sunfish-prerewrite-*.bundle`.

#### 2. Purge paths from all history

```bash
git filter-repo --invert-paths \
  --path todo.md \
  --path .gitlab-ci.yml \
  --path .vscode/ \
  --path .github/workflows/python-app.yml \
  --path sunfish-server.spec
```

Note: `claude.md` is **kept** (renamed to `CLAUDE.md` — see step 4). It's a legitimate developer/architecture guide and the `CLAUDE.md` convention is broadly recognized.

#### 3. Scrub commit messages

Create `scrub_messages.py`:

```python
import re
CLAUDE_LINE = re.compile(rb'(?i)(co-authored-by:.*claude|claude.*anthropic|generated with claude code|🤖.*claude)')
def callback(msg):
    lines = [l for l in msg.split(b'\n') if not CLAUDE_LINE.search(l)]
    # Collapse trailing blank lines
    while lines and lines[-1].strip() == b'':
        lines.pop()
    return b'\n'.join(lines) + b'\n'
```

```bash
git filter-repo --message-callback "$(cat scrub_messages.py)" --force
```

The commit `5a39c03 "Add trigger to apechess-desktop GitHub Actions on merge to master"` becomes empty after `.gitlab-ci.yml` removal and is auto-dropped by filter-repo.

#### 4. Retime author-owned commits to evenings

Only commits with `author_email == elie.pichon@gmail.com` are retimed. Upstream contributors (Thomas Ahle et al.) remain untouched.

Algorithm: for each qualifying commit, parse the local time (respecting the stored tz offset). If `weekday ∈ [Mon..Fri]` and `hour ∈ [9, 18)`, linearly map the seconds-since-09:00 into the 19:00–23:59 window of the same day:

```python
# inside a --commit-callback
import datetime
AUTHOR = b'elie.pichon@gmail.com'

def shift(ts_bytes):
    # ts format: b"<unix_seconds> <+HHMM>"
    secs_str, tz = ts_bytes.split(b' ')
    secs = int(secs_str)
    sign = 1 if tz[:1] == b'+' else -1
    tz_off = sign * (int(tz[1:3]) * 3600 + int(tz[3:5]) * 60)
    local = datetime.datetime.utcfromtimestamp(secs + tz_off)
    if local.weekday() >= 5:  # Sat/Sun
        return ts_bytes
    if not (9 <= local.hour < 18):
        return ts_bytes
    office_secs = (local.hour - 9) * 3600 + local.minute * 60 + local.second
    # Map [0, 32400) -> [19:00:00, 23:59:59) == [68400, 86399]
    new_secs_of_day = 68400 + int(office_secs / 32400 * (86399 - 68400))
    new_local = local.replace(hour=0, minute=0, second=0) + datetime.timedelta(seconds=new_secs_of_day)
    new_utc = new_local - datetime.timedelta(seconds=tz_off)
    new_unix = int(new_utc.timestamp()) if False else int((new_utc - datetime.datetime(1970,1,1)).total_seconds())
    return f"{new_unix} ".encode() + tz

def callback(commit, metadata):
    if commit.author_email == AUTHOR:
        commit.author_date = shift(commit.author_date)
        commit.committer_date = shift(commit.committer_date)
```

Properties:
- **Deterministic** — same input → same output, re-runnable
- **Monotonic within a day** — linear map preserves ordering
- **Date unchanged** — no spill into adjacent days, so chronology across days is safe
- **Upstream-safe** — gate on author email

#### 5. Rename `claude.md` → `CLAUDE.md`

After filter-repo passes, apply a final rename in the working tree (not via history rewrite — this is a single forward-facing commit so the rename appears as the last touch, which is fine):

```bash
git mv claude.md CLAUDE.md
# Optionally tone down Claude-specific framing at the top of the file
git commit -m "docs: rename claude.md to CLAUDE.md (standard convention)"
```

Optional trim pass on the file to remove any "assistant-voice" framing, keeping it as a pure architecture/dev guide.

#### 6. Sanity verify before publishing

```bash
# No forbidden paths remain
git log --all --oneline -- todo.md .gitlab-ci.yml sunfish-server.spec   # empty

# No Claude mentions in messages
git log --all --pretty=format:"%B" | grep -iE "claude|anthropic"         # empty

# No office-hours commits from Elie
git log --all --author=elie.pichon@gmail.com \
  --pretty=format:"%ad" --date=format-local:"%u %H" | \
  awk '$1<=5 && $2>=9 && $2<18 {c++} END{print c" office commits remain"}'
# Expected: 0

# Upstream authors still have original timestamps
git log --author=ahle@fb.com --pretty=format:"%h %ad" --date=iso | head -3
```

#### 7. Publish

```bash
# Create new GitHub repo first (via web UI or gh cli)
cd sunfish-public.git
git remote add origin git@github.com:EliePichon/<repo-name>.git
git push --mirror origin
```

No force-push to any existing remote. The private GitLab remote of the live `sunfish` working tree is never touched.

## Acceptance Criteria

- [ ] A `sunfish-prerewrite-YYYYMMDD.bundle` exists at `/Users/eliepichon/Workspace/` and clones back to the current HEAD
- [ ] `sunfish-public.git` is a `--mirror` clone, disjoint from the live repo
- [ ] `git log --all -- todo.md` is empty in the public mirror
- [ ] `git log --all -- .gitlab-ci.yml` is empty
- [ ] `git log --all -- .vscode/` is empty
- [ ] `git log --all -- sunfish-server.spec` is empty
- [ ] `git log --all -- .github/workflows/python-app.yml` is empty
- [ ] `git log --all --pretty=%B | grep -iE "claude|anthropic"` returns nothing
- [ ] No commit authored by `elie.pichon@gmail.com` has a local weekday time in `[9:00, 18:00)`
- [ ] Upstream commits (Thomas Ahle, PyChess contributors, etc.) retain original timestamps and author fields
- [ ] `CLAUDE.md` exists at repo root; `claude.md` does not
- [ ] `docs/specs/` is intact (all 11+ specs preserved)
- [ ] Live `/Users/eliepichon/Workspace/sunfish/` is unchanged — `git status` clean, HEAD unchanged, remotes unchanged
- [ ] Public repo push succeeds to new GitHub remote

## Out of Scope

- Squashing or relabeling existing commits (the 30+ refactor commits stay — they show iterative thinking)
- Replacing CI — no new GitHub Actions workflow is added; user can set that up later
- Adding `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue templates — not needed for a portfolio showcase
- Any changes to the private GitLab repo or live working tree
- Scrubbing secrets — none were found; `GITHUB_PAT` in `.gitlab-ci.yml` is only a variable reference and the whole file is being purged anyway
- Retiming upstream contributors' commits
- Rewriting `docs/specs/` content for "public voice" — they read fine as internal-but-professional design docs

## Open Questions

- **Stashed WIP** (`7e15809`) is a detached stash, not reachable from any branch. It will be discarded by the mirror clone (stashes don't propagate). Confirm this is fine. (Expected: yes, it's trivial.)
- **Optional `CLAUDE.md` trim**: do a content pass to remove any first-person "assistant voice" framing, or leave verbatim? Recommended: quick trim of the opening section to read as plain developer docs.
- **New GitHub repo name**: `sunfish`, `sunfish-api`, or something else? Picked at publish time, not history-rewrite time.

## Related

- `README.md` — already public-ready, no changes needed
- `CLAUDE.md` (after rename) — consider a light trim pass
- Upstream: [thomasahle/sunfish](https://github.com/thomasahle/sunfish) — attribution preserved in README
