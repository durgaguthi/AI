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
_Auto-updated: 2026-03-18 16:08:58_

### Recent commits
8f34e25 Auto-commit: 2026-03-18 16:03:47
ba6ec61 Auto-commit: 2026-03-18 15:58:31
80330a4 Auto-commit: 2026-03-18 15:53:23
a17e942 Auto-commit: 2026-03-18 15:48:15
7e4b74c Auto-commit: 2026-03-18 15:43:02

### Files changed since last commit
 M ContentCreation/ref/edge_persona.xlsx
 D ContentCreation/ref/~$edge_persona.xlsx
?? ContentCreation/ref/~$edge.xlsx

### Files in repo
- .DS_Store
- .env
- .env.example
- .gitignore
- CLAUDE.md
- ContentCreation/.DS_Store
- ContentCreation/ref/edge.xlsx
- ContentCreation/ref/edge1.xlsx
- ContentCreation/ref/edge_persona.xlsx
- ContentCreation/ref/~$edge_persona.xlsx
- adobe_analytics_dashboard.py
- auto-commit.sh
- tictactoe.html

