import time
import json
from unittest.mock import patch, MagicMock
import pytest

from desktop_dom.assistant.memory import AuraMemory
from desktop_dom.assistant.brain import AssistantBrain
from desktop_dom.assistant.omnibar import FloatingOmnibar


def test_fresh_user_onboarding_and_zero_speculation_execution(tmp_path):
    """
    Hermetic test verifying that starting with a completely fresh user database,
    onboarding seals pure user data into the Knowledge Graph, and all subsequent
    Level 2 / Level 2.5 intent actions execute strictly from verified user state
    with zero hallucination, zero ambient YouTube/Fireship drift, and strict cluster isolation.
    """
    db_file = tmp_path / "fresh_user_aura.db"
    mem = AuraMemory(db_path=str(db_file))

    # 1. Provide Pure User Onboarding Data
    fresh_profile = {
        "user_name": "Piyush Dua",
        "user_email": "piyushdua01@gmail.com",
        "user_role": "Backend Engineer",
        "user_company": "Crcle.ai",
        "app_bindings": {
            "browser": "Google Chrome",
            "mail": "Microsoft Outlook",
            "terminal": "Terminal",
            "ai": "ChatGPT",
            "music": "Spotify",
            "editor": "Zed",
        },
        "playlists": {
            "focus": "Deep Focus",
            "gaming": "Gaming Soundtrack",
            "personal": "Ambient Chill",
        },
        "collaborators": [
            {"name": "Joshua Rayan", "role": "Founder / CTO", "company": "Crcle.ai", "email": "josh@crcle.ai"},
            {"name": "Cyril Rayan", "role": "Founder / CEO", "company": "Crcle.ai", "email": "cyril@crcle.ai"},
        ],
        "work_repos": ["desktop-dom"],
        "default_repo": "PDgit12/desktop-dom",
    }

    # Complete onboarding
    result = mem.complete_verified_onboarding(fresh_profile)
    assert result["status"] == "success"
    assert result["verified"] is True
    assert result["mode"] == "pure_user_data"
    assert result["user_name"] == "Piyush Dua"
    assert result["user_role"] == "Backend Engineer"
    assert result["user_company"] == "Crcle.ai"
    assert result["collaborators_count"] == 2
    assert result["cluster_isolation_verified"] is True

    # Check verified preferences and habit locks
    assert mem.is_onboarding_verified() is True
    assert mem.get_preference("user.name") == "Piyush Dua"
    assert mem.get_preference("user.company") == "Crcle.ai"
    assert mem.get_preference("mail.preferred_client") == "Microsoft Outlook"
    assert mem.get_preference("spotify.favorite_playlist") == "Deep Focus"
    assert mem.resolve_habit("spotify.favorite_playlist") == "Deep Focus"

    # Confirm NO synthetic YouTube channel is seeded
    assert mem.get_preference("youtube.favorite_channel.tech") is None
    assert mem.get_preference("youtube.favorite_channel") is None

    # Initialize Assistant Brain with fresh verified memory
    brain = AssistantBrain(preferred_model="ministral-3:8b", memory=mem)

    # 2. Test Work Email Drafting to Joshua Rayan
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        email_res = brain.execute_intent("write an email to josh saying the intent layer is finalized")
        assert email_res["status"] == "success"
        assert email_res["action"] == "send_message"
        assert email_res["recipient"] == "Joshua Rayan"
        assert email_res["email"] == "josh@crcle.ai"
        assert email_res["client"] == "Microsoft Outlook"
        assert "intent layer is finalized" in email_res["draft_body"].lower()
        assert "Piyush Dua" in email_res["draft_body"]
        assert "Backend Engineer | Crcle.ai" in email_res["signature"]

        # Anti-leakage check: absolutely no personal media in work email
        assert "Ambient Chill" not in email_res["draft_body"]
        assert "YouTube" not in email_res["draft_body"]
        assert "Fireship" not in email_res["draft_body"]

    # 3. Test Work Message to Cyril Rayan
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        cyril_res = brain.execute_intent("message cyril backend tests passing 100%")
        assert cyril_res["status"] == "success"
        assert cyril_res["action"] == "send_message"
        assert cyril_res["recipient"] == "Cyril Rayan"
        assert cyril_res["email"] == "cyril@crcle.ai"
        assert "backend tests passing 100%" in cyril_res["draft_body"].lower()

    # 4. Test Habitual Spotify Intent (Exact Track Order, No Speculation)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        spot_res = brain.execute_intent("play focus playlist")
        assert spot_res["status"] == "success"
        assert spot_res["action"] in ["spotify_play", "spotify_playlist"]
        assert "Deep Focus" in (spot_res.get("playlist") or spot_res.get("query", ""))

    # 5. Test Developer Work Repo Intent
    with patch("webbrowser.open") as mock_open:
        repo_res = brain.execute_intent("open my repo")
        assert repo_res["status"] == "success"
        assert "github.com/PDgit12/desktop-dom" in repo_res["url"]

    # 6. Test YouTube Intent (Strict Neutrality - No Fireship, No ThePrimeagen)
    with patch("webbrowser.open") as mock_open:
        yt_home_res = brain.execute_intent("open youtube")
        assert yt_home_res["status"] == "success"
        assert yt_home_res["url"] == "https://www.youtube.com"
        assert yt_home_res["channel"] == "YouTube"
        assert "Fireship" not in yt_home_res["url"]
        assert "ThePrimeagen" not in yt_home_res["url"]

    # 7. Test Disjoint Cluster Isolation
    shared_ctx = mem.find_shared_context("Joshua Rayan", "Ambient Chill")
    assert shared_ctx["status"] == "disjoint"
    assert shared_ctx["distance"] == float("inf")
