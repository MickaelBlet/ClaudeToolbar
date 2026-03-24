"""
Claude Code Toolbar - Windows system tray app showing context and weekly usage.
Fetches data from claude.ai web API.
"""

import threading
import time
import tkinter as tk
from tkinter import simpledialog, messagebox

from PIL import Image, ImageDraw, ImageFont

import pystray

from claude_usage import ClaudeWebAPI, format_tokens
from config import REFRESH_INTERVAL


class ClaudeToolbar:
    def __init__(self):
        self.running = True
        self.api = ClaudeWebAPI()
        self.session_data = None
        self.usage_data = None
        self.icon = None
        self.refresh_interval = REFRESH_INTERVAL

    def create_icon_image(self, percent=0, connected=True):
        """Create a tray icon showing context usage percentage."""
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        if not connected:
            # Dark background
            draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=8, fill="#333333")
            try:
                font = ImageFont.truetype("arialbd.ttf", 24)
            except OSError:
                try:
                    font = ImageFont.truetype("arial.ttf", 24)
                except OSError:
                    font = ImageFont.load_default()
            text = "—"
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(((size - tw) / 2, (size - th) / 2), text, fill="#888888", font=font)
            return img

        # Colored number on transparent background
        if percent <= 60:
            text_color = "#4ade80"  # green
        elif percent <= 85:
            text_color = "#facc15"  # yellow
        else:
            text_color = "#ef4444"  # red

        num_text = str(int(percent))
        try:
            font = ImageFont.truetype("arialbd.ttf", 64 if len(num_text) <= 2 else 48)
        except OSError:
            try:
                font = ImageFont.truetype("arial.ttf", 64 if len(num_text) <= 2 else 48)
            except OSError:
                font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), num_text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            ((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]),
            num_text,
            fill=text_color,
            font=font,
        )

        return img

    def _build_tooltip(self, percent, connected):
        if connected and self.usage_data and isinstance(self.usage_data, dict):
            five_hour = self.usage_data.get("five_hour", {})
            week = self.usage_data.get("seven_day", {})
            week_pct = week.get("utilization", 0) if week else 0
            # Calculate time remaining until 5h reset
            reset_str = ""
            if five_hour and five_hour.get("resets_at"):
                try:
                    from datetime import datetime, timezone
                    reset_at = datetime.fromisoformat(five_hour["resets_at"])
                    now = datetime.now(timezone.utc)
                    remaining = reset_at - now
                    total_seconds = int(remaining.total_seconds())
                    if total_seconds > 0:
                        hours = total_seconds // 3600
                        minutes = (total_seconds % 3600) // 60
                        reset_str = f" (reset {hours}h{minutes:02d}m)"
                except (ValueError, TypeError):
                    pass
            return f"5h: {percent:.0f}%{reset_str} | 7d: {week_pct:.0f}%"
        elif connected:
            return f"5h: {percent:.0f}%"
        return "Claude Toolbar: Not connected"

    def build_menu(self):
        """Build the system tray context menu."""
        items = []

        if not self.api.is_authenticated():
            items.append(pystray.MenuItem("Not connected", None, enabled=False))
            if self.api.last_error:
                items.append(pystray.MenuItem(f"  Error: {self.api.last_error}", None, enabled=False))
            items.append(pystray.MenuItem("Set Session Key...", self.on_set_key))
            items.append(pystray.Menu.SEPARATOR)
            items.append(pystray.MenuItem("Quit", self.on_quit))
            return pystray.Menu(*items)

        # Session context info
        if self.session_data and self.session_data.get("active"):
            s = self.session_data
            ctx_pct = s.get("context_percent", 0)
            name = s.get("name", "Unknown")
            items.append(pystray.MenuItem(f"Session: {name[:40]}", None, enabled=False))
            items.append(
                pystray.MenuItem(
                    f"  Context: {ctx_pct:.1f}% (~{format_tokens(s.get('estimated_tokens', 0))} tokens)",
                    None,
                    enabled=False,
                )
            )
            items.append(
                pystray.MenuItem(
                    f"  Messages: {s.get('message_count', 0)}",
                    None,
                    enabled=False,
                )
            )
            if s.get("model"):
                items.append(
                    pystray.MenuItem(f"  Model: {s['model']}", None, enabled=False)
                )
        else:
            items.append(pystray.MenuItem("No active session", None, enabled=False))

        items.append(pystray.Menu.SEPARATOR)

        # Usage data from settings/usage
        if self.usage_data:
            items.append(pystray.MenuItem("--- Usage Stats ---", None, enabled=False))
            # Display whatever fields the API returns
            if isinstance(self.usage_data, dict):
                for key, value in self.usage_data.items():
                    if key in ("uuid", "organization_uuid"):
                        continue
                    label = key.replace("_", " ").title()
                    if isinstance(value, (int, float)):
                        items.append(
                            pystray.MenuItem(f"  {label}: {format_tokens(int(value))}", None, enabled=False)
                        )
                    elif isinstance(value, str):
                        items.append(
                            pystray.MenuItem(f"  {label}: {value}", None, enabled=False)
                        )
                    elif isinstance(value, dict):
                        items.append(pystray.MenuItem(f"  {label}:", None, enabled=False))
                        for k2, v2 in value.items():
                            lbl2 = k2.replace("_", " ").title()
                            items.append(
                                pystray.MenuItem(f"    {lbl2}: {v2}", None, enabled=False)
                            )
                    elif isinstance(value, list) and len(value) <= 5:
                        items.append(pystray.MenuItem(f"  {label}:", None, enabled=False))
                        for entry in value:
                            if isinstance(entry, dict):
                                summary = ", ".join(f"{k}: {v}" for k, v in list(entry.items())[:3])
                                items.append(
                                    pystray.MenuItem(f"    {summary}", None, enabled=False)
                                )
        elif self.api.last_error:
            items.append(pystray.MenuItem(f"Error: {self.api.last_error}", None, enabled=False))

        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("Set Session Key...", self.on_set_key))
        items.append(pystray.MenuItem(f"Refresh Interval ({self.refresh_interval}s)...", self.on_set_refresh))
        items.append(pystray.MenuItem("Refresh", self.on_refresh))
        items.append(pystray.MenuItem("Open Usage Page", self.on_open_usage))
        items.append(pystray.MenuItem("Quit", self.on_quit))

        return pystray.Menu(*items)

    def on_set_refresh(self, icon, item):
        """Prompt user for refresh interval."""
        thread = threading.Thread(target=self._prompt_refresh_interval, daemon=True)
        thread.start()

    def _prompt_refresh_interval(self):
        """Show a dialog to set the refresh interval."""
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        value = simpledialog.askinteger(
            "Claude Toolbar - Refresh Interval",
            f"Enter refresh interval in seconds (current: {self.refresh_interval}s):",
            initialvalue=self.refresh_interval,
            minvalue=10,
            maxvalue=3600,
            parent=root,
        )
        root.destroy()
        if value:
            self.refresh_interval = value
            if self.icon:
                self.icon.menu = self.build_menu()

    def on_set_key(self, icon, item):
        """Prompt user for session key."""
        thread = threading.Thread(target=self._prompt_session_key, daemon=True)
        thread.start()

    def _prompt_session_key(self):
        """Show a dialog to enter the session key."""
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        messagebox.showinfo(
            "Claude Toolbar - Session Key",
            "To get your session key:\n\n"
            "1. Open https://claude.ai in your browser\n"
            "2. Open DevTools (F12) → Application → Cookies\n"
            "3. Find the cookie named 'sessionKey'\n"
            "4. Copy its value\n\n"
            "Paste it in the next dialog.",
            parent=root,
        )

        key = simpledialog.askstring(
            "Claude Toolbar",
            "Paste your sessionKey cookie value:",
            parent=root,
        )
        root.destroy()

        if key:
            if self.api.set_session_key(key):
                self.refresh_data()
            else:
                root2 = tk.Tk()
                root2.withdraw()
                root2.attributes("-topmost", True)
                messagebox.showerror(
                    "Claude Toolbar",
                    f"Authentication failed.\n{self.api.last_error or 'Invalid session key.'}",
                    parent=root2,
                )
                root2.destroy()

    def on_refresh(self, icon, item):
        """Manual refresh."""
        self.refresh_data()

    def on_open_usage(self, icon, item):
        """Open the usage page in browser."""
        import webbrowser
        webbrowser.open("https://claude.ai/settings/usage")

    def on_quit(self, icon, item):
        """Quit the application."""
        self.running = False
        icon.stop()

    def refresh_data(self):
        """Fetch latest usage data from web API."""
        if self.api.is_authenticated():
            self.session_data = self.api.get_current_session_context()
            self.usage_data = self.api.get_usage()

        # Update icon with 5-hour utilization
        percent = 0
        connected = self.api.is_authenticated()
        if self.usage_data and isinstance(self.usage_data, dict):
            five_hour = self.usage_data.get("five_hour")
            if five_hour:
                percent = five_hour.get("utilization", 0)

        if self.icon:
            self.icon.icon = self.create_icon_image(percent, connected)
            self.icon.menu = self.build_menu()

            self.icon.title = self._build_tooltip(percent, connected)

    def update_loop(self):
        """Background thread that periodically refreshes data."""
        while self.running:
            try:
                self.refresh_data()
            except Exception as e:
                print(f"Error refreshing: {e}")
            time.sleep(self.refresh_interval)

    def run(self):
        """Start the toolbar application."""
        # Initial data fetch
        self.refresh_data()

        percent = 0
        connected = self.api.is_authenticated()
        if self.usage_data and isinstance(self.usage_data, dict):
            five_hour = self.usage_data.get("five_hour")
            if five_hour:
                percent = five_hour.get("utilization", 0)

        self.icon = pystray.Icon(
            "claude_toolbar",
            icon=self.create_icon_image(percent, connected),
            title=self._build_tooltip(percent, connected),
            menu=self.build_menu(),
        )

        # Start background updater
        updater = threading.Thread(target=self.update_loop, daemon=True)
        updater.start()

        # If not authenticated, try browser import first
        if not connected:
            prompt_thread = threading.Thread(target=self._prompt_session_key, daemon=True)
            prompt_thread.start()

        # Run the icon (blocks)
        self.icon.run()


def main():
    app = ClaudeToolbar()
    app.run()


if __name__ == "__main__":
    main()
