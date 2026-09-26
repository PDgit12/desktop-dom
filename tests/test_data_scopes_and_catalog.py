"""
Unit & Integration Tests for Sovereign Data Scopes and Expanded Integration Catalog.
Verifies:
1. User Data Autonomy: Granular toggleable data scopes (calendar, repos, contacts, notes, media).
2. Pipeline Enforcement: Composio ingestion pipelines strictly honor user data scope choices.
3. Onboarding & Settings Roundtrip: Data scopes persist cleanly across profile and settings updates.
4. Expanded Catalog: Multi-domain categories and toolkit coverage.
5. Omnibar WebKit IPC: Onboarding and Settings script messages persist data_scopes to memory.
"""

import json
import re
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

from desktop_dom.assistant.memory import AuraMemory
from desktop_dom.assistant.integrations.composio_ingest import ComposioIngest
from desktop_dom.assistant.integrations.composio_client import ComposioHttpClient
from desktop_dom.assistant.omnibar import OMNIBAR_HTML, FloatingOmnibar, OmnibarScriptHandler


@pytest.fixture
def clean_memory(tmp_path):
    db_path = str(tmp_path / "test_scopes_aura.db")
    mem = AuraMemory(db_path=db_path)
    return mem


def test_default_data_scopes(clean_memory):
    """Verifies default data scopes are all initialized to True."""
    scopes = clean_memory.get_data_scopes()
    assert isinstance(scopes, dict)
    assert scopes.get("calendar") is True
    assert scopes.get("repos") is True
    assert scopes.get("contacts") is True
    assert scopes.get("notes") is True
    assert scopes.get("media") is True


def test_set_and_query_data_scopes(clean_memory):
    """Verifies granular data scope toggling and querying."""
    # Disable calendar and repos
    updated = clean_memory.set_data_scopes({"calendar": False, "repos": False})
    assert updated.get("calendar") is False
    assert updated.get("repos") is False
    assert updated.get("contacts") is True  # preserved default

    assert clean_memory.is_data_scope_enabled("calendar") is False
    assert clean_memory.is_data_scope_enabled("repos") is False
    assert clean_memory.is_data_scope_enabled("contacts") is True
    assert clean_memory.is_data_scope_enabled("notes") is True
    assert clean_memory.is_data_scope_enabled("media") is True


def test_purge_data_scope(clean_memory):
    """Verifies that disabling and purging a data scope deletes cached data."""
    # Set calendar cache
    clean_memory.set_preference("calendar.events.today", json.dumps([{"title": "Sync"}]), category="calendar")
    clean_memory.set_preference("calendar.last_synced", "123456", category="calendar")

    # Purge calendar scope
    res = clean_memory.purge_data_scope("calendar")
    assert res.get("status") == "success"
    assert res.get("scope") == "calendar"
    assert clean_memory.get_preference("calendar.events.today") == "[]"
    assert clean_memory.get_preference("calendar.last_synced") == "0"


def test_onboarding_saves_and_retrieves_data_scopes(clean_memory):
    """Verifies complete_verified_onboarding and get_verified_onboarding_profile handle data scopes."""
    profile_input = {
        "user_name": "Alice Tester",
        "user_role": "Platform Lead",
        "user_company": "Acme Corp",
        "data_scopes": {
            "calendar": True,
            "repos": True,
            "contacts": False,
            "notes": False,
            "media": True
        }
    }
    result = clean_memory.complete_verified_onboarding(profile_input)
    assert result.get("verified") is True

    retrieved = clean_memory.get_verified_onboarding_profile()
    scopes = retrieved.get("data_scopes", {})
    assert scopes.get("calendar") is True
    assert scopes.get("repos") is True
    assert scopes.get("contacts") is False
    assert scopes.get("notes") is False
    assert scopes.get("media") is True


def test_settings_saves_and_retrieves_data_scopes(clean_memory):
    """Verifies get_user_settings and update_user_settings handle data scopes."""
    settings_update = {
        "user": {"name": "Bob Tester", "role": "Architect", "company": "Matrix Inc"},
        "data_scopes": {
            "calendar": False,
            "repos": True,
            "contacts": True,
            "notes": True,
            "media": False
        }
    }
    clean_memory.update_user_settings(settings_update)

    current_settings = clean_memory.get_user_settings()
    scopes = current_settings.get("data_scopes", {})
    assert scopes.get("calendar") is False
    assert scopes.get("repos") is True
    assert scopes.get("contacts") is True
    assert scopes.get("notes") is True
    assert scopes.get("media") is False


def test_composio_ingest_skips_when_scope_disabled(clean_memory):
    """Verifies Composio ingestion pipelines abort when user has disabled corresponding scope."""
    mock_client = MagicMock(spec=ComposioHttpClient)
    pipeline = ComposioIngest(client=mock_client, memory=clean_memory)

    # 1. Disable calendar scope
    clean_memory.set_data_scopes({"calendar": False})
    cal_res = pipeline.sync_calendar("test_user")
    assert cal_res.get("status") == "skipped"
    assert "disabled" in cal_res.get("reason", "").lower()
    mock_client.execute_read_action.assert_not_called()

    # 2. Disable repos scope
    clean_memory.set_data_scopes({"repos": False})
    repo_res = pipeline.sync_github("test_user")
    assert repo_res.get("status") == "skipped"
    assert "disabled" in repo_res.get("reason", "").lower()
    mock_client.execute_read_action.assert_not_called()

    # 3. Disable contacts scope
    clean_memory.set_data_scopes({"contacts": False})
    gmail_res = pipeline.sync_gmail("test_user")
    assert gmail_res.get("status") == "skipped"
    assert "disabled" in gmail_res.get("reason", "").lower()
    mock_client.execute_read_action.assert_not_called()


