"""
Unit & Integration Tests for Composio & SaaS External Integrations Layer.
Validates:
1. Canonical Data Contracts (contracts.py)
2. ComposioHttpClient unconfigured & mock response handling (composio_client.py)
3. AuraMemory connected_accounts persistence & provenance-based deletion/privacy guarantees.
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from desktop_dom.assistant.integrations.contracts import (
    ConnectedAccountState,
    CanonicalContact,
    CanonicalCalendarEvent,
    CanonicalRepository,
    CanonicalCommunicationSnippet,
)
from desktop_dom.assistant.integrations.composio_client import ComposioHttpClient
from desktop_dom.assistant.memory import AuraMemory


def test_canonical_contracts_instantiation():
    """Verifies that canonical data models initialize with strict types and default provenance."""
    contact = CanonicalContact(
        id="c1",
        name="Alex Rivera",
        email="alex@example.com",
        role="Product Manager",
        company="Acme Corp",
        aliases=["alex", "arivera"],
        interaction_count=5,
    )
    assert contact.name == "Alex Rivera"
    assert contact.email == "alex@example.com"
    assert contact.provenance == "composio"

    event = CanonicalCalendarEvent(
        id="e1",
        title="Weekly Product Review",
        start_time="2026-09-18T10:00:00Z",
        end_time="2026-09-18T10:45:00Z",
        attendees=[{"name": "Alex Rivera", "email": "alex@example.com"}],
        meeting_url="https://meet.google.com/abc-defg-hij",
    )
    assert event.title == "Weekly Product Review"
    assert event.meeting_url == "https://meet.google.com/abc-defg-hij"
    assert event.provenance == "composio:googlecalendar"

    repo = CanonicalRepository(
        id="r1",
        name="desktop-dom",
        full_name="PDgit12/desktop-dom",
        owner="PDgit12",
        html_url="https://github.com/PDgit12/desktop-dom",
        open_prs_count=2,
    )
    assert repo.full_name == "PDgit12/desktop-dom"
    assert repo.provenance == "composio:github"

    msg = CanonicalCommunicationSnippet(
        id="m1",
        channel_or_subject="Sprint Planning Followup",
        sender_name="Alex Rivera",
        sender_email="alex@example.com",
        snippet="Thanks for the update on the release schedule.",
        app="gmail",
    )
    assert msg.app == "gmail"


def test_composio_client_unconfigured_graceful_degradation():
    """Verifies that ComposioHttpClient gracefully degrades when COMPOSIO_API_KEY is unset."""
    client = ComposioHttpClient(api_key="")
    assert not client.is_configured()

    # Connection initiation fails gracefully with status FAILED instead of raising
    state = client.initiate_connection("googlecalendar", entity_id="test_user")
    assert state.status == "FAILED"
    assert "COMPOSIO_API_KEY" in (state.error_message or "")

    # Status query fails gracefully
    st = client.get_connection_status("ca_invalid")
    assert st.status == "FAILED"

    # List returns empty
    conns = client.list_connections("test_user")
    assert conns == []

    # Disconnect returns False
    assert not client.disconnect_account("ca_invalid")

    # Read action returns error dict
    act = client.execute_read_action("GOOGLECALENDAR_FIND_EVENTS", entity_id="test_user")
    assert act.get("status") == "error"
    assert act.get("code") == "UNCONFIGURED"


def test_composio_client_mock_oauth_flow():
    """Verifies ComposioHttpClient request formatting and response parsing with simulated API."""
    client = ComposioHttpClient(api_key="test_key_xyz123")
    assert client.is_configured()

    # 1. Test initiate_connection
    mock_init_resp = {
        "connectedAccountId": "ca_999",
        "redirectUrl": "https://auth.composio.dev/connect/googlecalendar/xyz",
        "status": "INITIATING",
    }
    with patch.object(client, "_request", return_value=mock_init_resp) as mock_req:
        res = client.initiate_connection("googlecalendar", entity_id="piyush@crcle.ai")
        mock_req.assert_called_once()
        assert res.app == "googlecalendar"
        assert res.status == "AWAITING_USER_AUTH"
        assert res.account_id == "ca_999"
        assert "auth.composio.dev" in res.auth_url

    # 2. Test get_connection_status when ACTIVE
    mock_status_resp = {
        "appName": "googlecalendar",
        "status": "ACTIVE",
        "userIdentifier": "piyush@crcle.ai",
    }
    with patch.object(client, "_request", return_value=mock_status_resp):
        res = client.get_connection_status("ca_999")
        assert res.status == "ACTIVE"
        assert res.user_identifier == "piyush@crcle.ai"
        assert res.last_synced is not None

    # 3. Test list_connections
    mock_list_resp = {
        "items": [
            {"appName": "googlecalendar", "status": "ACTIVE", "connectedAccountId": "ca_999"},
            {"appName": "github", "status": "ACTIVE", "connectedAccountId": "ca_888"},
        ]
    }
    with patch.object(client, "_request", return_value=mock_list_resp):
        conns = client.list_connections("piyush@crcle.ai")
        assert len(conns) == 2
        assert conns[0].app == "googlecalendar"
        assert conns[1].app == "github"

    # 4. Test disconnect_account
    with patch.object(client, "_request", return_value={"status": "success"}):
        ok = client.disconnect_account("ca_999")
        assert ok is True


def test_auramemory_connected_accounts_persistence_and_purge(tmp_path):
    """Verifies that connected account states and provenance-tagged data persist in SQLite and support purge."""
    with AuraMemory(tmp_path / "composio_memory.db") as mem:
        # Upsert accounts using canonical schema
        mem.upsert_connected_account({
            "provider": "composio",
            "user_id": "piyush@crcle.ai",
            "toolkit": "googlecalendar",
            "auth_config_id": "auth_cal_1",
            "external_id": "ca_cal_1",
            "status": "ACTIVE",
            "data_scopes": ["calendar.readonly"],
            "metadata": {"account_email": "piyush@crcle.ai"},
        })
        mem.upsert_connected_account({
            "provider": "composio",
            "user_id": "piyush@crcle.ai",
            "toolkit": "github",
            "auth_config_id": "auth_gh_1",
            "external_id": "ca_gh_1",
            "status": "PENDING",
            "data_scopes": ["repo", "read:user"],
        })

        # Retrieve by toolkit and user_id
        cal = mem.get_connected_account(toolkit="googlecalendar", user_id="piyush@crcle.ai")
        assert cal is not None
        assert cal["status"] == "ACTIVE"
        assert cal["external_id"] == "ca_cal_1"
        assert "calendar.readonly" in cal["data_scopes"]

        gh = mem.get_connected_account(toolkit="github", user_id="piyush@crcle.ai")
        assert gh is not None
        assert gh["status"] == "PENDING"

        # List
        all_accounts = mem.list_connected_accounts(user_id="piyush@crcle.ai")
        toolkits = [a["toolkit"] for a in all_accounts]
        assert "googlecalendar" in toolkits
        assert "github" in toolkits

        # Add entities with provenance
        ent = mem.add_entity(
            name="External Client",
            email="client@partner.com",
            metadata={"provenance": "composio:googlecalendar"},
        )
        eid = ent["id"]
        assert eid > 0
        mem.add_edge("Piyush Dua", "External Client", "meets_with", metadata={"provenance": "composio:googlecalendar"})

        # Verify entity exists
        found = mem.get_entity(eid)
        assert found is not None
        assert found["name"] == "External Client"

        # Privacy purge: Purge data originating from googlecalendar
        purge_res = mem.purge_provenance_data("composio:googlecalendar")
        assert purge_res["purged_entities"] >= 1
        assert purge_res["purged_edges"] >= 1

        # Verify purged entity is gone while standard user entities remain
        assert mem.get_entity(eid) is None
        assert mem.resolve_entity("Piyush Dua") is not None

        # Revoke connected account
        revoked = mem.revoke_connected_account("ca_cal_1")
        assert revoked["status"] == "REVOKED"
        assert revoked["revoked_at"] is not None
