import time
import pytest
from unittest.mock import patch, MagicMock
from desktop_dom.assistant.context_feed import ContextFeedEngine, ActiveContextSnapshot
from desktop_dom.assistant.memory import AuraMemory
from desktop_dom.assistant.brain import AssistantBrain


@pytest.fixture
def mock_memory(tmp_path):
    db_file = tmp_path / "test_memory.db"
    mem = AuraMemory(db_path=db_file)
    return mem


def test_context_feed_engine_initialization(mock_memory):
    engine = ContextFeedEngine(memory=mock_memory)
    assert engine.memory == mock_memory

    # Verify context_feed table was created
    with mock_memory._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='context_feed';")
        row = cursor.fetchone()
        assert row is not None


def test_classify_activity_gaming(mock_memory):
    engine = ContextFeedEngine(memory=mock_memory)
    activity, topic, playlist, genre = engine.classify_activity(
        frontmost_app="FIFA 23",
        window_title="FIFA 23 - Ultimate Team",
    )
    assert activity == "Gaming"
    assert "FIFA" in topic
    assert playlist == "FIFA Soundtrack"
    assert genre == "Gaming Energy"


def test_classify_activity_coding(mock_memory):
    engine = ContextFeedEngine(memory=mock_memory)
    activity, topic, playlist, genre = engine.classify_activity(
        frontmost_app="Visual Studio Code",
        window_title="desktop-dom — brain.py",
    )
    assert activity == "Engineering"
    assert "desktop-dom" in topic or "Code" in topic
    assert playlist == "Deep Focus"
    assert genre == "Focus Beats"


def test_classify_activity_chrome_github(mock_memory):
    engine = ContextFeedEngine(memory=mock_memory)
    activity, topic, playlist, genre = engine.classify_activity(
        frontmost_app="Google Chrome",
        window_title="Pull Request #42 · PDgit12/desktop-dom",
        browser_name="Google Chrome",
        browser_title="Pull Request #42 · PDgit12/desktop-dom",
        browser_url="https://github.com/PDgit12/desktop-dom/pull/42",
    )
    assert activity == "Engineering"
    assert "GitHub: PDgit12/desktop-dom" in topic
    assert playlist == "Deep Focus"


def test_classify_activity_communication(mock_memory):
    engine = ContextFeedEngine(memory=mock_memory)
    activity, topic, playlist, genre = engine.classify_activity(
        frontmost_app="Microsoft Outlook",
        window_title="Inbox - josh@crcle.ai",
    )
    assert activity == "Communication"
    assert playlist == "Discover Weekly"


def test_record_and_fetch_snapshot(mock_memory):
    engine = ContextFeedEngine(memory=mock_memory)
    snap = ActiveContextSnapshot(
        timestamp=time.time(),
        frontmost_app="FIFA 23",
        window_title="Matchday",
        activity_category="Gaming",
        focused_topic="FIFA Gaming Session",
        suggested_playlist="FIFA Soundtrack",
        suggested_genre="Gaming Energy",
        browser_name=None,
        browser_url=None,
        browser_title=None,
        metadata={"test": True}
    )
    engine.record_snapshot(snap)

    history = engine.get_recent_history(limit=5)
    assert len(history) >= 1
    assert history[0]["frontmost_app"] == "FIFA 23"
    assert history[0]["activity_category"] == "Gaming"


def test_summarize_current_context(mock_memory):
    engine = ContextFeedEngine(memory=mock_memory)
    with patch.object(engine, "capture_active_context") as mock_cap:
        mock_cap.return_value = ActiveContextSnapshot(
            timestamp=time.time(),
            frontmost_app="Google Chrome",
            window_title="Crcle.ai - The Intent Layer",
            activity_category="Research",
            focused_topic="Crcle.ai - The Intent Layer",
            suggested_playlist="Lofi Beats",
            suggested_genre="Study / Instrumental",
            browser_name="Google Chrome",
            browser_url="https://crcle.ai",
            browser_title="Crcle.ai - The Intent Layer",
        )
        summary = engine.summarize_current_context()
        assert "Research" in summary
        assert "Google Chrome" in summary
        assert "https://crcle.ai" in summary
        assert "Lofi Beats" in summary


