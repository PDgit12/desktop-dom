"""
Unit & Integration Tests for Composio & SaaS External Integrations Layer.
Validates:
1. Canonical Data Contracts (contracts.py)
2. ComposioHttpClient unconfigured & mock response handling (composio_client.py)
3. AuraMemory connected_accounts persistence & provenance-based deletion/privacy guarantees.
"""

import json
import time
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


def test_composio_normalizer_calendar_event():
    """Verifies ComposioNormalizer converts raw Google Calendar payload to CanonicalCalendarEvent and contacts."""
    from desktop_dom.assistant.integrations.normalizer import ComposioNormalizer

    raw_event = {
        "id": "event_gcal_101",
        "summary": "Sprint Sync & Architecture Review",
        "start": {"dateTime": "2026-09-18T10:00:00-04:00"},
        "end": {"dateTime": "2026-09-18T10:45:00-04:00"},
        "hangoutLink": "https://meet.google.com/abc-defg-hij",
        "attendees": [
            {"displayName": "Joshua Rayan", "email": "josh@crcle.ai"},
            {"displayName": "Cyril Rayan", "email": "cyril@crcle.ai"},
        ],
    }

    event, contacts = ComposioNormalizer.normalize_calendar_event(raw_event)
    assert event.id == "event_gcal_101"
    assert event.title == "Sprint Sync & Architecture Review"
    assert event.meeting_url == "https://meet.google.com/abc-defg-hij"
    assert len(contacts) == 2
    assert contacts[0].name == "Joshua Rayan"
    assert contacts[0].email == "josh@crcle.ai"
    assert contacts[0].provenance == "composio:googlecalendar"


def test_composio_normalizer_github_and_gmail():
    """Verifies ComposioNormalizer converts GitHub repos and Gmail messages."""
    from desktop_dom.assistant.integrations.normalizer import ComposioNormalizer

    # GitHub
    raw_repo = {
        "id": 89201,
        "name": "desktop-dom",
        "full_name": "PDgit12/desktop-dom",
        "owner": {"login": "PDgit12"},
        "description": "Semantic Accessibility DOM for AI Agents",
        "default_branch": "main",
        "open_issues_count": 5,
        "html_url": "https://github.com/PDgit12/desktop-dom",
        "language": "Python",
    }
    repo = ComposioNormalizer.normalize_github_repo(raw_repo)
    assert repo.name == "desktop-dom"
    assert repo.owner == "PDgit12"
    assert repo.open_prs_count == 5
    assert repo.languages == ["Python"]
    assert repo.provenance == "composio:github"

    # Gmail
    raw_msg = {
        "id": "msg_999",
        "threadId": "thread_888",
        "headers": {
            "subject": "Q3 Roadmap Alignment",
            "from": "Cyril Rayan <cyril@crcle.ai>",
            "to": "Piyush Dua <piyush@crcle.ai>",
        },
        "snippet": "Let's review the new Composio onboarding architecture tomorrow.",
        "internalDate": 1726700000.0,
    }
    comm, contacts = ComposioNormalizer.normalize_gmail_message(raw_msg)
    assert comm.channel_or_subject == "Q3 Roadmap Alignment"
    assert comm.sender_name == "Cyril Rayan"
    assert comm.sender_email == "cyril@crcle.ai"
    assert "review the new Composio" in comm.snippet
    assert len(contacts) == 2  # sender + recipient


