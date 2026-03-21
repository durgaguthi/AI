# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

A collection of AI/web projects by Durga Guthi, currently containing a single-file browser game styled with Solidigm branding. All projects are auto-committed and pushed to GitHub every 5 minutes via a launchd job.

## Auto-commit Infrastructure

- **Script:** `auto-commit.sh` — stages all changes, commits with a timestamp, and pushes to `origin main`
- **Scheduler:** macOS launchd (`~/Library/LaunchAgents/com.durgaguthi.ai-autocommit.plist`), runs every 300 seconds
- **Log:** `.auto-commit.log` (gitignored)
- Push uses `gh auth token` to authenticate — requires the `gh` CLI to be logged in

To manually trigger: `bash auto-commit.sh`

To stop auto-commits:
```bash
launchctl unload ~/Library/LaunchAgents/com.durgaguthi.ai-autocommit.plist
```

## Current Projects

### `tictactoe.html`
A fully self-contained single-file Tic Tac Toe game. Open directly in any browser — no build step, no dependencies, no server needed.

**Architecture:** All CSS, HTML, and JS live in one file.
- Solidigm brand palette defined as CSS custom properties in `:root`
- Game state: flat 9-element array (`board[]`), `current` player, `gameOver` flag, persistent `scores` object
- Symbols drawn as inline SVG elements created dynamically via `makeSVG(player)`
- Win detection: checks all 8 winning combinations from the `WINS` constant on every move

**Known quirk:** `makeSVG` for X renders 4 lines (the first two are duplicates from a `.flat()` leftover); visually correct but redundant.
## Project Status
_Auto-updated: 2026-03-20 23:11:42_

### Recent commits
ad7ab36 Auto-commit: 2026-03-20 23:06:41
8ebec12 Auto-commit: 2026-03-20 23:01:39
a8003f2 Auto-commit: 2026-03-20 22:56:37
8466626 Auto-commit: 2026-03-20 22:51:36
daa69b4 Auto-commit: 2026-03-20 22:46:35

### Files changed since last commit
(none)

### Files in repo
- .DS_Store
- .env
- .env.example
- .gitignore
- CLAUDE.md
- ContentCreation/.DS_Store
- ContentCreation/b2b-persona-copy.skill
- ContentCreation/b2b_persona_copy_eval_review.html
- ContentCreation/ref/edge.xlsx
- ContentCreation/ref/edge1.xlsx
- ContentCreation/ref/edge_persona.xlsx
- Solidigm_Analytics_Report_JanFeb_FY26.pptx
- adobe_analytics_dashboard.py
- auto-commit.sh
- dotcom_analytics.xlsx
- dotcom_analytics_feb2026.xlsx
- dotcom_analytics_jan2026.xlsx
- tictactoe.html
- webanalytics/.DS_Store
- webanalytics/Solidigm_Analytics_Report_JanFeb_FY26.pptx
- webanalytics/data/dotcom_analytics.xlsx
- webanalytics/data/dotcom_analytics_feb2026.xlsx
- webanalytics/data/dotcom_analytics_jan2026.xlsx
- webanalytics/eval-review-iteration-1.html
- webanalytics/skill-test-results.pptx
- webanalytics/~$Solidigm_Analytics_Report_JanFeb_FY26.pptx