def test_catalog_coverage_and_categories():
    """Verifies that the integration catalog in Omnibar HTML spans all core domains with 40+ toolkits."""
    toolkits = re.findall(r'toolkit:\s*"([^"]+)"', OMNIBAR_HTML)
    categories = set(re.findall(r'category:\s*"([^"]+)"', OMNIBAR_HTML))

    assert len(toolkits) >= 40
    expected_categories = {"meetings", "dev", "communication", "productivity", "crm"}
    assert expected_categories.issubset(categories)

    # Check key toolkits exist in catalog
    required = {
        "googlecalendar", "github", "gmail", "slack", "zoom", "linear",
        "jira", "notion", "spotify", "salesforce", "hubspot", "discord"
    }
    assert required.issubset(set(toolkits))


def test_omnibar_webkit_ipc_data_scopes(tmp_path):
    """Verifies FloatingOmnibar and OmnibarScriptHandler persist data_scopes through WebKit IPC."""
    from desktop_dom.assistant.brain import AssistantBrain

    mem = AuraMemory(db_path=str(tmp_path / "omnibar_scopes.db"))
    brain = AssistantBrain(memory=mem)
    bar = FloatingOmnibar(brain=brain)
    bar.evaluate_js = MagicMock()
    handler = OmnibarScriptHandler(bar)

    # 1. Onboarding IPC with custom data scopes
    mock_msg_onb = MagicMock()
    mock_msg_onb.body.return_value = json.dumps({
        "action": "save_onboarding",
        "profile": {
            "user_name": "IPC Tester",
            "data_scopes": {
                "calendar": False,
                "repos": True,
                "contacts": False,
                "notes": True,
                "media": False
            }
        }
    })
    handler.userContentController_didReceiveScriptMessage_(None, mock_msg_onb)

    assert mem.is_data_scope_enabled("calendar") is False
    assert mem.is_data_scope_enabled("repos") is True
    assert mem.is_data_scope_enabled("contacts") is False
    assert mem.is_data_scope_enabled("notes") is True
    assert mem.is_data_scope_enabled("media") is False
    assert "window.auraOnboardingSaved" in bar.evaluate_js.call_args[0][0]

    # 2. Settings IPC updating data scopes
    bar.evaluate_js.reset_mock()
    mock_msg_settings = MagicMock()
    mock_msg_settings.body.return_value = json.dumps({
        "action": "save_settings",
        "settings": {
            "data_scopes": {
                "calendar": True,
                "repos": True,
                "contacts": True,
                "notes": True,
                "media": True
            }
        }
    })
    handler.userContentController_didReceiveScriptMessage_(None, mock_msg_settings)

    assert mem.is_data_scope_enabled("calendar") is True
    assert mem.is_data_scope_enabled("contacts") is True
    assert mem.is_data_scope_enabled("media") is True
    assert "window.auraSettingsSaved" in bar.evaluate_js.call_args[0][0]


def test_get_audit_report_local_storage_and_zero_tokens(clean_memory):
    """Verifies that get_audit_report generates a comprehensive local-only report with zero token violations."""
    report = clean_memory.get_audit_report()
    assert isinstance(report, dict)
    assert report.get("engine") == "Aura Sovereign Local Memory Engine"
    assert "100% Local-First" in report.get("architecture", "")
    assert "PostgreSQL" in report.get("architecture", "")

    db_info = report.get("database", {})
    assert Path(db_info.get("path")).exists()
    assert db_info.get("journal_mode") == "WAL"
    assert db_info.get("foreign_keys") is True
    assert "0o600" in db_info.get("file_permissions", "")

    sec_info = report.get("security_and_privacy", {})
    assert sec_info.get("zero_token_custody_verified") is True
    assert sec_info.get("token_violations_count") == 0
    assert sec_info.get("network_isolated_storage") is True

    record_counts = report.get("record_counts", {})
    assert "entities" in record_counts
    assert "graph_edges" in record_counts
    assert "preferences" in record_counts
    assert "habits" in record_counts


def test_cli_audit_command():
    """Verifies that desktop-dom audit command executes cleanly and prints Rich audit dashboard."""
    from typer.testing import CliRunner
    from desktop_dom.cli.main import app

    runner = CliRunner()
    res = runner.invoke(app, ["audit"])
    assert res.exit_code == 0
    assert "Aura Sovereign Memory & Storage Audit" in res.output
    assert "SQLite 3" in res.output
    assert "No PostgreSQL" in res.output
    assert "Zero-Token Custody Verified" in res.output
    assert "Sovereign Data Scopes Governance" in res.output


def test_cli_audit_json():
    """Verifies that desktop-dom audit --json produces valid JSON audit report."""
    from typer.testing import CliRunner
    from desktop_dom.cli.main import app

    runner = CliRunner()
    res = runner.invoke(app, ["audit", "--json"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data["architecture"] == "100% Local-First Embedded SQLite (Zero PostgreSQL / No External Server)"
    assert data["security_and_privacy"]["zero_token_custody_verified"] is True
    assert data["security_and_privacy"]["token_violations_count"] == 0
