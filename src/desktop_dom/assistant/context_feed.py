from __future__ import annotations
import re
import sys
import time
import json
import logging
import sqlite3
import subprocess
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger("desktop_dom.assistant.context_feed")


@dataclass
class ActiveContextSnapshot:
    """
    Structured telemetry snapshot representing the user's active desktop environment
    at a single point in time. Ingested from OS process tables, active window DOM,
    and browser tab state to synthesize real-time meaning and intent.
    """
    timestamp: float
    frontmost_app: str
    window_title: str
    activity_category: str  # "Gaming", "Engineering", "Communication", "Research", "Design", "General"
    focused_topic: str
    suggested_playlist: str
    suggested_genre: str
    browser_name: Optional[str] = None
    browser_url: Optional[str] = None
    browser_title: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ContextFeedEngine:
    """
    Stage 1 & Stage 2 Engine for the Crcle.ai Intent Layer.
    - Stage 1 (Data Ingestion / Feeding): Ingests frontmost application, active window title,
      and real-time browser tab (Chrome/Safari/Arc) via native OS IPC and accessibility trees.
    - Stage 2 (Meaning Synthesis): Synthesizes raw telemetry into human activity categories,
      focal topics, and contextual habit mappings (e.g. FIFA gaming -> FIFA Soundtrack,
      VS Code / GitHub -> Deep Focus).
    """

    def __init__(self, memory=None):
        self.memory = memory
        self._last_snapshot: Optional[ActiveContextSnapshot] = None
        self._init_memory_tables()

    def _init_memory_tables(self):
        """Ensures the context_feed table exists in the SQLite memory engine."""
        if not self.memory:
            return
        try:
            with self.memory._lock, self.memory._get_connection() as conn:
                conn.execute("""
                CREATE TABLE IF NOT EXISTS context_feed (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    frontmost_app TEXT NOT NULL,
                    window_title TEXT,
                    activity_category TEXT NOT NULL,
                    focused_topic TEXT,
                    browser_name TEXT,
                    browser_url TEXT,
                    browser_title TEXT,
                    suggested_playlist TEXT,
                    metadata TEXT DEFAULT '{}'
                );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_context_timestamp ON context_feed(timestamp DESC);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_context_activity ON context_feed(activity_category);")
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to initialize context_feed table: {e}")

    def capture_active_context(self, record: bool = True) -> ActiveContextSnapshot:
        """
        Captures the current desktop context in <20ms using native macOS IPC.
        Reads active application, window title, and browser tab (if in Chrome/Safari/Arc).
        Synthesizes activity classification and contextual habit mappings.
        """
        now = time.time()
        frontmost_app, window_title = self._get_frontmost_app_and_title()
        browser_name, browser_title, browser_url = self.get_browser_tab(frontmost_app)

        # Stage 2: Meaning Synthesis
        activity, topic, playlist, genre = self.classify_activity(
            frontmost_app=frontmost_app,
            window_title=window_title,
            browser_name=browser_name,
            browser_title=browser_title,
            browser_url=browser_url,
        )

        snapshot = ActiveContextSnapshot(
            timestamp=now,
            frontmost_app=frontmost_app,
            window_title=window_title,
            activity_category=activity,
            focused_topic=topic,
            suggested_playlist=playlist,
            suggested_genre=genre,
            browser_name=browser_name,
            browser_url=browser_url,
            browser_title=browser_title,
            metadata={
                "feed_latency_ms": round((time.time() - now) * 1000, 2),
                "platform": sys.platform,
            }
        )

        self._last_snapshot = snapshot

        if record and self.memory:
            self.record_snapshot(snapshot)

        return snapshot

    def _get_frontmost_app_and_title(self) -> Tuple[str, str]:
        """Resolves the frontmost application name and its active window title."""
        if sys.platform != "darwin":
            return "Desktop", "Main Window"

        try:
            osa = '''
            tell application "System Events"
                set frontProc to first process whose frontmost is true
                set procName to name of frontProc
                set winTitle to ""
                try
                    if exists (window 1 of frontProc) then
                        set winTitle to name of window 1 of frontProc
                    end if
                end try
                return procName & "|||" & winTitle
            end tell
            '''
            res = subprocess.run(["osascript", "-e", osa], capture_output=True, text=True, timeout=1.2)
            if res.returncode == 0 and "|||" in res.stdout:
                parts = res.stdout.strip().split("|||", 1)
                return parts[0].strip() or "Desktop", parts[1].strip() or ""
        except Exception:
            pass

        return "Desktop", ""

    def get_browser_tab(self, frontmost_app: Optional[str] = None) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Queries the active browser tab (URL and title) via AppleScript in <15ms.
        Supported browsers: Google Chrome, Arc, Brave Browser, Safari, Microsoft Edge.
        Returns: (browser_name, tab_title, tab_url)
        """
        if sys.platform != "darwin":
            return None, None, None

        app_lower = (frontmost_app or "").lower()

        # 1. Chromium-based browsers (Google Chrome, Arc, Brave, Microsoft Edge)
        chromium_apps = [
            ("Google Chrome", "google chrome"),
            ("Arc", "arc"),
            ("Brave Browser", "brave"),
            ("Microsoft Edge", "edge"),
        ]

        for target_name, match_str in chromium_apps:
            if match_str in app_lower or (not frontmost_app and self._is_process_running(target_name)):
                try:
                    osa = f'''
                    tell application "{target_name}"
                        if running and (count of windows) > 0 then
                            return (title of active tab of front window) & "|||" & (URL of active tab of front window)
                        end if
                    end tell
                    '''
                    res = subprocess.run(["osascript", "-e", osa], capture_output=True, text=True, timeout=1.0)
                    if res.returncode == 0 and "|||" in res.stdout:
                        parts = res.stdout.strip().split("|||", 1)
                        title = parts[0].strip()
                        url = parts[1].strip()
                        if title or url:
                            return target_name, title, url
                except Exception:
                    pass

        # 2. Apple Safari
        if "safari" in app_lower or (not frontmost_app and self._is_process_running("Safari")):
            try:
                osa = '''
                tell application "Safari"
                    if running and (count of windows) > 0 then
                        return (name of current tab of front window) & "|||" & (URL of current tab of front window)
                    end if
                end tell
                '''
                res = subprocess.run(["osascript", "-e", osa], capture_output=True, text=True, timeout=1.0)
                if res.returncode == 0 and "|||" in res.stdout:
                    parts = res.stdout.strip().split("|||", 1)
                    title = parts[0].strip()
                    url = parts[1].strip()
                    if title or url:
                        return "Safari", title, url
            except Exception:
                pass

        return None, None, None

    def _is_process_running(self, app_name: str) -> bool:
        """Checks if a named GUI process is currently running on macOS."""
        if sys.platform != "darwin":
            return False
        try:
            osa = f'tell application "System Events" to exists (processes whose name is "{app_name}")'
            res = subprocess.run(["osascript", "-e", osa], capture_output=True, text=True, timeout=0.8)
            return "true" in res.stdout.lower()
        except Exception:
            return False

    def classify_activity(
        self,
        frontmost_app: str,
        window_title: str = "",
        browser_name: Optional[str] = None,
        browser_title: Optional[str] = None,
        browser_url: Optional[str] = None,
    ) -> Tuple[str, str, str, str]:
        """
        Stage 2: Meaning Synthesis.
        Classifies the user's current environment into high-level activity context,
        extracts the focal topic, and binds to contextual habits.
        
        Returns: (activity_category, focused_topic, suggested_playlist, suggested_genre)
        """
        app_low = frontmost_app.lower()
        win_low = window_title.lower()
        b_title_low = (browser_title or "").lower()
        b_url_low = (browser_url or "").lower()

        # Combined text signal
        combined_text = f"{app_low} {win_low} {b_title_low} {b_url_low}"

        # 1. Gaming Context
        gaming_signals = ["fifa", "ea sports fc", "steam", "epic games", "fortnite", "game", "cyberpunk", "valorant", "league of legends"]
        if any(sig in combined_text for sig in gaming_signals):
            topic = "FIFA / Gaming Session" if ("fifa" in combined_text or "ea sports" in combined_text) else "Gaming Session"
            return "Gaming", topic, "FIFA Soundtrack", "Gaming Energy"

        # 2. Software Engineering / Coding Context
        coding_apps = ["visual studio code", "code", "cursor", "xcode", "terminal", "iterm", "iterm2", "pycharm", "sublime text", "neovim", "docker"]
        coding_urls = ["github.com", "gitlab.com", "stackoverflow.com", "localhost", "127.0.0.1", "pypi.org", "developer.apple.com"]
        if any(sig in app_low for sig in coding_apps) or any(sig in b_url_low for sig in coding_urls):
            # Extract repository or project name if possible
            topic = "Software Engineering"
            repo_match = re.search(r"github\.com/([^/]+/[^/]+)", browser_url or "", flags=re.IGNORECASE)
            if repo_match:
                topic = f"GitHub: {repo_match.group(1)}"
            elif "desktop-dom" in combined_text:
                topic = "desktop-dom Core Development"
            elif window_title and not window_title.startswith("Untitled"):
                topic = f"Code: {window_title.split('—')[0].split('-')[0].strip()}"
            return "Engineering", topic, "Deep Focus", "Focus Beats"

        # 3. Communication & Messaging Context
        comm_apps = ["microsoft outlook", "outlook", "mail", "slack", "messages", "discord", "zoom", "teams", "whatsapp"]
        if any(sig in app_low for sig in comm_apps) or "mail.google.com" in b_url_low:
            topic = "Email & Communications"
            if "josh" in combined_text:
                topic = "Crcle.ai Discussion with Josh"
            elif "cyril" in combined_text:
                topic = "Architecture Sync with Cyril"
            return "Communication", topic, "Discover Weekly", "Ambient Focus"

        # 4. Design & Creative Context
        design_apps = ["figma", "canva", "sketch", "photoshop", "illustrator", "blender"]
        if any(sig in app_low for sig in design_apps) or "figma.com" in b_url_low or "canva.com" in b_url_low:
            topic = "UI/UX & Visual Design"
            return "Design", topic, "Creative Flow", "Electronic / Chill"

        # 5. Media & Entertainment (YouTube, Spotify, Netflix, Twitch) -> Personal Media, NOT Work Research!
        media_domains = ["youtube.com", "youtu.be", "spotify.com", "netflix.com", "twitch.tv", "disneyplus.com", "hulu.com", "primevideo.com", "soundcloud.com"]
        is_media = any(d in b_url_low for d in media_domains) or any(s in b_title_low for s in ["- youtube", "spotify", "netflix", "twitch"])
        if is_media:
            clean_title = re.sub(r"^\(\d+\)\s*", "", browser_title or "")
            clean_title = re.sub(r"\s*-\s*YouTube$", "", clean_title, flags=re.IGNORECASE).strip()
            return "Media", f"Media: {clean_title}" if clean_title else "Streaming Media", "Deep Focus", "Personal"

        # 6. Research & Web Reading
        if browser_name or any(b in app_low for b in ["chrome", "safari", "arc", "edge", "brave"]):
            topic = browser_title if browser_title else "Web Research"
            if len(topic) > 40:
                topic = topic[:37] + "..."
            return "Research", topic, "Lofi Beats", "Study / Instrumental"

        # 6. Fallback General
        topic = window_title if window_title else frontmost_app
        return "General", topic, "Deep Focus", "Personal"

    def record_snapshot(self, snapshot: ActiveContextSnapshot):
        """Persists the telemetry snapshot to SQLite WAL memory."""
        if not self.memory:
            return
        try:
            with self.memory._lock, self.memory._get_connection() as conn:
                conn.execute("""
                INSERT INTO context_feed (
                    timestamp, frontmost_app, window_title, activity_category,
                    focused_topic, browser_name, browser_url, browser_title,
                    suggested_playlist, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    snapshot.timestamp,
                    snapshot.frontmost_app,
                    snapshot.window_title,
                    snapshot.activity_category,
                    snapshot.focused_topic,
                    snapshot.browser_name or "",
                    snapshot.browser_url or "",
                    snapshot.browser_title or "",
                    snapshot.suggested_playlist,
                    json.dumps(snapshot.metadata),
                ))
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to record context snapshot to SQLite: {e}")

    def get_recent_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves recent context snapshots from SQLite memory."""
        if not self.memory:
            return []
        try:
            with self.memory._lock, self.memory._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT timestamp, frontmost_app, window_title, activity_category,
                       focused_topic, browser_name, browser_url, suggested_playlist
                FROM context_feed
                ORDER BY timestamp DESC
                LIMIT ?;
                """, (limit,))
                return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            logger.warning(f"Failed to fetch context history: {e}")
            return []

    def summarize_current_context(self) -> str:
        """
        Generates a concise, natural language summary of the user's active context.
        Used for queries like 'what was I doing?', 'summarize my screen', or 'what's my active context?'.
        """
        snapshot = self.capture_active_context(record=True)
        
        lines = [f"You are currently engaged in **{snapshot.activity_category}**."]
        lines.append(f"• Active App: `{snapshot.frontmost_app}`")
        if snapshot.window_title:
            lines.append(f"• Window: \"{snapshot.window_title}\"")
        if snapshot.browser_url:
            lines.append(f"• Browser Tab ({snapshot.browser_name}): [{snapshot.browser_title or 'Link'}]({snapshot.browser_url})")
        lines.append(f"• Focus: {snapshot.focused_topic}")
        lines.append(f"• Contextual Audio: `{snapshot.suggested_playlist}` ({snapshot.suggested_genre})")
        
        return "\n".join(lines)
