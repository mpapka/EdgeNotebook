#!/usr/bin/env bash
# ============================================================================
# publish.sh — release lab notebook(s) to students, in one step.
#
# Does BOTH halves of a weekly rollout:
#   1. Copies the named notebook(s) + the shared toolkit onto the `release`
#      branch (what nbgitpuller pulls into each student's ~/EdgeNotebook).
#   2. Flips `published: true` on the matching course-site lab card and pushes the
#      site, so the Labs page lists only labs that are actually available.
#
# The .md docs, this script, and unreleased labs never touch `release`, so students
# only ever get what you have published.
#
#   ./publish.sh lab01                 # accepts lab01, lab01DevTooling, or a filename
#   ./publish.sh lab01 lab02           # several at once
#   ./publish.sh --list                # show what is currently on release
#   ./publish.sh --unpublish lab01     # withdraw a lab: off release, card hidden
#
# Develop/test on `main` (Hermes tests main). A dedicated worktree
# (../EdgeNotebook-release) is used so your main checkout is never disturbed.
# Course-site checkout defaults to ../UIC_Course_Website; override with
# COURSE_SITE_DIR. If the site is absent, the card step is skipped.
# ============================================================================
set -euo pipefail

# In-place edit that behaves the same on macOS and Linux. GNU sed and BSD sed
# disagree about `sed -i` (BSD reads the script as a backup suffix), so use perl,
# which is present on both and needs no suffix.
inplace() { perl -pi -e "$1" "$2"; }

REPO="$(git -C "$(dirname "$(readlink -f "$0")")" rev-parse --show-toplevel)"
WT="${REPO}-release"
SITE="${COURSE_SITE_DIR:-$(dirname "$REPO")/UIC_Course_Website}"

# What every student needs no matter which labs are published. This is the whole
# toolkit, not just the module: labHelpers finds uicTheme.css by looking NEXT TO
# itself, so shipping the module alone leaves applyNotebookTheme() with nothing to
# load -- and it fails SILENTLY by design, so the labs would simply arrive unskinned
# with nothing in any log to say why. These three travel together.
toolkit=(labHelpers.py uicTheme.css uicCourse.json)

git -C "$REPO" fetch -q origin release
if ! git -C "$REPO" worktree list --porcelain | grep -qx "worktree $WT"; then
  git -C "$REPO" worktree add -q "$WT" release 2>/dev/null \
    || git -C "$REPO" worktree add -q -B release "$WT" origin/release
fi
git -C "$WT" checkout -q release
git -C "$WT" reset -q --hard origin/release
git -C "$WT" clean -fdq            # worktree == release exactly; no stray untracked files

if [ "${1:-}" = "--list" ]; then
  echo "On release now (students get these):"; git -C "$WT" ls-files; exit 0
fi

MODE=publish
if [ "${1:-}" = "--unpublish" ]; then MODE=unpublish; shift; fi
[ "$#" -ge 1 ] || { echo "usage: $0 [--unpublish] <lab> [lab ...]   e.g.  $0 lab01"; exit 1; }

# --- 1. add to, or remove from, the release branch ---
files=()
if [ "$MODE" = publish ]; then
  git -C "$WT" checkout main -- "${toolkit[@]}"
  for lab in "$@"; do
    f="$(git -C "$REPO" ls-files "${lab}*.ipynb" | head -1)"
    [ -n "$f" ] || { echo "no notebook on main matches '$lab'"; exit 1; }
    git -C "$WT" checkout main -- "$f"
    files+=("$f"); echo "  + $f"
  done
  git -C "$WT" add -- "${toolkit[@]}" "${files[@]}"   # explicit: never sweep in stray files
else
  # Resolve against release, not main: only what students actually have can be withdrawn.
  for lab in "$@"; do
    f="$(git -C "$WT" ls-files "${lab}*.ipynb" | head -1)"
    [ -n "$f" ] || { echo "not on release, nothing to withdraw: '$lab'"; exit 1; }
    case " ${toolkit[*]} " in *" $f "*) echo "refusing to remove the shared toolkit"; exit 1;; esac
    git -C "$WT" rm -q -- "$f"
    files+=("$f"); echo "  - $f"
  done
fi

if git -C "$WT" diff --cached --quiet; then
  echo "release already current for: $*"
else
  git -C "$WT" commit -q -m "release: $MODE $*"
  git -C "$WT" push -q origin release
  echo "${MODE}ed on release: $*"
fi

# --- 2. reveal or hide the matching site card(s) so the Labs page tracks release ---
if [ "$MODE" = publish ]; then STATE=true; VERB=revealed; else STATE=false; VERB=hid; fi
if [ -d "$SITE/_labs" ]; then
  for f in "${files[@]}"; do
    card="$(grep -rl "file: \"$f\"" "$SITE/_labs" 2>/dev/null | head -1)"
    [ -n "$card" ] || { echo "  (no site card references $f)"; continue; }
    if grep -q '^published:' "$card"; then
      inplace "s/^published:.*/published: $STATE/" "$card"
    else
      inplace "s{^(file:.*)\$}{\$1\\npublished: $STATE}" "$card"
    fi
    echo "  $VERB card: $(basename "$card")"
  done
  if ! git -C "$SITE" diff --quiet -- _labs; then
    git -C "$SITE" add _labs
    git -C "$SITE" commit -q -m "Labs: $VERB card(s) for $*"
    echo "  pushing site ..."
    git -C "$SITE" push 2>&1 | grep -vE 'dependabot|vulnerabilit|^remote:( |$)' | tail -4 || true
  else
    echo "  site cards already current."
  fi
else
  echo "  (course site not at $SITE; skipped card reveal -- set COURSE_SITE_DIR)"
fi
echo "done. students get it on their next Launch (nbgitpuller fast-forwards)."
echo "note: the Labs page only changes once the site is rebuilt and rsynced on"
echo "      the box -- pushing alone does not deploy. See DEPLOY.md."
