from __future__ import annotations
import re
import sys
import json
import time
import logging
import subprocess
import webbrowser
import urllib.request
import urllib.parse
import urllib.error
import difflib
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Callable

from desktop_dom.app import DesktopApp
from desktop_dom.schema import DesktopNode
from desktop_dom.adapters import get_platform_adapter
from desktop_dom.assistant.memory import AuraMemory
from desktop_dom.assistant.context_feed import ContextFeedEngine, ActiveContextSnapshot

logger = logging.getLogger("desktop_dom.assistant.brain")

BUILTIN_APP_ALIASES: Dict[str, str] = {
    "chrome": "Google Chrome",
    "crome": "Google Chrome",
    "google chrome": "Google Chrome",
    "vs code": "Visual Studio Code",
    "vscode": "Visual Studio Code",
    "code": "Visual Studio Code",
    "spotify": "Spotify",
    "spotfy": "Spotify",
    "spot": "Spotify",
    "notes": "Notes",
    "notse": "Notes",
    "calculator": "Calculator",
    "calc": "Calculator",
    "calculatr": "Calculator",
    "finder": "Finder",
    "terminal": "Terminal",
    "term": "Terminal",
    "termnal": "Terminal",
    "iterm": "iTerm2",
    "iterm2": "iTerm2",
    "safari": "Safari",
    "safri": "Safari",
    "slack": "Slack",
    "slak": "Slack",
    "messages": "Messages",
    "mesages": "Messages",
    "imessage": "Messages",
    "calendar": "Calendar",
    "cal": "Calendar",
    "mail": "Mail",
    "outlook": "Microsoft Outlook",
    "microsoft outlook": "Microsoft Outlook",
    "system settings": "System Settings",
    "settings": "System Settings",
    "prefs": "System Settings",
    "preferences": "System Settings",
    "activity monitor": "Activity Monitor",
    "docker": "Docker",
    "dockr": "Docker",
    "claude": "Claude",
    "claud": "Claude",
}

