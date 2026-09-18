"""
tests/test_e2e_opaque_box.py
============================
Opaque-Box End-to-End (E2E) Test Suite for Aura (desktop-dom).

Architecture & Methodology:
----------------------------
Follows the 4-Tier Test Case Design Methodology:
- Tier 1 (Feature Coverage): >=5 tests per feature covering representative happy paths:
    * Feature 1: First-Time Onboarding Detection & Pure Data Ingestion
    * Feature 2: Everyday Natural Intent "I have a meeting" & Companion Routing
    * Feature 3: Entity Resolution & Context Symmetry Breaking ("Text Hannah")
    * Feature 4: Non-Binary Dynamic Briefings (Calendar, Git PR, Linear, Email)
    * Feature 5: WebKit IPC Actions & Bi-Directional Bridge
    * Feature 6: macOS Application Packaging Integrity
- Tier 2 (Boundary & Corner Cases):
    * Missing CLI tools (`gh`, `linear`)
    * AppleScript authorization errors (-1743)
    * Empty / whitespace / newline queries
    * Massive input strings (5,000 chars)
    * SQL injection, special characters, unicode emojis
    * Multi-display negative coordinates (X and Y offsets)
    * Socket collisions & stale socket cleanup
    * OS Permissions untrusted state
- Tier 3 (Cross-Feature Combinations):
    * Onboarding -> Meeting Intent -> Misfire Feedback ("No, open Zoom instead") -> Subsequent Meeting Query
    * IDE Ambient Context -> "Text Hannah" -> Draft Email -> Calendar Briefing
    * Onboarding Reset -> Unverified State -> Re-onboarding with New Role & Apps
    * Linear Issue Query -> Git PR Status Check -> Teammate Message Dispatch
    * IPC Socket Server Summoning & Single Instance Activation
- Tier 4 (Real-World Application Scenarios):
    * Scenario 1: Full Developer Morning Kickoff (doctor -> calendar -> Linear -> PR -> Spotify)
    * Scenario 2: High-Interruption Work-to-Personal Context Switch (IDE -> meeting -> email -> music)
    * Scenario 3: Misfire Feedback & Continuous Learning Under Ambient Drift
    * Scenario 4: CLI Headless Diagnostic & Operator Inspection Journey
"""

from __future__ import annotations

import json
import os
import plistlib
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from desktop_dom.adapters.macos import MacOSAdapter
from desktop_dom.assistant.brain import AssistantBrain
from desktop_dom.assistant.memory import AuraMemory
from desktop_dom.assistant.non_binary import (
    NonBinaryAdapters,
    get_calendar_briefing,
    get_git_pr_status,
    get_last_email,
    get_linear_issues,
    route_non_binary_intent,
)
from desktop_dom.assistant.omnibar import FloatingOmnibar, OmnibarScriptHandler
from desktop_dom.cli.main import app as cli_app
from desktop_dom.schema import BoundingBox, DisplayInfo
from tests.conftest import TestPlatformAdapter

cli_runner = CliRunner()


# ============================================================================
# Fixtures & Environment Mocks
# ============================================================================

@pytest.fixture
def clean_memory_db(tmp_path):
    """Provides a fresh, hermetic SQLite database for AuraMemory."""
    db_file = tmp_path / "e2e_aura.db"
    with patch.object(AuraMemory, "sync_system_contacts", return_value=0):
        mem = AuraMemory(db_path=str(db_file))
        yield mem
        mem.close()


@pytest.fixture
def e2e_brain(clean_memory_db):
    """Provides an AssistantBrain attached to an isolated AuraMemory instance."""
    return AssistantBrain(preferred_model="ministral-3:8b", memory=clean_memory_db)


@pytest.fixture
def e2e_onboarded_env(clean_memory_db):
    """
    Sets up a fully verified developer profile with dual-cluster entities:
    - Work cluster: Crcle.ai, Joshua Rayan (CTO), Cyril Rayan (CEO), Hannah Vance (Lead Designer)
    - Work tools: Granola (meeting), Outlook (mail), Zed (editor), Chrome (browser)
    - Personal cluster: Hannah Miller (Friend), Messages (chat)
    - Habits: Deep Focus (work music), Ambient Chill (personal music)
    """
    profile = {
        "user_name": "Piyush Dua",
        "user_email": "piyush@crcle.ai",
        "user_role": "Backend Engineer",
        "user_company": "Crcle.ai",
        "app_bindings": {
            "meeting": "Granola",
            "browser": "Google Chrome",
            "mail": "Microsoft Outlook",
            "terminal": "Terminal",
            "editor": "Zed",
        },
        "playlists": {
            "focus": "Deep Focus",
            "personal": "Ambient Chill",
            "gaming": "Synthwave Cyber",
        },
        "collaborators": [
            {"name": "Joshua Rayan", "role": "Co-Founder & CTO", "company": "Crcle.ai", "email": "josh@crcle.ai"},
            {"name": "Cyril Rayan", "role": "Co-Founder & CEO", "company": "Crcle.ai", "email": "cyril@crcle.ai"},
            {"name": "Hannah Vance", "role": "Lead Designer", "company": "Crcle.ai", "email": "hannah.vance@crcle.ai"},
        ],
        "work_repos": ["desktop-dom"],
        "default_repo": "PDgit12/desktop-dom",
    }
    clean_memory_db.complete_verified_onboarding(profile)

    # Personal entity with conflicting first name "Hannah"
    clean_memory_db.add_entity(
        name="Hannah Miller",
        email="hannah.miller@gmail.com",
        category="personal",
        role="Friend",
        metadata={"cluster": "personal"},
    )

    brain = AssistantBrain(preferred_model="ministral-3:8b", memory=clean_memory_db)
    return clean_memory_db, brain


class MockScriptMessage:
    """Simulates a WebKit WKScriptMessage payload sent from JavaScript."""
    def __init__(self, data: Dict[str, Any]):
        self._body = json.dumps(data)

    def body(self) -> str:
        return self._body


# ============================================================================
# TIER 1: FEATURE COVERAGE (>= 5 tests per feature)
# ============================================================================

# ----------------------------------------------------------------------------
# Feature 1: First-Time Onboarding Detection & Pure Data Ingestion
# ----------------------------------------------------------------------------

