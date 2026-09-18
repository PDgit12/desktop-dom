"""
External SaaS Integrations & Composio Ingestion Layer for desktop-dom / Aura.
"""

from .contracts import (
    ConnectedAccountState,
    CanonicalContact,
    CanonicalCalendarEvent,
    CanonicalRepository,
    CanonicalCommunicationSnippet,
)
from .composio_client import ComposioHttpClient
from .normalizer import ComposioNormalizer
from .composio_ingest import ComposioIngest

__all__ = [
    "ConnectedAccountState",
    "CanonicalContact",
    "CanonicalCalendarEvent",
    "CanonicalRepository",
    "CanonicalCommunicationSnippet",
    "ComposioHttpClient",
    "ComposioNormalizer",
    "ComposioIngest",
]
