"""Fetch Claude usage data from claude.ai web API."""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from curl_cffi import requests as curl_requests

from config import CLAUDE_API_BASE, CONFIG_FILE, MAX_CONTEXT_TOKENS


class ClaudeWebAPI:
    def __init__(self):
        self.session_key = None
        self.org_id = None
        self.session = curl_requests.Session(impersonate="chrome")
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": "https://claude.ai",
            "Referer": "https://claude.ai/",
        })
        self.last_error = None
        self._load_config()

    def _load_config(self):
        """Load saved session key from config file."""
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text())
                self.session_key = data.get("session_key")
                self.org_id = data.get("org_id")
                if self.session_key:
                    self._apply_session_key()
            except (json.JSONDecodeError, OSError):
                pass

    def _save_config(self):
        """Save session key to config file."""
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps({
            "session_key": self.session_key,
            "org_id": self.org_id,
        }))

    def _apply_session_key(self):
        """Apply session key as cookie."""
        self.session.cookies.set(
            "sessionKey", self.session_key, domain=".claude.ai"
        )

    def set_session_key(self, key):
        """Set a new session key."""
        self.session_key = key.strip()
        self._apply_session_key()
        # Try to fetch org info to validate
        if self._fetch_org_id():
            self._save_config()
            return True
        return False

    def is_authenticated(self):
        return self.session_key is not None and self.org_id is not None

    def _fetch_org_id(self):
        """Fetch the organization ID from the API."""
        try:
            resp = self.session.get(
                f"{CLAUDE_API_BASE}/organizations",
                timeout=10,
            )
            if resp.status_code == 200:
                orgs = resp.json()
                if orgs and len(orgs) > 0:
                    self.org_id = orgs[0].get("uuid")
                    return True
            self.last_error = f"Auth failed (HTTP {resp.status_code}): {resp.text[:200]}"
        except Exception as e:
            self.last_error = f"Connection error: {e}"
        return False

    def get_usage(self):
        """Fetch usage data from claude.ai settings/usage page API."""
        if not self.is_authenticated():
            self.last_error = "Not authenticated"
            return None

        try:
            resp = self.session.get(
                f"{CLAUDE_API_BASE}/organizations/{self.org_id}/usage",
                timeout=15,
            )
            if resp.status_code == 200:
                self.last_error = None
                return resp.json()
            elif resp.status_code == 403:
                self.last_error = "Session expired - update session key"
                self.session_key = None
                self.org_id = None
                self._save_config()
            else:
                self.last_error = f"HTTP {resp.status_code}"
        except Exception as e:
            self.last_error = f"Connection error: {e}"
        return None

    def get_current_session_context(self):
        """Fetch current active conversation context usage."""
        if not self.is_authenticated():
            return None

        try:
            # Get recent conversations
            resp = self.session.get(
                f"{CLAUDE_API_BASE}/organizations/{self.org_id}/chat_conversations",
                params={"limit": 5},
                timeout=15,
            )
            if resp.status_code != 200:
                return None

            conversations = resp.json()
            if not conversations:
                return None

            # Get the most recent conversation
            latest = conversations[0]
            conv_id = latest.get("uuid")
            name = latest.get("name", "Untitled")
            updated = latest.get("updated_at", "")
            model = latest.get("model")

            # Check if it was recently active (within last 2 hours)
            if updated:
                try:
                    dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    if datetime.now(dt.tzinfo) - dt > timedelta(hours=2):
                        return {"active": False, "name": name}
                except (ValueError, TypeError):
                    pass

            # Get conversation details for token count
            resp2 = self.session.get(
                f"{CLAUDE_API_BASE}/organizations/{self.org_id}/chat_conversations/{conv_id}",
                timeout=15,
            )
            if resp2.status_code != 200:
                return {"active": True, "name": name, "model": model}

            conv_data = resp2.json()
            messages = conv_data.get("chat_messages", [])

            # Estimate token usage from message count and length
            total_chars = 0
            msg_count = 0
            for msg in messages:
                content = msg.get("text", "") or msg.get("content", "")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            total_chars += len(block.get("text", ""))
                elif isinstance(content, str):
                    total_chars += len(content)
                msg_count += 1

            # Rough estimate: ~4 chars per token
            estimated_tokens = total_chars // 4
            context_percent = min(100.0, (estimated_tokens / MAX_CONTEXT_TOKENS) * 100)

            return {
                "active": True,
                "name": name,
                "model": model or "unknown",
                "estimated_tokens": estimated_tokens,
                "context_percent": context_percent,
                "message_count": msg_count,
            }

        except Exception as e:
            self.last_error = f"Connection error: {e}"
            return None


def format_tokens(n):
    """Format token count for display."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)
