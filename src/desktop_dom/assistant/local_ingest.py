"""
Local Machine Persona & History Ingestion Engine.
Directly ingests the user's REAL local environment (Chrome SQLite history,
macOS Contacts, Git identity, top visited web apps) into ~/.aura/memory.db.
Eliminates synthetic/hardcoded mock data in favor of true zero-touch personalization.
"""

from __future__ import annotations
import os
import re
import sys
import time
import json
import shutil
import sqlite3
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("desktop_dom.assistant.local_ingest")


class LocalMachineIngest:
    """
    Ingests actual personal machine telemetry from:
    1. Google Chrome SQLite History (~/Library/Application Support/Google/Chrome/Default/History)
    2. macOS Contacts AddressBook (via osascript / AddressBook framework)
    3. Git identity (git config user.name, user.email, remote origin)
    4. Shell history (~/.zsh_history)
    """

    def __init__(self, memory=None):
        self.memory = memory

    def ingest_git_identity(self) -> Dict[str, str]:
        """Reads real git identity and default repo from local machine."""
        identity = {}
        try:
            name = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True).stdout.strip()
            email = subprocess.run(["git", "config", "user.email"], capture_output=True, text=True).stdout.strip()
            if name:
                identity["name"] = name
            if email:
                identity["email"] = email
        except Exception:
            pass

        try:
            origin = subprocess.run(["git", "config", "--get", "remote.origin.url"], capture_output=True, text=True).stdout.strip()
            m = re.search(r"github\.com[:/]([^/]+/[^/.]+)", origin)
            if m:
                identity["repo"] = m.group(1)
        except Exception:
            pass

        return identity

    def ingest_chrome_history(self, max_entries: int = 30) -> Dict[str, Any]:
        """
        Safely copies local Chrome History SQLite DB to a temp file and extracts:
        - Real YouTube watch history & favorite channels
        - Top visited domains and web applications
        """
        chrome_path = Path.home() / "Library/Application Support/Google/Chrome/Default/History"
        if not chrome_path.exists():
            return {"youtube": [], "top_sites": []}

        tmp_path = Path("/tmp/aura_chrome_ingest_copy.db")
        try:
            shutil.copy2(chrome_path, tmp_path)
            conn = sqlite3.connect(tmp_path)
            c = conn.cursor()

            # 1. Real YouTube entries
            c.execute("""
            SELECT title, url, visit_count, last_visit_time
            FROM urls 
            WHERE (url LIKE '%youtube.com/watch%' OR url LIKE '%youtube.com/@%') AND title != ''
            ORDER BY visit_count DESC, last_visit_time DESC 
            LIMIT ?;
            """, (max_entries,))
            yt_entries = []
            for title, url, count, last_time in c.fetchall():
                clean_title = title.replace(" - YouTube", "").strip()
                m = re.search(r"youtube\.com/@([^/?]+)", url)
                channel = m.group(1) if m else "YouTube"
                yt_entries.append({
                    "channel": channel,
                    "title": clean_title,
                    "url": url,
                    "visits": count,
                })

            # 2. Top frequented domains / web applications
            c.execute("""
            SELECT title, url, visit_count
            FROM urls 
            WHERE url NOT LIKE '%google.com/search%' 
              AND url NOT LIKE '%chrome://%' 
              AND url NOT LIKE 'file://%'
              AND title != ''
            ORDER BY visit_count DESC 
            LIMIT ?;
            """, (max_entries,))
            top_sites = []
            for title, url, count in c.fetchall():
                top_sites.append({
                    "title": title.strip(),
                    "url": url.strip(),
                    "visits": count,
                })

            conn.close()
            return {"youtube": yt_entries, "top_sites": top_sites}
        except Exception as e:
            logger.warning(f"Failed to ingest Chrome history: {e}")
            return {"youtube": [], "top_sites": []}
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass

    def sync_to_memory(self) -> Dict[str, Any]:
        """
        Synchronizes actual local persona data into Aura's SQLite memory store.
        Replaces demo placeholders with real machine habits.
        """
        if not self.memory:
            return {"status": "error", "message": "No memory engine attached"}

        # 1. Sync Git Identity
        git_id = self.ingest_git_identity()
        if git_id.get("name"):
            self.memory.set_preference("user.name", git_id["name"], category="user")
        if git_id.get("email"):
            self.memory.set_preference("user.email", git_id["email"], category="user")
        if git_id.get("repo"):
            self.memory.set_preference("github.default_repo", git_id["repo"], category="developer")

        # 2. Sync Chrome History
        chrome_data = self.ingest_chrome_history(max_entries=25)
        yt_list = chrome_data.get("youtube", [])
        top_sites = chrome_data.get("top_sites", [])

        if yt_list:
            # Store real YouTube history
            formatted_yt = []
            for item in yt_list:
                formatted_yt.append({
                    "channel": item["channel"],
                    "topic": item["title"],
                    "url": item["url"],
                    "visits": item["visits"],
                    "timestamp": time.time(),
                })
            self.memory.set_preference("youtube.watch_history", json.dumps(formatted_yt), category="media")

            # Discover top favorite channel from real history
            channels = [i["channel"] for i in yt_list if i["channel"] != "YouTube"]
            if channels:
                self.memory.set_preference("youtube.favorite_channel.tech", channels[0], category="media")

        if top_sites:
            self.memory.set_preference("browser.top_sites", json.dumps(top_sites[:10]), category="web")

        # 3. Sync macOS Contacts (if on darwin)
        contacts_synced = 0
        if sys.platform == "darwin":
            try:
                contacts_synced = self.memory.sync_system_contacts(limit=50)
            except Exception as e:
                logger.debug(f"Contacts sync exception: {e}")

        return {
            "status": "success",
            "git_identity": git_id,
            "youtube_entries_ingested": len(yt_list),
            "top_sites_ingested": len(top_sites),
            "contacts_synced": contacts_synced,
        }