def test_composio_ingest_pipeline_end_to_end():
    """Verifies ComposioIngest synchronizes calendar, repos, and contacts into AuraMemory with privacy purge."""
    from desktop_dom.assistant.integrations.composio_ingest import ComposioIngest

    with AuraMemory() as mem:
        mock_client = MagicMock()
        mock_client.is_configured.return_value = True

        # Mock calendar read
        mock_client.execute_read_action.side_effect = [
            # 1. Calendar
            {
                "status": "success",
                "data": {
                    "items": [
                        {
                            "id": "evt_synced_1",
                            "summary": "Design Sync",
                            "start": {"dateTime": "2026-09-18T14:00:00Z"},
                            "end": {"dateTime": "2026-09-18T14:30:00Z"},
                            "hangoutLink": "https://meet.google.com/synced-meet",
                            "attendees": [{"displayName": "Hannah Vance", "email": "hannah.vance@crcle.ai"}],
                        }
                    ]
                },
            },
            # 2. GitHub
            {
                "status": "success",
                "data": [
                    {
                        "id": 12345,
                        "name": "aura-core",
                        "full_name": "CrcleAI/aura-core",
                        "owner": {"login": "CrcleAI"},
                        "html_url": "https://github.com/CrcleAI/aura-core",
                        "open_issues_count": 3,
                    }
                ],
            },
        ]

        ingest = ComposioIngest(memory=mem, client=mock_client)

        # 1. Sync Calendar
        cal_res = ingest.sync_calendar(user_id="piyush@crcle.ai")
        assert cal_res["status"] == "success"
        assert cal_res["synced_events"] == 1
        assert cal_res["synced_contacts"] == 1

        # Verify Hannah Vance attendee added to Knowledge Graph
        hannah = mem.resolve_entity("Hannah Vance")
        assert hannah is not None
        assert hannah["email"] == "hannah.vance@crcle.ai"

        # 2. Sync GitHub
        gh_res = ingest.sync_github(user_id="piyush@crcle.ai")
        assert gh_res["status"] == "success"
        assert gh_res["synced_repos"] == 1

        # Verify repo entity in memory
        repo = mem.resolve_entity("aura-core")
        assert repo is not None
        assert repo["category"] == "project"

        # 3. Disconnect and Purge GitHub data
        mock_client.disconnect_account.return_value = True
        mem.upsert_connected_account({
            "provider": "composio",
            "user_id": "piyush@crcle.ai",
            "toolkit": "github",
            "auth_config_id": "auth_123",
            "external_id": "ca_gh_123",
            "status": "ACTIVE",
            "data_scopes": ["repo"],
        })

        purge_result = ingest.disconnect_and_purge("github", user_id="piyush@crcle.ai")
        assert purge_result["toolkit"] == "github"
        assert purge_result["purged_entities"] >= 1

        # Verify aura-core is purged, while Hannah Vance from calendar remains
        assert mem.resolve_entity("aura-core") is None
        assert mem.resolve_entity("Hannah Vance") is not None


def test_brain_composio_connect_and_status(tmp_path):
    """Verifies that AssistantBrain coordinates Composio connections and status queries."""
    from desktop_dom.assistant.brain import AssistantBrain

    mem = AuraMemory(db_path=str(tmp_path / "brain_composio.db"))
    brain = AssistantBrain(memory=mem)

    # Mock client connection response
    mock_connect_res = {
        "status": "INITIATED",
        "connection_id": "ca_test_gcal_99",
        "redirect_url": "https://connect.composio.dev/auth/mock-gcal",
    }
    with patch.object(brain.composio_ingest.client, "initiate_connection", return_value=mock_connect_res):
        res = brain.connect_composio_app("googlecalendar")
        assert res["status"] == "INITIATED"
        assert res["redirect_url"] == "https://connect.composio.dev/auth/mock-gcal"

    # Verify status reflects PENDING
    status = brain.get_composio_status()
    assert "googlecalendar" in status["accounts"]
    assert status["accounts"]["googlecalendar"]["status"] == "PENDING"

    # Simulate connection becoming ACTIVE
    mem.update_connected_account("ca_test_gcal_99", status="ACTIVE")
    status_active = brain.get_composio_status()
    assert status_active["accounts"]["googlecalendar"]["connected"] is True
    assert status_active["accounts"]["googlecalendar"]["status"] == "ACTIVE"

    # Disconnect & Purge
    with patch.object(brain.composio_ingest.client, "disconnect_account", return_value=True):
        disc_res = brain.disconnect_composio_app("googlecalendar")
        assert disc_res["toolkit"] == "googlecalendar"

    status_revoked = brain.get_composio_status()
    assert status_revoked["accounts"]["googlecalendar"]["connected"] is False


