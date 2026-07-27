#!/usr/bin/env bash
# ============================================================================
# publish.sh — release lab notebook(s) to students.
#
# nbgitpuller pulls the `release` branch into each student's ~/EdgeNotebook. This
# copies the named notebook(s) PLUS the current labHelpers.py from `main` onto
# `release`. The .md docs, this script, and any unreleased labs never touch
# `release`, so students only ever get what you have published.
#
#   ./publish.sh lab01                 # accepts lab01, lab01DevTooling, or a filename
#   ./publish.sh lab01 lab02           # publish several at once
#   ./publish.sh --list                # show what is currently on release
#
# Develop and test on `main` (all notebooks + docs); publish to `release` weekly.
# A dedicated worktree (../EdgeNotebook-release) is used so your main checkout is
# never disturbed.
# ============================================================================
set -euo pipefail
REPO="$(git -C "$(dirname "$(readlink -f "$0")")" rev-parse --show-toplevel)"
WT="${REPO}-release"

git -C "$REPO" fetch -q origin release
if ! git -C "$REPO" worktree list --porcelain | grep -qx "worktree $WT"; then
  git -C "$REPO" worktree add -q "$WT" release 2>/dev/null \
    || git -C "$REPO" worktree add -q -B release "$WT" origin/release
fi
git -C "$WT" checkout -q release
git -C "$WT" reset -q --hard origin/release

if [ "${1:-}" = "--list" ]; then
  echo "On release now (students get these):"; git -C "$WT" ls-files; exit 0
fi
[ "$#" -ge 1 ] || { echo "usage: $0 <lab> [lab ...]   e.g.  $0 lab01"; exit 1; }

# Always ship the current shared toolkit, then the requested notebook(s).
git -C "$WT" checkout main -- labHelpers.py
for lab in "$@"; do
  f="$(git -C "$REPO" ls-files "${lab}*.ipynb" | head -1)"
  [ -n "$f" ] || { echo "no notebook on main matches '$lab'"; exit 1; }
  git -C "$WT" checkout main -- "$f"
  echo "  + $f"
done

git -C "$WT" add -A
if git -C "$WT" diff --cached --quiet; then
  echo "already up to date; nothing to publish"; exit 0
fi
git -C "$WT" commit -q -m "release: publish $*"
git -C "$WT" push -q origin release
echo "published to release: $*"
echo "students get it on their next Launch (nbgitpuller fast-forwards their copy)."