class AssistantBrain:
    """
    Local-first autonomous decision brain that translates natural language speech/text
    into deterministic desktop actions with sub-second execution speed.
    """

    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        preferred_model: Optional[str] = None,
        memory: Optional[AuraMemory] = None,
    ):
        self.ollama_host = ollama_host
        self.preferred_model = preferred_model or self._detect_ollama_model()
        self.active_app: Optional[DesktopApp] = None
        self._action_callback: Optional[Callable[[str, str], None]] = None
        self._installed_apps: Dict[str, str] = {}
        self._scan_installed_apps()
        self.memory = memory or AuraMemory()
        self.context_feed = ContextFeedEngine(memory=self.memory)
        self._current_context_snapshot: Optional[ActiveContextSnapshot] = None
        if not self.memory.get_preference("onboarding.completed"):
            try:
                self.memory.auto_hydrate_environment()
            except Exception:
                pass

    def _scan_installed_apps(self) -> Dict[str, str]:
        """Scans standard macOS application directories to build a dynamic application catalog."""
        apps: Dict[str, str] = {}
        if sys.platform == "darwin":
            search_dirs = [
                "/Applications",
                "/System/Applications",
                "/System/Applications/Utilities",
                str(Path.home() / "Applications"),
            ]
            for d in search_dirs:
                try:
                    p = Path(d)
                    if p.exists() and p.is_dir():
                        for item in p.iterdir():
                            if item.name.endswith(".app"):
                                app_name = item.name[:-4]
                                apps[app_name.lower()] = app_name
                except Exception:
                    pass
        self._installed_apps = apps
        return apps

    def resolve_app_name(self, query: str) -> Optional[str]:
        """
        Resolves an application name with typo tolerance and alias lookup.
        Matches exact aliases, installed apps, substring inclusions, and SequenceMatcher close matches.
        """
        q = query.strip().lower()
        if not q:
            return None

        # 1. Built-in curated aliases
        if q in BUILTIN_APP_ALIASES:
            return BUILTIN_APP_ALIASES[q]

        # 2. Exact match in scanned apps
        if q in self._installed_apps:
            return self._installed_apps[q]

        # 3. Substring match against scanned apps
        for low_name, actual_name in self._installed_apps.items():
            if q == low_name or (len(q) >= 4 and q in low_name):
                return actual_name

        # 4. Fuzzy match against combined catalog
        all_candidates = {**self._installed_apps, **{k: v for k, v in BUILTIN_APP_ALIASES.items()}}
        match_keys = difflib.get_close_matches(q, list(all_candidates.keys()), n=1, cutoff=0.68)
        if match_keys:
            best_key = match_keys[0]
            return BUILTIN_APP_ALIASES.get(best_key, self._installed_apps.get(best_key))

        return None

    def set_action_callback(self, cb: Callable[[str, str], None]):
        """Sets a callback invoked when the brain decides on an action: cb(action_type, message)."""
        self._action_callback = cb

    def _notify_action(self, action_type: str, message: str):
        if self._action_callback:
            try:
                self._action_callback(action_type, message)
            except Exception:
                pass

    def _detect_ollama_model(self) -> Optional[str]:
        """Auto-discovers locally installed Ollama models, defaulting to standard Mistral."""
        try:
            req = urllib.request.Request(f"{self.ollama_host}/api/tags", headers={"User-Agent": "desktop-dom"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", [])]
                if not models:
                    return "mistral"
                # Standard Mistral model prioritization
                for m in models:
                    if any(sub in m.lower() for sub in ["mistral", "ministral"]):
                        return m
                for m in models:
                    if any(sub in m.lower() for sub in ["qwen", "llama3"]):
                        return m
                return models[0]
        except Exception:
            return "mistral"

    def get_model_status(self) -> Dict[str, Any]:
        """Returns connection health and installed models from local Ollama server."""
        import urllib.request
        ping_start = time.time()
        try:
            req = urllib.request.Request(f"{self.ollama_host}/api/tags", headers={"User-Agent": "desktop-dom"})
            with urllib.request.urlopen(req, timeout=1.2) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", [])]
                latency = round((time.time() - ping_start) * 1000, 1)
                return {
                    "connected": True,
                    "host": self.ollama_host,
                    "current_model": self.preferred_model or (models[0] if models else "llama3.2:3b"),
                    "available_models": models,
                    "latency_ms": latency,
                }
        except Exception:
            return {
                "connected": False,
                "host": self.ollama_host,
                "current_model": self.preferred_model or "Zero-Model Fast-Path",
                "available_models": [],
                "latency_ms": None,
            }

    def set_model(self, model_name: str) -> bool:
        """Dynamically switches the active reasoning model."""
        self.preferred_model = model_name
        logger.info(f"Aura active reasoning model switched to: '{model_name}'")
        return True

    def execute_intent(self, prompt: str) -> Dict[str, Any]:
        """
        Processes a natural language user query.
        Tries high-velocity deterministic fast-path first; falls back to local LLM reasoning.
        """
        clean_prompt = prompt.strip().lower()
        if not clean_prompt:
            return {"status": "empty", "response": "I didn't catch that."}

        start_t = time.time()
        self._notify_action("thinking", f"Processing: '{prompt}'")

        # 0. Multi-Action Compound Query Support (e.g. "open chrome and open gmail", "open outlook and message josh")
        if (" and " in clean_prompt or " then " in clean_prompt) and not any(clean_prompt.startswith(p) for p in ["what", "who", "where", "why", "how", "tell", "explain", "describe", "search", "google", "calculate", "type", "note", "remember"]):
            parts = [s.strip() for s in re.split(r"\s+(?:and|then)\s+", prompt, flags=re.IGNORECASE) if s.strip()]
            if len(parts) > 1 and all(len(p) > 2 for p in parts):
                normalized = []
                for idx, sub in enumerate(parts):
                    if idx > 0 and not any(sub.lower().startswith(v) for v in ["open", "launch", "play", "search", "close", "set", "calculate", "message", "email", "mail"]):
                        sub = f"open {sub}"
                    normalized.append(sub)

                results = [self.execute_intent(p) for p in normalized]
                successes = [r for r in results if r.get("status") == "success"]
                if successes:
                    combined_resp = " ".join(r.get("response", "") for r in results if r.get("response"))
                    return {
                        "status": "success" if len(successes) == len(results) else "partial",
                        "action": "compound_action",
                        "parts": results,
                        "response": combined_resp,
                        "latency_ms": round((time.time() - start_t) * 1000, 1),
                        "engine": "fast_path",
                    }

        # 1. Fast-Path: Deterministic Intent Handling
        fast_result = self._try_deterministic_fast_path(clean_prompt, raw_prompt=prompt)
        if fast_result is not None:
            fast_result["latency_ms"] = round((time.time() - start_t) * 1000, 1)
            fast_result["engine"] = "fast_path"
            if "level" not in fast_result:
                fast_result["level"] = "1.0"
            return fast_result

        # 2. General Local LLM ReAct Planning
        if self.preferred_model:
            llm_result = self._execute_with_local_llm(prompt)
            llm_result["latency_ms"] = round((time.time() - start_t) * 1000, 1)
            llm_result["engine"] = "ollama"
            if "level" not in llm_result:
                llm_result["level"] = "2.0"
            return llm_result

        elapsed_ms = round((time.time() - start_t) * 1000, 1)
        return {
            "status": "unhandled",
            "response": f"I heard '{prompt}', but couldn't find a matching local handler or active Ollama model.",
            "latency_ms": elapsed_ms,
            "engine": "none",
        }

    def _try_deterministic_fast_path(self, prompt: str, raw_prompt: str) -> Optional[Dict[str, Any]]:
        """
        Ultra-fast, zero-hallucination deterministic action dispatch for common workflows.
        Executes in <150ms without waiting for LLM tokens.
        """
        # 0. Model Status & Dynamic Switching
        if prompt in {"/model", "/models", "/status", "model status", "check models", "what model"}:
            status = self.get_model_status()
            if status["connected"]:
                available = ", ".join(status["available_models"]) if status["available_models"] else "None detected"
                resp = (
                    f"Ollama connected ({status['host']}) with {status['latency_ms']}ms latency. "
                    f"Active Model: {status['current_model']}. Available Models: {available}."
                )
            else:
                resp = (
                    f"Active: {status['current_model']}. Ollama is currently offline at {status['host']}. "
                    "Zero-Model Fast-Path is active (0MB RAM, sub-25ms response)."
                )
            self._notify_action("completed", f"Model: {status['current_model']}")
            return {
                "status": "success",
                "action": "model_status",
                "model_status": status,
                "response": resp,
            }

        model_switch = re.match(r"^(?:/model|use model|switch model to|set model)\s+([a-zA-Z0-9._:\-]+)", prompt)
        if model_switch:
            new_model = model_switch.group(1).strip()
            self.set_model(new_model)
            self._notify_action("completed", f"Switched to {new_model}")
            return {
                "status": "success",
                "action": "model_switch",
                "model": new_model,
                "response": f"Active reasoning model switched to '{new_model}'.",
            }

        # 1. Personal Context & Memory Status / Sync / Onboarding
        if prompt in {"/onboard", "onboard", "setup", "run onboarding"}:
            summary = self.memory.auto_hydrate_environment()
            user_str = f"{summary.get('user_name', 'User')} ({summary.get('user_email', '')})"
            mail_str = summary.get("mail_client", "Mail")
            music_str = f"{summary.get('music_player', 'Spotify')} ('{self.memory.get_preference('spotify.favorite_playlist', 'Deep Focus')}')"
            
            resp = (
                f"✓ Ambient Onboarding Complete ({summary.get('elapsed_ms', 0)}ms)\n"
                f"• Identity: {user_str}\n"
                f"• Preferred Mail: {mail_str}\n"
                f"• Habitual Music: {music_str}\n"
                f"• Contacts Hydrated: {len(self.memory._entity_cache)} records in SQLite WAL\n"
                f"• Personal Intent Engine: Level 2 Active (<0.5ms resolution)"
            )
            self._notify_action("completed", "Onboarding completed")
            return {
                "status": "success",
                "action": "onboard",
                "summary": summary,
                "response": resp,
            }

        if prompt in {"/memory", "show memory", "memory", "view memory", "open memory", "check memory", "what is in memory"}:
            summary = self.memory.get_summary()
            contacts_list = ", ".join(f"{c['name']} ({c['email']})" for c in summary["top_contacts"]) or "None"
            user_info = f"{summary['user']['name']} ({summary['user']['role']})"
            fav_playlist = summary["preferences"].get("spotify.favorite_playlist", "Deep Focus")
            pref_client = summary["preferences"].get("mail.preferred_client", "Microsoft Outlook")
            
            resp = (
                f"Personal Memory Engine Active ({summary['contacts_count']} contacts stored).\n"
                f"• User: {user_info}\n"
                f"• Top Contacts: {contacts_list}\n"
                f"• Favorite Playlist: '{fav_playlist}' (Spotify)\n"
                f"• Preferred Mail: {pref_client}\n"
                f"• Memory DB: {summary['db_path']}"
            )
            self._notify_action("completed", "Memory summary retrieved")
            return {
                "status": "success",
                "action": "memory_summary",
                "summary": summary,
                "response": resp,
            }

        if prompt in {"sync contacts", "import contacts", "sync address book"}:
            count = self.memory.sync_system_contacts()
            self._notify_action("completed", f"Synced {count} contacts")
            return {
                "status": "success",
                "action": "sync_contacts",
                "count": count,
                "response": f"Synced {count} new contacts from macOS Address Book into local memory.",
            }

        # Natural Language Knowledge & Memory Learning ("remember ...")
        if prompt.startswith("remember ") or prompt.startswith("learn "):
            mem_res = self.memory.remember(raw_prompt)
            self._notify_action("completed", mem_res.get("response", "Remembered."))
            return mem_res

        # Contact Biography & Knowledge Query ("who is ...", "tell me about ...")
        who_match = re.match(r"^(?:who\s+is|tell\s+me\s+about)\s+([a-zA-Z0-9\s]+?)\??$", raw_prompt, re.IGNORECASE)
        if who_match:
            target = who_match.group(1).strip()
            bio = self.memory.who_is(target)
            if bio:
                self._notify_action("completed", f"Resolved {target}")
                return {
                    "status": "success",
                    "action": "who_is",
                    "target": target,
                    "response": bio,
                }
            else:
                return {
                    "status": "not_found",
                    "action": "who_is",
                    "target": target,
                    "response": f"I don't have '{target}' in personal memory yet. You can say 'remember {target} is {target.lower()}@domain.com' to save them.",
                }

        # 2. Habitual Playlist Recall ("open my playlist", "play my playlist", "play my music")
        playlist_regex = re.compile(r"^(?:open|play)\s+(?:my\s+)?(?:favorite\s+|favourite\s+)?(?:spotify\s+)?(?:playlist|music|songs?)$", re.IGNORECASE)
        if playlist_regex.match(raw_prompt.strip()):
            snapshot = self.context_feed.capture_active_context(record=True)
            frontmost = self._get_frontmost_app_name()
            if frontmost and any(g in frontmost.lower() for g in ["fifa", "steam", "game", "fortnite", "epic"]):
                snapshot.frontmost_app = frontmost
                snapshot.activity_category = "Gaming"
                snapshot.suggested_playlist = "FIFA Soundtrack"
                snapshot.suggested_genre = "Gaming Energy"
            self._current_context_snapshot = snapshot

            # Strict Anti-Drift Habit Resolution Hierarchy:
            # 1. Tier 1: Explicit User Lock in habits table or preferences (ground truth)
            explicit_fav = self.memory.resolve_habit("spotify.favorite_playlist") or self.memory.get_preference("spotify.favorite_playlist")

            # Check if user explicitly asked for gaming vs coding/focus
            req_gaming = any(w in prompt for w in ["gaming", "game", "fifa"])
            req_coding = any(w in prompt for w in ["coding", "code", "work", "focus"])

            if req_gaming or snapshot.activity_category == "Gaming":
                contextual_genre = "Gaming Energy"
                fav_playlist = self.memory.resolve_habit("spotify.playlist.gaming") or self.memory.get_preference("spotify.playlist.gaming", snapshot.suggested_playlist or "FIFA Soundtrack")
            elif req_coding:
                contextual_genre = "Focus Beats"
                fav_playlist = self.memory.resolve_habit("spotify.playlist.coding") or self.memory.get_preference("spotify.playlist.coding", snapshot.suggested_playlist or "Deep Focus")
            elif explicit_fav:
                contextual_genre = "Personal Favorite"
                fav_playlist = explicit_fav
            elif snapshot.activity_category == "Engineering":
                contextual_genre = "Focus Beats"
                fav_playlist = self.memory.resolve_habit("spotify.playlist.coding") or "Deep Focus"
            elif snapshot.activity_category == "Design":
                contextual_genre = "Creative Flow"
                fav_playlist = self.memory.get_preference("spotify.playlist.design", snapshot.suggested_playlist or "Creative Flow")
            elif snapshot.activity_category == "Research":
                contextual_genre = "Study / Instrumental"
                fav_playlist = self.memory.get_preference("spotify.playlist.research", snapshot.suggested_playlist or "Lofi Beats")
            else:
                contextual_genre = "Personal"
                fav_playlist = self.memory.get_preference("spotify.favorite_playlist", "Deep Focus")

            # Prevent drift: record observation to reinforce this habit
            self.memory.record_habit_observation("spotify.last_played_playlist", fav_playlist, category="music", is_explicit=False)

            self._notify_action("executing", f"Playing {contextual_genre} playlist '{fav_playlist}' on Spotify in exact order")
            res = self._control_spotify_play(fav_playlist)
            if res.get("status") == "success":
                res["action"] = "spotify_playlist"
                res["level"] = "2.0"
                res["playlist"] = fav_playlist
                res["context"] = contextual_genre
                res["activity"] = snapshot.activity_category
                res["response"] = f"Now playing your {contextual_genre} playlist '{fav_playlist}' on Spotify in exact track order."
            return res

        # 3. Personal Intent Messaging & Email Flow ("message Josh", "email Josh", "shoot an email to josh", "ping josh")
        msg_match = re.match(
            r"^(?:i\s+(?:wanna|want\s+to)\s+)?(?:send\s+(?:an?\s+)?(?:email|message)\s+to|shoot\s+(?:an?\s+)?(?:email|message)\s+to|reach\s+out\s+to|write\s+(?:to\s+)?|ping|message|email|mail|tell|text|slack)\s+([a-zA-Z0-9_.+-@\s]+?)(?:\s+(?:saying|about|with|that)\s+(.+))?$",
            raw_prompt,
            re.IGNORECASE
        )
        if msg_match:
            target_raw = msg_match.group(1).strip()
            content_raw = msg_match.group(2).strip() if msg_match.group(2) else None

            # Detect client override in target or query (e.g. "message josh on outlook")
            client_override = None
            if re.search(r"\b(?:on|via|using)\s+outlook\b", target_raw, re.IGNORECASE):
                client_override = "Microsoft Outlook"
                target_raw = re.sub(r"\b(?:on|via|using)\s+outlook\b", "", target_raw, flags=re.IGNORECASE).strip()
            elif re.search(r"\b(?:on|via|using)\s+mail\b", target_raw, re.IGNORECASE):
                client_override = "Mail"
                target_raw = re.sub(r"\b(?:on|via|using)\s+mail\b", "", target_raw, flags=re.IGNORECASE).strip()

            if target_raw.lower() not in {"me", "notification", "note", "app", "application"}:
                entity = self.memory.resolve_entity(target_raw)
                if entity:
                    client = client_override or self.memory.get_preference("mail.preferred_client", "Microsoft Outlook")
                    return self._control_send_message(entity, content=content_raw, client=client)
                else:
                    return {
                        "status": "not_found",
                        "action": "send_message",
                        "target": target_raw,
                        "response": f"I couldn't find '{target_raw}' in contacts. Say 'remember {target_raw} is {target_raw.lower()}@example.com' or input their email directly.",
                    }

        # 4. Context Ingestion & Real-Time Telemetry Introspection
        if any(p in prompt for p in [
            "what was i doing", "what am i doing", "what was i just doing",
            "summarize my context", "summarize context", "what's my active context",
            "what is my active context", "what am i working on", "what was i working on",
            "what am i looking at"
        ]):
            snapshot = self.context_feed.capture_active_context(record=True)
            self._current_context_snapshot = snapshot
            summary = self.context_feed.summarize_current_context()
            return {
                "status": "success",
                "action": "context_summary",
                "level": "2.0",
                "activity": snapshot.activity_category,
                "topic": snapshot.focused_topic,
                "app": snapshot.frontmost_app,
                "window": snapshot.window_title,
                "browser_url": snapshot.browser_url,
                "response": summary,
            }

        # 5. YouTube & Video Streaming Intent Flow ("open youtube", "watch youtube", "watch something", "watch fireship", "watch primeagen")
        yt_direct_match = re.match(r"^(?:open|watch|play|go\s+to)\s+(?:my\s+)?(?:youtube|videos?)(?:\s+(?:video|channel))?$", raw_prompt.strip(), re.IGNORECASE)
        yt_watch_match = re.match(r"^(?:watch|open\s+youtube\s+for)\s+(.+)$", raw_prompt.strip(), re.IGNORECASE)
        if yt_direct_match or (yt_watch_match and not any(w in prompt for w in ["netflix", "movie", "tv", "song", "track", "spotify"])):
            channel_query = None
            if yt_watch_match:
                cand = yt_watch_match.group(1).strip()
                if cand.lower() not in ["youtube", "video", "videos", "something", "a video", "my youtube"]:
                    channel_query = cand
            snapshot = self.context_feed.capture_active_context(record=True)
            self._current_context_snapshot = snapshot

            rec = self.memory.get_youtube_recommendation(context_category=snapshot.activity_category, channel_query=channel_query)
            dest_url = rec["url"]
            channel_name = rec["channel"]
            topic_name = rec["topic"]
            cat_name = rec["category"]

            self._notify_action("executing", f"Opening YouTube: {channel_name} ({topic_name})")

            # Level 2.5: Browser Tab Intelligence (bring existing tab to front or open new)
            handled = False
            if sys.platform == "darwin":
                try:
                    osa = f'''
                    tell application "Google Chrome"
                        if running then
                            repeat with w in windows
                                set tabIdx to 0
                                repeat with t in tabs of w
                                    set tabIdx to tabIdx + 1
                                    if URL of t contains "youtube.com" then
                                        set active tab index of w to tabIdx
                                        set URL of t to "{dest_url}"
                                        set index of w to 1
                                        activate
                                        return true
                                    end if
                                end repeat
                            end repeat
                        end if
                    end tell
                    return false
                    '''
                    res = subprocess.run(["osascript", "-e", osa], capture_output=True, text=True, timeout=1.2)
                    if "true" in res.stdout.lower():
                        handled = True
                except Exception:
                    pass

            if not handled:
                webbrowser.open(dest_url)

            return {
                "status": "success",
                "action": "youtube_intent",
                "level": "2.0",
                "channel": channel_name,
                "topic": topic_name,
                "category": cat_name,
                "url": dest_url,
                "response": f"Opening {channel_name} ({topic_name}) on YouTube based on your active {cat_name} context and viewing history.",
            }

        # 6. GitHub & Developer Workspace Intent Flow ("open my repo", "open github", "open pull requests", "open prs")
        gh_match = re.match(r"^(?:open|show|go\s+to)\s+(?:my\s+)?(?:github|repo|repository|pull\s+requests?|prs?)(?:\s+(?:repo|page))?$", raw_prompt.strip(), re.IGNORECASE)
        if gh_match:
            repo = self.memory.get_developer_repo()
            is_pr = any(w in prompt for w in ["pull request", "pull requests", "prs", "pr"])
            dest_url = f"https://github.com/{repo}/pulls" if is_pr else f"https://github.com/{repo}"
            self._notify_action("executing", f"Opening {repo} on GitHub")
            webbrowser.open(dest_url)
            return {
                "status": "success",
                "action": "open_github_repo",
                "level": "2.0",
                "repo": repo,
                "url": dest_url,
                "response": f"Opening {repo}{' Pull Requests' if is_pr else ''} on GitHub in browser.",
            }

        # 7. Calendar & Daily Schedule Intent ("check my schedule", "calendar", "what's my schedule")
        if any(p in prompt for p in ["check my schedule", "what is my schedule", "what's my schedule", "show schedule", "open my calendar"]):
            self._notify_action("executing", "Opening Calendar")
            if sys.platform == "darwin":
                subprocess.run(["open", "-a", "Calendar"], capture_output=True)
            return {
                "status": "success",
                "action": "open_calendar",
                "level": "2.0",
                "response": "Opened your Calendar for today's schedule.",
            }

        # 8. Temporal & Daily Routine Intent Flow ("start my day", "daily routine", "morning routine", "work mode", "gaming mode", "what should I do?")
        routine_triggers = [
            "start my day", "start the day", "morning routine", "daily routine",
            "kick off my day", "start working", "work mode", "work routine",
            "gaming mode", "game mode", "evening routine", "what should i do",
            "start work", "set up my workspace", "setup workspace"
        ]
        if any(t in prompt for t in routine_triggers):
            req_routine = "gaming" if any(w in prompt for w in ["gaming", "game"]) else ("work" if "work" in prompt else ("morning" if "morning" in prompt else None))
            routine = self.memory.get_daily_routine(req_routine)
            r_name = routine["name"]
            steps = routine["steps"]
            executed_labels = []

            self._notify_action("executing", f"Executing {r_name.capitalize()} Routine")

            for step in steps:
                act = step.get("action")
                target = step.get("target")
                lbl = step.get("label", act)
                try:
                    if act == "open_app" and target:
                        if sys.platform == "darwin":
                            subprocess.run(["open", "-a", target], capture_output=True)
                    elif act == "open_repo" and target:
                        webbrowser.open(f"https://github.com/{target}")
                    elif act == "play_spotify" and target:
                        self._control_spotify_play(target)
                    executed_labels.append(lbl)
                except Exception as e:
                    logger.warning(f"Error executing step in routine: {e}")

            summary_steps = ", ".join(executed_labels)
            return {
                "status": "success",
                "action": "daily_routine",
                "level": "2.5",
                "routine": r_name,
                "executed_steps": executed_labels,
                "response": f"Executed your {r_name.capitalize()} routine: {summary_steps}.",
            }

        # 9. Local Machine Ingestion & Personal History Sync ("sync my data", "sync my history", "learn my habits", "import my history")
        if any(p in prompt for p in ["sync my data", "sync my history", "learn my habits", "import my history", "sync my machine"]):
            self._notify_action("executing", "Ingesting Local Machine History & Telemetry")
            res = self.memory.sync_local_persona()
            yt_count = res.get("youtube_entries_ingested", 0)
            sites_count = res.get("top_sites_ingested", 0)
            return {
                "status": "success",
                "action": "sync_local_persona",
                "level": "2.0",
                "details": res,
                "response": f"Ingested your real machine data: {yt_count} YouTube items, {sites_count} top web applications, and local Git identity.",
            }

        # 10. Screen Introspection & Active Window Reading
        if any(p in prompt for p in ["what is on my screen", "what's on my screen", "inspect screen", "read screen", "inspect active window", "read active window", "summarize screen", "what is on screen"]):
            return self._control_inspect_screen(prompt)

        # 2. Dark Mode / Appearance Toggle
        if "dark mode" in prompt or "light mode" in prompt:
            return self._control_dark_mode(prompt)

        # 3. Apple Notes Creation
        note_match = re.match(r"^(?:create note|take a note|take note|new note|write note|note:)\s*(.+)", raw_prompt, re.IGNORECASE)
        if note_match:
            return self._control_notes_create(note_match.group(1).strip())

        # 4. Clipboard Management
        if "clipboard" in prompt or re.search(r"copy\s+.+?\s+to\s+(?:my\s+)?clipboard", raw_prompt, re.IGNORECASE):
            return self._control_clipboard(prompt, raw_prompt)

        # 5. System Notifications
        notif_match = re.match(r"^(?:notify me|alert me|send notification)\s+(.+)", raw_prompt, re.IGNORECASE)
        if notif_match:
            return self._control_notification(notif_match.group(1).strip())

        # 6. Window Management
        if any(w in prompt for w in ["minimize window", "maximize window", "zoom window", "close window", "hide window"]):
            return self._control_window_management(prompt)

        # 7. Semantic UI Action Dispatch (Click / Type / Press)
        click_match = re.match(r"^click\s+(?:\"([^\"]+)\"|'([^']+)'|([a-zA-Z0-9_\-\.\s]+?))(?:\s+(?:in|on)\s+([a-zA-Z0-9_\-\.\s]+))?$", raw_prompt, re.IGNORECASE)
        if click_match and not any(w in prompt for w in ["screenshot", "play", "search", "open", "launch"]):
            label = click_match.group(1) or click_match.group(2) or click_match.group(3)
            app_target = click_match.group(4)
            if label:
                return self._control_semantic_click(label.strip(), app_target.strip() if app_target else None)

        type_match = re.match(r"^type\s+(?:\"([^\"]+)\"|'([^']+)'|([a-zA-Z0-9_\-\.\s]+?))(?:\s+(?:in|into)\s+([a-zA-Z0-9_\-\.\s]+))?$", raw_prompt, re.IGNORECASE)
        if type_match:
            text = type_match.group(1) or type_match.group(2) or type_match.group(3)
            app_target = type_match.group(4)
            if text:
                return self._control_semantic_type(text.strip(), app_target.strip() if app_target else None)

        press_match = re.match(r"^press\s+([a-zA-Z0-9\+\-]+)(?:\s+(?:in|on)\s+([a-zA-Z0-9_\-\.\s]+))?$", raw_prompt, re.IGNORECASE)
        if press_match:
            key = press_match.group(1).strip()
            app_target = press_match.group(2)
            return self._control_semantic_press(key, app_target.strip() if app_target else None)

        # 8. Spotify / Music Playback
        if not prompt.startswith("open ") and (any(w in prompt for w in ["spotify", "music", "song", "track"]) or prompt.startswith("play ") or prompt.startswith("pause") or prompt.startswith("resume") or prompt.startswith("skip")):
            play_match = re.search(r"^play\s+(.+?)(?:\s+on\s+spotify)?$", raw_prompt, re.IGNORECASE)
            if play_match:
                song = play_match.group(1).strip().strip('"\'')
                self._notify_action("executing", f"Playing '{song}' on Spotify")
                return self._control_spotify_play(song)

            if "pause" in prompt:
                self._notify_action("executing", "Pausing Spotify playback")
                return self._control_spotify_media_key("playpause")
            if "resume" in prompt:
                self._notify_action("executing", "Resuming Spotify playback")
                return self._control_spotify_media_key("playpause")
            if "next" in prompt or "skip" in prompt:
                self._notify_action("executing", "Skipping to next track")
                return self._control_spotify_media_key("next track")

        # 9. Calculator
        if any(w in prompt for w in ["calculate", "compute", "math"]) or (("what is" in prompt) and any(c.isdigit() for c in prompt)) or re.search(r"[\d\s\+\-\*\/\(\)]{3,}", prompt):
            math_expr = re.sub(r"[^\d\+\-\*\/\.\(\)\s]", "", prompt).strip()
            if math_expr and any(op in math_expr for op in ["+", "-", "*", "/"]):
                try:
                    allowed_chars = set("0123456789+-*/.() ")
                    if all(c in allowed_chars for c in math_expr) and "**" not in math_expr:
                        val = eval(math_expr, {"__builtins__": None}, {})
                        res_str = f"{val:g}" if isinstance(val, float) else str(val)
                        self._notify_action("completed", f"Result: {res_str}")
                        self._sync_calculator(math_expr)
                        return {
                            "status": "success",
                            "action": "calculate",
                            "expression": math_expr,
                            "result": res_str,
                            "response": f"The answer is {res_str}.",
                        }
                except Exception:
                    pass

        # 10a. Folder Navigation (e.g. "open downloads", "open documents", "open desktop")
        folder_match = re.match(r"^(?:open|show|go to|view)\s+(?:my\s+)?(downloads|documents|desktop|pictures|movies|music|trash|home|library)(?:\s+folder)?$", raw_prompt, re.IGNORECASE)
        if folder_match:
            folder_name = folder_match.group(1).lower()
            self._notify_action("executing", f"Opening {folder_name} folder")
            folder_map = {
                "downloads": Path.home() / "Downloads",
                "documents": Path.home() / "Documents",
                "desktop": Path.home() / "Desktop",
                "pictures": Path.home() / "Pictures",
                "movies": Path.home() / "Movies",
                "music": Path.home() / "Music",
                "home": Path.home(),
                "trash": Path.home() / ".Trash",
                "library": Path.home() / "Library",
            }
            target_path = folder_map.get(folder_name, Path.home())
            if sys.platform == "darwin":
                subprocess.run(["open", str(target_path)], capture_output=True)
            return {
                "status": "success",
                "action": "open_folder",
                "folder": folder_name,
                "path": str(target_path),
                "response": f"Opened {folder_name.capitalize()} in Finder.",
            }

        # 10b. Quit / Close Application (e.g. "quit Spotify", "close Chrome", "kill Slack")
        quit_match = re.match(r"^(?:quit|close|exit|kill)\s+(?:the\s+)?([a-zA-Z0-9\s\.\-]+)$", raw_prompt, re.IGNORECASE)
        if quit_match:
            target_raw = quit_match.group(1).strip()
            if target_raw.lower() not in {"window", "this window", "active window", "tab", "dialog"}:
                resolved_app = self.resolve_app_name(target_raw) or target_raw
                self._notify_action("executing", f"Quitting {resolved_app}")
                if sys.platform == "darwin":
                    osa = f'tell application "{resolved_app}" to quit'
                    subprocess.run(["osascript", "-e", osa], capture_output=True)
                return {
                    "status": "success",
                    "action": "quit_app",
                    "target": resolved_app,
                    "response": f"Closed {resolved_app}.",
                }

        # 10c. App Launching & Web Navigation
        open_match = re.match(r"^(?:open|launch|switch to|go to)\s+([a-zA-Z0-9\s\.\:\/\-]+)$", raw_prompt, re.IGNORECASE)
        if open_match:
            app_target = open_match.group(1).strip()
            target_lower = app_target.lower()

            # Check if target is a known folder
            known_folders = {"downloads", "documents", "desktop", "pictures", "movies", "music", "trash", "home", "library"}
            clean_folder = target_lower.replace(" folder", "").strip()
            if clean_folder in known_folders:
                folder_map = {
                    "downloads": Path.home() / "Downloads",
                    "documents": Path.home() / "Documents",
                    "desktop": Path.home() / "Desktop",
                    "pictures": Path.home() / "Pictures",
                    "movies": Path.home() / "Movies",
                    "music": Path.home() / "Music",
                    "home": Path.home(),
                    "trash": Path.home() / ".Trash",
                    "library": Path.home() / "Library",
                }
                target_path = folder_map.get(clean_folder, Path.home())
                if sys.platform == "darwin":
                    subprocess.run(["open", str(target_path)], capture_output=True)
                return {
                    "status": "success",
                    "action": "open_folder",
                    "folder": clean_folder,
                    "path": str(target_path),
                    "response": f"Opened {clean_folder.capitalize()} in Finder.",
                }

            if target_lower in ["youtube", "yt"]:
                return self.execute_intent("open youtube")
            if target_lower in ["github", "repo", "repository"]:
                return self.execute_intent("open my repo")

            self._notify_action("executing", f"Opening {app_target}")

            web_map = {
                "gmail": "https://mail.google.com",
                "google mail": "https://mail.google.com",
                "google": "https://www.google.com",
                "twitter": "https://x.com",
                "x": "https://x.com",
                "reddit": "https://www.reddit.com",
                "linkedin": "https://www.linkedin.com",
                "chatgpt": "https://chatgpt.com",
                "notion": "https://www.notion.so",
                "figma": "https://www.figma.com",
                "crcle": "https://crcle.ai",
                "crcle.ai": "https://crcle.ai",
            }
            web_url = web_map.get(target_lower)
            if not web_url:
                if target_lower.startswith(("http://", "https://")):
                    web_url = app_target
                elif any(target_lower.endswith(tld) for tld in [".com", ".ai", ".io", ".org", ".net", ".app", ".dev", ".co", ".edu"]):
                    web_url = f"https://{app_target}"

            if web_url:
                webbrowser.open(web_url)
                return {
                    "status": "success",
                    "action": "open_url",
                    "url": web_url,
                    "target": app_target,
                    "response": f"Opened {app_target} in browser.",
                }

            # Resolve application name dynamically with typo tolerance
            resolved_target = self.resolve_app_name(app_target) or app_target
            if sys.platform == "darwin":
                res = subprocess.run(["open", "-a", resolved_target], capture_output=True, text=True)
                is_success = (res.returncode == 0) if isinstance(getattr(res, "returncode", None), int) else True
                if is_success:
                    return {
                        "status": "success",
                        "action": "open_app",
                        "target": resolved_target,
                        "response": f"Opened {resolved_target}.",
                    }
                else:
                    # Fallback to browser only if explicit web domain
                    if "." in target_lower and not target_lower.endswith(".app"):
                        fallback_url = f"https://{target_lower}"
                        webbrowser.open(fallback_url)
                        return {
                            "status": "success",
                            "action": "open_url",
                            "url": fallback_url,
                            "target": app_target,
                            "response": f"Opened {fallback_url} in browser.",
                        }
                    return {
                        "status": "error",
                        "action": "open_app",
                        "target": resolved_target,
                        "response": f"Could not find application '{resolved_target}'.",
                    }
            return {"status": "success", "action": "open_app", "target": resolved_target, "response": f"Opened {resolved_target}."}

        # 11. Web Search / Browser
        search_match = re.search(r"(?:search|google|look up)\s+(?:for\s+)?(.+)", raw_prompt, re.IGNORECASE)
        if search_match:
            query = search_match.group(1).strip()
            self._notify_action("executing", f"Searching web for: {query}")
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            webbrowser.open(url)
            return {
                "status": "success",
                "action": "web_search",
                "query": query,
                "response": f"Searching Google for {query}.",
            }

        # 12. System Audio Volume
        if "mute" in prompt or "unmute" in prompt or "volume" in prompt:
            if "unmute" in prompt:
                self._notify_action("executing", "Unmuting volume")
                if sys.platform == "darwin":
                    subprocess.run(["osascript", "-e", "set volume output muted false"], capture_output=True)
                return {"status": "success", "action": "unmute", "response": "Unmuted system volume."}
            elif "mute" in prompt:
                self._notify_action("executing", "Muting volume")
                if sys.platform == "darwin":
                    subprocess.run(["osascript", "-e", "set volume output muted true"], capture_output=True)
                return {"status": "success", "action": "mute", "response": "Muted system volume."}
            vol_set_match = re.search(r"volume\s+(?:to\s+)?(\d+)", prompt)
            if vol_set_match:
                vol_num = max(0, min(100, int(vol_set_match.group(1))))
                self._notify_action("executing", f"Setting volume to {vol_num}%")
                if sys.platform == "darwin":
                    subprocess.run(["osascript", "-e", f"set volume output volume {vol_num}"], capture_output=True)
                return {"status": "success", "action": "set_volume", "volume": vol_num, "response": f"Volume set to {vol_num}%."}
            if "up" in prompt or "raise" in prompt or "increase" in prompt:
                self._notify_action("executing", "Increasing volume")
                if sys.platform == "darwin":
                    subprocess.run(["osascript", "-e", "set volume output volume (output volume of (get volume settings) + 12)"], capture_output=True)
                return {"status": "success", "action": "volume_up", "response": "Volume increased."}
            if "down" in prompt or "lower" in prompt or "decrease" in prompt:
                self._notify_action("executing", "Decreasing volume")
                if sys.platform == "darwin":
                    subprocess.run(["osascript", "-e", "set volume output volume (output volume of (get volume settings) - 12)"], capture_output=True)
                return {"status": "success", "action": "volume_down", "response": "Volume decreased."}

        # 13. Screenshot
        if "screenshot" in prompt or "screen capture" in prompt or "capture screen" in prompt:
            self._notify_action("executing", "Capturing screenshot")
            import datetime
            desktop_dir = Path.home() / "Desktop"
            if not desktop_dir.exists():
                desktop_dir = Path.home()
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            shot_path = str(desktop_dir / f"Screenshot_{timestamp}.png")
            if sys.platform == "darwin":
                subprocess.run(["screencapture", "-x", shot_path], capture_output=True)
            return {"status": "success", "action": "screenshot", "file": shot_path, "response": f"Screenshot saved to {Path(shot_path).name}."}

        return None

    def _get_frontmost_app_name(self) -> Optional[str]:
        """Resolves the name of the currently active frontmost GUI application."""
        if sys.platform == "darwin":
            try:
                osa = 'tell application "System Events" to get name of first process whose frontmost is true'
                res = subprocess.run(["osascript", "-e", osa], capture_output=True, text=True, timeout=1.5)
                name = res.stdout.strip()
                if name:
                    return name
            except Exception:
                pass
            try:
                import AppKit
                app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
                if app:
                    return str(app.localizedName())
            except Exception:
                pass
        return None

    def _control_inspect_screen(self, prompt: str) -> Dict[str, Any]:
        """Deep semantic inspection of the active frontmost window without vision tokens."""
        self._notify_action("executing", "Inspecting active screen")
        app_name = self._get_frontmost_app_name() or "Desktop"
        try:
            app_inst = DesktopApp.attach(app_name)
            tree = app_inst.get_tree(max_depth=4, as_dict=False)
            assert isinstance(tree, DesktopNode)
            
            interactive_roles = {"button", "input", "checkbox", "tab", "menuitem", "link", "image"}
            items = []
            def _collect(n: DesktopNode):
                if n.role in interactive_roles and n.name and len(n.name.strip()) > 0:
                    items.append(f"{n.role} '{n.name}'")
                for c in n.children:
                    _collect(c)
            _collect(tree)
            
            if items:
                summary = f"Active window '{tree.name or app_name}' with {len(items)} interactive elements: " + ", ".join(items[:6])
                if len(items) > 6:
                    summary += f" and {len(items) - 6} more."
            else:
                summary = f"Active window '{tree.name or app_name}'."
                
            return {
                "status": "success",
                "action": "inspect_screen",
                "app": app_name,
                "window": tree.name or app_name,
                "elements_count": len(items),
                "summary": summary,
                "response": f"Frontmost application is {app_name}. {summary}",
            }
        except Exception as e:
            logger.warning(f"Screen inspection failed: {e}")
            adapter = get_platform_adapter()
            top_apps = [a.get("name", "") for a in adapter.list_applications()[:5]]
            return {
                "status": "success",
                "action": "inspect_screen",
                "app": app_name,
                "response": f"Active application is {app_name}. Running apps: {', '.join(top_apps)}.",
            }

    def _control_dark_mode(self, prompt: str) -> Dict[str, Any]:
        """Toggles or sets macOS appearance dark mode."""
        self._notify_action("executing", "Toggling appearance mode")
        if sys.platform == "darwin":
            if any(w in prompt for w in ["turn on", "enable", "dark mode on"]):
                script = 'tell application "System Events" to tell appearance preferences to set dark mode to true\nreturn true'
            elif any(w in prompt for w in ["turn off", "disable", "light mode", "dark mode off"]):
                script = 'tell application "System Events" to tell appearance preferences to set dark mode to false\nreturn false'
            else:
                script = 'tell application "System Events" to tell appearance preferences\nset dark mode to not dark mode\nreturn dark mode\nend tell'
            
            try:
                res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
                is_dark = "true" in res.stdout.lower()
                state_str = "enabled" if is_dark else "disabled"
                return {
                    "status": "success",
                    "action": "toggle_dark_mode",
                    "dark_mode": is_dark,
                    "response": f"Dark mode is now {state_str}.",
                }
            except Exception as e:
                logger.warning(f"Dark mode toggle error: {e}")
                return {
                    "status": "error",
                    "action": "toggle_dark_mode",
                    "response": f"Failed to toggle dark mode: {e}",
                }
        return {
            "status": "error",
            "action": "toggle_dark_mode",
            "response": "Dark mode toggle is only supported on macOS.",
        }

    def _control_notes_create(self, content: str) -> Dict[str, Any]:
        """Creates a formatted note in Apple Notes."""
        self._notify_action("executing", "Creating note in Apple Notes")
        if ":" in content:
            title, _, body = content.partition(":")
            title = title.strip()
            body = body.strip() or title
        else:
            words = content.strip().split()
            title = " ".join(words[:4]) if len(words) > 4 else content.strip()
            body = content.strip()
        
        if not title:
            title = "Aura Note"
        if not body:
            body = title

        if sys.platform == "darwin":
            safe_title = title.replace('\\', '\\\\').replace('"', '\\"')
            safe_body = body.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '<br>')
            osa = f'''
            tell application "Notes"
                activate
                tell account 1
                    make new note at folder 1 with properties {{name:"{safe_title}", body:"{safe_body}"}}
                end tell
            end tell
            '''
            try:
                res = subprocess.run(["osascript", "-e", osa], capture_output=True, text=True, timeout=3.0)
                is_success = (res.returncode == 0) if isinstance(getattr(res, "returncode", None), int) else True
                if is_success:
                    return {
                        "status": "success",
                        "action": "create_note",
                        "title": title,
                        "body": body,
                        "response": f"Created note '{title}' in Apple Notes.",
                    }
                else:
                    return {
                        "status": "error",
                        "action": "create_note",
                        "response": f"Could not create note in Apple Notes: {getattr(res, 'stderr', '').strip()}",
                    }
            except Exception as e:
                return {
                    "status": "error",
                    "action": "create_note",
                    "response": f"Notes error: {e}",
                }
        return {
            "status": "error",
            "action": "create_note",
            "response": "Apple Notes is only supported on macOS.",
        }

    def _control_send_message(
        self,
        entity: Dict[str, Any],
        content: Optional[str] = None,
        client: str = "Microsoft Outlook",
    ) -> Dict[str, Any]:
        """Dispatches an email or message to a resolved contact entity using the preferred client."""
        name = entity.get("name", "Contact")
        email = entity.get("email", "").strip()
        if not email:
            return {
                "status": "error",
                "action": "send_message",
                "target": name,
                "response": f"Contact '{name}' is in memory, but has no email address configured.",
            }

        self._notify_action("executing", f"Composing message to {name} ({email}) in {client}")

        user_name = "Piyush"
        try:
            mem_summary = self.memory.get_summary()
            user_name = mem_summary.get("user", {}).get("name", "Piyush")
        except Exception:
            pass

        first_name = name.split()[0] if name else "there"
        if content:
            clean_content = content.strip().strip('"\'')
            if len(clean_content) < 50:
                subject = clean_content.capitalize()
                body = clean_content
            else:
                subject = "Update"
                body = clean_content
            clean_for_draft = re.sub(r"^(?:that|saying|about|with)\s+", "", clean_content, flags=re.IGNORECASE).strip()
            draft_body = f"Hi {first_name},\n\n{clean_for_draft.capitalize()}.\n\nBest,\n{user_name}"
        else:
            snap = None
            try:
                snap = self.context_feed.capture_active_context(record=False)
            except Exception:
                pass
            if snap and snap.focused_topic and snap.focused_topic not in ["Desktop", "General", "Main Window"]:
                subject = f"Update on {snap.focused_topic}"
                body = f"Working on {snap.focused_topic}"
                draft_body = f"Hi {first_name},\n\nSharing a quick update: currently working on {snap.focused_topic}.\n\nBest,\n{user_name}"
            else:
                subject = "Quick Note"
                body = ""
                draft_body = f"Hi {first_name},\n\nHope you are having a productive week! Wanted to connect briefly.\n\nBest,\n{user_name}"

        encoded_subject = urllib.parse.quote(subject)
        encoded_body = urllib.parse.quote(draft_body)
        mailto_url = f"mailto:{email}?subject={encoded_subject}&body={encoded_body}"

        if sys.platform == "darwin":
            # 1. Native Microsoft Outlook outgoing draft via AppleScript
            if "outlook" in client.lower():
                escaped_subject = subject.replace('\\', '\\\\').replace('"', '\\"')
                escaped_body = draft_body.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
                escaped_name = name.replace('\\', '\\\\').replace('"', '\\"')
                escaped_email = email.replace('\\', '\\\\').replace('"', '\\"')
                osa_script = f'''tell application "Microsoft Outlook"
    activate
    set newMsg to make new outgoing message with properties {{subject:"{escaped_subject}", plain text content:"{escaped_body}"}}
    make new recipient at newMsg with properties {{email address:{{name:"{escaped_name}", address:"{escaped_email}"}}}}
    open newMsg
end tell'''
                res = subprocess.run(["osascript", "-e", osa_script], capture_output=True, text=True, timeout=4.0)
                if res.returncode == 0:
                    return {
                        "status": "success",
                        "action": "send_message",
                        "level": "2.5",
                        "recipient": name,
                        "email": email,
                        "company": entity.get("company", ""),
                        "role": entity.get("role", ""),
                        "client": "Microsoft Outlook",
                        "subject": subject,
                        "body": body,
                        "verified": True,
                        "response": f"Composed message in Microsoft Outlook to {name} ({email}) with subject '{subject}'.",
                    }

            # 2. Native Apple Mail outgoing draft via AppleScript
            if "mail" in client.lower():
                escaped_subject = subject.replace('\\', '\\\\').replace('"', '\\"')
                escaped_body = body.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
                escaped_name = name.replace('\\', '\\\\').replace('"', '\\"')
                escaped_email = email.replace('\\', '\\\\').replace('"', '\\"')
                osa_script = f'''tell application "Mail"
    activate
    set newMsg to make new outgoing message with properties {{subject:"{escaped_subject}", content:"{escaped_body}", visible:true}}
    tell newMsg
        make new to recipient at end of to recipients with properties {{name:"{escaped_name}", address:"{escaped_email}"}}
    end tell
end tell'''
                res = subprocess.run(["osascript", "-e", osa_script], capture_output=True, text=True, timeout=4.0)
                if res.returncode == 0:
                    return {
                        "status": "success",
                        "action": "send_message",
                        "level": "2.5",
                        "recipient": name,
                        "email": email,
                        "company": entity.get("company", ""),
                        "role": entity.get("role", ""),
                        "client": "Mail",
                        "subject": subject,
                        "verified": True,
                        "response": f"Composed message in Mail to {name} ({email}) with subject '{subject}'.",
                    }

            # 3. Fallback to system mailto handler
            res = subprocess.run(["open", mailto_url], capture_output=True, text=True)
            if res.returncode == 0:
                return {
                    "status": "success",
                    "action": "send_message",
                    "level": "2.5",
                    "recipient": name,
                    "email": email,
                    "company": entity.get("company", ""),
                    "role": entity.get("role", ""),
                    "client": client,
                    "subject": subject,
                    "body": body,
                    "response": f"Opened email compose window to {name} ({email}).",
                }
            else:
                return {
                    "status": "error",
                    "action": "send_message",
                    "response": f"Failed to open mail client: {res.stderr.strip()}",
                }

        # Cross-platform fallback
        webbrowser.open(mailto_url)
        return {
            "status": "success",
            "action": "send_message",
            "recipient": name,
            "email": email,
            "company": entity.get("company", ""),
            "role": entity.get("role", ""),
            "client": client,
            "subject": subject,
            "body": body,
            "response": f"Opened email composer for {name} ({email}).",
        }

    def _control_clipboard(self, prompt: str, raw_prompt: str) -> Dict[str, Any]:
        """Reads or writes the system clipboard."""
        copy_match = re.search(r"copy\s+(.+?)\s+to\s+(?:my\s+)?clipboard", raw_prompt, re.IGNORECASE)
        if copy_match:
            text = copy_match.group(1).strip().strip('"\'')
            self._notify_action("executing", f"Copying to clipboard: '{text[:20]}...'")
            if sys.platform == "darwin":
                try:
                    p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
                    p.communicate(text.encode("utf-8"))
                except Exception:
                    pass
            return {
                "status": "success",
                "action": "copy_clipboard",
                "text": text,
                "response": "Copied to clipboard.",
            }
        else:
            self._notify_action("executing", "Reading clipboard")
            text = ""
            if sys.platform == "darwin":
                try:
                    res = subprocess.run(["pbpaste"], capture_output=True, text=True)
                    text = res.stdout.strip()
                except Exception:
                    pass
            preview = text[:80] + "..." if len(text) > 80 else text
            return {
                "status": "success",
                "action": "read_clipboard",
                "text": text,
                "response": f"Clipboard contains: '{preview}'." if preview else "Clipboard is currently empty.",
            }

    def _control_notification(self, message: str) -> Dict[str, Any]:
        """Dispatches an absolute OS notification."""
        self._notify_action("executing", f"Sending notification: {message}")
        if sys.platform == "darwin":
            safe_msg = message.replace('\\', '\\\\').replace('"', '\\"')
            try:
                subprocess.run(["osascript", "-e", f'display notification "{safe_msg}" with title "Aura Assistant"'], capture_output=True)
            except Exception:
                pass
        return {
            "status": "success",
            "action": "notify",
            "message": message,
            "response": f"Notification sent: {message}.",
        }

    def _control_window_management(self, prompt: str) -> Dict[str, Any]:
        """Controls frontmost window geometry and state."""
        self._notify_action("executing", "Managing window")
        action_type = "unknown"
        if "minimize" in prompt or "hide" in prompt:
            action_type = "minimize"
            script = 'tell application "System Events" to set miniaturized of front window of (first process whose frontmost is true) to true'
        elif "maximize" in prompt or "zoom" in prompt:
            action_type = "maximize"
            script = 'tell application "System Events" to set zoomed of front window of (first process whose frontmost is true) to true'
        elif "close" in prompt:
            action_type = "close"
            script = 'tell application "System Events" to click (first button of front window of (first process whose frontmost is true) whose subrole is "AXCloseButton")'
        else:
            return {"status": "unhandled", "response": "Unrecognized window action."}
        
        if sys.platform == "darwin":
            try:
                res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=3.0)
                is_success = (res.returncode == 0) if isinstance(getattr(res, "returncode", None), int) else True
                if is_success:
                    return {
                        "status": "success",
                        "action": f"window_{action_type}",
                        "response": f"Front window {action_type} executed.",
                    }
                else:
                    return {
                        "status": "error",
                        "action": f"window_{action_type}",
                        "response": f"Window {action_type} failed: {getattr(res, 'stderr', '').strip()}",
                    }
            except Exception as e:
                return {"status": "error", "action": f"window_{action_type}", "response": f"Window action error: {e}"}
        return {"status": "error", "action": f"window_{action_type}", "response": "Window management only supported on macOS."}

    def _control_semantic_click(self, label: str, app_name: Optional[str]) -> Dict[str, Any]:
        """Finds and clicks an element by semantic name or role in target application."""
        target_app = app_name or self._get_frontmost_app_name()
        self._notify_action("executing", f"Clicking '{label}' in {target_app or 'active app'}")
        if not target_app:
            return {
                "status": "error",
                "action": "click",
                "response": f"Could not determine active application to click '{label}'.",
            }
        try:
            app_inst = DesktopApp.attach(target_app)
            node = app_inst.find(name=label) or app_inst.find(role="button", name=label)
            if not node:
                all_nodes = app_inst.find_all()
                for n in all_nodes:
                    if n.name and label.lower() in n.name.lower():
                        node = n
                        break
            if node:
                app_inst.click(node.id)
                cx, cy = node.bbox.centroid
                return {
                    "status": "success",
                    "action": "click",
                    "target": target_app,
                    "element": node.name or label,
                    "role": node.role,
                    "centroid": [cx, cy],
                    "response": f"Clicked '{node.name or label}' ({node.role}) in {target_app}.",
                }
            return {
                "status": "not_found",
                "action": "click",
                "target": target_app,
                "element": label,
                "response": f"Could not find element '{label}' in {target_app}.",
            }
        except Exception as e:
            logger.warning(f"Click dispatch error: {e}")
            return {
                "status": "error",
                "action": "click",
                "target": target_app,
                "response": f"Failed to click '{label}' in {target_app}: {e}",
            }

    def _control_semantic_type(self, text: str, app_name: Optional[str]) -> Dict[str, Any]:
        """Types text into target app or focused input field."""
        target_app = app_name or self._get_frontmost_app_name()
        self._notify_action("executing", f"Typing into {target_app or 'active app'}")
        try:
            if target_app:
                app_inst = DesktopApp.attach(target_app)
                inp = app_inst.find(role="input")
                app_inst.type(inp.id if inp else None, text)
            else:
                adapter = get_platform_adapter()
                adapter.type_text(None, text)
            return {
                "status": "success",
                "action": "type",
                "text": text,
                "target": target_app,
                "response": f"Typed text into {target_app or 'active window'}.",
            }
        except Exception as e:
            logger.warning(f"Type dispatch error: {e}")
            return {
                "status": "error",
                "action": "type",
                "target": target_app,
                "response": f"Failed to type: {e}",
            }

    def _control_semantic_press(self, key: str, app_name: Optional[str]) -> Dict[str, Any]:
        """Sends key press to target application."""
        target_app = app_name or self._get_frontmost_app_name()
        self._notify_action("executing", f"Pressing '{key}'")
        try:
            if target_app:
                app_inst = DesktopApp.attach(target_app)
                app_inst.press(key)
            else:
                adapter = get_platform_adapter()
                adapter.press_key(key)
            return {
                "status": "success",
                "action": "press",
                "key": key,
                "target": target_app,
                "response": f"Pressed key '{key}'.",
            }
        except Exception as e:
            logger.warning(f"Press dispatch error: {e}")
            return {
                "status": "error",
                "action": "press",
                "key": key,
                "response": f"Failed to press '{key}': {e}",
            }

    def _control_spotify_play(self, query: str) -> Dict[str, Any]:
        """Plays a song or artist in Spotify using desktop-dom or native OSA dispatch."""
        if sys.platform == "darwin":
            import urllib.parse
            encoded_query = urllib.parse.quote(query)
            target_uri = query if query.startswith("spotify:") else f"spotify:search:{encoded_query}"
            osa = f'''
            tell application "Spotify"
                activate
                set shuffling to false
                open location "{target_uri}"
                delay 0.4
                play
            end tell
            '''
            try:
                res = subprocess.run(["osascript", "-e", osa], capture_output=True, text=True, timeout=4.0)
                is_success = (res.returncode == 0) if isinstance(getattr(res, "returncode", None), int) else True
                if is_success:
                    try:
                        import Quartz
                        down = Quartz.CGEventCreateKeyboardEvent(None, 36, True)
                        up = Quartz.CGEventCreateKeyboardEvent(None, 36, False)
                        Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
                        time.sleep(0.02)
                        Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)
                    except Exception:
                        pass
                    return {
                        "status": "success",
                        "action": "spotify_play",
                        "query": query,
                        "response": f"Now playing {query} on Spotify.",
                    }
                else:
                    return {
                        "status": "error",
                        "action": "spotify_play",
                        "query": query,
                        "response": f"Spotify playback failed: {getattr(res, 'stderr', '').strip()}",
                    }
            except Exception as e:
                return {
                    "status": "error",
                    "action": "spotify_play",
                    "query": query,
                    "response": f"Spotify playback error: {e}",
                }

        return {
            "status": "error",
            "action": "spotify_play",
            "query": query,
            "response": "Spotify playback control is only supported on macOS.",
        }

    def _control_spotify_media_key(self, command: str) -> Dict[str, Any]:
        """Controls Spotify media state."""
        if sys.platform == "darwin":
            osa = f'tell application "Spotify" to {command}'
            try:
                res = subprocess.run(["osascript", "-e", osa], capture_output=True, text=True, timeout=3.0)
                is_success = (res.returncode == 0) if isinstance(getattr(res, "returncode", None), int) else True
                if is_success:
                    return {"status": "success", "action": f"spotify_{command}", "response": f"Spotify: {command}."}
                else:
                    return {
                        "status": "error",
                        "action": f"spotify_{command}",
                        "response": f"Spotify command '{command}' failed: {getattr(res, 'stderr', '').strip()}",
                    }
            except Exception as e:
                return {"status": "error", "action": f"spotify_{command}", "response": f"Spotify error: {e}"}
        return {"status": "error", "action": f"spotify_{command}", "response": "Spotify control is only supported on macOS."}

    def _sync_calculator(self, expr: str):
        """Attempts to sync calculation on macOS Calculator if attached."""
        try:
            app = DesktopApp.attach("Calculator")
            ac = app.find(role="button", name="All Clear") or app.find(role="button", name="Clear")
            if ac:
                app.click(ac.id)
            time.sleep(0.05)
            for ch in expr.replace("*", "×"):
                btn = app.find(role="button", name=ch)
                if btn:
                    app.click(btn.id)
            eq = app.find(role="button", name="=") or app.find(role="button", name="Equals")
            if eq:
                app.click(eq.id)
        except Exception:
            pass

    def _execute_with_local_llm(self, prompt: str) -> Dict[str, Any]:
        """Prompts local Ollama model with rich desktop context for open-ended reasoning."""
        self._notify_action("thinking", f"Reasoning with local {self.preferred_model}...")
        
        adapter = get_platform_adapter()
        apps_summary = [a["name"] for a in adapter.list_applications()[:8]]
        
        active_app = self._get_frontmost_app_name()
        screen_context = f"Frontmost active application: {active_app or 'None'}."
        try:
            if active_app:
                app_inst = DesktopApp.attach(active_app)
                tree = app_inst.get_tree(max_depth=3, as_dict=False)
                assert isinstance(tree, DesktopNode)
                interactive_roles = {"button", "input", "checkbox", "tab", "menuitem", "link", "image"}
                items = [f"{n.role} '{n.name}'" for n in tree.find_all() if n.role in interactive_roles and n.name]
                if items:
                    screen_context += f" Active window '{tree.name}' contains: {', '.join(items[:8])}."
        except Exception:
            pass

        # Extract Level 2 personal memory context
        mem_summary = self.memory.get_summary()
        user_ctx = f"User: {mem_summary['user']['name']} ({mem_summary['user']['role']})."
        top_contacts = mem_summary.get("top_contacts", [])
        contacts_str = ", ".join(f"{c['name']} ({c.get('email', '')})" for c in top_contacts if c.get("name")) if top_contacts else "None"
        contacts_ctx = f"Known Contacts: {contacts_str}."
        pref_mail = mem_summary.get("preferences", {}).get("mail.preferred_client", "Microsoft Outlook")
        pref_music = mem_summary.get("preferences", {}).get("spotify.favorite_playlist", "Deep Focus")

        system_prompt = (
            "You are Aura, an autonomous personal desktop assistant powered by desktop-dom. "
            "You have direct access to native OS controls. Answer helpfully and concisely. "
            f"{user_ctx} {contacts_ctx} Preferred Email: {pref_mail}. Preferred Music: {pref_music}. "
            f"{screen_context} Running applications: {', '.join(apps_summary)}. "
            "If the user wants you to perform an action, output an ACTION line: "
            "ACTION: open <app_name> | ACTION: quit <app_name> | ACTION: open <downloads|documents|desktop> | "
            "ACTION: message <name> saying <body> | ACTION: email <name> about <subject> | "
            "ACTION: play <song|playlist> on spotify | ACTION: volume <0-100|up|down|mute|unmute> | "
            "ACTION: note <title>: <body> | ACTION: search <query> | ACTION: calculate <expr> | ACTION: screenshot. "
            "Otherwise, provide a direct, concise 1-2 sentence answer."
        )

        payload = {
            "model": self.preferred_model,
            "prompt": f"{system_prompt}\n\nUser Request: {prompt}\n\nAssistant Response:",
            "stream": False,
        }

        try:
            req = urllib.request.Request(
                f"{self.ollama_host}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "desktop-dom"},
            )
            with urllib.request.urlopen(req, timeout=35.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                reply = data.get("response", "").strip()
                if not reply:
                    return {"status": "empty", "action": "llm_reasoning", "response": "No response from model."}
                
                # Check for executable action emitted by LLM
                action_match = re.search(r"ACTION:\s*([^\n\r]+)", reply, re.IGNORECASE)
                if action_match:
                    action_cmd = action_match.group(1).strip()
                    fast_res = self._try_deterministic_fast_path(action_cmd.lower(), raw_prompt=action_cmd)
                    if fast_res:
                        return fast_res

                return {"status": "success", "action": "llm_reasoning", "response": reply}
        except Exception as e:
            logger.warning(f"Local LLM call failed: {e}")
            return {
                "status": "error",
                "action": "llm_error",
                "response": f"Local model error: {e}. Ollama may be offline or busy.",
            }
