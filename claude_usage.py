"""Fetch Claude usage data from claude.ai web API."""

import base64
import json
import os
import shutil
import sqlite3
import tempfile
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
        """Load saved config from file."""
        self.refresh_interval = None
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text())
                self.session_key = data.get("session_key")
                self.org_id = data.get("org_id")
                self.refresh_interval = data.get("refresh_interval")
                if self.session_key:
                    self._apply_session_key()
            except (json.JSONDecodeError, OSError):
                pass

    def _save_config(self, refresh_interval=None):
        """Save config to file."""
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "session_key": self.session_key,
            "org_id": self.org_id,
        }
        if refresh_interval is not None:
            data["refresh_interval"] = refresh_interval
        elif self.refresh_interval is not None:
            data["refresh_interval"] = self.refresh_interval
        CONFIG_FILE.write_text(json.dumps(data))

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

    def extract_session_from_desktop(self):
        """Extract sessionKey from Claude Desktop's Chromium cookie store (Windows only).
        Returns (session_key, org_id) or raises RuntimeError on failure.
        Requires pycryptodome.
        """
        import ctypes
        import ctypes.wintypes
        import re

        try:
            from Cryptodome.Cipher import AES
        except ImportError:
            try:
                from Crypto.Cipher import AES
            except ImportError:
                raise RuntimeError("Install pycryptodome first:\npip install pycryptodome")

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", ctypes.wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_char)),
            ]

        def dpapi_decrypt(encrypted):
            blob_in = DATA_BLOB(len(encrypted), ctypes.create_string_buffer(encrypted, len(encrypted)))
            blob_out = DATA_BLOB()
            if ctypes.windll.crypt32.CryptUnprotectData(
                ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
            ):
                data = ctypes.string_at(blob_out.pbData, blob_out.cbData)
                ctypes.windll.kernel32.LocalFree(blob_out.pbData)
                return data
            raise RuntimeError("DPAPI decryption failed")

        # Get encryption key from Local State
        local_state_path = os.path.join(os.environ.get("APPDATA", ""), "Claude", "Local State")
        if not os.path.exists(local_state_path):
            raise RuntimeError("Claude Desktop not found (no Local State file)")

        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.load(f)

        encrypted_key_b64 = local_state["os_crypt"]["encrypted_key"]
        encrypted_key = base64.b64decode(encrypted_key_b64)[5:]  # Remove "DPAPI" prefix
        key = dpapi_decrypt(encrypted_key)

        # Read cookies DB
        cookies_path = os.path.join(os.environ.get("APPDATA", ""), "Claude", "Network", "Cookies")
        if not os.path.exists(cookies_path):
            raise RuntimeError("Claude Desktop cookies DB not found")

        tmp = tempfile.mktemp(suffix=".db")
        # Try multiple methods to copy the locked Cookies file
        import subprocess
        copied = False
        # Method 1: esentutl (Windows built-in, can copy locked files)
        try:
            subprocess.run(
                ["esentutl.exe", "/y", cookies_path, "/vss", "/d", tmp],
                check=True, capture_output=True,
            )
            copied = True
        except (subprocess.CalledProcessError, OSError, FileNotFoundError):
            pass
        # Method 2: shutil.copy2 (works if not exclusively locked)
        if not copied:
            try:
                shutil.copy2(cookies_path, tmp)
                copied = True
            except OSError:
                pass
        # Method 3: Windows 'copy' command
        if not copied:
            try:
                subprocess.run(
                    ["cmd", "/c", "copy", "/y", cookies_path, tmp],
                    check=True, capture_output=True,
                )
                copied = True
            except (subprocess.CalledProcessError, OSError):
                pass
        # Method 4: Kill Claude Desktop, copy, then relaunch
        if not copied:
            claude_was_running = False
            try:
                # Check if Claude Desktop is running
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq claude.exe", "/NH"],
                    capture_output=True, text=True,
                )
                claude_was_running = "claude.exe" in result.stdout.lower()

                if claude_was_running:
                    subprocess.run(
                        ["taskkill", "/F", "/IM", "claude.exe"],
                        capture_output=True,
                    )
                    time.sleep(2)

                shutil.copy2(cookies_path, tmp)
                copied = True
            except OSError:
                pass
            finally:
                if claude_was_running:
                    # Relaunch Claude Desktop
                    # Find the latest installed version
                    claude_base = os.path.join(
                        os.environ.get("LOCALAPPDATA", ""),
                        "AnthropicClaude",
                    )
                    claude_exe = None
                    if os.path.isdir(claude_base):
                        app_dirs = sorted(
                            [d for d in os.listdir(claude_base) if d.startswith("app-")],
                            reverse=True,
                        )
                        for d in app_dirs:
                            candidate = os.path.join(claude_base, d, "claude.exe")
                            if os.path.exists(candidate):
                                claude_exe = candidate
                                break
                    if claude_exe and os.path.exists(claude_exe):
                        subprocess.Popen(
                            [claude_exe],
                            creationflags=0x00000008,  # DETACHED_PROCESS
                        )

        if not copied:
            raise RuntimeError("Cannot copy Cookies file.")

        try:
            conn = sqlite3.connect(tmp)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, encrypted_value FROM cookies "
                "WHERE host_key = '.claude.ai' AND name IN ('sessionKey', 'lastActiveOrg')"
            )
            rows = cursor.fetchall()
            conn.close()

            results = {}
            for name, encrypted_value in rows:
                if encrypted_value[:3] == b"v10":
                    nonce = encrypted_value[3:15]
                    ciphertext_tag = encrypted_value[15:]
                    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
                    decrypted = cipher.decrypt_and_verify(
                        ciphertext_tag[:-16], ciphertext_tag[-16:]
                    )
                    text = decrypted.decode("latin-1")
                    idx = text.find("sk-ant-")
                    if idx >= 0:
                        results[name] = text[idx:]
                    else:
                        m = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', text)
                        results[name] = m.group(0) if m else text
                else:
                    raise RuntimeError(f"Unknown encryption version: {encrypted_value[:3]}")

            if "sessionKey" not in results:
                raise RuntimeError("sessionKey cookie not found in Claude Desktop")

            return results["sessionKey"], results.get("lastActiveOrg")
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

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
