import json
import subprocess
import sys
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from desktop_dom.assistant.non_binary import (
    NonBinaryAdapters,
    get_calendar_briefing,
    get_git_pr_status,
    get_last_email,
    get_linear_issues,
    route_non_binary_intent,
)


# ============================================================================
# 1. Calendar Briefing Adapter Tests
# ============================================================================

def test_calendar_briefing_apple_calendar_success():
    """Verifies Apple Calendar query parses events, times, attendees, and meeting URLs."""
    mock_apple_script_output = (
        "Sprint 42 Sync<FIELD>Wednesday, September 16, 2026 at 10:00:00 AM<FIELD>"
        "Wednesday, September 16, 2026 at 10:45:00 AM<FIELD>Room 401<FIELD>"
        "https://meet.google.com/abc-defg-hij<FIELD>Josh Rayan;;;Cyril Rayan<FIELD>"
        "Discussion on architecture and benchmarks.<RECORD>"
        "Design Review<FIELD>Wednesday, September 16, 2026 at 2:00:00 PM<FIELD>"
        "Wednesday, September 16, 2026 at 2:30:00 PM<FIELD><FIELD><FIELD>"
        "Hannah Vance<FIELD>Review Omnibar mocks at https://zoom.us/j/9876543210"
    )

    with patch("sys.platform", "darwin"):
        with patch("desktop_dom.assistant.non_binary._run_applescript") as mock_osa:
            mock_osa.return_value = (0, mock_apple_script_output, "")
            res = get_calendar_briefing(calendar_client="Calendar")

            assert res["status"] == "success"
            assert res["action"] == "calendar_briefing"
            assert res["event_count"] == 2
            assert len(res["events"]) == 2

            ev1 = res["events"][0]
            assert ev1["title"] == "Sprint 42 Sync"
            assert ev1["start_time"] == "Wednesday, September 16, 2026 at 10:00:00 AM"
            assert ev1["meeting_url"] == "https://meet.google.com/abc-defg-hij"
            assert "Josh Rayan" in ev1["attendees"]
            assert "Cyril Rayan" in ev1["attendees"]

            ev2 = res["events"][1]
            assert ev2["title"] == "Design Review"
            # Extracted meeting url from description
            assert ev2["meeting_url"] == "https://zoom.us/j/9876543210"
            assert "Hannah Vance" in ev2["attendees"]

            assert "Sprint 42 Sync" in res["response"]
            assert "Design Review" in res["response"]


def test_calendar_briefing_outlook_success():
    """Verifies Microsoft Outlook calendar query parsing."""
    mock_outlook_output = (
        "Architecture Sync<FIELD>Wednesday, September 16, 2026 at 4:00:00 PM<FIELD>"
        "Wednesday, September 16, 2026 at 4:30:00 PM<FIELD>Virtual<FIELD><FIELD>"
        "josh@crcle.ai;;;piyush@crcle.ai<FIELD>Join Teams: https://teams.microsoft.com/l/meetup-join/123"
    )

    with patch("sys.platform", "darwin"):
        with patch("desktop_dom.assistant.non_binary._run_applescript") as mock_osa:
            mock_osa.return_value = (0, mock_outlook_output, "")
            res = get_calendar_briefing(calendar_client="Outlook")

            assert res["status"] == "success"
            assert res["event_count"] == 1
            ev = res["events"][0]
            assert ev["title"] == "Architecture Sync"
            assert ev["calendar"] == "Microsoft Outlook"
            assert ev["meeting_url"] == "https://teams.microsoft.com/l/meetup-join/123"
            assert "josh@crcle.ai" in ev["attendees"]


def test_calendar_briefing_empty_schedule():
    """Verifies empty calendar returns 0 events and an informative message."""
    with patch("sys.platform", "darwin"):
        with patch("desktop_dom.assistant.non_binary._run_applescript") as mock_osa:
            mock_osa.return_value = (0, "", "")
            res = get_calendar_briefing(calendar_client="Calendar")

            assert res["status"] == "success"
            assert res["event_count"] == 0
            assert res["events"] == []
            assert "No upcoming events scheduled for today" in res["response"]


def test_calendar_briefing_non_darwin():
    """Verifies non-darwin platform degradation without throwing exceptions."""
    with patch("sys.platform", "linux"):
        res = get_calendar_briefing()
        assert res["status"] == "error"
        assert "darwin" in res["message"]
        assert res["events"] == []