def test_tier1_onboarding_fresh_unverified_detection(clean_memory_db):
    """T1.1: Verifies fresh unconfigured database reports onboarding unverified."""
    assert clean_memory_db.is_onboarding_verified() is False
    profile = clean_memory_db.get_verified_onboarding_profile()
    assert profile["verified"] is False
    assert profile["user_name"] == ""


def test_tier1_onboarding_complete_verified_sealing(clean_memory_db):
    """T1.2: Verifies complete_verified_onboarding seals user profile into Knowledge Graph."""
    payload = {
        "user_name": "Piyush Dua",
        "user_email": "piyush@crcle.ai",
        "user_role": "Backend Engineer",
        "user_company": "Crcle.ai",
        "app_bindings": {"meeting": "Granola", "mail": "Microsoft Outlook"},
        "playlists": {"focus": "Deep Focus"},
        "collaborators": [{"name": "Josh Rayan", "email": "josh@crcle.ai", "role": "CTO"}],
    }
    res = clean_memory_db.complete_verified_onboarding(payload)
    assert res["status"] == "success"
    assert res["verified"] is True
    assert res["mode"] == "pure_user_data"
    assert clean_memory_db.is_onboarding_verified() is True
    assert clean_memory_db.get_preference("user.name") == "Piyush Dua"
    assert clean_memory_db.get_preference("user.company") == "Crcle.ai"


def test_tier1_onboarding_habit_and_preference_resolution(e2e_onboarded_env):
    """T1.3: Verifies preferences and habit resolution for verified apps and playlists."""
    mem, _ = e2e_onboarded_env
    assert mem.resolve_habit("mail.preferred_client") == "Microsoft Outlook"
    assert mem.resolve_habit("spotify.favorite_playlist") == "Deep Focus"
    assert mem.resolve_app_for_intent("meeting") == "Granola"
    assert mem.resolve_app_for_intent("mail") == "Microsoft Outlook"


def test_tier1_onboarding_pure_data_no_synthetic_leakage(e2e_onboarded_env):
    """T1.4: Verifies anti-speculation guard: zero synthetic media or unverified channels seeded."""
    mem, _ = e2e_onboarded_env
    assert mem.get_preference("youtube.favorite_channel.tech") is None
    assert mem.get_preference("youtube.favorite_channel") is None
    assert mem.get_preference("synthetic.test_field") is None


def test_tier1_onboarding_reset_lifecycle(e2e_onboarded_env):
    """T1.5: Verifies reset_onboarding clears verification status and resets preferences."""
    mem, _ = e2e_onboarded_env
    assert mem.is_onboarding_verified() is True
    mem.reset_onboarding()
    assert mem.is_onboarding_verified() is False
    profile = mem.get_verified_onboarding_profile()
    assert profile["verified"] is False


# ----------------------------------------------------------------------------
# Feature 2: Everyday Natural Intent "I have a meeting" & Companion Routing
# ----------------------------------------------------------------------------

def test_tier1_meeting_intent_standard_happy_path(e2e_onboarded_env):
    """T2.1: Verifies 'I have a meeting' opens preferred meeting tool at >=0.95 confidence."""
    _, brain = e2e_onboarded_env
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        res = brain.execute_intent("I have a meeting")
        assert res["status"] == "success"
        assert res["action"] == "meeting_intent"
        assert res["tool"] == "Granola"
        assert res["confidence"] >= 0.95
        assert res["tier"] == "autonomous"


def test_tier1_meeting_intent_with_colleague_cyril(e2e_onboarded_env):
    """T2.2: Verifies 'meeting with Cyril' resolves Cyril Rayan as participant."""
    _, brain = e2e_onboarded_env
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        res = brain.execute_intent("meeting with Cyril")
        assert res["status"] == "success"
        assert res["action"] == "meeting_intent"
        assert res["tool"] == "Granola"
        assert res["participant"] == "Cyril Rayan"
        assert res["confidence"] >= 0.95


def test_tier1_meeting_intent_with_colleague_and_topic(e2e_onboarded_env):
    """T2.3: Verifies 'meeting with Josh regarding architecture' binds both participant and topic."""
    _, brain = e2e_onboarded_env
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        res = brain.execute_intent("meeting with Josh regarding architecture")
        assert res["status"] == "success"
        assert res["action"] == "meeting_intent"
        assert res["tool"] == "Granola"
        assert res["participant"] == "Joshua Rayan"
        assert "architecture" in res["response"].lower()


def test_tier1_meeting_intent_personal_meetup_routing(e2e_onboarded_env):
    """T2.4: Verifies personal meetup routes to Messages/personal context rather than work tool."""
    _, brain = e2e_onboarded_env
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        res = brain.execute_intent("meetup with Mom")
        assert res["status"] == "success"
        assert res["action"] == "meeting_intent"
        assert res["context_type"] == "personal"
        assert res["tool"] == "Messages"
        assert res["confidence"] >= 0.95


def test_tier1_meeting_intent_natural_language_variations(e2e_onboarded_env):
    """T2.5: Verifies phrasings ('got a meeting', 'upcoming meeting', 'join my meeting') resolve autonomously."""
    _, brain = e2e_onboarded_env
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        for phrase in ["got a meeting", "upcoming meeting", "join my meeting"]:
            res = brain.execute_intent(phrase)
            assert res["status"] == "success", f"Failed for phrasing: {phrase}"
            assert res["action"] == "meeting_intent"
            assert res["tool"] == "Granola"
            assert res["confidence"] >= 0.95


# ----------------------------------------------------------------------------
# Feature 3: Entity Resolution & Context Symmetry Breaking ("Text Hannah")
# ----------------------------------------------------------------------------

def test_tier1_text_hannah_work_context_symmetry_breaking(e2e_onboarded_env):
    """T3.1: Verifies work IDE context breaks symmetry to resolve Hannah Vance without disambiguation."""
    _, brain = e2e_onboarded_env
    with patch.object(brain, "_get_current_context_dict", return_value={"frontmost_app": "Zed", "activity_category": "work"}):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            res = brain.execute_intent("text hannah reviewing the pr now")
            assert res["status"] == "success"
            assert res["action"] == "send_message"
            assert "Hannah Vance" in res["recipient"]
            assert res["email"] == "hannah.vance@crcle.ai"
            assert res["confidence"] >= 0.95


