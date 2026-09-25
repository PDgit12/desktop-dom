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
        self.client = client or ComposioHttpClient(memory=self.memory)

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
        user_company = self.memory.get_user_company()

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
        user_company = self.memory.get_user_company()

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

    # -------------------------------------------------------------------------
    # Active Execution / Write Actions (Powering Omnibar Direct Actions)
    # -------------------------------------------------------------------------

    def create_github_issue(
        self,
        repo: str,
        title: str,
        body: Optional[str] = None,
        user_id: str = "user_local",
    ) -> Dict[str, Any]:
        """Creates a GitHub issue on the specified repository using connected GitHub credentials."""
        if not self.client.is_configured():
            return {"status": "unconfigured", "toolkit": "github", "message": "Composio API key is not configured."}

        acc = self.memory.get_connected_account(toolkit="github", user_id=user_id)
        if not acc or acc.get("status") != "ACTIVE":
            return {
                "status": "unconnected",
                "toolkit": "github",
                "message": "GitHub account is not connected. Connect GitHub in Settings (Composio) to create issues.",
            }

        # Parse owner/repo
        clean_repo = repo.strip().strip("/")
        if "/" in clean_repo:
            owner, repo_name = clean_repo.split("/", 1)
        else:
            owner = self.memory.get_preference("user.github_owner") or self.memory.system_identity.get("github_owner", "")
            repo_name = clean_repo

        params = {
            "owner": owner,
            "repo": repo_name,
            "title": title,
            "body": body or f"Filed autonomously via Aura Omnibar on {time.strftime('%Y-%m-%d %H:%M:%S')}.",
        }

        res = self.client.execute_action(
            action_name="GITHUB_CREATE_AN_ISSUE",
            entity_id=user_id,
            params=params,
        )

        if res.get("status") == "error":
            return {"status": "error", "toolkit": "github", "error": res.get("message", "Failed to create issue")}

        issue_data = res.get("data") or res
        issue_url = issue_data.get("html_url") or f"https://github.com/{owner}/{repo_name}/issues"
        issue_num = issue_data.get("number")

        return {
            "status": "success",
            "action": "create_github_issue",
            "toolkit": "github",
            "repo": f"{owner}/{repo_name}",
            "title": title,
            "number": issue_num,
            "url": issue_url,
            "response": f"Created GitHub issue #{issue_num or ''} on {owner}/{repo_name}: '{title}'.\n• URL: {issue_url}",
        }

    def create_calendar_event(
        self,
        title: str,
        start_time: str,
        end_time: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        description: Optional[str] = None,
        user_id: str = "user_local",
    ) -> Dict[str, Any]:
        """Schedules a calendar event on Google Calendar with attendee invites."""
        if not self.client.is_configured():
            return {"status": "unconfigured", "toolkit": "googlecalendar", "message": "Composio API key is not configured."}

        acc = self.memory.get_connected_account(toolkit="googlecalendar", user_id=user_id)
        if not acc or acc.get("status") != "ACTIVE":
            return {
                "status": "unconnected",
                "toolkit": "googlecalendar",
                "message": "Google Calendar is not connected. Connect Google Calendar in Settings (Composio) to schedule events.",
            }

        attendee_list = []
        if attendees:
            for att in attendees:
                if "@" in att:
                    attendee_list.append({"email": att})
                else:
                    ent = self.memory.resolve_entity(att)
                    if ent and ent.get("email"):
                        attendee_list.append({"email": ent["email"], "displayName": ent.get("name", att)})
                    else:
                        attendee_list.append({"displayName": att})

        params = {
            "summary": title,
            "start": {"dateTime": start_time},
            "end": {"dateTime": end_time or start_time},
            "description": description or "Scheduled autonomously via Aura Omnibar.",
        }
        if attendee_list:
            params["attendees"] = attendee_list

        res = self.client.execute_action(
            action_name="GOOGLECALENDAR_CREATE_EVENT",
            entity_id=user_id,
            params=params,
        )

        if res.get("status") == "error":
            return {"status": "error", "toolkit": "googlecalendar", "error": res.get("message", "Failed to create event")}

        ev_data = res.get("data") or res
        meeting_url = ev_data.get("hangoutLink") or ev_data.get("htmlLink") or "https://calendar.google.com"

        return {
            "status": "success",
            "action": "create_calendar_event",
            "toolkit": "googlecalendar",
            "title": title,
            "meeting_url": meeting_url,
            "attendees": [a.get("displayName") or a.get("email") for a in attendee_list],
            "response": f"Scheduled '{title}' on Google Calendar.\n• Link: {meeting_url}",
        }

    def create_email_draft(
        self,
        to: str,
        subject: str,
        body: str,
        user_id: str = "user_local",
    ) -> Dict[str, Any]:
        """Creates an email draft in Gmail using connected Composio credentials."""
        if not self.client.is_configured():
            return {"status": "unconfigured", "toolkit": "gmail", "message": "Composio API key is not configured."}

        acc = self.memory.get_connected_account(toolkit="gmail", user_id=user_id)
        if not acc or acc.get("status") != "ACTIVE":
            return {
                "status": "unconnected",
                "toolkit": "gmail",
                "message": "Gmail is not connected. Connect Gmail in Settings (Composio) to draft emails.",
            }

        recipient_email = to
        if "@" not in recipient_email:
            ent = self.memory.resolve_entity(to)
            if ent and ent.get("email"):
                recipient_email = ent["email"]

        params = {
            "to": [recipient_email],
            "subject": subject,
            "body": body,
        }

        res = self.client.execute_action(
            action_name="GMAIL_CREATE_DRAFT",
            entity_id=user_id,
            params=params,
        )

        if res.get("status") == "error":
            return {"status": "error", "toolkit": "gmail", "error": res.get("message", "Failed to draft email")}

        return {
            "status": "success",
            "action": "create_email_draft",
            "toolkit": "gmail",
            "to": recipient_email,
            "subject": subject,
            "response": f"Created email draft to {recipient_email} regarding '{subject}'.",
        }

    def send_slack_message(
        self,
        channel: str,
        text: str,
        user_id: str = "user_local",
    ) -> Dict[str, Any]:
        """Sends a message to a Slack channel using connected Composio Slack credentials."""
        if not self.client.is_configured():
            return {"status": "unconfigured", "toolkit": "slack", "message": "Composio API key is not configured."}

        acc = self.memory.get_connected_account(toolkit="slack", user_id=user_id)
        if not acc or acc.get("status") != "ACTIVE":
            return {
                "status": "unconnected",
                "toolkit": "slack",
                "message": "Slack is not connected. Connect Slack in Settings (Composio) to send messages.",
            }

        params = {
            "channel": channel.lstrip("#"),
            "text": text,
        }

        res = self.client.execute_action(
            action_name="SLACK_CHAT_POST_MESSAGE",
            entity_id=user_id,
            params=params,
        )

        if res.get("status") == "error":
            return {"status": "error", "toolkit": "slack", "error": res.get("message", "Failed to post to Slack")}

        return {
            "status": "success",
            "action": "send_slack_message",
            "toolkit": "slack",
            "channel": channel,
            "response": f"Sent message to #{channel} on Slack: '{text}'.",
        }