def test_calendar_briefing_applescript_timeout():
    """Verifies timeout handling returns error status gracefully."""
    with patch("sys.platform", "darwin"):
        with patch("desktop_dom.assistant.non_binary._run_applescript") as mock_osa:
            mock_osa.return_value = (124, "", "AppleScript execution timed out after 4.0s")
            res = get_calendar_briefing(calendar_client="Calendar")
            assert res["status"] == "error"
            assert "timed out" in res["message"]
            assert res["events"] == []


# ============================================================================
# 2. Git & PR Status Adapter Tests
# ============================================================================

def test_git_pr_status_with_open_approved_pr():
    """Verifies git branch, clean tree, and approved PR status check rollup."""
    pr_json = json.dumps({
        "number": 108,
        "title": "feat: non-binary desktop adapters",
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
                    m.stdout = "true\n"
                elif "rev-parse --abbrev-ref HEAD" in cmd_str:
                    m.returncode = 0
                    m.stdout = "feature/adapters\n"
                elif "status --porcelain" in cmd_str:
                    m.returncode = 0
                    m.stdout = ""  # Clean working tree
                elif "gh pr view" in cmd_str:
                    m.returncode = 0
                    m.stdout = pr_json
                else:
                    m.returncode = 0
                    m.stdout = ""
                return m

            mock_sub.side_effect = side_effect
            res = get_git_pr_status()

            assert res["status"] == "success"
            assert res["branch"] == "feature/adapters"
            assert res["uncommitted_changes"] is False
            assert res["uncommitted_count"] == 0
            assert res["open_pr_number"] == 108
            assert res["pr_title"] == "feat: non-binary desktop adapters"
            assert res["review_status"] == "APPROVED"
            assert res["ci_status"] == "SUCCESS"
            assert "#108" in res["response"]
            assert "Clean (0 files)" in res["response"]


def test_git_pr_status_with_uncommitted_and_failing_ci():
    """Verifies uncommitted files list and CI failure detection."""
    pr_json = json.dumps({
        "number": 99,
        "title": "fix: race condition in activation loop",
        "url": "https://github.com/crcle-ai/desktop-dom/pull/99",
        "state": "OPEN",
        "reviewDecision": "CHANGES_REQUESTED",
        "statusCheckRollup": [
            {"conclusion": "SUCCESS", "status": "COMPLETED", "name": "build"},
            {"conclusion": "FAILURE", "status": "COMPLETED", "name": "lint"},
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
                    m.stdout = "develop\n"
                elif "status --porcelain" in cmd_str:
                    m.returncode = 0
                    m.stdout = " M src/desktop_dom/brain.py\n?? tests/test_extra.py\n"
                elif "gh pr view" in cmd_str:
                    m.returncode = 0
                    m.stdout = pr_json
                return m

            mock_sub.side_effect = side_effect
            res = get_git_pr_status()

            assert res["status"] == "success"
            assert res["branch"] == "develop"
            assert res["uncommitted_changes"] is True
            assert res["uncommitted_count"] == 2
            assert "src/desktop_dom/brain.py" in res["modified_files"]
            assert res["review_status"] == "CHANGES_REQUESTED"
            assert res["ci_status"] == "FAILURE"


def test_git_pr_status_not_a_git_repo():
    """Verifies graceful handling when executed outside a git repo."""
    with patch("shutil.which", return_value="/usr/bin/git"):
        with patch("subprocess.run") as mock_sub:
            m = MagicMock()
            m.returncode = 128
            m.stderr = "fatal: not a git repository"
            mock_sub.return_value = m

            res = get_git_pr_status(cwd="/tmp/random_empty_dir")
            assert res["status"] == "error"
            assert "Not a git repository" in res["message"]
            assert res["branch"] is None


def test_git_pr_status_missing_gh_cli():
    """Verifies git status succeeds even if GitHub CLI (gh) is not installed."""
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
                    m.stdout = "main\n"
                elif "status --porcelain" in cmd_str:
                    m.returncode = 0
                    m.stdout = ""
                return m

            mock_sub.side_effect = side_effect
            res = get_git_pr_status()

            assert res["status"] == "success"
            assert res["branch"] == "main"
            assert res["open_pr_number"] is None
            assert "not installed" in res["response"]


# ============================================================================
# 3. Linear Issues Adapter Tests
# ============================================================================

def test_linear_issues_api_success():
    """Verifies querying Linear GraphQL API with API key."""
    mock_response_data = {
        "data": {
            "viewer": {
                "assignedIssues": {
                    "nodes": [
                        {
                            "id": "node-1",
                            "identifier": "ENG-240",
                            "title": "Implement non-binary desktop adapters",
                            "priority": 1,
                            "dueDate": "2026-09-20",
                            "url": "https://linear.app/crcle/issue/ENG-240",
                            "state": {"name": "In Progress"},
                        },
                        {
                            "id": "node-2",
                            "identifier": "ENG-241",
                            "title": "Evaluate memory retention under load",
                            "priority": 2,
                            "dueDate": None,
                            "url": "https://linear.app/crcle/issue/ENG-241",
                            "state": {"name": "Todo"},
                        },
                    ]
                }
            }
        }
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_response_data).encode("utf-8")

    with patch("urllib.request.urlopen") as mock_url:
        mock_url.return_value.__enter__.return_value = mock_resp
        res = get_linear_issues(api_key="lin_api_test_key")

        assert res["status"] == "success"
        assert res["source"] == "api"
        assert res["issue_count"] == 2
        assert res["issues"][0]["identifier"] == "ENG-240"
        assert res["issues"][0]["priority"] == "Urgent"
        assert res["issues"][1]["identifier"] == "ENG-241"
        assert res["issues"][1]["priority"] == "High"
        assert "ENG-240" in res["response"]


def test_linear_issues_cli_success():
    """Verifies querying issues via linear CLI."""
    cli_output = json.dumps([
        {
            "id": "lin-1",
            "identifier": "ENG-310",
            "title": "Add AppleScript Outlook briefing",
            "priority": "High",
            "state": {"name": "In Review"},
            "dueDate": None,
            "url": "https://linear.app/crcle/issue/ENG-310",
        }
    ])

    with patch("shutil.which", return_value="/usr/local/bin/linear"):
        with patch("subprocess.run") as mock_sub:
            mock_sub.return_value.returncode = 0
            mock_sub.return_value.stdout = cli_output
            res = get_linear_issues()

            assert res["status"] == "success"
            assert res["source"] == "cli"
            assert res["issue_count"] == 1
            assert res["issues"][0]["identifier"] == "ENG-310"


def test_linear_issues_fallback_mode():
    """Verifies fallback mode when credentials are not configured."""
    with patch("shutil.which", return_value=None):
        with patch.dict("os.environ", {}, clear=True):
            # Without fallback: returns error status
            res_err = get_linear_issues(allow_fallback=False)
            assert res_err["status"] == "error"
            assert "LINEAR_API_KEY" in res_err["message"]

            # With allow_fallback: returns structured sprint fallback
            res_fb = get_linear_issues(allow_fallback=True)
            assert res_fb["status"] == "success"
            assert res_fb["source"] == "fallback"
            assert res_fb["issue_count"] >= 1
            assert any("ENG-" in i["identifier"] for i in res_fb["issues"])


def test_linear_issues_network_timeout():
    """Verifies graceful degradation on network timeouts."""
    with patch("shutil.which", return_value=None):
        with patch("urllib.request.urlopen", side_effect=TimeoutError("Connection timed out")):
            res = get_linear_issues(api_key="lin_api_test_key", allow_fallback=False)
            assert res["status"] == "error"
            assert "failed" in res["message"].lower()


# ============================================================================
# 4. Last Email Adapter Tests
# ============================================================================

def test_get_last_email_outlook_success():
    """Verifies retrieval of last email from Outlook."""
    mock_email_output = (
        "Sprint 42 Architecture Review|||2026-09-16 16:30:00|||"
        "Hey Piyush, the backend benchmarks look great. Let's sync tomorrow."
    )

    with patch("sys.platform", "darwin"):
        with patch("desktop_dom.assistant.non_binary._run_applescript") as mock_osa:
            mock_osa.return_value = (0, mock_email_output, "")
            res = get_last_email("Josh Rayan", app="Outlook")

            assert res["status"] == "success"
            assert res["contact"] == "Josh Rayan"
            assert res["subject"] == "Sprint 42 Architecture Review"
            assert res["received"] == "2026-09-16 16:30:00"
            assert "benchmarks look great" in res["snippet"]
            assert "Sprint 42 Architecture Review" in res["response"]


def test_get_last_email_apple_mail_fallback():
    """Verifies fallback to Apple Mail when Outlook returns NO_MESSAGES_FOUND."""
    mail_output = (
        "Design System Update|||2026-09-16 14:15:00|||"
        "Updated the Figma tokens and omnibar themes."
    )

    with patch("sys.platform", "darwin"):
        with patch("desktop_dom.assistant.non_binary._run_applescript") as mock_osa:
            # First call for Outlook returns NO_MESSAGES_FOUND, second for Mail returns message
            mock_osa.side_effect = [
                (0, "NO_MESSAGES_FOUND", ""),
                (0, mail_output, ""),
            ]
            res = get_last_email("Hannah", app="auto")

            assert res["status"] == "success"
            assert res["app"] == "Apple Mail"
            assert res["subject"] == "Design System Update"
            assert "Figma tokens" in res["snippet"]


def test_get_last_email_not_found():
    """Verifies not_found response when contact has no emails."""
    with patch("sys.platform", "darwin"):
        with patch("desktop_dom.assistant.non_binary._run_applescript") as mock_osa:
            mock_osa.return_value = (0, "NO_MESSAGES_FOUND", "")
            res = get_last_email("Unknown Contact", app="Outlook")

            assert res["status"] == "not_found"
            assert "No recent emails found" in res["response"]
            assert res["subject"] is None


def test_get_last_email_non_darwin():
    """Verifies non-darwin platform degradation."""
    with patch("sys.platform", "win32"):
        res = get_last_email("Josh", app="Outlook")
        assert res["status"] == "error"
        assert "darwin" in res["message"]


# ============================================================================
# 5. Non-Binary Intent Router Tests
# ============================================================================

def test_route_non_binary_intent_calendar():
    """Verifies calendar briefing intent pattern routing."""
    with patch("desktop_dom.assistant.non_binary.get_calendar_briefing") as mock_cal:
        mock_cal.return_value = {"status": "success", "action": "calendar_briefing"}
        res = route_non_binary_intent("what's on my calendar today?")
        assert res is not None
        assert res["action"] == "calendar_briefing"
        mock_cal.assert_called_once()


def test_route_non_binary_intent_git_pr():
    """Verifies git PR status intent pattern routing."""
    with patch("desktop_dom.assistant.non_binary.get_git_pr_status") as mock_git:
        mock_git.return_value = {"status": "success", "action": "git_pr_status"}
        res = route_non_binary_intent("check git pr status")
        assert res is not None
        assert res["action"] == "git_pr_status"
        mock_git.assert_called_once()


def test_route_non_binary_intent_linear():
    """Verifies linear issues intent pattern routing."""
    with patch("desktop_dom.assistant.non_binary.get_linear_issues") as mock_linear:
        mock_linear.return_value = {"status": "success", "action": "linear_issues"}
        res = route_non_binary_intent("my linear issues")
        assert res is not None
        assert res["action"] == "linear_issues"
        mock_linear.assert_called_once()


def test_route_non_binary_intent_email():
    """Verifies last email intent pattern routing."""
    with patch("desktop_dom.assistant.non_binary.get_last_email") as mock_email:
        mock_email.return_value = {"status": "success", "action": "last_email_query"}
        res = route_non_binary_intent("last email from Cyril")
        assert res is not None
        assert res["action"] in ("last_email_query", "get_last_email")
        mock_email.assert_called_once_with(contact_name="cyril")


def test_route_non_binary_intent_unmatched():
    """Verifies unrelated query returns None."""
    res = route_non_binary_intent("play Synthwave Chill on Spotify")
    assert res is None


def test_non_binary_adapters_class_interface():
    """Verifies NonBinaryAdapters static interface matches standalone functions."""
    with patch("desktop_dom.assistant.non_binary.get_calendar_briefing") as m_cal, \
         patch("desktop_dom.assistant.non_binary.get_git_pr_status") as m_git, \
         patch("desktop_dom.assistant.non_binary.get_linear_issues") as m_lin, \
         patch("desktop_dom.assistant.non_binary.get_last_email") as m_mail:

        m_cal.return_value = {"status": "success"}
        m_git.return_value = {"status": "success"}
        m_lin.return_value = {"status": "success"}
        m_mail.return_value = {"status": "success"}

        assert NonBinaryAdapters.get_calendar_briefing()["status"] == "success"
        assert NonBinaryAdapters.get_git_pr_status()["status"] == "success"
        assert NonBinaryAdapters.get_linear_issues()["status"] == "success"
        assert NonBinaryAdapters.get_last_email("Josh")["status"] == "success"
