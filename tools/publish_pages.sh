#!/bin/sh
# Mirror ytfeed RSS files to a GitHub Pages repo. Commits and pushes only if
# something changed. Edit the variables below, then run by hand, from cron or
# from launchd (see README).
#
# One-time setup: create a public repo with Pages enabled (branch main, root),
# clone it to PAGES_CLONE, and set a git identity inside that clone.

# --- configure ---------------------------------------------------------------
FEED_DIR="$HOME/ytfeed/data"                 # folder with feed.xml, <source>.xml
FEED_FILES="feed.xml"                        # space-separated, e.g. "feed.xml tldr.xml"
PAGES_CLONE="$HOME/ytfeed-pages/repo"        # local clone of the Pages repo
PAGES_BRANCH="main"
LOG_FILE="$HOME/ytfeed-pages/publish.log"
# -----------------------------------------------------------------------------

export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG_FILE"; }

mkdir -p "$(dirname "$LOG_FILE")"
cd "$PAGES_CLONE" || { log "ERROR no clone at $PAGES_CLONE"; exit 1; }
git pull -q --rebase origin "$PAGES_BRANCH" >> "$LOG_FILE" 2>&1 || log "WARN pull failed"

for name in $FEED_FILES; do
  [ -f "$FEED_DIR/$name" ] && cp "$FEED_DIR/$name" "$PAGES_CLONE/$name"
done

git add -A
if git diff --cached --quiet; then exit 0; fi
git commit -qm "Update feeds $(date '+%Y-%m-%d %H:%M')" >> "$LOG_FILE" 2>&1
if git push -q origin "$PAGES_BRANCH" >> "$LOG_FILE" 2>&1; then
  log "pushed: $(git diff --name-only HEAD~1 | tr '\n' ' ')"
else
  log "ERROR push failed"; exit 1
fi
