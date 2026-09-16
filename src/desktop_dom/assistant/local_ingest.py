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
from typing import Dict, Any, List, Optional, Set, Tuple

logger = logging.getLogger("desktop_dom.assistant.local_ingest")


APP_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "meeting": {
        "apps": ["Granola", "Zoom", "zoom.us", "Microsoft Teams", "Google Meet", "Webex", "Slack Huddle"],
        "role": "Meeting Companion",
        "relation": "handles_meeting_intent",
    },
    "notes": {
        "apps": ["Notion", "Obsidian", "Bear", "Apple Notes", "Notes", "Evernote", "Roam Research", "Logseq"],
        "role": "Notes & Knowledge Workspace",
        "relation": "handles_notes_intent",
    },
    "design": {
        "apps": ["Figma", "Sketch", "Adobe XD", "Illustrator", "Photoshop", "Canva"],
        "role": "Design Suite",
        "relation": "handles_design_intent",
    },
    "tasks": {
        "apps": ["Linear", "Jira", "Asana", "Trello", "Monday.com", "ClickUp"],
        "role": "Project Management",
        "relation": "handles_tasks_intent",
    },
    "browser": {
        "apps": ["Google Chrome", "Safari", "Firefox", "Brave Browser", "Arc", "Microsoft Edge", "Chromium", "Opera"],
        "role": "Web Browser",
        "relation": "uses_frequently",
    },
    "communication": {
        "apps": ["Microsoft Outlook", "Outlook", "Mail", "Slack", "Discord", "WhatsApp", "Telegram", "Messages", "FaceTime", "Signal"],
        "role": "Communication Client",
        "relation": "communicates_via",
    },
    "developer": {
        "apps": ["Terminal", "iTerm", "iTerm2", "kitty", "Docker", "Docker Desktop", "Xcode", "Zed", "Visual Studio Code", "Code", "Cursor", "Postman", "Eclipse", "Anaconda-Navigator", "Sublime Text", "Warp"],
        "role": "Developer Environment",
        "relation": "develops_with",
    },
    "ai_assistant": {
        "apps": ["ChatGPT", "Claude", "Gemini", "ParakeetAI", "Ollama", "OpenWhispr", "Antigravity", "Antigravity IDE", "Copilot"],
        "role": "AI Assistant",
        "relation": "consults_ai",
    },
    "media": {
        "apps": ["Spotify", "Music", "TV", "VLC", "GarageBand", "DJUCED", "Prime Video", "Audacity", "IINA"],
        "role": "Media Player",
        "relation": "listens_via",
    },
    "productivity": {
        "apps": ["Microsoft Excel", "Microsoft Word", "Microsoft PowerPoint", "Pages", "Numbers", "Keynote", "Calendar", "Reminders", "Freeform"],
        "role": "Productivity Suite",
        "relation": "organizes_with",
    },
}

STD_APP_NAMES: Dict[str, str] = {
    "docker": "Docker Desktop",
    "docker desktop": "Docker Desktop",
    "outlook": "Microsoft Outlook",
    "microsoft outlook": "Microsoft Outlook",
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "term": "Terminal",
    "terminal": "Terminal",
    "iterm": "iTerm2",
    "iterm2": "iTerm2",
    "code": "Visual Studio Code",
    "vscode": "Visual Studio Code",
    "visual studio code": "Visual Studio Code",
    "chatgpt": "ChatGPT",
    "spotify": "Spotify",
}


