import os
from pathlib import Path

# Claude.ai web API base
CLAUDE_API_BASE = "https://claude.ai/api"

# Refresh interval in seconds
REFRESH_INTERVAL = 60

# Context window size (Claude Opus 4.6 = 200k tokens)
MAX_CONTEXT_TOKENS = 200_000

# Config file for storing session key
CONFIG_FILE = Path.home() / ".claude" / "system_tray_usage_config.json"