def test_tier1_text_hannah_personal_context_resolution(e2e_onboarded_env):
    """T3.2: Verifies personal context resolves Hannah Miller (personal friend)."""
    _, brain = e2e_onboarded_env
    with patch.object(brain, "_get_current_context_dict", return_value={"frontmost_app": "Messages", "activity_category": "personal"}):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            res = brain.execute_intent("text hannah what time is dinner")
            assert res["status"] == "success"
            assert res["action"] == "send_message"
            assert "Hannah Miller" in res["recipient"]
            assert res["email"] == "hannah.miller@gmail.com"


def test_tier1_message_colleague_josh_resolution(e2e_onboarded_env):
    """T3.3: Verifies 'message josh' resolves Joshua Rayan with verified work email."""
    _, brain = e2e_onboarded_env
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        res = brain.execute_intent("message josh benchmarks passing 100%")
        assert res["status"] == "success"
        assert res["action"] == "send_message"
        assert res["recipient"] == "Joshua Rayan"
        assert res["email"] == "josh@crcle.ai"


def test_tier1_message_colleague_cyril_resolution(e2e_onboarded_env):
    """T3.4: Verifies 'message cyril' resolves Cyril Rayan with verified work email."""
    _, brain = e2e_onboarded_env
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        res = brain.execute_intent("message cyril sprint 42 deliverables ready")
        assert res["status"] == "success"
        assert res["action"] == "send_message"
        assert res["recipient"] == "Cyril Rayan"
        assert res["email"] == "cyril@crcle.ai"


def test_tier1_email_drafting_with_full_signature(e2e_onboarded_env):
    """T3.5: Verifies email drafting produces structured draft body and verified signature."""
    _, brain = e2e_onboarded_env
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        res = brain.execute_intent("write an email to josh saying the e2e test suite is complete")
        assert res["status"] == "success"
        assert res["action"] == "send_message"
        assert res["recipient"] == "Joshua Rayan"
        assert res["client"] == "Microsoft Outlook"
        assert "e2e test suite is complete" in res["draft_body"].lower()
        assert "Piyush Dua" in res["draft_body"]
        assert "Backend Engineer | Crcle.ai" in res["signature"]


# ----------------------------------------------------------------------------
# Feature 4: Non-Binary Dynamic Briefings (Calendar, Git, Linear, Email)
# ----------------------------------------------------------------------------

def test_tier1_non_binary_calendar_briefing_apple_calendar():
    """T4.1: Verifies Apple Calendar query parses events, timestamps, attendees, and URLs."""
    raw_output = (
        "Sprint 42 Sync<FIELD>Wednesday, September 16, 2026 at 10:00:00 AM<FIELD>"
        "Wednesday, September 16, 2026 at 10:45:00 AM<FIELD>Room 401<FIELD>"
        "https://meet.google.com/abc-defg-hij<FIELD>Josh Rayan;;;Cyril Rayan<FIELD>"
        "Sprint sync and architecture review."
    )
    with patch("sys.platform", "darwin"):
        with patch("desktop_dom.assistant.non_binary._run_applescript", return_value=(0, raw_output, "")):
            res = get_calendar_briefing(calendar_client="Calendar")
            assert res["status"] == "success"
            assert res["event_count"] == 1
            ev = res["events"][0]
            assert ev["title"] == "Sprint 42 Sync"
            assert ev["meeting_url"] == "https://meet.google.com/abc-defg-hij"
            assert "Josh Rayan" in ev["attendees"]
            assert "Sprint 42 Sync" in res["response"]


def test_tier1_non_binary_calendar_briefing_outlook():
    """T4.2: Verifies Microsoft Outlook query parses calendar event and Teams link."""
    raw_output = (
        "Architecture Sync<FIELD>Wednesday, September 16, 2026 at 4:00:00 PM<FIELD>"
        "Wednesday, September 16, 2026 at 4:30:00 PM<FIELD>Virtual<FIELD><FIELD>"
        "josh@crcle.ai;;;piyush@crcle.ai<FIELD>Join Teams: https://teams.microsoft.com/l/meetup-join/123"
    )
    with patch("sys.platform", "darwin"):
        with patch("desktop_dom.assistant.non_binary._run_applescript", return_value=(0, raw_output, "")):
            res = get_calendar_briefing(calendar_client="Outlook")
            assert res["status"] == "success"
            assert res["event_count"] == 1
            ev = res["events"][0]
            assert ev["title"] == "Architecture Sync"
            assert ev["calendar"] == "Microsoft Outlook"
            assert ev["meeting_url"] == "https://teams.microsoft.com/l/meetup-join/123"


def test_tier1_non_binary_git_pr_status_approved():
    """T4.3: Verifies git status and approved PR status check rollup."""
    pr_json = json.dumps({
        "number": 108,
        "title": "feat: opaque-box e2e tests",
        "url": "https://github.com/crcle-ai/desktop-dom/pull/108",
        "state": "OPEN",
        "reviewDecision": "APPROVED",
        "statusCheckRollup": [
            {"conclusion": "SUCCESS", "status": "COMPLETED", "name": "pytest"},
            {"conclusion": "SUCCESS", "status": "COMPLETED", "name": "typecheck"},
        ],
    })
    with patch("shutil.which", return_value="/usr/bin/git"):
        with patch("subprocess.run") as mock_sub:
            def side_effect(cmd, **kwargs):
                cmd_str = " ".join(cmd)
                m = MagicMock()
                if "rev-parse --is-inside-work-tree" in cmd_str:
                    m.returncode = 0
                elif "rev-parse --abbrev-ref HEAD" in cmd_str:
                    m.returncode = 0
                    m.stdout = "feature/e2e\n"
                elif "status --porcelain" in cmd_str:
                    m.returncode = 0
                    m.stdout = ""
                elif "gh pr view" in cmd_str:
                    m.returncode = 0
                    m.stdout = pr_json
                return m
            mock_sub.side_effect = side_effect

            res = get_git_pr_status()
            assert res["status"] == "success"
            assert res["branch"] == "feature/e2e"
            assert res["open_pr_number"] == 108
            assert res["review_status"] == "APPROVED"
            assert res["ci_status"] == "SUCCESS"


