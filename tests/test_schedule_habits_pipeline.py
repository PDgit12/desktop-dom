import json
import re
import sys
import pytest
from unittest.mock import MagicMock, patch

from desktop_dom.assistant.brain import AssistantBrain
from desktop_dom.assistant.memory import AuraMemory
from desktop_dom.assistant.non_binary import get_calendar_briefing, route_non_binary_intent


@pytest.fixture
def clean_brain_env(tmp_path):
    """Provides an isolated AssistantBrain and AuraMemory instance."""
    db_file = tmp_path / "test_schedule_habits.db"
    mem = AuraMemory(db_path=str(db_file))
    mem.set_preference("user.name", "Piyush Dua", category="user")
    mem.set_preference("user.email", "piyush@example.com", category="user")
    mem.set_preference("apps.primary_meeting", "Granola", category="apps")
    brain = AssistantBrain(memory=mem)
    return mem, brain


def test_schedule_intent_name_prefixed_returns_calendar_briefing_not_google(clean_brain_env):
    """
    Verifies that 'Piyush Dua schedule' routes to calendar briefing
    and NEVER opens a Google search in the browser.
    """
    mem, brain = clean_brain_env

    # Seed mock canonical calendar events from Composio/Apple Calendar
    mock_events = [
        {
            "id": "evt_arch_1",
            "title": "Architecture & Model Sync",
            "start_time": "10:00 AM",
            "end_time": "10:45 AM",
            "meeting_url": "https://meet.google.com/abc-defg-hij",
            "attendees": ["Joshua Rayan", "Cyril Rayan"],
        }
    ]
    mem.set_preference("calendar.events.today", json.dumps(mock_events), category="calendar")

    with patch("webbrowser.open") as mock_browser:
        res = brain.execute_intent("Piyush Dua schedule")

        # Must execute calendar briefing
        assert res["status"] == "success"
        assert res["action"] in ["open_calendar", "calendar_briefing"]
        assert res["event_count"] == 1
        assert "Architecture & Model Sync" in res["response"]
        assert "https://meet.google.com/abc-defg-hij" in res["response"]

        # MUST NEVER open a Google search in browser
        mock_browser.assert_not_called()
        for call in mock_browser.call_args_list:
            assert "google.com/search" not in str(call)


def test_schedule_intent_natural_language_variations(clean_brain_env):
    """
    Verifies that natural variations ('my schedule', 'check schedule', 'calendar', 'today's schedule')
    all resolve deterministically to calendar briefing without LLM web search.
    """
    mem, brain = clean_brain_env
    mock_events = [
        {
            "id": "evt_2",
            "title": "Product Demo Review",
            "start_time": "3:00 PM",
            "end_time": "3:30 PM",
            "meeting_url": "https://zoom.us/j/1234567890",
            "attendees": ["Team Member"],
        }
    ]
    mem.set_preference("calendar.events.today", json.dumps(mock_events), category="calendar")

    queries = [
        "my schedule",
        "check schedule",
        "what is my schedule",
        "what's my schedule",
        "today's schedule",
        "calendar",
        "what is on my calendar",
        "upcoming meetings",
    ]

    for q in queries:
        with patch("webbrowser.open") as mock_browser:
            res = brain.execute_intent(q)
            assert res["status"] == "success", f"Failed on query: {q}"
            assert res["action"] in ["open_calendar", "calendar_briefing"], f"Expected calendar action on: {q}"
            assert "Product Demo Review" in res["response"]
            mock_browser.assert_not_called()


def test_schedule_briefing_self_learns_meeting_platform_habit(clean_brain_env):
    """
    Verifies that when calendar events contain meeting links,
    Aura self-learns and reinforces the meeting platform habit in sovereign memory.
    """
    mem, brain = clean_brain_env
    mock_events = [
        {
            "id": "evt_zoom_1",
            "title": "Executive Standup",
            "start_time": "9:00 AM",
            "end_time": "9:30 AM",
            "meeting_url": "https://zoom.us/j/9988776655",
            "attendees": ["Founders"],
        }
    ]
    mem.set_preference("calendar.events.today", json.dumps(mock_events), category="calendar")

    res = brain.execute_intent("check my schedule")
    assert res["status"] == "success"

    # Habit must be recorded in memory
    learned_platform = mem.resolve_habit("meeting.platform")
    assert learned_platform == "Zoom"