def test_omnibar_webkit_composio_bridge(tmp_path):
    """Verifies Omnibar WebKit IPC script handlers dispatch Composio actions with JS updates."""
    from desktop_dom.assistant.brain import AssistantBrain
    from desktop_dom.assistant.omnibar import FloatingOmnibar, OmnibarScriptHandler

    mem = AuraMemory(db_path=str(tmp_path / "omnibar_composio.db"))
    brain = AssistantBrain(memory=mem)

    # Initialize FloatingOmnibar
    bar = FloatingOmnibar(brain=brain)
    bar._webview = MagicMock()
    handler = OmnibarScriptHandler(bar)

    # 1. Test get_composio_status action
    mock_msg_status = MagicMock()
    mock_msg_status.body.return_value = json.dumps({"action": "get_composio_status"})
    bar._webview.reset_mock()
    handler.userContentController_didReceiveScriptMessage_(None, mock_msg_status)
    assert "window.renderComposioStatuses" in bar._webview.evaluateJavaScript_completionHandler_.call_args[0][0]

    # 2. Test connect_composio_app action
    mock_connect_res = {
        "status": "INITIATED",
        "connection_id": "ca_ipc_123",
        "redirect_url": "https://connect.composio.dev/test-link",
    }
    mock_msg_connect = MagicMock()
    mock_msg_connect.body.return_value = json.dumps({
        "action": "connect_composio_app",
        "toolkit": "github",
    })
    with patch.object(brain.composio_ingest.client, "initiate_connection", return_value=mock_connect_res), \
         patch("webbrowser.open") as mock_browser:
        bar._webview.reset_mock()
        handler.userContentController_didReceiveScriptMessage_(None, mock_msg_connect)
        assert mock_browser.called
        assert "window.updateComposioCardStatus('github'" in bar._webview.evaluateJavaScript_completionHandler_.call_args[0][0]

    # 3. Test disconnect_composio_app action
    mock_msg_disc = MagicMock()
    mock_msg_disc.body.return_value = json.dumps({
        "action": "disconnect_composio_app",
        "toolkit": "github",
    })
    with patch.object(brain.composio_ingest.client, "disconnect_account", return_value=True):
        bar._webview.reset_mock()
        handler.userContentController_didReceiveScriptMessage_(None, mock_msg_disc)
        assert "window.updateComposioCardStatus('github', 'DISCONNECTED'" in bar._webview.evaluateJavaScript_completionHandler_.call_args[0][0]


def test_calendar_briefing_canonical_routing(tmp_path):
    """Verifies get_calendar_briefing retrieves and formats cached canonical Composio events."""
    from desktop_dom.assistant.non_binary import get_calendar_briefing

    mem = AuraMemory(db_path=str(tmp_path / "calendar_routing.db"))
    events = [
        {
            "id": "e_today_1",
            "title": "Architecture & Roadmap Alignment",
            "start_time": "10:00 AM",
            "end_time": "10:45 AM",
            "meeting_url": "https://meet.google.com/xyz-uvwx-rst",
            "attendees": ["Joshua Rayan", "Cyril Rayan"],
        }
    ]
    mem.set_preference("calendar.events.today", json.dumps(events), category="calendar")
    mem.upsert_connected_account({
        "provider": "composio",
        "user_id": "piyush@crcle.ai",
        "toolkit": "googlecalendar",
        "auth_config_id": "ac_gcal",
        "external_id": "ca_gcal_1",
        "status": "ACTIVE",
        "data_scopes": ["calendar.readonly"],
    })

    briefing = get_calendar_briefing(memory=mem)
    assert briefing["status"] == "success"
    assert briefing["client"] == "Google Calendar (Composio)"
    assert briefing["tier"] == "canonical_composio"
    assert briefing["event_count"] == 1
    assert "https://meet.google.com/xyz-uvwx-rst" in briefing["response"]
    assert "Joshua Rayan" in briefing["response"]