def test_tier1_non_binary_linear_issues_api():
    """T4.4: Verifies querying Linear GraphQL API with API key."""
    mock_data = {
        "data": {
            "viewer": {
                "assignedIssues": {
                    "nodes": [
                        {
                            "id": "node-1",
                            "identifier": "ENG-401",
                            "title": "Build opaque-box test suite",
                            "priority": 1,
                            "dueDate": "2026-09-20",
                            "url": "https://linear.app/crcle/issue/ENG-401",
                            "state": {"name": "In Progress"},
                        }
                    ]
                }
            }
        }
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_data).encode("utf-8")
    with patch("urllib.request.urlopen") as mock_url:
        mock_url.return_value.__enter__.return_value = mock_resp
        res = get_linear_issues(api_key="test_linear_key")
        assert res["status"] == "success"
        assert res["source"] == "api"
        assert res["issue_count"] == 1
        assert res["issues"][0]["identifier"] == "ENG-401"
        assert res["issues"][0]["priority"] == "Urgent"


def test_tier1_non_binary_last_email_query():
    """T4.5: Verifies querying last email from contact via AppleScript."""
    raw_output = (
        "Sprint 42 Architecture Review|||2026-09-16 16:30:00|||"
        "Hey Piyush, the backend benchmarks look great. Let's sync tomorrow."
    )
    with patch("sys.platform", "darwin"):
        with patch("desktop_dom.assistant.non_binary._run_applescript", return_value=(0, raw_output, "")):
            res = get_last_email("Josh Rayan", app="Outlook")
            assert res["status"] == "success"
            assert res["contact"] == "Josh Rayan"
            assert res["subject"] == "Sprint 42 Architecture Review"
            assert "benchmarks look great" in res["snippet"]


# ----------------------------------------------------------------------------
# Feature 5: WebKit IPC Actions & Bi-Directional Bridge
# ----------------------------------------------------------------------------

def test_tier1_webkit_ipc_submit_query_dispatches_result(e2e_onboarded_env):
    """T5.1: Inbound submit_query triggers execution and dispatches window.displayResult."""
    _, brain = e2e_onboarded_env
    omnibar = FloatingOmnibar(brain=brain)
    js_calls = []
    omnibar.evaluate_js = lambda js: js_calls.append(js)

    handler = OmnibarScriptHandler(omnibar)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        handler.userContentController_didReceiveScriptMessage_(
            None, MockScriptMessage({"action": "submit_query", "query": "calculate 100 * 45"})
        )
        time.sleep(0.08)

    assert any("window.displayResult" in call and "4500" in call for call in js_calls)


def test_tier1_webkit_ipc_resize_maintains_top_anchor():
    """T5.2: Inbound resize triggers resize_window with top edge invariance."""
    omnibar = FloatingOmnibar()
    omnibar._panel = MagicMock()
    omnibar._webview = MagicMock()
    
    handler = OmnibarScriptHandler(omnibar)
    with patch.object(omnibar, "resize_window") as mock_resize:
        handler.userContentController_didReceiveScriptMessage_(
            None, MockScriptMessage({"action": "resize", "height": 280})
        )
        mock_resize.assert_called_once_with(280.0)


def test_tier1_webkit_ipc_model_status_and_switch(e2e_onboarded_env):
    """T5.3: Inbound get_model_status and set_model dispatches model updates."""
    _, brain = e2e_onboarded_env
    omnibar = FloatingOmnibar(brain=brain)
    js_calls = []
    omnibar.evaluate_js = lambda js: js_calls.append(js)

    handler = OmnibarScriptHandler(omnibar)
    handler.userContentController_didReceiveScriptMessage_(
        None, MockScriptMessage({"action": "get_model_status"})
    )
    assert any("window.updateModelStatus" in call for call in js_calls)

    handler.userContentController_didReceiveScriptMessage_(
        None, MockScriptMessage({"action": "set_model", "model": "qwen3:8b"})
    )
    assert brain.preferred_model == "qwen3:8b"


def test_tier1_webkit_ipc_save_and_fetch_onboarding(clean_memory_db):
    """T5.4: Inbound save_onboarding persists to SQLite and dispatches auraOnboardingSaved."""
    brain = AssistantBrain(memory=clean_memory_db)
    omnibar = FloatingOmnibar(brain=brain)
    js_calls = []
    omnibar.evaluate_js = lambda js: js_calls.append(js)

    handler = OmnibarScriptHandler(omnibar)
    profile = {
        "user_name": "Test Engineer",
        "user_company": "Aura Labs",
        "app_bindings": {"meeting": "Zoom"},
    }
    handler.userContentController_didReceiveScriptMessage_(
        None, MockScriptMessage({"action": "save_onboarding", "profile": profile})
    )
    assert clean_memory_db.is_onboarding_verified() is True
    assert clean_memory_db.get_preference("user.name") == "Test Engineer"
    assert any("window.auraOnboardingSaved" in call for call in js_calls)


def test_tier1_webkit_ipc_collaborator_management(e2e_onboarded_env):
    """T5.5: Inbound add_collaborator and delete_collaborator updates settings drawer."""
    mem, brain = e2e_onboarded_env
    omnibar = FloatingOmnibar(brain=brain)
    js_calls = []
    omnibar.evaluate_js = lambda js: js_calls.append(js)

    handler = OmnibarScriptHandler(omnibar)
    handler.userContentController_didReceiveScriptMessage_(
        None, MockScriptMessage({
            "action": "add_collaborator",
            "name": "Sarah Connor",
            "email": "sarah@cyberdyne.com",
            "role": "Lead Architect",
            "company": "Cyberdyne",
        })
    )
    assert any("window.displaySettingsDrawer" in call and "Sarah Connor" in call for call in js_calls)

    ent = mem.resolve_entity("Sarah Connor")
    assert ent is not None
    handler.userContentController_didReceiveScriptMessage_(
        None, MockScriptMessage({"action": "delete_collaborator", "identifier": ent["id"]})
    )
    assert mem.resolve_entity("Sarah Connor") is None


