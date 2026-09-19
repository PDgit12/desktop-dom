"""
Canonical Data Contracts & Connection State Models for External Integrations (Composio / SaaS).
Provides typed, immutable schemas that decouple Aura's sovereign SQLite Knowledge Graph
from third-party API payload changes.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ConnectedAccountState(BaseModel):
    """Represents the authentication and connection lifecycle of an external app."""
    app: str  # e.g. "googlecalendar", "github", "gmail", "slack"
    status: str = "DISCONNECTED"  # DISCONNECTED, INITIATING, AWAITING_USER_AUTH, ACTIVE, EXPIRED, FAILED
    account_id: Optional[str] = None
    auth_url: Optional[str] = None
    user_identifier: Optional[str] = None  # e.g. email or username in the connected app
    scopes: List[str] = Field(default_factory=list)
    last_synced: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def redirect_url(self) -> Optional[str]:
        return self.auth_url

    def get(self, key: str, default: Any = None) -> Any:
        if key == "redirect_url":
            return self.auth_url if self.auth_url is not None else default
        if key in {"connection_id", "id"}:
            return self.account_id if self.account_id is not None else default
        if hasattr(self, key):
            val = getattr(self, key)
            return val if val is not None else default
        return self.metadata.get(key, default) if self.metadata else default

    def __getitem__(self, key: str) -> Any:
        val = self.get(key)
        if val is None:
            raise KeyError(key)
        return val


class CanonicalContact(BaseModel):
    """Normalized contact entity extracted from Gmail, Slack, or Google Calendar."""
    id: str
    name: str
    email: str
    role: Optional[str] = None
    company: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    interaction_count: int = 1
    last_interaction: float = Field(default_factory=time.time)
    provenance: str = "composio"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CanonicalCalendarEvent(BaseModel):
    """Normalized calendar event extracted from Google Calendar."""
    id: str
    title: str
    start_time: str
    end_time: str
    attendees: List[Dict[str, str]] = Field(default_factory=list)  # [{"name": "...", "email": "..."}]
    meeting_url: Optional[str] = None
    location: Optional[str] = None
    status: str = "confirmed"
    is_recurring: bool = False
    calendar_name: str = "Primary"
    provenance: str = "composio:googlecalendar"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CanonicalRepository(BaseModel):
    """Normalized git/project repository extracted from GitHub."""
    id: str
    name: str
    full_name: str
    owner: str
    description: Optional[str] = None
    default_branch: str = "main"
    open_prs_count: int = 0
    assigned_issues_count: int = 0
    html_url: str
    is_private: bool = False
    languages: List[str] = Field(default_factory=list)
    provenance: str = "composio:github"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CanonicalCommunicationSnippet(BaseModel):
    """Normalized recent correspondence summary from Gmail or Slack."""
    id: str
    thread_id: Optional[str] = None
    channel_or_subject: str
    sender_name: str
    sender_email: Optional[str] = None
    snippet: str
    timestamp: float = Field(default_factory=time.time)
    app: str  # "gmail", "slack"
    provenance: str = "composio"
    metadata: Dict[str, Any] = Field(default_factory=dict)
