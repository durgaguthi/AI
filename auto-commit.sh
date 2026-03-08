#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

cd /Users/durga.guthi/AI
git add -A
if ! git diff --cached --quiet; then
    git commit -m "Auto-commit: $(date '+%Y-%m-%d %H:%M:%S')"
    GH_TOKEN=$(gh auth token 2>/dev/null)
    git push "https://${GH_TOKEN}@github.com/durgaguthi/AI.git" main 2>/dev/null
fi