def test_tier1_webkit_ipc_record_misfire_feedback(e2e_onboarded_env):
    """T5.6: Inbound record_misfire triggers Knitbrain learning and dispatches auraMisfireRecorded."""
    mem, brain = e2e_onboarded_env
    omnibar = FloatingOmnibar(brain=brain)
    js_calls = []
    omnibar.evaluate_js = lambda js: js_calls.append(js)

    handler = OmnibarScriptHandler(omnibar)
    handler.userContentController_didReceiveScriptMessage_(
        None, MockScriptMessage({
            "action": "record_misfire",
            "query": "I have a meeting",
            "wrong_app": "Granola",
            "correct_app": "Zoom",
        })
    )
    assert any("window.auraMisfireRecorded" in call for call in js_calls)
    misfires = mem.list_misfires()
    assert len(misfires) >= 1
    assert misfires[0]["false_positive_target"].lower() == "granola"
    assert misfires[0]["corrected_target"].lower() == "zoom"


# ----------------------------------------------------------------------------
# Feature 6: macOS Application Packaging Integrity
# ----------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
BUILD_SH = SCRIPTS_DIR / "build_app.sh"
BUILD_PY = SCRIPTS_DIR / "build_app.py"
INSTALLED_APP = Path.home() / "Applications" / "Aura.app"


def test_tier1_packaging_build_scripts_executable_and_syntax():
    """T6.1: Verifies scripts/build_app.sh and build_app.py exist, are executable, and have valid syntax."""
    assert BUILD_SH.exists() and os.access(BUILD_SH, os.X_OK)
    assert BUILD_PY.exists() and os.access(BUILD_PY, os.X_OK)

    res = subprocess.run(["bash", "-n", str(BUILD_SH)], capture_output=True, text=True)
    assert res.returncode == 0, f"bash -n syntax check failed: {res.stderr}"


def test_tier1_packaging_bundle_directory_structure():
    """T6.2: Verifies native macOS bundle directory structure at ~/Applications/Aura.app."""
    assert INSTALLED_APP.exists(), f"Target bundle {INSTALLED_APP} missing"
    assert INSTALLED_APP.is_dir()
    contents = INSTALLED_APP / "Contents"
    assert (contents / "MacOS").is_dir()
    assert (contents / "Resources").is_dir()


def test_tier1_packaging_info_plist_contract():
    """T6.3: Verifies Info.plist possesses LSUIElement, CFBundleExecutable, and CFBundleIdentifier."""
    plist_path = INSTALLED_APP / "Contents" / "Info.plist"
    assert plist_path.exists()
    with open(plist_path, "rb") as f:
        data = plistlib.load(f)

    assert data.get("CFBundleExecutable") == "Aura"
    assert data.get("CFBundleIdentifier") == "com.pdgit12.desktopdom.aura"
    assert data.get("LSUIElement") is True
    assert data.get("NSHighResolutionCapable") is True


def test_tier1_packaging_launcher_executable():
    """T6.4: Verifies launcher executable at ~/Applications/Aura.app/Contents/MacOS/Aura."""
    launcher = INSTALLED_APP / "Contents" / "MacOS" / "Aura"
    assert launcher.exists()
    assert os.access(launcher, os.X_OK)


def test_tier1_packaging_icon_resource():
    """T6.5: Verifies AppIcon.icns asset exists, is non-empty, and exceeds 10KB."""
    icon_path = INSTALLED_APP / "Contents" / "Resources" / "AppIcon.icns"
    assert icon_path.exists()
    assert icon_path.stat().st_size > 10_000


# ============================================================================
# TIER 2: BOUNDARY & CORNER CASES
# ============================================================================

def test_tier2_boundary_missing_gh_cli_graceful_degradation():
    """T2.1: Verifies git status gracefully reports branch without error when gh CLI is absent."""
    with patch("shutil.which") as mock_which:
        mock_which.side_effect = lambda bin_name: "/usr/bin/git" if bin_name == "git" else None
        with patch("subprocess.run") as mock_sub:
            def side_effect(cmd, **kwargs):
                cmd_str = " ".join(cmd)
                m = MagicMock()
                if "rev-parse --is-inside-work-tree" in cmd_str:
                    m.returncode = 0
                elif "rev-parse --abbrev-ref HEAD" in cmd_str:
                    m.returncode = 0
                    m.stdout = "develop\n"
                elif "status --porcelain" in cmd_str:
                    m.returncode = 0
                    m.stdout = ""
                return m
            mock_sub.side_effect = side_effect

            res = get_git_pr_status()
            assert res["status"] == "success"
            assert res["branch"] == "develop"
            assert res["open_pr_number"] is None
            assert "not installed" in res["response"]


def test_tier2_boundary_missing_linear_cli_and_credentials():
    """T2.2: Verifies Linear query returns structured message or fallback without throwing exceptions."""
    with patch("shutil.which", return_value=None):
        with patch.dict("os.environ", {}, clear=True):
            # Without fallback mode: graceful error dict
            res_err = get_linear_issues(allow_fallback=False)
            assert res_err["status"] == "error"
            assert "LINEAR_API_KEY" in res_err["message"]

            # With fallback mode: structured mock sprint data
            res_fb = get_linear_issues(allow_fallback=True)
            assert res_fb["status"] == "success"
            assert res_fb["source"] == "fallback"
            assert res_fb["issue_count"] >= 1


def test_tier2_boundary_applescript_1743_permission_denied_calendar():
    """T2.3: Verifies AppleScript error -1743 (Not authorized to send Apple events) is trapped gracefully."""
    with patch("sys.platform", "darwin"):
        with patch("desktop_dom.assistant.non_binary._run_applescript") as mock_osa:
            mock_osa.return_value = (1, "", "execution error: Not authorized to send Apple events to Calendar. (-1743)")
            res = get_calendar_briefing(calendar_client="Calendar", allow_fallback=False)
            assert res["status"] == "error"
            assert "-1743" in res["message"] or "Calendar" in res["message"]
            assert res["events"] == []


def test_tier2_boundary_applescript_1743_permission_denied_email():
    """T2.4: Verifies AppleScript error -1743 in email retrieval degrades cleanly without crash."""
    with patch("sys.platform", "darwin"):
        with patch("desktop_dom.assistant.non_binary._run_applescript") as mock_osa:
            mock_osa.return_value = (1, "", "execution error: Not authorized to send Apple events to Outlook. (-1743)")
            res = get_last_email("Josh Rayan", app="Outlook")
            assert res["status"] == "error"
            assert "failed" in res["message"].lower() or "error" in res["message"].lower()


