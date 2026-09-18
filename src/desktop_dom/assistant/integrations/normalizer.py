"""
Normalizer Pipeline for Composio / SaaS Payloads.
Transforms heterogeneous raw JSON dictionaries from Google Calendar, GitHub, and Gmail
into Aura's strict Canonical Data Contracts.
Guarantees zero coupling between external API changes and Aura's SQLite schema.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple

from .contracts import (
    CanonicalCalendarEvent,
    CanonicalContact,
    CanonicalRepository,
    CanonicalCommunicationSnippet,
)

# Regex matching meeting URLs (Google Meet, Zoom, Teams, Webex)
MEETING_URL_REGEX = re.compile(
    r"https?://(?:[a-zA-Z0-9-]+\.)?(?:zoom\.us|meet\.google\.com|teams\.microsoft\.com|webex\.com|chime\.aws)/[^\s\"'<>]+",
    re.IGNORECASE,
)


def extract_meeting_url_from_text(text: Optional[str]) -> Optional[str]:
    """Scans text for meeting URLs (Google Meet, Zoom, Microsoft Teams)."""
    if not text:
        return None
    match = MEETING_URL_REGEX.search(text)
    if match:
        return match.group(0).rstrip(".,;)")
    return None


class ComposioNormalizer:
    """Normalizes raw payloads from Composio tool actions into canonical models."""

    @staticmethod
    def normalize_calendar_event(raw: Dict[str, Any]) -> Tuple[CanonicalCalendarEvent, List[CanonicalContact]]:
        """
        Normalizes a Google Calendar event payload.
        Also extracts attendees as CanonicalContact objects for Knowledge Graph collaborator hydration.
        """
        event_id = str(raw.get("id") or raw.get("eventId") or f"evt_{int(time.time()*1000)}")
        title = str(raw.get("summary") or raw.get("title") or "Untitled Event").strip()

        # Extract start and end timestamps
        start_obj = raw.get("start") or {}
        end_obj = raw.get("end") or {}
        start_time = start_obj.get("dateTime") or start_obj.get("date") or str(raw.get("startTime") or "")
        end_time = end_obj.get("dateTime") or end_obj.get("date") or str(raw.get("endTime") or "")

        # Extract meeting URL from hangoutLink, conferenceData, location, or description
        meeting_url = raw.get("hangoutLink")
        if not meeting_url and isinstance(raw.get("conferenceData"), dict):
            entry_points = raw["conferenceData"].get("entryPoints") or []
            for ep in entry_points:
                if ep.get("entryPointType") == "video" and ep.get("uri"):
                    meeting_url = ep["uri"]
                    break

        location = raw.get("location")
        description = raw.get("description")

        if not meeting_url:
            meeting_url = (
                extract_meeting_url_from_text(location)
                or extract_meeting_url_from_text(description)
            )

        # Parse attendees
        raw_attendees = raw.get("attendees") or []
        attendees: List[Dict[str, str]] = []
        contacts: List[CanonicalContact] = []

        for att in raw_attendees:
            if not isinstance(att, dict):
                continue
            email = str(att.get("email") or "").strip().lower()
            if not email or "resource.calendar.google.com" in email:
                continue

            name = str(att.get("displayName") or att.get("name") or "").strip()
            if not name:
                name = email.split("@")[0].replace(".", " ").title()

            attendees.append({"name": name, "email": email})

            first_name = name.split()[0].lower() if name else ""
            contacts.append(
                CanonicalContact(
                    id=f"contact_{email}",
                    name=name,
                    email=email,
                    aliases=[name.lower(), first_name] if first_name else [name.lower()],
                    provenance="composio:googlecalendar",
                    metadata={"source": "googlecalendar_attendee"},
                )
            )

        event = CanonicalCalendarEvent(
            id=event_id,
            title=title,
            start_time=start_time,
            end_time=end_time,
            attendees=attendees,
            meeting_url=meeting_url,
            location=location,
            status=str(raw.get("status") or "confirmed").lower(),
            is_recurring=bool(raw.get("recurringEventId")),
            calendar_name=str(raw.get("calendarName") or "Primary"),
            provenance="composio:googlecalendar",
            metadata={"raw_id": raw.get("id")},
        )

        return event, contacts

    @staticmethod
    def normalize_github_repo(raw: Dict[str, Any]) -> CanonicalRepository:
        """Normalizes a GitHub repository payload."""
        repo_id = str(raw.get("id") or raw.get("node_id") or f"repo_{raw.get('name')}")
        name = str(raw.get("name") or "").strip()
        full_name = str(raw.get("full_name") or f"user/{name}").strip()

        owner_obj = raw.get("owner")
        if isinstance(owner_obj, dict):
            owner = str(owner_obj.get("login") or owner_obj.get("name") or "")
        else:
            owner = str(owner_obj or full_name.split("/")[0])

        description = raw.get("description")
        default_branch = str(raw.get("default_branch") or "main")
        open_prs_count = int(raw.get("open_issues_count") or raw.get("open_prs_count") or 0)
        html_url = str(raw.get("html_url") or f"https://github.com/{full_name}")
        is_private = bool(raw.get("private", False))

        languages = []
        lang = raw.get("language")
        if lang:
            languages.append(str(lang))

        return CanonicalRepository(
            id=repo_id,
            name=name,
            full_name=full_name,
            owner=owner,
            description=description,
            default_branch=default_branch,
            open_prs_count=open_prs_count,
            html_url=html_url,
            is_private=is_private,
            languages=languages,
            provenance="composio:github",
            metadata={"visibility": "private" if is_private else "public"},
        )

    @staticmethod
    def normalize_gmail_message(raw: Dict[str, Any]) -> Tuple[CanonicalCommunicationSnippet, List[CanonicalContact]]:
        """
        Normalizes a Gmail message snippet payload and extracts sender/recipient contacts.
        """
        msg_id = str(raw.get("id") or raw.get("messageId") or f"msg_{int(time.time()*1000)}")
        thread_id = raw.get("threadId")

        # Parse headers (Subject, From, To)
        headers = raw.get("headers") or {}
        if isinstance(headers, list):
            header_map = {}
            for h in headers:
                if isinstance(h, dict) and "name" in h and "value" in h:
                    header_map[h["name"].lower()] = h["value"]
            headers = header_map

        subject = str(headers.get("subject") or raw.get("subject") or "No Subject").strip()
        from_raw = str(headers.get("from") or raw.get("from") or raw.get("sender") or "").strip()
        to_raw = str(headers.get("to") or raw.get("to") or "").strip()
        snippet = str(raw.get("snippet") or raw.get("body") or "").strip()

        # Parse sender name and email
        sender_name, sender_email = ComposioNormalizer._parse_name_email(from_raw)
        contacts: List[CanonicalContact] = []

        if sender_email:
            first_name = sender_name.split()[0].lower() if sender_name else ""
            contacts.append(
                CanonicalContact(
                    id=f"contact_{sender_email}",
                    name=sender_name or sender_email.split("@")[0].title(),
                    email=sender_email,
                    aliases=[sender_name.lower(), first_name] if first_name else [sender_name.lower()],
                    interaction_count=1,
                    provenance="composio:gmail",
                    metadata={"source": "gmail_correspondent"},
                )
            )

        # Parse recipients
        if to_raw:
            for recipient in to_raw.split(","):
                r_name, r_email = ComposioNormalizer._parse_name_email(recipient.strip())
                if r_email and r_email != sender_email:
                    first = r_name.split()[0].lower() if r_name else ""
                    contacts.append(
                        CanonicalContact(
                            id=f"contact_{r_email}",
                            name=r_name or r_email.split("@")[0].title(),
                            email=r_email,
                            aliases=[r_name.lower(), first] if first else [r_name.lower()],
                            interaction_count=1,
                            provenance="composio:gmail",
                            metadata={"source": "gmail_recipient"},
                        )
                    )

        comm = CanonicalCommunicationSnippet(
            id=msg_id,
            thread_id=thread_id,
            channel_or_subject=subject,
            sender_name=sender_name or (sender_email or "Unknown"),
            sender_email=sender_email,
            snippet=snippet,
            timestamp=float(raw.get("timestamp") or raw.get("internalDate") or time.time()),
            app="gmail",
            provenance="composio:gmail",
            metadata={"thread_id": thread_id},
        )

        return comm, contacts

    @staticmethod
    def _parse_name_email(raw: str) -> Tuple[str, str]:
        """Extracts (Display Name, email@domain.com) from standard email header formats."""
        if not raw:
            return "", ""
        match = re.search(r"^(.*?)\s*<([^>]+)>$", raw.strip())
        if match:
            name = match.group(1).strip(' "')
            email = match.group(2).strip().lower()
            return name, email
        if "@" in raw:
            return "", raw.strip().lower()
        return raw.strip(), ""