def test_brain_context_introspection_intent(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    with patch.object(brain.context_feed, "capture_active_context") as mock_cap:
        mock_cap.return_value = ActiveContextSnapshot(
            timestamp=time.time(),
            frontmost_app="Visual Studio Code",
            window_title="desktop-dom - brain.py",
            activity_category="Engineering",
            focused_topic="desktop-dom Core Development",
            suggested_playlist="Deep Focus",
            suggested_genre="Focus Beats",
            browser_name=None,
            browser_url=None,
            browser_title=None,
        )
        res = brain.execute_intent("what am I working on?")
        assert res.get("status") == "success"
        assert res.get("level") == "2.0"
        assert res.get("action") == "context_summary"
        assert res.get("activity") == "Engineering"
        assert "desktop-dom" in res.get("topic")


def test_brain_habit_recall_with_gaming_context(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    with patch.object(brain.context_feed, "capture_active_context") as mock_cap:
        mock_cap.return_value = ActiveContextSnapshot(
            timestamp=time.time(),
            frontmost_app="FIFA 23",
            window_title="Matchday",
            activity_category="Gaming",
            focused_topic="FIFA Gaming Session",
            suggested_playlist="FIFA Soundtrack",
            suggested_genre="Gaming Energy",
            browser_name=None,
            browser_url=None,
            browser_title=None,
        )
        with patch.object(brain, "_control_spotify_play") as mock_play:
            mock_play.return_value = {"status": "success"}
            res = brain.execute_intent("play my playlist")
            assert res.get("status") == "success"
            assert res.get("level") == "2.0"
            assert res.get("playlist") == "FIFA Soundtrack"
            assert res.get("context") == "Gaming Energy"
            assert res.get("activity") == "Gaming"


def test_brain_email_josh_context_enrichment(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    # Ensure Josh exists in memory
    josh = mock_memory.resolve_entity("Josh")
    assert josh is not None

    with patch.object(brain.context_feed, "capture_active_context") as mock_cap:
        mock_cap.return_value = ActiveContextSnapshot(
            timestamp=time.time(),
            frontmost_app="Google Chrome",
            window_title="Crcle Deck v2 - Slides",
            activity_category="Research",
            focused_topic="Crcle Deck v2",
            suggested_playlist="Lofi Beats",
            suggested_genre="Study / Instrumental",
            browser_name="Google Chrome",
            browser_url="https://docs.google.com/presentation/d/crcle-deck",
            browser_title="Crcle Deck v2 - Slides",
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            res = brain.execute_intent("message Josh")
            assert res.get("status") == "success"
            assert res.get("level") == "2.5"
            assert res.get("recipient") == "Joshua Rayan"
            assert res.get("email") == "josh@crcle.ai"
            assert "Crcle Deck v2" in res.get("subject")
            assert res.get("verified") is True


def test_youtube_recommendation_engineering_context(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    with patch.object(brain.context_feed, "capture_active_context") as mock_cap:
        mock_cap.return_value = ActiveContextSnapshot(
            timestamp=time.time(),
            frontmost_app="Visual Studio Code",
            window_title="desktop-dom - brain.py",
            activity_category="Engineering",
            focused_topic="Systems Development",
            suggested_playlist="Deep Focus",
            suggested_genre="Focus Beats",
            browser_name=None,
            browser_url=None,
            browser_title=None,
        )
        with patch("webbrowser.open") as mock_open:
            res = brain.execute_intent("open youtube")
            assert res.get("status") == "success"
            assert res.get("action") == "youtube_intent"
            assert res.get("level") == "2.0"
            assert res.get("channel") == "ThePrimeagen"
            assert res.get("category") == "Engineering"
            assert "youtube.com" in res.get("url")


def test_youtube_recommendation_gaming_context(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    with patch.object(brain.context_feed, "capture_active_context") as mock_cap:
        mock_cap.return_value = ActiveContextSnapshot(
            timestamp=time.time(),
            frontmost_app="FIFA 23",
            window_title="Matchday",
            activity_category="Gaming",
            focused_topic="FIFA Gaming Session",
            suggested_playlist="FIFA Soundtrack",
            suggested_genre="Gaming Energy",
            browser_name=None,
            browser_url=None,
            browser_title=None,
        )
        with patch("webbrowser.open") as mock_open:
            res = brain.execute_intent("watch youtube")
            assert res.get("status") == "success"
            assert res.get("action") == "youtube_intent"
            assert res.get("level") == "2.0"
            assert res.get("channel") == "EA SPORTS FC"
            assert res.get("category") == "Gaming"


def test_youtube_explicit_watch_fireship(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    with patch("webbrowser.open") as mock_open:
        res = brain.execute_intent("watch fireship")
        assert res.get("status") == "success"
        assert res.get("action") == "youtube_intent"
        assert res.get("level") == "2.0"
        assert res.get("channel") == "Fireship"
        assert "@Fireship" in res.get("url")


def test_youtube_remember_favorite_channel(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    res_rem = brain.execute_intent("remember my favorite youtube channel for tech is Fireship")
    assert res_rem.get("status") == "success"
    assert mock_memory.get_preference("youtube.favorite_channel.tech") == "Fireship"

    with patch.object(brain.context_feed, "capture_active_context") as mock_cap:
        mock_cap.return_value = ActiveContextSnapshot(
            timestamp=time.time(),
            frontmost_app="Terminal",
            window_title="zsh",
            activity_category="Engineering",
            focused_topic="Software Engineering",
            suggested_playlist="Deep Focus",
            suggested_genre="Focus Beats",
            browser_name=None,
            browser_url=None,
            browser_title=None,
        )
        with patch("webbrowser.open") as mock_open:
            res = brain.execute_intent("open youtube")
            assert res.get("channel") == "Fireship"


def test_github_developer_repo_intent(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    with patch("webbrowser.open") as mock_open:
        res = brain.execute_intent("open my repo")
        assert res.get("status") == "success"
        assert res.get("action") == "open_github_repo"
        assert res.get("level") == "2.0"
        assert "PDgit12/desktop-dom" in res.get("repo")
        assert "github.com/PDgit12/desktop-dom" in res.get("url")

        res_pr = brain.execute_intent("open pull requests")
        assert res_pr.get("status") == "success"
        assert "/pulls" in res_pr.get("url")


def test_calendar_schedule_intent(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        res = brain.execute_intent("check my schedule")
        assert res.get("status") == "success"
        assert res.get("action") == "open_calendar"
        assert res.get("level") == "2.0"


def test_daily_routine_morning_execution(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    with patch("subprocess.run") as mock_run, patch("webbrowser.open") as mock_open, patch.object(brain, "_control_spotify_play") as mock_spot:
        mock_run.return_value = MagicMock(returncode=0)
        res = brain.execute_intent("start my day")
        assert res.get("status") == "success"
        assert res.get("action") == "daily_routine"
        assert res.get("level") == "2.5"
        assert len(res.get("executed_steps", [])) >= 2


def test_daily_routine_gaming_execution(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    with patch("subprocess.run") as mock_run, patch.object(brain, "_control_spotify_play") as mock_spot:
        mock_run.return_value = MagicMock(returncode=0)
        res = brain.execute_intent("gaming mode")
        assert res.get("status") == "success"
        assert res.get("action") == "daily_routine"
        assert res.get("routine") == "gaming"


def test_remember_daily_routine(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    res = brain.execute_intent("remember my morning routine is open VS Code and play Lofi Beats")
    assert res.get("status") == "success"
    assert "open VS Code" in mock_memory.get_preference("routine.morning.desc")


def test_sync_local_persona(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    with patch.object(mock_memory, "sync_local_persona") as mock_sync:
        mock_sync.return_value = {
            "status": "success",
            "git_identity": {"name": "PDgit12", "email": "piyushdua01@gmail.com"},
            "youtube_entries_ingested": 15,
            "top_sites_ingested": 10,
            "contacts_synced": 5,
        }
        res = brain.execute_intent("sync my data")
        assert res.get("status") == "success"
        assert res.get("action") == "sync_local_persona"
        assert "15 YouTube items" in res.get("response", "")


def test_habit_anti_drift_explicit_lock(mock_memory):
    # 1. Lock explicit habit
    res1 = mock_memory.record_habit_observation("spotify.favorite_playlist", "Karan Aujla Hits", is_explicit=True)
    assert res1["action"] == "locked_explicit"
    assert res1["confidence"] == 1.0

    # 2. Transient passive observation of another playlist should be REJECTED
    res2 = mock_memory.record_habit_observation("spotify.favorite_playlist", "Random Coffee Lofi", is_explicit=False)
    assert res2["action"] == "drift_rejected"

    # 3. Resolved value remains strictly the locked ground truth
    assert mock_memory.resolve_habit("spotify.favorite_playlist") == "Karan Aujla Hits"


def test_habit_anti_drift_passive_hysteresis(mock_memory):
    # 1. First passive observation creates candidate with 0.5 confidence
    res1 = mock_memory.record_habit_observation("media.genre", "Tech Podcasts", is_explicit=False)
    assert res1["action"] == "created"
    assert res1["confidence"] == 0.50

    # 2. Conflicting passive observation decays confidence instead of immediately switching
    res2 = mock_memory.record_habit_observation("media.genre", "Cooking Shows", is_explicit=False)
    assert res2["action"] == "decayed_old"
    assert res2["confidence"] < 0.50

    # 3. Same observation reinforces habit
    res3 = mock_memory.record_habit_observation("media.genre", "Tech Podcasts", is_explicit=False)
    assert res3["action"] == "reinforced"


def test_playlist_recall_exact_order_and_explicit_priority(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    # Set explicit personal favorite playlist
    mock_memory.record_habit_observation("spotify.favorite_playlist", "Diljit Dosanjh Essentials", is_explicit=True)

    with patch.object(brain.context_feed, "capture_active_context") as mock_cap, patch.object(brain, "_control_spotify_play") as mock_spot:
        # 1. Active gaming context routes to gaming playlist
        mock_cap.return_value = ActiveContextSnapshot(
            timestamp=time.time(),
            frontmost_app="FIFA 23",
            window_title="Matchday",
            activity_category="Gaming",
            focused_topic="Gaming Session",
            suggested_playlist="FIFA Soundtrack",
            suggested_genre="Gaming Energy",
            browser_name=None,
            browser_url=None,
            browser_title=None,
        )
        mock_spot.return_value = {"status": "success"}

        res_gaming = brain.execute_intent("open playlist")
        assert res_gaming.get("status") == "success"
        assert res_gaming.get("playlist") == "FIFA Soundtrack"
        assert res_gaming.get("context") == "Gaming Energy"
        assert "exact track order" in res_gaming.get("response", "")

        # 2. In non-gaming context, explicit personal favorite takes priority over generic defaults
        mock_cap.return_value = ActiveContextSnapshot(
            timestamp=time.time(),
            frontmost_app="Google Chrome",
            window_title="New Tab",
            activity_category="General",
            focused_topic="Browsing",
            suggested_playlist=None,
            suggested_genre=None,
            browser_name="Google Chrome",
            browser_url="chrome://newtab",
            browser_title="New Tab",
        )
        res_fav = brain.execute_intent("open playlist")
        assert res_fav.get("status") == "success"
        assert res_fav.get("playlist") == "Diljit Dosanjh Essentials"
        assert res_fav.get("context") == "Personal Favorite"


def test_youtube_default_home_feed_no_fireship(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    with patch.object(brain.context_feed, "capture_active_context") as mock_cap, patch("webbrowser.open") as mock_open:
        mock_cap.return_value = ActiveContextSnapshot(
            timestamp=time.time(),
            frontmost_app="Finder",
            window_title="Desktop",
            activity_category="General",
            focused_topic="Desktop",
            suggested_playlist=None,
            suggested_genre=None,
            browser_name=None,
            browser_url=None,
            browser_title=None,
        )
        res = brain.execute_intent("open youtube")
        assert res.get("status") == "success"
        assert res.get("action") == "youtube_intent"
        # Must NOT force Fireship by default!
        assert res.get("channel") == "YouTube"
        assert res.get("url") == "https://www.youtube.com"
        assert "Fireship" not in res.get("url")

        # Explicit search for Diljit Dosanjh
        res_music = brain.execute_intent("watch Diljit Dosanjh")
        assert res_music.get("status") == "success"
        assert res_music.get("channel") == "Diljit Dosanjh"
        assert "Diljit" in res_music.get("url")


def test_outlook_email_formatting_and_signature(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        # Command with colloquial phrasing and message content
        res = brain.execute_intent("message josh that the deck is ready")
        assert res.get("status") == "success"
        assert res.get("level") == "2.5"
        assert res.get("recipient") == "Joshua Rayan"
        assert res.get("email") == "josh@crcle.ai"
        assert res.get("client") == "Microsoft Outlook"
        # Subject must be properly capitalized and formatted (not 'That the deck is ready')
        assert "Pitch Deck" in res.get("subject", "") or "Deck" in res.get("subject", "")
        # Body must have proper salutation, content, and professional signoff
        draft_body = res.get("draft_body", "")
        assert "Hi Joshua," in draft_body or "Hi Josh," in draft_body
        assert "The deck is ready." in draft_body
        assert "Best regards," in draft_body
        assert "Piyush Dua" in draft_body
        assert "Backend Engineer | Crcle.ai" in draft_body
        # Verify AppleScript received the formatted draft body
        args = mock_run.call_args[0][0]
        script_sent = args[2]
        assert "plain text content:" in script_sent
        assert "Hi Joshua" in script_sent or "Hi Josh" in script_sent
        assert "Piyush Dua" in script_sent


def test_user_profile_and_essentials_inspection(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    res = brain.execute_intent("who am i?")
    assert res.get("status") == "success"
    assert res.get("action") == "user_profile"
    assert res.get("level") == "2.0"
    profile = res.get("profile", {})
    assert profile.get("name") == "Piyush Dua"
    assert profile.get("role") == "Backend Engineer"
    assert profile.get("company") == "Crcle.ai"
    assert profile.get("email") == "piyushdua01@gmail.com"
    assert profile.get("preferred_mail") == "Microsoft Outlook"
    assert profile.get("github_repo") == "PDgit12/desktop-dom"
    assert profile.get("exact_track_order") is True
    assert "Piyush Dua" in res.get("response", "")
    assert "Crcle.ai" in res.get("response", "")


def test_habits_and_preferences_inspection(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    res = brain.execute_intent("what are my habits?")
    assert res.get("status") == "success"
    assert res.get("action") == "list_habits"
    assert res.get("level") == "2.0"
    assert isinstance(res.get("habits"), list)
    assert "anti-drift protection" in res.get("response", "")




