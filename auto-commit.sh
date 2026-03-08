#!/bin/bash
cd /Users/durga.guthi/AI
git add -A
git diff --cached --quiet || git commit -m "Auto-commit: $(date '+%Y-%m-%d %H:%M:%S')"
git push origin main 2>/dev/null
