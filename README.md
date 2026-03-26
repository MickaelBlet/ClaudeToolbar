<p align="center">
  <img src="assets/tray_icons_preview.drawio.png" alt="Tray icon states" />
</p>

<h1 align="center">ClaudeSystemTrayUsage</h1>

<p align="center">
  <b>Real-time Claude.ai usage monitor in your Windows system tray</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows-blue?logo=windows" alt="Windows" />
  <img src="https://img.shields.io/badge/python-3.10+-yellow?logo=python" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License" />
</p>

---

## Features

### Live Tray Icon
Your **5-hour usage percentage** displayed as a bold number on a dark rounded background, color-coded at a glance:

| Usage | Color | Meaning |
|-------|-------|---------|
| 0–60% | ![#4ade80](https://placehold.co/12x12/4ade80/4ade80.png) Green | Plenty of capacity |
| 61–85% | ![#facc15](https://placehold.co/12x12/facc15/facc15.png) Yellow | Getting close |
| 86–100% | ![#ef4444](https://placehold.co/12x12/ef4444/ef4444.png) Red | Near the limit |

### Hover Tooltip

<p align="center">
  <img src="assets/tooltip_preview.drawio.png" alt="Tooltip showing usage and reset timer" />
</p>

- **5-hour** and **7-day** usage at a glance
- **Countdown timer** until your next 5-hour reset

### Right-Click Menu

<p align="center">
  <img src="assets/menu_preview.drawio.png" alt="Context menu with usage details" />
</p>

- Detailed usage breakdown (5h, 7d, extra usage)
- Active session info (context %, model, message count)
- Configurable refresh interval (persisted across restarts)
- **Auto-detect Session Key** from Claude Desktop (no manual copy needed)
- **Launch at Startup** toggle (adds/removes Windows Registry Run entry)
- Set Session Key / Refresh / Open Usage Page / Quit

---

## Quick Start

### Option 1: Standalone .exe (recommended)

Download `ClaudeSystemTrayUsage.exe` from [Releases](../../releases) and run it. No Python needed.

### Option 2: Run from source

```bash
pip install -r requirements.txt
python main.py
```

### Option 3: Build the .exe yourself

```bash
pip install -r requirements.txt
python build.py
```

The executable will be at `dist/ClaudeSystemTrayUsage.exe`.

---

## Setup

On first launch, you have two options to authenticate:

### Auto-detect from Claude Desktop (recommended)

Click **"Auto-detect Session Key (Claude Desktop)"** in the tray menu. This extracts the session cookie directly from Claude Desktop's local storage. Requires `pycryptodome` (`pip install pycryptodome`) when running from source.

> If the cookie file is locked, the app will briefly close and relaunch Claude Desktop to read it.
> The session cookie is stored locally at `~/.claude/system_tray_usage_config.json`

### Manual session key

1. Open [claude.ai](https://claude.ai) in your browser
2. Press `F12` → **Application** tab → **Cookies** → `claude.ai`
3. Find the cookie named **`sessionKey`**
4. Copy its value and paste into the dialog

> The key is stored locally at `~/.claude/system_tray_usage_config.json`

---

## Configuration

The **refresh interval** can be changed directly from the tray menu via **"Refresh Interval (60s)..."**. The setting is persisted in `~/.claude/system_tray_usage_config.json`.

**Launch at Startup** can be toggled from the tray menu. This adds or removes a `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` registry entry pointing to the app executable (or `python main.py` when running from source).

Default values in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `REFRESH_INTERVAL` | `60` | Seconds between API refreshes (configurable from tray) |
| `MAX_CONTEXT_TOKENS` | `200,000` | Context window size for token estimation |

---

## How It Works

```
ClaudeSystemTrayUsage
    │
    ├─ Polls claude.ai/api every 60s
    │   ├─ /organizations/{org}/usage        → 5h & 7d utilization %
    │   └─ /organizations/{org}/conversations → active session context
    │
    ├─ Uses curl_cffi (Chrome TLS fingerprint) to bypass Cloudflare
    │
    └─ Renders usage as a colored number in the system tray
```

## Dependencies

| Package | Purpose |
|---------|---------|
| [`pystray`](https://pypi.org/project/pystray/) | System tray icon |
| [`Pillow`](https://pypi.org/project/Pillow/) | Icon image rendering |
| [`curl_cffi`](https://pypi.org/project/curl-cffi/) | HTTP client (Cloudflare bypass) |
| [`pycryptodome`](https://pypi.org/project/pycryptodome/) | Cookie decryption (for auto-detect) |

## Requirements

- Windows 10/11
- Python 3.10+ (for source/build)
- [Claude Pro or Team](https://claude.ai) account

---

## License

MIT