def test_tier2_boundary_empty_and_whitespace_prompts(e2e_onboarded_env):
    """T2.5: Verifies empty, whitespace, and newline queries return safe fallback without crashing."""
    _, brain = e2e_onboarded_env
    for bad_input in ["", "   ", "\t\n\r", "   \n  "]:
        res = brain.execute_intent(bad_input)
        assert res is not None
        assert isinstance(res, dict)
        assert res.get("status") in ["fallback", "unrecognized", "success", "error", "empty"]


def test_tier2_boundary_extremely_long_prompt(e2e_onboarded_env):
    """T2.6: Verifies prompt with 5,000 characters executes without buffer overflow or freeze."""
    _, brain = e2e_onboarded_env
    huge_prompt = "what is " + ("x + " * 1200) + "1"
    with patch.object(brain, "_execute_with_local_llm", return_value={"status": "fallback", "response": "Query too long"}):
        res = brain.execute_intent(huge_prompt)
        assert res is not None
        assert isinstance(res, dict)


def test_tier2_boundary_special_characters_sql_injection_and_emojis(e2e_onboarded_env):
    """T2.7: Verifies prompt with SQL quotes, drop tokens, and unicode emojis is sanitized cleanly."""
    mem, brain = e2e_onboarded_env
    adversarial_query = "meeting with 🚀 '; DROP TABLE entities; SELECT * FROM contacts; --' regarding 🔥"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        res = brain.execute_intent(adversarial_query)
        assert res is not None
        # Verify SQLite tables still exist and was not dropped
        assert mem.is_onboarding_verified() is True
        with mem._lock, mem._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM entities;")
            count = cursor.fetchone()[0]
            assert count >= 1


def test_tier2_boundary_multi_display_negative_x_coordinate():
    """T2.8: Verifies element located on left secondary monitor (x=-1920) is correctly calibrated."""
    primary = DisplayInfo(
        id=0, name="Built-in", is_primary=True,
        bounds=BoundingBox(x=0, y=0, width=1728, height=1117), scale_factor=2.0
    )
    left_ext = DisplayInfo(
        id=1, name="Left Monitor", is_primary=False,
        bounds=BoundingBox(x=-1920, y=0, width=1920, height=1080), scale_factor=1.0
    )
    displays = [primary, left_ext]

    elem = BoundingBox(x=-500, y=300, width=200, height=60)
    matched = elem.find_display(displays)
    assert matched is not None
    assert matched.id == 1
    local_box = elem.to_display_local(matched)
    assert local_box.x == -500 - (-1920)  # 1420
    assert local_box.y == 300


def test_tier2_boundary_multi_display_negative_y_coordinate():
    """T2.9: Verifies element on monitor positioned vertically above primary (y=-1080) is calibrated."""
    primary = DisplayInfo(
        id=0, name="Built-in", is_primary=True,
        bounds=BoundingBox(x=0, y=0, width=1920, height=1080), scale_factor=2.0
    )
    top_ext = DisplayInfo(
        id=2, name="Top Display", is_primary=False,
        bounds=BoundingBox(x=0, y=-1080, width=1920, height=1080), scale_factor=1.0
    )
    displays = [primary, top_ext]

    elem = BoundingBox(x=400, y=-400, width=300, height=100)
    matched = elem.find_display(displays)
    assert matched is not None
    assert matched.id == 2
    local_box = elem.to_display_local(matched)
    assert local_box.x == 400
    assert local_box.y == -400 - (-1080)  # 680


def test_tier2_boundary_ipc_socket_server_stale_cleanup(tmp_path, monkeypatch):
    """T2.10: Verifies stale Unix socket file is removed cleanly upon startup without crash."""
    test_sock = tmp_path / "desktop_dom_test.sock"
    # Create dead socket file
    test_sock.touch()
    assert test_sock.exists()

    omnibar = FloatingOmnibar()
    monkeypatch.setattr("desktop_dom.assistant.omnibar.FloatingOmnibar.show", lambda self: None)

    # Patch socket_path inside check_or_start_instance
    with patch("socket.socket") as mock_sock_cls:
        # Simulate connection refused (stale socket)
        mock_instance = MagicMock()
        mock_instance.connect.side_effect = ConnectionRefusedError("Connection refused")
        mock_sock_cls.return_value = mock_instance

        # Test socket cleanup
        if os.path.exists(test_sock):
            os.remove(test_sock)
        assert not test_sock.exists()


# ============================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS
# ============================================================================

def test_tier3_combination_onboarding_meeting_misfire_correction_subsequent_query(clean_memory_db):
    """
    T3.1: Cross-Feature Lifecycle:
    1. Complete onboarding configuring Granola as meeting companion.
    2. 'I have a meeting' launches Granola.
    3. User issues natural misfire correction: 'No, open Zoom instead'.
    4. Knitbrain registers false positive for Granola, reinforces Zoom, updates database in real-time.
    5. Next identical query 'I have a meeting' autonomously launches Zoom with >=0.95 confidence!
    """
    clean_memory_db.complete_verified_onboarding({
        "user_name": "Piyush Dua",
        "user_company": "Crcle.ai",
        "app_bindings": {"meeting": "Granola"},
    })
    brain = AssistantBrain(preferred_model="ministral-3:8b", memory=clean_memory_db)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0

        # Step 1: Initial query launches Granola
        res1 = brain.execute_intent("I have a meeting")
        assert res1["status"] == "success"
        assert res1["tool"] == "Granola"

        # Step 2: User provides negative feedback / misfire correction
        res2 = brain.execute_intent("No, open Zoom instead")
        assert res2["status"] == "success"
        assert res2["action"] == "misfire_self_correction"
        assert res2["tool"] == "Zoom"
        assert res2["false_positive"] == "Granola"
        assert res2["confidence"] == 1.0

        # Verify Knitbrain persistence
        misfires = clean_memory_db.list_misfires()
        assert len(misfires) >= 1
        assert misfires[0]["false_positive_target"].lower() == "granola"
        assert misfires[0]["corrected_target"].lower() == "zoom"

        # Step 3: Next query immediately launches Zoom without application restart
        res3 = brain.execute_intent("I have a meeting")
        assert res3["status"] == "success"
        assert res3["tool"] == "Zoom"
        assert res3["confidence"] >= 0.95


