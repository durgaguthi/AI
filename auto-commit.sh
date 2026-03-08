#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

cd /Users/durga.guthi/AI

# Regenerate the Project Status section in CLAUDE.md
CLAUDE_FILE="CLAUDE.md"
MARKER="## Project Status"

# Build the new status block
STATUS_BLOCK="${MARKER}
_Auto-updated: $(date '+%Y-%m-%d %H:%M:%S')_

### Recent commits
$(git log --oneline -5 2>/dev/null || echo '(no commits yet)')

### Files changed since last commit
$(git status --short 2>/dev/null | grep -v '^$' || echo '(none)')

### Files in repo
$(git ls-files 2>/dev/null | grep -v '^$' | sed 's/^/- /')
"

# Strip everything from the marker to end of file, then append new block
if grep -q "^${MARKER}" "$CLAUDE_FILE" 2>/dev/null; then
    # Remove old status section
    CONTENT_BEFORE=$(sed "/^${MARKER}/,\$d" "$CLAUDE_FILE")
    printf '%s\n%s\n' "$CONTENT_BEFORE" "$STATUS_BLOCK" > "$CLAUDE_FILE"
else
    # Append for the first time
    printf '\n%s\n' "$STATUS_BLOCK" >> "$CLAUDE_FILE"
fi

git add -A
if ! git diff --cached --quiet; then
    git commit -m "Auto-commit: $(date '+%Y-%m-%d %H:%M:%S')"
    GH_TOKEN=$(gh auth token 2>/dev/null)
    git push "https://${GH_TOKEN}@github.com/durgaguthi/AI.git" main 2>/dev/null
fi