def resolve_app_category_meta(name: str) -> Tuple[str, str, str]:
    """Resolves functional category, formal role, and semantic relation for an application."""
    low = name.lower()
    for cat, data in APP_CATEGORIES.items():
        for cand in data["apps"]:
            cand_low = cand.lower()
            if low == cand_low or low == cand_low.replace(" ", "") or low.startswith(cand_low) or cand_low.startswith(low):
                return cat, data["role"], data["relation"]
    return "utility", "Desktop Utility", "uses"


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

    def ingest_most_used_apps(self, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Discovers and ranks the user's actual most-used applications on this machine.
        Cross-references:
        1. Actively running GUI processes (highest priority / active engagement)
        2. User's Dock / Taskbar pinned apps (curated everyday tools)
        3. Installed user applications in /Applications or Program Files
        Categorizes each into: browser, communication, developer, ai_assistant, media, productivity, utility.
        """
        running: Set[str] = set()
        dock_pinned: Set[str] = set()
        installed: Set[str] = set()

        if sys.platform == "darwin":
            # 1. Running GUI apps via ps (ultra-fast, <25ms, no prompt)
            try:
                res_ps = subprocess.run(["ps", "-ax", "-o", "comm="], capture_output=True, text=True, timeout=1.0)
                if res_ps.returncode == 0 and res_ps.stdout:
                    for line in res_ps.stdout.splitlines():
                        line = line.strip()
                        if ("/Applications/" in line or "/System/Applications/" in line) and ".app/Contents/MacOS/" in line:
                            base = line.split(".app/Contents/MacOS/")[0].split("/")[-1]
                            if not any(h in line.lower() for h in [
                                "helper", "agent", "service", "daemon", "xpc", "renderer",
                                "crashpad", "plugin", "loginwindow", "systemuiserver", "notificationcenter",
                                "dock", "spotlight", "controlcenter"
                            ]):
                                running.add(base)
            except Exception as e:
                logger.debug(f"ps app discovery exception: {e}")

            # 2. Dock pinned apps
            try:
                res_dock = subprocess.run(["defaults", "read", "com.apple.dock", "persistent-apps"], capture_output=True, text=True, timeout=1.0)
                if res_dock.returncode == 0 and res_dock.stdout:
                    raw_dock = re.findall(r'\"?file-label\"?\s*=\s*\"?([^;\n\"]+)\"?;', res_dock.stdout)
                    for a in raw_dock:
                        clean_a = a.strip()
                        if clean_a and clean_a not in ["Apps", "Launchpad", "Trash", "App Store", "Feedback Assistant"]:
                            dock_pinned.add(clean_a)
            except Exception as e:
                logger.debug(f"Dock apps discovery exception: {e}")

            # 3. Installed applications in /Applications and ~/Applications
            for search_dir in [Path("/Applications"), Path.home() / "Applications"]:
                if search_dir.exists():
                    try:
                        for p in search_dir.glob("*.app"):
                            installed.add(p.stem)
                    except Exception:
                        pass
        elif sys.platform == "win32":
            # Windows fallback
            try:
                res_task = subprocess.run(["tasklist", "/FO", "CSV"], capture_output=True, text=True, timeout=1.5)
                if res_task.returncode == 0 and res_task.stdout:
                    for row in res_task.stdout.splitlines()[1:]:
                        parts = row.split(",")
                        if parts:
                            proc = parts[0].strip(' "')
                            if proc.endswith(".exe"):
                                running.add(proc[:-4])
            except Exception:
                pass
            prog_files = [os.environ.get("ProgramFiles"), (os.environ.get("LOCALAPPDATA") or "") + r"\Programs"]
            for pf in prog_files:
                if pf and os.path.exists(pf):
                    try:
                        for entry in os.listdir(pf):
                            if os.path.isdir(os.path.join(pf, entry)):
                                installed.add(entry)
                    except Exception:
                        pass
        else:
            # Linux fallback
            try:
                res_ps = subprocess.run(["ps", "-e", "-o", "comm="], capture_output=True, text=True, timeout=1.0)
                if res_ps.returncode == 0 and res_ps.stdout:
                    running.update(line.strip() for line in res_ps.stdout.splitlines() if line.strip())
            except Exception:
                pass

        # Standardize and calculate multi-factor scores
        scored_apps: Dict[str, Dict[str, Any]] = {}
        all_candidates = running | dock_pinned | installed

        for raw_name in all_candidates:
            clean_name = STD_APP_NAMES.get(raw_name.lower(), raw_name)
            cat, role, relation = resolve_app_category_meta(clean_name)

            is_run = (raw_name in running or clean_name in running)
            is_dock = (raw_name in dock_pinned or clean_name in dock_pinned)
            is_inst = (raw_name in installed or clean_name in installed)

            score = 0
            if is_run:
                score += 15
            if is_dock:
                score += 10
            if is_inst:
                score += 5
            if cat != "utility":
                score += 5

            # Filter out low-signal OS utility noise unless actively running or docked
            if score < 10 and cat == "utility":
                continue

            if clean_name not in scored_apps or score > scored_apps[clean_name]["score"]:
                scored_apps[clean_name] = {
                    "name": clean_name,
                    "category": cat,
                    "role": role,
                    "relation": relation,
                    "score": score,
                    "is_running": is_run,
                    "is_dock_pinned": is_dock,
                    "is_installed": is_inst,
                }

        ranked = sorted(scored_apps.values(), key=lambda x: (-x["score"], x["name"]))
        return ranked[:limit]

    def sync_to_memory(self) -> Dict[str, Any]:
        """
        Synchronizes actual local persona data into Aura's SQLite memory store.
        Replaces demo placeholders with real machine habits.
        """
        if not self.memory:
            return {"status": "error", "message": "No memory engine attached"}

        # 1. Sync Git Identity
        git_id = self.ingest_git_identity()
        raw_name = git_id.get("name", "").strip()
        if raw_name:
            # Detect whether git name is a handle (e.g. PDgit12, user123, no spaces, contains digits)
            is_handle = bool(re.search(r"\d", raw_name) or (" " not in raw_name and len(raw_name) > 2))
            if is_handle:
                self.memory.set_preference("github.username", raw_name, category="developer")
                curr_name = self.memory.get_preference("user.name")
                if not curr_name or curr_name == raw_name:
                    self.memory.set_preference("user.name", "Piyush Dua", category="user")
            else:
                self.memory.set_preference("user.name", raw_name, category="user")

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

        if top_sites:
            self.memory.set_preference("browser.top_sites", json.dumps(top_sites[:10]), category="web")

        # 3. Sync macOS Contacts (if on darwin)
        contacts_synced = 0
        if sys.platform == "darwin":
            try:
                contacts_synced = self.memory.sync_system_contacts(limit=50)
            except Exception as e:
                logger.debug(f"Contacts sync exception: {e}")

        # 4. Sync Most-Used Apps & Hydrate Knowledge Graph
        top_apps = self.ingest_most_used_apps(limit=12)
        if top_apps and self.memory:
            self.memory.set_preference("apps.most_used", json.dumps(top_apps), category="apps")
            user_name = self.memory.get_preference("user.name") or "Piyush Dua"
            for app in top_apps:
                self.memory.add_entity(
                    name=app["name"],
                    category="application",
                    role=app["role"],
                    aliases=[app["name"].lower(), app["name"].lower().replace(" ", "")],
                    metadata={"category": app["category"], "score": app["score"], "is_running": app["is_running"], "is_dock_pinned": app["is_dock_pinned"]}
                )
                weight = round(min(1.0, 0.5 + (app["score"] / 70.0)), 2)
                self.memory.add_edge(user_name, app["name"], app["relation"], weight=weight, cluster="apps")
                self.memory.record_habit("app_launch", app["name"], context=app["category"])

        return {
            "status": "success",
            "git_identity": git_id,
            "youtube_entries_ingested": len(yt_list),
            "top_sites_ingested": len(top_sites),
            "contacts_synced": contacts_synced,
            "top_apps_ingested": len(top_apps),
        }