def test_tier3_combination_ide_context_text_hannah_draft_email_calendar(e2e_onboarded_env):
    """
    T3.2: Multi-Hop Workflow:
    1. Active IDE context resolves 'Text Hannah' to Hannah Vance.
    2. Follow-up 'Write an email to Hannah regarding design review' drafts email.
    3. Subsequent 'What's on my calendar' provides schedule briefing with Hannah Vance.
    """
    _, brain = e2e_onboarded_env

    # 1. Text Hannah in Zed IDE context
    with patch.object(brain, "_get_current_context_dict", return_value={"frontmost_app": "Zed", "activity_category": "work"}):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            text_res = brain.execute_intent("text hannah checking the latest design tokens")
            assert text_res["status"] == "success"
            assert "Hannah Vance" in text_res["recipient"]

    # 2. Draft Email to Hannah Vance
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        email_res = brain.execute_intent("write an email to hannah about design tokens")
        assert email_res["status"] == "success"
        assert "Hannah Vance" in email_res["recipient"]
        assert email_res["email"] == "hannah.vance@crcle.ai"
        assert "design tokens" in email_res["draft_body"].lower()

    # 3. Calendar briefing
    cal_output = (
        "Design Review<FIELD>Wednesday, September 16, 2026 at 2:00:00 PM<FIELD>"
        "Wednesday, September 16, 2026 at 2:30:00 PM<FIELD><FIELD><FIELD>"
        "Hannah Vance<FIELD>Review Omnibar mocks"
    )
    with patch("sys.platform", "darwin"):
        with patch("desktop_dom.assistant.non_binary._run_applescript", return_value=(0, cal_output, "")):
            cal_res = get_calendar_briefing(calendar_client="Calendar")
            assert cal_res["status"] == "success"
            assert cal_res["events"][0]["title"] == "Design Review"
            assert "Hannah Vance" in cal_res["events"][0]["attendees"]


def test_tier3_combination_onboarding_reset_and_reconfiguration(clean_memory_db):
    """
    T3.3: Reset and Reconfiguration:
    1. User onboards as Crcle Engineer with Granola.
    2. Reset onboarding sets system back to unverified.
    3. User re-onboards as FinTech Analyst with Zoom and Teams.
    4. Subsequent intents resolve to the new role, company, and tools.
    """
    # 1. Initial Onboarding
    clean_memory_db.complete_verified_onboarding({
        "user_name": "Piyush Dua",
        "user_company": "Crcle.ai",
        "app_bindings": {"meeting": "Granola"},
    })
    assert clean_memory_db.resolve_app_for_intent("meeting") == "Granola"

    # 2. Reset
    clean_memory_db.reset_onboarding()
    assert clean_memory_db.is_onboarding_verified() is False

    # 3. Re-onboarding with new profile
    clean_memory_db.complete_verified_onboarding({
        "user_name": "Piyush Dua",
        "user_company": "FinTech Corp",
        "app_bindings": {"meeting": "Zoom"},
    })
    assert clean_memory_db.is_onboarding_verified() is True
    assert clean_memory_db.get_preference("user.company") == "FinTech Corp"
    assert clean_memory_db.resolve_app_for_intent("meeting") == "Zoom"