def test_meeting_intent_enriches_with_canonical_meeting_url(tmp_path):
    """Verifies meeting intent extracts meeting URL from canonical calendar events."""
    from desktop_dom.assistant.brain import AssistantBrain

    mem = AuraMemory(db_path=str(tmp_path / "meeting_enrich.db"))
    events = [
        {
            "id": "e_today_2",
            "title": "Design Sync with Hannah",
            "start_time": "2:00 PM",
            "end_time": "2:30 PM",
            "meeting_url": "https://zoom.us/j/9988776655",
            "attendees": ["Hannah Vance"],
        }
    ]
    mem.set_preference("calendar.events.today", json.dumps(events), category="calendar")
    mem.set_preference("apps.primary_meeting", "Granola", category="apps")
    mem.add_entity(name="Hannah Vance", category="contact", company="Crcle.ai")

    brain = AssistantBrain(memory=mem)
    res = brain.execute_intent("i have a meeting with Hannah")

    assert res["status"] == "success"
    assert res["action"] == "meeting_intent"
    assert res.get("meeting_url") == "https://zoom.us/j/9988776655"
    assert "https://zoom.us/j/9988776655" in res["response"]


def test_composio_write_actions_github_calendar_email_slack(tmp_path):
    """Verifies that Composio write actions execute successfully when accounts are connected."""
    from desktop_dom.assistant.brain import AssistantBrain
    from desktop_dom.assistant.integrations.composio_ingest import ComposioIngest

    mem = AuraMemory(db_path=str(tmp_path / "write_actions.db"))
    mock_client = MagicMock()
    mock_client.is_configured.return_value = True

    ingest = ComposioIngest(memory=mem, client=mock_client)

    # 1. GitHub Issue when unconnected
    res_unconn = ingest.create_github_issue("desktop-dom", "Fix hover", user_id="piyush@crcle.ai")
    assert res_unconn["status"] == "unconnected"

    # Connect GitHub
    mem.upsert_connected_account({
        "provider": "composio",
        "user_id": "piyush@crcle.ai",
        "toolkit": "github",
        "auth_config_id": "ac_github",
        "status": "ACTIVE",
        "data_scopes": ["repo"],
    })

    mock_client.execute_action.return_value = {
        "status": "success",
        "data": {
            "number": 42,
            "html_url": "https://github.com/PDgit12/desktop-dom/issues/42",
        },
    }

    res_issue = ingest.create_github_issue("desktop-dom", "Fix hover bug", user_id="piyush@crcle.ai")
    assert res_issue["status"] == "success"
    assert res_issue["number"] == 42
    assert "https://github.com/PDgit12/desktop-dom/issues/42" in res_issue["response"]

    # 2. Google Calendar Event Creation
    mem.upsert_connected_account({
        "provider": "composio",
        "user_id": "piyush@crcle.ai",
        "toolkit": "googlecalendar",
        "auth_config_id": "ac_googlecalendar",
        "status": "ACTIVE",
        "data_scopes": ["calendar"],
    })
    mock_client.execute_action.return_value = {
        "status": "success",
        "data": {
            "hangoutLink": "https://meet.google.com/test-meet-123",
        },
    }
    res_cal = ingest.create_calendar_event(
        title="Sync with Joshua",
        start_time="2026-09-19T14:00:00Z",
        attendees=["josh@crcle.ai"],
        user_id="piyush@crcle.ai",
    )
    assert res_cal["status"] == "success"
    assert res_cal["meeting_url"] == "https://meet.google.com/test-meet-123"

    # 3. Gmail Draft Creation
    mem.upsert_connected_account({
        "provider": "composio",
        "user_id": "piyush@crcle.ai",
        "toolkit": "gmail",
        "auth_config_id": "ac_gmail",
        "status": "ACTIVE",
        "data_scopes": ["gmail.compose"],
    })
    mock_client.execute_action.return_value = {
        "status": "success",
        "data": {"id": "draft_999"},
    }
    res_draft = ingest.create_email_draft(
        to="josh@crcle.ai",
        subject="Sprint Alignment",
        body="All tests passing.",
        user_id="piyush@crcle.ai",
    )
    assert res_draft["status"] == "success"
    assert res_draft["to"] == "josh@crcle.ai"

    # 4. Slack Message
    mem.upsert_connected_account({
        "provider": "composio",
        "user_id": "piyush@crcle.ai",
        "toolkit": "slack",
        "auth_config_id": "ac_slack",
        "status": "ACTIVE",
        "data_scopes": ["chat:write"],
    })

    mock_client.execute_action.return_value = {
        "status": "success",
        "data": {"ok": True},
    }
    res_slack = ingest.send_slack_message(
        channel="#general",
        text="Build succeeded",
        user_id="piyush@crcle.ai",
    )
    assert res_slack["status"] == "success"


