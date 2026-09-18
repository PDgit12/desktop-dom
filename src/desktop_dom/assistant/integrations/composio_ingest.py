"""
Composio Ingestion & Knowledge Graph Synchronization Pipeline.
Translates canonical models from Google Calendar, GitHub, and Gmail into Aura's
sovereign SQLite Knowledge Graph with strict source provenance, cluster isolation,
and privacy-preserving purge capabilities.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from desktop_dom.assistant.memory import AuraMemory
from .composio_client import ComposioHttpClient
from .normalizer import ComposioNormalizer

logger = logging.getLogger("desktop_dom.assistant.integrations.ingest")


class ComposioIngest:
    """Orchestrates bounded data ingestion from Composio into AuraMemory."""

    def __init__(self, memory: Optional[AuraMemory] = None, client: Optional[ComposioHttpClient] = None):
        self.memory = memory or AuraMemory()
        self.client = client or ComposioHttpClient()

    def sync_calendar(self, user_id: str, limit: int = 20) -> Dict[str, Any]:
        """
        Ingests Google Calendar agenda, extracts meeting links, and adds attendees as collaborators.
        """
        if not self.client.is_configured():
            return {"status": "unconfigured", "synced_events": 0, "synced_contacts": 0}

        res = self.client.execute_read_action(
            action_name="GOOGLECALENDAR_FIND_EVENTS",
            entity_id=user_id,
            params={"maxResults": limit},
        )
        if res.get("status") == "error":
            return {"status": "error", "error": res.get("message"), "synced_events": 0}

        raw_events = res.get("data", {}).get("items") or res.get("items") or []
        user_name = self.memory.get_preference("user.name") or "User"
        user_company = self.memory.get_preference("user.company") or "Crcle.ai"

        canonical_events = []
        synced_contacts_count = 0

        for raw_e in raw_events:
            event, contacts = ComposioNormalizer.normalize_calendar_event(raw_e)
            canonical_events.append(event.model_dump())

            # Hydrate attendees into Knowledge Graph
            for contact in contacts:
                # Deduplicate and add
                self.memory.add_entity(
                    name=contact.name,
                    email=contact.email,
                    aliases=contact.aliases,
                    company=user_company if contact.email.endswith(f"@{user_company.lower().replace(' ', '')}.com") else "",
                    category="contact",
                    metadata={"provenance": contact.provenance, "verified": True},
                )
                self.memory.add_edge(
                    source=user_name,
                    target=contact.name,
                    relation="meets_with",
                    cluster="work",
                    weight=0.90,
                    metadata={"provenance": contact.provenance},
                )
                synced_contacts_count += 1

        # Cache canonical agenda in memory preferences
        self.memory.set_preference("calendar.events.today", json.dumps(canonical_events[: limit // 2]), category="calendar")
        self.memory.set_preference("calendar.last_synced", str(time.time()), category="calendar")

        return {
            "status": "success",
            "synced_events": len(canonical_events),
            "synced_contacts": synced_contacts_count,
            "events": canonical_events,
        }

    def sync_github(self, user_id: str, limit: int = 15) -> Dict[str, Any]:
        """
        Ingests user repositories and open pull requests from GitHub into the Knowledge Graph.
        """
        if not self.client.is_configured():
            return {"status": "unconfigured", "synced_repos": 0}

        res = self.client.execute_read_action(
            action_name="GITHUB_GET_USER_REPOS",
            entity_id=user_id,
            params={"per_page": limit},
        )
        if res.get("status") == "error":
            return {"status": "error", "error": res.get("message"), "synced_repos": 0}

        raw_repos = res.get("data") if isinstance(res.get("data"), list) else res.get("items", [])
        user_name = self.memory.get_preference("user.name") or "User"
        user_company = self.memory.get_preference("user.company") or "Crcle.ai"

        canonical_repos = []
        for raw_r in raw_repos:
            repo = ComposioNormalizer.normalize_github_repo(raw_r)
            canonical_repos.append(repo.model_dump())

            # Add repo entity to Knowledge Graph
            self.memory.add_entity(
                name=repo.name,
                role="Code Repository",
                company=user_company,
                category="project",
                aliases=[repo.full_name, repo.name.lower()],
                metadata={
                    "provenance": repo.provenance,
                    "full_name": repo.full_name,
                    "html_url": repo.html_url,
                    "open_prs_count": repo.open_prs_count,
                },
            )
            self.memory.add_edge(
                source=user_name,
                target=repo.name,
                relation="develops_repo",
                cluster="work",
                weight=1.0,
                metadata={"provenance": repo.provenance},
            )

        repo_names = [r["name"] for r in canonical_repos]
        self.memory.set_preference("work.repos", json.dumps(repo_names), category="developer")
        self.memory.set_preference("github.last_synced", str(time.time()), category="developer")

        return {
            "status": "success",
            "synced_repos": len(canonical_repos),
            "repos": canonical_repos,
        }

    def sync_gmail(self, user_id: str, limit: int = 25) -> Dict[str, Any]:
        """
        Discovers top correspondents from recent Gmail messages and populates work contacts.
        """
        if not self.client.is_configured():
            return {"status": "unconfigured", "synced_contacts": 0}

        res = self.client.execute_read_action(
            action_name="GMAIL_LIST_MESSAGES",
            entity_id=user_id,
            params={"maxResults": limit},
        )
        if res.get("status") == "error":
            return {"status": "error", "error": res.get("message"), "synced_contacts": 0}

        raw_messages = res.get("data", {}).get("messages") or res.get("messages") or []
        user_name = self.memory.get_preference("user.name") or "User"

        contact_freq: Dict[str, CanonicalContact] = {}
        for raw_m in raw_messages:
            _, contacts = ComposioNormalizer.normalize_gmail_message(raw_m)
            for c in contacts:
                if c.email in contact_freq:
                    contact_freq[c.email].interaction_count += 1
                else:
                    contact_freq[c.email] = c

        synced_count = 0
        for contact in contact_freq.values():
            self.memory.add_entity(
                name=contact.name,
                email=contact.email,
                aliases=contact.aliases,
                category="contact",
                metadata={"provenance": contact.provenance, "verified": True},
            )
            weight = min(1.0, 0.6 + (contact.interaction_count * 0.1))
            self.memory.add_edge(
                source=user_name,
                target=contact.name,
                relation="communicates_with",
                cluster="work",
                weight=round(weight, 2),
                metadata={"provenance": contact.provenance},
            )
            synced_count += 1

        self.memory.set_preference("gmail.last_synced", str(time.time()), category="mail")

        return {
            "status": "success",
            "synced_contacts": synced_count,
        }

    def sync_all_active(self, user_id: str) -> Dict[str, Any]:
        """Syncs all external apps that are currently marked ACTIVE in connected_accounts."""
        accounts = self.memory.list_connected_accounts(user_id=user_id)
        results = {}

        for acc in accounts:
            if acc.get("status") == "ACTIVE":
                toolkit = acc.get("toolkit", "")
                if toolkit == "googlecalendar":
                    results["googlecalendar"] = self.sync_calendar(user_id)
                elif toolkit == "github":
                    results["github"] = self.sync_github(user_id)
                elif toolkit == "gmail":
                    results["gmail"] = self.sync_gmail(user_id)

                if acc.get("external_id"):
                    self.memory.update_connected_account(acc["external_id"], last_synced_at=time.time())

        return results

    def disconnect_and_purge(self, toolkit: str, user_id: str) -> Dict[str, Any]:
        """
        Disconnects an external integration, revokes the connection, and purges all
        entities/edges originating solely from this integration (Sovereign Privacy Guarantee).
        """
        clean_toolkit = toolkit.strip().lower()
        acc = self.memory.get_connected_account(toolkit=clean_toolkit, user_id=user_id)

        remote_disconnected = False
        if acc and acc.get("external_id"):
            remote_disconnected = self.client.disconnect_account(acc["external_id"])
            self.memory.revoke_connected_account(acc["external_id"])

        # Purge local SQLite data matching provenance prefix
        provenance_prefix = f"composio:{clean_toolkit}"
        purge_stats = self.memory.purge_provenance_data(provenance_prefix)

        return {
            "toolkit": clean_toolkit,
            "remote_disconnected": remote_disconnected,
            "purged_entities": purge_stats.get("purged_entities", 0),
            "purged_edges": purge_stats.get("purged_edges", 0),
        }