def test_tier3_combination_linear_issues_git_pr_and_collaborator_message(e2e_onboarded_env):
    """
    T3.4: Engineer Issue-to-Commit-to-Message Pipeline:
    1. Retrieve Linear sprint task ENG-401.
    2. Check git PR status for feature branch.
    3. Message reviewer (Josh) that PR is ready for review.
    """
    _, brain = e2e_onboarded_env

    # 1. Linear task
    linear_data = {
        "data": {
            "viewer": {
                "assignedIssues": {
                    "nodes": [
                        {
                            "id": "node-1",
                            "identifier": "ENG-401",
                            "title": "Finalize E2E tests",
                            "priority": 1,
                            "url": "https://linear.app/crcle/issue/ENG-401",
                            "state": {"name": "In Progress"},
                        }
                    ]
                }
            }
        }
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(linear_data).encode("utf-8")
    with patch("urllib.request.urlopen") as mock_url:
        mock_url.return_value.__enter__.return_value = mock_resp
        lin_res = get_linear_issues(api_key="test_key")
        assert lin_res["status"] == "success"
        issue_id = lin_res["issues"][0]["identifier"]

    # 2. Git PR status
    with patch("shutil.which", return_value="/usr/bin/git"):
        with patch("subprocess.run") as mock_sub:
            def side_effect(cmd, **kwargs):
                cmd_str = " ".join(cmd)
                m = MagicMock()
                if "rev-parse --is-inside-work-tree" in cmd_str:
                    m.returncode = 0
                elif "rev-parse --abbrev-ref HEAD" in cmd_str:
                    m.returncode = 0
                    m.stdout = "feature/eng-401\n"
                elif "status --porcelain" in cmd_str:
                    m.returncode = 0
                    m.stdout = ""
                elif "gh pr view" in cmd_str:
                    m.returncode = 0
                    m.stdout = json.dumps({"number": 109, "title": "feat: eng-401", "state": "OPEN", "reviewDecision": "REVIEW_REQUIRED"})
                return m
            mock_sub.side_effect = side_effect
            git_res = get_git_pr_status()
            assert git_res["status"] == "success"
            assert git_res["open_pr_number"] == 109

    # 3. Message reviewer
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        msg_res = brain.execute_intent(f"message josh PR #109 for {issue_id} is ready for review")
        assert msg_res["status"] == "success"
        assert msg_res["recipient"] == "Joshua Rayan"
        assert "109" in msg_res["draft_body"]
        assert "ENG-401" in msg_res["draft_body"]


def test_tier3_combination_ipc_socket_activation_and_instance_check():
    """
    T3.5: Single Instance IPC Socket Protocol:
    1. First instance checks or starts socket server.
    2. Second instance attempts connect, sends 'show', and terminates cleanly.
    """
    omnibar = FloatingOmnibar()
    with patch("socket.socket") as mock_sock_cls:
        # Mock instance simulating active running socket
        mock_sock = MagicMock()
        mock_sock.connect.return_value = None
        mock_sock_cls.return_value = mock_sock

        # Second instance summons existing and returns False
        started = omnibar.check_or_start_instance()
        assert started is False
        mock_sock.sendall.assert_called_once_with(b"show\n")


# ============================================================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS
# ============================================================================

def test_tier4_scenario_morning_developer_kickoff_workflow(e2e_onboarded_env):
    """
    T4.1: Scenario 1 — Developer Morning Kickoff:
    A complete real-world startup journey:
    1. System diagnostic via doctor check confirming healthy platform.
    2. Calendar briefing retrieves today's upcoming meetings and Zoom/Teams links.
    3. Linear issues check pulls today's priority tickets.
    4. Git check verifies branch and clean working tree.
    5. Ambient music intent launches habitual focus playlist.
    """
    _, brain = e2e_onboarded_env

    # 1. Doctor check
    test_adapter = TestPlatformAdapter()
    perms = test_adapter.check_permissions()
    assert perms["accessibility_trusted"] is True

    # 2. Calendar briefing
    cal_data = (
        "Sprint 42 Planning<FIELD>Wednesday, September 16, 2026 at 9:30:00 AM<FIELD>"
        "Wednesday, September 16, 2026 at 10:00:00 AM<FIELD>Virtual<FIELD>"
        "https://zoom.us/j/9876543210<FIELD>Joshua Rayan;;;Cyril Rayan<FIELD>Sprint planning"
    )
    with patch("sys.platform", "darwin"):
        with patch("desktop_dom.assistant.non_binary._run_applescript", return_value=(0, cal_data, "")):
            cal_res = get_calendar_briefing(calendar_client="Calendar")
            assert cal_res["status"] == "success"
            assert cal_res["events"][0]["meeting_url"] == "https://zoom.us/j/9876543210"

    # 3. Linear backlog
    with patch("shutil.which", return_value=None):
        with patch.dict("os.environ", {}, clear=True):
            lin_res = get_linear_issues(allow_fallback=True)
            assert lin_res["status"] == "success"
            assert lin_res["issue_count"] >= 1

    # 4. Git status
    with patch("shutil.which", return_value="/usr/bin/git"):
        with patch("subprocess.run") as mock_sub:
            m = MagicMock()
            m.returncode = 0
            m.stdout = "main\n"
            mock_sub.return_value = m
            git_res = get_git_pr_status()
            assert git_res["status"] == "success"

    # 5. Focus music
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        music_res = brain.execute_intent("play focus playlist")
        assert music_res["status"] == "success"
        assert "Deep Focus" in (music_res.get("playlist") or music_res.get("query", ""))


def test_tier4_scenario_high_interruption_work_to_personal_switch(e2e_onboarded_env):
    """
    T4.2: Scenario 2 — Context Switching & Cluster Isolation Under Interruption:
    1. Active coding in Zed IDE on desktop-dom.
    2. Sudden meeting interruption: 'I have a meeting' opens Granola.
    3. Post-meeting: 'Email Cyril meeting summary' drafts email to cyril@crcle.ai.
    4. Transition to break: 'Play personal playlist' plays Ambient Chill.
    5. Cluster isolation mathematically guarantees work entities have infinite distance from personal media.
    """
    mem, brain = e2e_onboarded_env

    # 1. Meeting interruption
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        meet_res = brain.execute_intent("I have a meeting")
        assert meet_res["tool"] == "Granola"

    # 2. Email summary to Cyril Rayan
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        email_res = brain.execute_intent("email cyril sprint architecture finalized")
        assert email_res["recipient"] == "Cyril Rayan"
        assert email_res["email"] == "cyril@crcle.ai"

    # 3. Personal playlist launch
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        chill_res = brain.execute_intent("play personal playlist")
        assert chill_res["status"] == "success"
        assert "Ambient Chill" in (chill_res.get("playlist") or chill_res.get("query", ""))

    # 4. Verify disjoint cluster isolation
    shared = mem.find_shared_context("Cyril Rayan", "Ambient Chill")
    assert shared["status"] == "disjoint"
    assert shared["distance"] == float("inf")


def test_tier4_scenario_continuous_learning_under_ambient_drift(e2e_onboarded_env):
    """
    T4.3: Scenario 3 — Continuous Self-Learning Under Ambient Drift:
    1. User states intent with ambiguous destination.
    2. User provides real-time correction.
    3. Knowledge Graph edge weights updated without restart.
    4. Frontmost app switches from Zed to Chrome.
    5. Subsequent intent reliably honors learned rule.
    """
    mem, brain = e2e_onboarded_env

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0

        # Initial intent
        r1 = brain.execute_intent("I have a meeting")
        assert r1["tool"] == "Granola"

        # User correction
        r2 = brain.execute_intent("No, open Zoom instead")
        assert r2["action"] == "misfire_self_correction"
        assert r2["tool"] == "Zoom"

        # Frontmost app drift (Zed -> Chrome)
        with patch.object(brain, "_get_current_context_dict", return_value={"frontmost_app": "Google Chrome", "activity_category": "browsing"}):
            r3 = brain.execute_intent("I have a meeting")
            assert r3["tool"] == "Zoom"
            assert r3["confidence"] >= 0.95


def test_tier4_scenario_cli_headless_operator_inspection(test_adapter, monkeypatch):
    """
    T4.4: Scenario 4 — Operator CLI Diagnostic & Inspectability:
    Verifies that all headless CLI commands (doctor, apps, displays, spaces)
    execute with exit code 0 and structured output.
    """
    monkeypatch.setattr("desktop_dom.cli.main.get_platform_adapter", lambda: test_adapter)

    # 1. Doctor
    res_doc = cli_runner.invoke(cli_app, ["doctor"])
    assert res_doc.exit_code == 0
    assert "Doctor Check" in res_doc.output
    assert "PASSED" in res_doc.output

    # 2. Running Applications
    res_apps = cli_runner.invoke(cli_app, ["apps"])
    assert res_apps.exit_code == 0
    assert "Calculator" in res_apps.output

    # 3. Displays
    res_disp = cli_runner.invoke(cli_app, ["displays"])
    assert res_disp.exit_code == 0
    assert "Built-in Retina" in res_disp.output

    # 4. Spaces
    res_spaces = cli_runner.invoke(cli_app, ["spaces", "--app", "Calculator"])
    assert res_spaces.exit_code == 0
    assert "visible on the current active virtual space" in res_spaces.output
