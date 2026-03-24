# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Windows system tray app that monitors Claude.ai usage in real-time. Displays 5-hour utilization as a color-coded number in the tray, with tooltip showing reset countdown and 7-day stats.

## Commands

```bash
# Run from source
pip install -r requirements.txt
python main.py

# Build standalone exe
python build.py
# Output: dist/ClaudeToolbar.exe
```

## Architecture

Three files, one data flow:

```
config.py (constants) ──→ claude_usage.py (API client) ──→ main.py (tray UI)
```

- **main.py** — `ClaudeToolbar` class: tray icon rendering (Pillow), pystray menu, tkinter dialogs, threading
- **claude_usage.py** — `ClaudeWebAPI` class: session auth, HTTP calls to claude.ai/api, token estimation
- **config.py** — `CLAUDE_API_BASE`, `REFRESH_INTERVAL`, `MAX_CONTEXT_TOKENS`, `CONFIG_FILE` path

### Threading Model

- **Main thread**: `pystray.Icon.run()` (blocking)
- **Updater daemon thread**: polls `refresh_data()` every N seconds
- **Dialog daemon threads**: spawned on-demand for tkinter input prompts

No locks — data access is single-writer (updater thread writes, main thread reads on menu build).

### API Endpoints Used

All requests go through `curl_cffi` with Chrome TLS impersonation to bypass Cloudflare.

- `GET /api/organizations` — validate session, get org UUID
- `GET /api/organizations/{org}/usage` — 5h and 7d utilization percentages
- `GET /api/organizations/{org}/chat_conversations` — recent conversations
- `GET /api/organizations/{org}/chat_conversations/{id}` — message details for token estimation

### Auth & Storage

Session key stored as cookie (`sessionKey`). Persisted with org_id to `~/.claude/toolbar_config.json`.

## Key Constraints

- **Windows-only** — uses pystray._win32, Arial fonts, Windows paths
- **curl_cffi required** — standard `requests` gets blocked by Cloudflare
- **Chrome cookie DB is locked** while Chrome runs — browser cookie import was attempted and removed; manual paste is the only reliable auth method
- **Tray icon is 64x64** but rendered at ~16-24px by Windows — text must be large/bold to be readable
- **PyInstaller excludes** in build.py must not remove modules needed by curl_cffi (e.g., `email`, `xml` are required by `importlib.metadata`)