def test_brain_write_intent_routing(tmp_path):
    """Verifies that execute_intent routes GitHub issue, Calendar booking, and project switching."""
    from desktop_dom.assistant.brain import AssistantBrain

    mem = AuraMemory(db_path=str(tmp_path / "brain_write.db"))
    brain = AssistantBrain(memory=mem)

    # 1. Project Switcher Intent
    res_proj = brain.execute_intent("switch project to desktop-dom")
    assert res_proj["status"] == "success"
    assert res_proj["project"] == "desktop-dom"
    assert mem.get_preference("workspace.active_project") == "desktop-dom"

    # 2. GitHub issue creation unconfigured fallback
    res_gh = brain.execute_intent("create issue on desktop-dom: Fix hover padding")
    assert res_gh["action"] == "create_github_issue"
    assert res_gh["status"] == "unconfigured"
    assert "connect GitHub in Settings" in res_gh["response"]

    # 3. Calendar event scheduling unconfigured fallback
    res_sched = brain.execute_intent("schedule meeting with Cyril tomorrow at 3pm")
    assert res_sched["action"] == "create_calendar_event"
    assert res_sched["status"] == "unconfigured"
    assert "connect Google Calendar in Settings" in res_sched["response"]


def test_omnibar_project_and_key_bridge(tmp_path):
    """Verifies Omnibar WebKit IPC script handlers dispatch project switching and API key saving."""
    from desktop_dom.assistant.brain import AssistantBrain
    from desktop_dom.assistant.omnibar import FloatingOmnibar, OmnibarScriptHandler

    mem = AuraMemory(db_path=str(tmp_path / "omnibar_bridge.db"))
    brain = AssistantBrain(memory=mem)

    bar = FloatingOmnibar(brain=brain)
    bar._webview = MagicMock()
    handler = OmnibarScriptHandler(bar)

    # 1. Save Composio API key
    msg_key = MagicMock()
    msg_key.body.return_value = json.dumps({
        "action": "save_composio_api_key",
        "api_key": "comp_live_test_key_12345",
    })
    handler.userContentController_didReceiveScriptMessage_(None, msg_key)
    assert mem.get_preference("composio.api_key") == "comp_live_test_key_12345"

    # 2. Switch Project
    msg_proj = MagicMock()
    msg_proj.body.return_value = json.dumps({
        "action": "switch_project",
        "project": "Aura-Kernel",
    })
    bar._webview.reset_mock()
    handler.userContentController_didReceiveScriptMessage_(None, msg_proj)
    assert mem.get_preference("workspace.active_project") == "Aura-Kernel"
    assert "window.updateActiveProject('Aura-Kernel')" in bar._webview.evaluateJavaScript_completionHandler_.call_args[0][0]

    # 3. Get Projects
    msg_get_proj = MagicMock()
    msg_get_proj.body.return_value = json.dumps({"action": "get_projects"})
    bar._webview.reset_mock()
    handler.userContentController_didReceiveScriptMessage_(None, msg_get_proj)
    assert "window.renderProjectList('Aura-Kernel'" in bar._webview.evaluateJavaScript_completionHandler_.call_args[0][0]


