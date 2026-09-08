from __future__ import annotations
import os
import re
import sys
import time
import json
import sqlite3
import logging
import difflib
import threading
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("desktop_dom.assistant.memory")

DEFAULT_DB_DIR = Path.home() / ".desktop_dom"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "aura_memory.db"


class AuraMemory:
    """
    Local-first, sub-millisecond Personal Context & Memory Engine for Aura.
    Stores user contacts, preferences, habits, and activity logs in SQLite with WAL mode.
    Provides intelligent entity disambiguation, LRU/frequency ranking, natural language
    learning, and multi-source data ingestion (macOS Contacts, Spotify habits, etc.).
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        
        # In-memory hot cache for instant (<0.1ms) lookups
        self._entity_cache: List[Dict[str, Any]] = []
        self._pref_cache: Dict[str, str] = {}
        
        self._init_db()
        self._reload_cache()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a configured SQLite connection with row factories and WAL mode."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self):
        """Initializes database schema and bootstraps seed data if new."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Entities Table (Contacts, Colleagues, Founders, Organizations)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                aliases TEXT NOT NULL DEFAULT '[]',
                email TEXT,
                phone TEXT,
                company TEXT,
                role TEXT,
                category TEXT DEFAULT 'contact',
                interaction_count INTEGER DEFAULT 0,
                last_interaction REAL DEFAULT 0.0,
                metadata TEXT DEFAULT '{}',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_email ON entities(email);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_rank ON entities(interaction_count DESC, last_interaction DESC);")

            # 2. Preferences & Habits Table (Key-Value)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                updated_at REAL NOT NULL
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_preferences_category ON preferences(category);")

            # 3. Activity & Context Log
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                intent TEXT NOT NULL,
                entity_id INTEGER,
                query TEXT,
                details TEXT DEFAULT '{}',
                timestamp REAL NOT NULL,
                FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE SET NULL
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON activity_log(timestamp DESC);")

            # Check if seeding is required
            cursor.execute("SELECT COUNT(*) as count FROM entities;")
            row = cursor.fetchone()
            if row and row["count"] == 0:
                self._bootstrap_seed_data(cursor)

            conn.commit()

    def _bootstrap_seed_data(self, cursor: sqlite3.Cursor):
        """Pre-seeds high-frequency contacts and default preferences for Crcle.ai demo."""
        now = time.time()
        
        # Initial Contacts
        seeds = [
            (
                "Joshua Rayan",
                json.dumps(["josh", "joshua", "josh rayan", "joshua rayan"]),
                "josh@crcle.ai",
                "",
                "Crcle.ai",
                "Co-Founder & CEO",
                "colleague",
                10,
                now,
                json.dumps({"relation": "founder", "preferred_client": "Microsoft Outlook"}),
                now,
                now,
            ),
            (
                "Cyril Rayan",
                json.dumps(["cyril", "cyril rayan"]),
                "cyril@crcle.ai",
                "",
                "Crcle.ai",
                "Co-Founder",
                "colleague",
                8,
                now - 3600,
                json.dumps({"relation": "founder", "preferred_client": "Microsoft Outlook"}),
                now,
                now,
            ),
            (
                "Piyush Dua",
                json.dumps(["piyush", "me", "myself"]),
                "piyushdua01@gmail.com",
                "",
                "Crcle.ai",
                "Backend Engineer",
                "user",
                25,
                now,
                json.dumps({"user": True, "github": "PDgit12", "focus": "Systems & Intent Architecture"}),
                now,
                now,
            ),
        ]

        cursor.executemany("""
        INSERT INTO entities (
            name, aliases, email, phone, company, role, category,
            interaction_count, last_interaction, metadata, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, seeds)

        # Initial Preferences
        prefs = [
            ("spotify.favorite_playlist", "Deep Focus", "music", now),
            ("spotify.routine_playlist", "Discover Weekly", "music", now),
            ("mail.preferred_client", "Microsoft Outlook", "mail", now),
            ("messaging.default_target", "josh@crcle.ai", "messaging", now),
            ("user.name", "Piyush Dua", "user", now),
            ("user.company", "Crcle.ai", "user", now),
            ("user.role", "Backend Engineer", "user", now),
        ]

        cursor.executemany("""
        INSERT OR REPLACE INTO preferences (key, value, category, updated_at)
        VALUES (?, ?, ?, ?);
        """, prefs)

    def _reload_cache(self):
        """Loads all entities and preferences into fast in-memory structures."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM entities ORDER BY interaction_count DESC, last_interaction DESC;")
            entities = []
            for r in cursor.fetchall():
                ent = dict(r)
                try:
                    ent["aliases"] = json.loads(ent.get("aliases") or "[]")
                except Exception:
                    ent["aliases"] = []
                try:
                    ent["metadata"] = json.loads(ent.get("metadata") or "{}")
                except Exception:
                    ent["metadata"] = {}
                entities.append(ent)
            self._entity_cache = entities

            cursor.execute("SELECT key, value FROM preferences;")
            self._pref_cache = {r["key"]: r["value"] for r in cursor.fetchall()}

    # -------------------------------------------------------------------------
    # Entity Resolution & Disambiguation Engine (<0.5ms)
    # -------------------------------------------------------------------------

    def resolve_entity(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Disambiguates and resolves natural language references (e.g. 'josh', 'joshua',
        'cyril', 'piyush') into a canonical Entity record using tiered matching:
        1. Exact alias or name match (Score: 100)
        2. Word boundary / substring match (Score: 85)
        3. Fuzzy phonetic / string similarity match (Score: 70+)
        Ranked by confidence score + interaction recency/frequency.
        """
        clean = query.strip().lower()
        if not clean:
            return None

        # Clean noise words (e.g., 'to josh', 'my friend josh', 'mr josh')
        clean = re.sub(r"^(?:to|with|for|contact|email|message)\s+", "", clean).strip()

        best_entity: Optional[Dict[str, Any]] = None
        best_score = -1.0

        with self._lock:
            for ent in self._entity_cache:
                score = 0.0
                name_clean = ent["name"].lower()
                aliases = [a.lower() for a in ent.get("aliases", [])]

                # 1. Exact match on name or any alias
                if clean == name_clean:
                    score = 100.0
                elif clean in aliases:
                    score = 98.0
                elif any(clean == a.split()[0] for a in [name_clean] + aliases):
                    # First name exact match (e.g. "Josh" -> "Joshua Rayan")
                    score = 92.0
                elif clean in name_clean:
                    # Substring match
                    score = 80.0
                elif any(clean in a for a in aliases):
                    score = 78.0
                else:
                    # Fuzzy match
                    ratios = [difflib.SequenceMatcher(None, clean, a).ratio() for a in [name_clean] + aliases]
                    max_ratio = max(ratios) if ratios else 0.0
                    if max_ratio >= 0.72:
                        score = max_ratio * 75.0

                if score > 0:
                    # Interaction Frequency & Recency Boosting
                    freq_boost = min(ent.get("interaction_count", 0) * 0.5, 10.0)
                    score += freq_boost

                    if score > best_score:
                        best_score = score
                        best_entity = ent

        if best_entity and best_score >= 65.0:
            # Record resolution in memory
            self.touch_entity(best_entity["id"], query)
            return best_entity

        return None

    def touch_entity(self, entity_id: int, query: str = ""):
        """Increments interaction count and updates last_interaction timestamp."""
        now = time.time()
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE entities 
            SET interaction_count = interaction_count + 1, 
                last_interaction = ?,
                updated_at = ?
            WHERE id = ?;
            """, (now, now, entity_id))

            cursor.execute("""
            INSERT INTO activity_log (intent, entity_id, query, details, timestamp)
            VALUES (?, ?, ?, ?, ?);
            """, ("touch", entity_id, query, "{}", now))

            conn.commit()

        # Update in-memory cache
        for ent in self._entity_cache:
            if ent["id"] == entity_id:
                ent["interaction_count"] = ent.get("interaction_count", 0) + 1
                ent["last_interaction"] = now
                break

    # -------------------------------------------------------------------------
    # Preferences & Habit Recall (<0.1ms)
    # -------------------------------------------------------------------------

    def get_preference(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Returns stored preference by key (sub-0.1ms in-memory cache lookup)."""
        with self._lock:
            return self._pref_cache.get(key, default)

    def set_preference(self, key: str, value: str, category: str = "general"):
        """Persists preference in SQLite and syncs in-memory cache."""
        now = time.time()
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO preferences (key, value, category, updated_at)
            VALUES (?, ?, ?, ?);
            """, (key, str(value), category, now))
            conn.commit()
            self._pref_cache[key] = str(value)

    def list_preferences(self, category: Optional[str] = None) -> Dict[str, str]:
        """Returns key-value preferences dictionary."""
        with self._lock:
            if category:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT key, value FROM preferences WHERE category = ?;", (category,))
                    return {r["key"]: r["value"] for r in cursor.fetchall()}
            return dict(self._pref_cache)

    # -------------------------------------------------------------------------
    # Entity CRUD API
    # -------------------------------------------------------------------------

    def add_entity(
        self,
        name: str,
        email: Optional[str] = None,
        aliases: Optional[List[str]] = None,
        phone: str = "",
        company: str = "",
        role: str = "",
        category: str = "contact",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Adds or updates an entity in SQLite and updates cache."""
        now = time.time()
        alias_list = aliases or []
        first_name = name.strip().split()[0].lower()
        if first_name not in [a.lower() for a in alias_list]:
            alias_list.append(first_name)
        
        meta_dict = metadata or {}

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO entities (
                name, aliases, email, phone, company, role, category,
                interaction_count, last_interaction, metadata, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?);
            """, (
                name.strip(),
                json.dumps(alias_list),
                email.strip() if email else "",
                phone.strip(),
                company.strip(),
                role.strip(),
                category.strip(),
                now,
                json.dumps(meta_dict),
                now,
                now,
            ))
            entity_id = cursor.lastrowid
            conn.commit()

        self._reload_cache()
        return self.get_entity(entity_id) or {}

    def get_entity(self, entity_id: int) -> Optional[Dict[str, Any]]:
        """Returns entity dict by ID."""
        with self._lock:
            for ent in self._entity_cache:
                if ent["id"] == entity_id:
                    return ent
        return None

    def list_entities(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns top entities ranked by interaction count."""
        with self._lock:
            return self._entity_cache[:limit]

    # -------------------------------------------------------------------------
    # Natural Language Learning & Memory Ingestion ("remember ...")
    # -------------------------------------------------------------------------

    def remember(self, prompt: str) -> Dict[str, Any]:
        """
        Parses natural language knowledge statements and persists them into SQLite:
        - "remember Josh is josh@crcle.ai"
        - "remember Cyril's email is cyril@crcle.ai"
        - "remember my favorite playlist is Lofi Beats"
        - "remember my role is Senior Backend Engineer"
        """
        raw = prompt.strip()
        clean = re.sub(r"^remember\s+(?:that\s+)?", "", raw, flags=re.IGNORECASE).strip()

        # 1. Contact / Email Pattern
        email_match = re.match(
            r"^([a-zA-Z0-9\s]+?)(?:'s\s+email|'s\s+mail)?\s+(?:is|at|=)\s+([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)",
            clean,
            re.IGNORECASE
        )
        if email_match:
            name_raw = email_match.group(1).strip()
            email_val = email_match.group(2).strip().lower()

            # Check if entity already exists
            existing = self.resolve_entity(name_raw)
            if existing:
                with self._lock, self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                    UPDATE entities SET email = ?, updated_at = ? WHERE id = ?;
                    """, (email_val, time.time(), existing["id"]))
                    conn.commit()
                self._reload_cache()
                return {
                    "status": "success",
                    "action": "remember_contact",
                    "name": existing["name"],
                    "email": email_val,
                    "response": f"Updated {existing['name']}'s email to {email_val} in memory.",
                }
            else:
                new_ent = self.add_entity(name=name_raw, email=email_val)
                return {
                    "status": "success",
                    "action": "remember_contact",
                    "name": new_ent.get("name", name_raw),
                    "email": email_val,
                    "response": f"Saved new contact: {new_ent.get('name', name_raw)} ({email_val}) in memory.",
                }

        # 2. User Playlist Pattern
        playlist_match = re.match(
            r"^(?:my\s+)?(?:favorite\s+|favourite\s+)?playlist\s+is\s+(.+)$",
            clean,
            re.IGNORECASE
        )
        if playlist_match:
            playlist_name = playlist_match.group(1).strip().strip('"\'')
            self.set_preference("spotify.favorite_playlist", playlist_name, category="music")
            return {
                "status": "success",
                "action": "remember_preference",
                "key": "spotify.favorite_playlist",
                "value": playlist_name,
                "response": f"Remembered your favorite Spotify playlist is '{playlist_name}'.",
            }

        # 3. User Preference / Attribute Pattern (e.g. "my role is Backend Engineer")
        pref_match = re.match(r"^(?:my\s+)([a-zA-Z0-9_\s]+?)\s+is\s+(.+)$", clean, re.IGNORECASE)
        if pref_match:
            attr = pref_match.group(1).strip().lower().replace(" ", "_")
            val = pref_match.group(2).strip().strip('"\'')
            self.set_preference(f"user.{attr}", val, category="user")
            return {
                "status": "success",
                "action": "remember_preference",
                "key": f"user.{attr}",
                "value": val,
                "response": f"Remembered your {attr.replace('_', ' ')} is '{val}'.",
            }

        # 4. Fallback Generic Fact Memory
        self.set_preference(f"fact.{int(time.time())}", clean, category="facts")
        return {
            "status": "success",
            "action": "remember_fact",
            "fact": clean,
            "response": f"Stored in memory: '{clean}'.",
        }

    # -------------------------------------------------------------------------
    # Knowledge Inquiries ("who is ...", "what is my ...")
    # -------------------------------------------------------------------------

    def who_is(self, query: str) -> Optional[str]:
        """Provides natural language biography/contact info for a queried entity."""
        clean = re.sub(r"^(?:who\s+is|tell\s+me\s+about)\s+", "", query, flags=re.IGNORECASE).rstrip("?").strip()
        ent = self.resolve_entity(clean)
        if not ent:
            return None

        parts = [f"{ent['name']}"]
        role = ent.get("role")
        company = ent.get("company")
        if role and company:
            parts.append(f"is the {role} at {company}")
        elif role:
            parts.append(f"is {role}")
        elif company:
            parts.append(f"is at {company}")

        email = ent.get("email")
        if email:
            parts.append(f"({email})")

        interactions = ent.get("interaction_count", 0)
        parts.append(f"· {interactions} interactions recorded.")
        return " ".join(parts)

    def get_summary(self) -> Dict[str, Any]:
        """Returns high-level statistics and recent memory context."""
        with self._lock:
            contacts_count = len(self._entity_cache)
            top_contacts = [
                {"name": e["name"], "email": e.get("email", ""), "count": e.get("interaction_count", 0)}
                for e in self._entity_cache[:5]
            ]
            favorite_playlist = self.get_preference("spotify.favorite_playlist", "Deep Focus")
            preferred_client = self.get_preference("mail.preferred_client", "Microsoft Outlook")
            user_name = self.get_preference("user.name", "Piyush Dua")
            user_role = self.get_preference("user.role", "Backend Engineer")

            return {
                "user": {"name": user_name, "role": user_role},
                "contacts_count": contacts_count,
                "top_contacts": top_contacts,
                "preferences": {
                    "spotify.favorite_playlist": favorite_playlist,
                    "mail.preferred_client": preferred_client,
                },
                "db_path": str(self.db_path),
            }

    # -------------------------------------------------------------------------
    # Multi-Source Ingestion (macOS Contacts)
    # -------------------------------------------------------------------------

    def sync_system_contacts(self, limit: int = 40) -> int:
        """
        Safely imports contacts from macOS Address Book without external dependencies.
        Returns the number of contacts ingested or updated.
        """
        if sys.platform != "darwin":
            return 0

        script = f'''
        tell application "Contacts"
            set contactList to {{}}
            set maxCount to {limit}
            set pList to people
            set tot to count of pList
            if tot < maxCount then set maxCount to tot
            repeat with i from 1 to maxCount
                set p to item i of pList
                set pName to name of p
                set pEmail to ""
                if (count of emails of p) > 0 then
                    set pEmail to value of email 1 of p
                end if
                set pCompany to ""
                try
                    set pCompany to organization of p
                end try
                set end of contactList to (pName & "|||" & pEmail & "|||" & pCompany)
            end repeat
            return contactList
        end tell
        '''
        try:
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=4.0)
            if res.returncode != 0:
                logger.warning(f"macOS Contacts sync error: {res.stderr.strip()}")
                return 0

            raw_out = res.stdout.strip()
            if not raw_out:
                return 0

            items = [item.strip() for item in raw_out.split(", ") if "|||" in item]
            count = 0
            for item in items:
                parts = item.split("|||")
                if len(parts) >= 2:
                    c_name = parts[0].strip()
                    c_email = parts[1].strip() if len(parts) > 1 else ""
                    c_company = parts[2].strip() if len(parts) > 2 else ""

                    if c_name and c_email and "@" in c_email:
                        # Ingest if not present
                        existing = self.resolve_entity(c_name)
                        if not existing:
                            self.add_entity(name=c_name, email=c_email, company=c_company)
                            count += 1

            if count > 0:
                self._reload_cache()
            return count
        except Exception as e:
            logger.warning(f"macOS Contacts sync exception: {e}")
            return 0