def test_meeting_intent_enriches_and_launches_notes_companion_and_platform(clean_brain_env):
    """
    Verifies that 'I have a meeting':
    1. Detects upcoming meeting and platform (Zoom/Meet).
    2. Opens notes companion (Granola).
    3. Records meeting platform and notes companion habits.
    4. Provides structured link and attendee details.
    """
    mem, brain = clean_brain_env
    mock_events = [
        {
            "id": "evt_next_1",
            "title": "Investor Architecture Walkthrough",
            "start_time": "11:00 AM",
            "end_time": "11:45 AM",
            "meeting_url": "https://meet.google.com/xyz-uvwx-rst",
            "attendees": ["Partner"],
        }
    ]
    mem.set_preference("calendar.events.today", json.dumps(mock_events), category="calendar")
    mem.set_preference("apps.primary_meeting", "Granola", category="apps")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        res = brain.execute_intent("I have a meeting")

        assert res["status"] == "success"
        assert res["action"] == "meeting_intent"
        assert res["tool"] == "Granola"
        assert res["meeting_platform"] == "Google Meet"
        assert res["meeting_url"] == "https://meet.google.com/xyz-uvwx-rst"
        assert "https://meet.google.com/xyz-uvwx-rst" in res["response"]
        assert "Granola" in res["response"]

        # Verified habits saved to memory
        assert mem.resolve_habit("meeting.platform") == "Google Meet"
        assert mem.resolve_habit("meeting.notes_companion") == "Granola"


def test_daily_playlist_habit_playback_and_learning(clean_brain_env):
    """
    Verifies that user can set their daily playlist, and asking 'play my playlist'
    or 'play daily playlist' plays that exact playlist and reinforces anti-drift memory.
    """
    mem, brain = clean_brain_env

    # 1. Set daily playlist
    set_res = brain.execute_intent("set daily playlist to Midnight Lo-Fi")
    assert set_res["status"] == "success"
    assert mem.resolve_habit("spotify.favorite_playlist") == "Midnight Lo-Fi"

    # 2. Play daily playlist
    with patch.object(brain, "_control_spotify_play", return_value={"status": "success", "action": "spotify_play"}) as mock_play:
        res = brain.execute_intent("play my daily playlist")
        assert res["status"] == "success"
        assert res["action"] == "spotify_playlist"
        assert res["playlist"] == "Midnight Lo-Fi"
        mock_play.assert_called_once_with("Midnight Lo-Fi")

    # 3. 'play my playlist' natural phrasing
    with patch.object(brain, "_control_spotify_play", return_value={"status": "success", "action": "spotify_play"}) as mock_play2:
        res2 = brain.execute_intent("play my playlist")
        assert res2["status"] == "success"
        assert res2["playlist"] == "Midnight Lo-Fi"
        mock_play2.assert_called_once_with("Midnight Lo-Fi")


def test_web_search_guard_intercepts_personal_queries(clean_brain_env):
    """
    Verifies that prompts like 'search Piyush Dua schedule' or 'search for my playlist'
    are intercepted by the search guard and NEVER open Google in the browser.
    """
    mem, brain = clean_brain_env
    mem.record_habit_observation("spotify.favorite_playlist", "Focus Flow", category="music", is_explicit=True)

    with patch("webbrowser.open") as mock_browser:
        # Schedule query disguised with 'search'
        res_sched = brain.execute_intent("search Piyush Dua schedule")
        assert res_sched["action"] in ["open_calendar", "calendar_briefing"]
        mock_browser.assert_not_called()

        # Playlist query disguised with 'search'
        with patch.object(brain, "_control_spotify_play", return_value={"status": "success", "action": "spotify_play"}):
            res_music = brain.execute_intent("search for my playlist")
            assert res_music["action"] == "spotify_playlist"
            mock_browser.assert_not_called()


def test_empty_schedule_returns_clean_informative_message(clean_brain_env):
    """
    Verifies that when no events exist on today's calendar,
    Aura returns a clean, non-AI notification without error or search fallback.
    """
    mem, brain = clean_brain_env
    mem.set_preference("calendar.events.today", "[]", category="calendar")

    with patch("sys.platform", "darwin"), patch("desktop_dom.assistant.non_binary._run_applescript", return_value=(0, "", "")):
        res = brain.execute_intent("check my schedule")
        assert res["status"] == "success"
        assert res["action"] in ["open_calendar", "calendar_briefing"]
        assert res["event_count"] == 0
        assert "No upcoming events scheduled for today" in res["response"]