def test_composio_auto_polling_background_thread(tmp_path):
    """Verifies that the background auto-polling loop detects ACTIVE connection and triggers UI sync."""
    from desktop_dom.assistant.brain import AssistantBrain
    from desktop_dom.assistant.integrations.contracts import ConnectedAccountState
    from desktop_dom.assistant.omnibar import FloatingOmnibar

    mem = AuraMemory(db_path=str(tmp_path / "polling_test.db"))
    brain = AssistantBrain(memory=mem)

    # Pre-populate pending account
    mem.upsert_connected_account({
        "provider": "composio",
        "user_id": "piyush@crcle.ai",
        "toolkit": "googlecalendar",
        "auth_config_id": "ac_gcal",
        "external_id": "ca_poll_123",
        "status": "PENDING",
        "data_scopes": ["calendar.readonly"],
    })

    bar = FloatingOmnibar(brain=brain)
    bar._webview = MagicMock()

    # Mock client connection status returning ACTIVE
    mock_active_state = ConnectedAccountState(
        app="googlecalendar",
        status="ACTIVE",
        account_id="ca_poll_123",
        user_identifier="piyush@crcle.ai",
    )

    with patch.object(brain.composio_ingest.client, "get_connection_status", return_value=mock_active_state), \
         patch.object(brain, "sync_composio_app") as mock_sync, \
         patch("time.sleep"):
        # Run polling
        t = bar._start_composio_polling("googlecalendar", "ca_poll_123")
        if t:
            t.join(timeout=1.0)

        acc = mem.get_connected_account(toolkit="googlecalendar", user_id="piyush@crcle.ai")
        assert acc is not None
        assert acc["status"] == "ACTIVE"
        all_js_calls = [c[0][0] for c in bar._webview.evaluateJavaScript_completionHandler_.call_args_list]
        assert any("window.updateComposioCardStatus('googlecalendar', 'ACTIVE'" in js for js in all_js_calls)
        assert any("window.renderComposioStatuses" in js for js in all_js_calls)


def test_connect_composio_app_awaiting_user_auth_flow(tmp_path):
    """Verifies that initiate_connection returning AWAITING_USER_AUTH saves PENDING state and opens browser."""
    from desktop_dom.assistant.brain import AssistantBrain
    from desktop_dom.assistant.omnibar import FloatingOmnibar

    mem = AuraMemory(db_path=str(tmp_path / "brain_awaiting_auth.db"))
    brain = AssistantBrain(memory=mem)

    # Return ConnectedAccountState with status AWAITING_USER_AUTH
    mock_state = ConnectedAccountState(
        app="github",
        status="AWAITING_USER_AUTH",
        account_id="ca_awaiting_456",
        auth_url="https://connect.composio.dev/link/lk_test_github",
    )

    with patch.object(brain.composio_ingest.client, "initiate_connection", return_value=mock_state):
        res = brain.connect_composio_app("github")
        assert res["status"] == "AWAITING_USER_AUTH"
        assert res["redirect_url"] == "https://connect.composio.dev/link/lk_test_github"
        assert res["connection_id"] == "ca_awaiting_456"

    # Verify that account is saved in SQLite memory as PENDING
    acc = mem.get_connected_account(toolkit="github")
    assert acc is not None
    assert acc["status"] == "PENDING"
    assert acc["external_id"] == "ca_awaiting_456"
    assert acc["redirect_url"] == "https://connect.composio.dev/link/lk_test_github"

    # Test Omnibar on_connect_composio_app with this state
    bar = FloatingOmnibar(brain=brain)
    bar._webview = MagicMock()

    with patch.object(brain, "connect_composio_app", return_value=res), \
         patch("webbrowser.open") as mock_browser, \
         patch.object(bar, "_start_composio_polling") as mock_poll:
        bar.on_connect_composio_app("github")
        mock_browser.assert_called_once_with("https://connect.composio.dev/link/lk_test_github")
        mock_poll.assert_called_once_with("github", "ca_awaiting_456")
        all_js = [c[0][0] for c in bar._webview.evaluateJavaScript_completionHandler_.call_args_list]
        assert any("window.updateComposioCardStatus('github', 'AWAITING_USER_AUTH'" in js for js in all_js)







