import time
import json
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
        frontmost_app="Steam",
        window_title="Game Session",
    )
    assert activity == "Gaming"
    assert "Gaming" in topic
    assert playlist == "Gaming Soundtrack"
    assert genre == "Gaming Energy"

    # With user-configured gaming playlist in memory
    mock_memory.set_preference("spotify.playlist.gaming", "Synthwave Energy", category="music")
    _, _, custom_playlist, _ = engine.classify_activity(
        frontmost_app="Steam",
        window_title="Game Session",
    )
    assert custom_playlist == "Synthwave Energy"


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
        # Default without explicit preference: opens YouTube Home cleanly (Zero Speculation)
        with patch("webbrowser.open") as mock_open:
            res_default = brain.execute_intent("watch youtube")
            assert res_default.get("status") == "success"
            assert res_default.get("channel") == "YouTube"
            assert res_default.get("url") == "https://www.youtube.com"

        # Explicit user preference set:
        mock_memory.set_preference("youtube.favorite_channel.tech", "Go Conferences")
        with patch("webbrowser.open") as mock_open:
            res = brain.execute_intent("watch youtube")
            assert res.get("status") == "success"
            assert res.get("action") == "youtube_intent"
            assert res.get("level") == "2.0"
            assert res.get("channel") == "Go Conferences"
            assert res.get("category") == "Engineering"
            assert "youtube.com" in res.get("url")


def test_youtube_recommendation_gaming_context(mock_memory):
    mock_memory.set_preference("youtube.favorite_channel.gaming", "EA SPORTS FC")
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


def test_youtube_explicit_creator_search(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    with patch("webbrowser.open") as mock_open:
        res = brain.execute_intent("watch python tutorial")
        assert res.get("status") == "success"
        assert res.get("action") == "youtube_intent"
        assert res.get("level") == "2.0"
        assert "python" in res.get("url").lower()
        assert "search_query" in res.get("url")


def test_youtube_remember_favorite_channel(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    res_rem = brain.execute_intent("remember my favorite youtube channel for tech is Computerphile")
    assert res_rem.get("status") == "success"
    assert mock_memory.get_preference("youtube.favorite_channel.tech") == "Computerphile"

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
            res = brain.execute_intent("watch youtube")
            assert res.get("channel") == "Computerphile"


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
    mock_memory.record_habit_observation("spotify.favorite_playlist", "Ambient Chill", is_explicit=True)

    with patch.object(brain.context_feed, "capture_active_context") as mock_cap, patch.object(brain, "_control_spotify_play") as mock_spot:
        # 1. Active gaming context routes to gaming playlist
        mock_cap.return_value = ActiveContextSnapshot(
            timestamp=time.time(),
            frontmost_app="Steam",
            window_title="Game Session",
            activity_category="Gaming",
            focused_topic="Gaming Session",
            suggested_playlist="Gaming Soundtrack",
            suggested_genre="Gaming Energy",
            browser_name=None,
            browser_url=None,
            browser_title=None,
        )
        mock_spot.return_value = {"status": "success"}

        res_gaming = brain.execute_intent("open playlist")
        assert res_gaming.get("status") == "success"
        assert res_gaming.get("playlist") == "Gaming Soundtrack"
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
        assert res_fav.get("playlist") == "Ambient Chill"
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

        # Explicit search for 3Blue1Brown
        res_math = brain.execute_intent("watch 3Blue1Brown")
        assert res_math.get("status") == "success"
        assert res_math.get("channel") == "3Blue1Brown"
        assert "3Blue1Brown" in res_math.get("url")


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


def test_email_draft_filters_personal_media_leakage(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    # Simulate user having YouTube active in Chrome with Diljit Dosanjh
    with patch.object(brain.context_feed, "capture_active_context") as mock_cap, patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_cap.return_value = ActiveContextSnapshot(
            timestamp=time.time(),
            frontmost_app="Google Chrome",
            window_title="(6) Diljit Dosanjh latest - YouTube",
            activity_category="Media",
            focused_topic="(6) Diljit Dosanjh latest - YouTube",
            suggested_playlist=None,
            suggested_genre=None,
            browser_name="Google Chrome",
            browser_url="https://www.youtube.com/watch?v=xyz",
            browser_title="(6) Diljit Dosanjh latest - YouTube",
        )
        res = brain.execute_intent("message Josh")
        assert res.get("status") == "success"
        assert res.get("level") == "2.5"
        draft_body = res.get("draft_body", "")

        # CRITICAL INTENT RULE: Never leak personal media or YouTube titles into work emails!
        assert "Diljit" not in draft_body
        assert "YouTube" not in draft_body
        assert "(6)" not in draft_body
        assert "Diljit" not in res.get("subject", "")

        # Must sign with real human name "Piyush Dua", NEVER git handle "PDgit12"!
        assert "Piyush Dua" in draft_body
        assert "PDgit12" not in draft_body
        assert "Backend Engineer | Crcle.ai" in draft_body


def test_signature_uses_human_name_not_git_handle(mock_memory):
    # Even if git handle is stored in preferences as PDgit12
    mock_memory.set_preference("user.name", "PDgit12")
    profile = mock_memory.get_user_profile()
    assert profile["name"] == "Piyush Dua"
    assert "Piyush Dua" in profile["signature"]
    assert "PDgit12" not in profile["signature"]


def test_knowledge_graph_bootstrap_and_topology(mock_memory):
    summary = mock_memory.get_graph_summary()
    assert summary["nodes_count"] >= 7
    assert summary["edges_count"] >= 8
    assert "work" in summary["clusters"]
    assert "apps" in summary["clusters"]

    # When personal media and gaming are added during onboarding
    mock_memory.add_edge("Piyush Dua", "Deep Focus", "listens_to", cluster="personal_media")
    mock_memory.add_edge("Piyush Dua", "FIFA 23", "plays", cluster="gaming")

    ascii_view = mock_memory.format_graph_ascii()
    assert "AURA SEMANTIC KNOWLEDGE GRAPH" in ascii_view
    assert "Work Cluster" in ascii_view
    assert "Personal Media Cluster" in ascii_view
    assert "Gaming Cluster" in ascii_view


def test_knowledge_graph_edge_crud(mock_memory):
    # Add new dynamic relation
    ok = mock_memory.add_edge("Piyush Dua", "Anthropic", "researches", cluster="research", weight=0.92)
    assert ok is True

    # Verify connected nodes
    conns = mock_memory.get_connected_nodes("Piyush Dua", relation="researches")
    assert len(conns) >= 1
    assert conns[0]["node_name"] == "Anthropic"
    assert conns[0]["cluster"] == "research"

    # Query triplet
    triplets = mock_memory.query_graph(subject="Piyush", relation="researches")
    assert len(triplets) >= 1
    assert triplets[0]["target_name"] == "Anthropic"

    # Remove relation
    removed = mock_memory.remove_edge("Piyush Dua", "Anthropic", "researches")
    assert removed is True
    assert len(mock_memory.get_connected_nodes("Piyush Dua", relation="researches")) == 0


def test_knowledge_graph_shared_context_and_disjoint_isolation(mock_memory):
    # Work context: Piyush Dua <-> Joshua Rayan
    work_shared = mock_memory.find_shared_context("Piyush Dua", "Joshua Rayan")
    assert work_shared["status"] == "connected"
    assert work_shared["primary_topic"] == "desktop-dom"
    assert work_shared["distance"] == 1
    shared_names = [e["name"] for e in work_shared["shared_entities"]]
    assert "Crcle.ai" in shared_names or "Microsoft Outlook" in shared_names

    # Add personal media and gaming clusters to test strict disjoint isolation
    mock_memory.add_edge("Piyush Dua", "Synthwave Chill", "listens_to", cluster="personal_media")
    mock_memory.add_edge("Piyush Dua", "FIFA 23", "plays", cluster="gaming")

    # Personal media context: Synthwave Chill <-> Joshua Rayan
    # Mathematical Guarantee: Personal media is strictly disjoint from work contacts!
    media_disjoint = mock_memory.find_shared_context("Synthwave Chill", "Joshua Rayan")
    assert media_disjoint["status"] == "disjoint"
    assert media_disjoint["primary_topic"] is None
    assert media_disjoint["distance"] == float("inf")
    assert len(media_disjoint["direct_relations"]) == 0
    assert len(media_disjoint["shared_entities"]) == 0

    # Gaming context: FIFA 23 <-> Joshua Rayan
    gaming_disjoint = mock_memory.find_shared_context("FIFA 23", "Joshua Rayan")
    assert gaming_disjoint["status"] == "disjoint"
    assert gaming_disjoint["primary_topic"] is None
    assert gaming_disjoint["distance"] == float("inf")


def test_knowledge_graph_natural_language_queries(mock_memory):
    brain = AssistantBrain(memory=mock_memory)

    # 1. Show graph
    res_graph = brain.execute_intent("show graph")
    assert res_graph["status"] == "success"
    assert res_graph["action"] == "knowledge_graph"
    assert res_graph["level"] == "2.5"
    assert "AURA SEMANTIC KNOWLEDGE GRAPH" in res_graph["response"]

    # 2. Connections for Josh
    res_conns = brain.execute_intent("who is connected to Josh?")
    assert res_conns["status"] == "success"
    assert res_conns["action"] == "graph_connections"
    assert "Joshua Rayan" in res_conns["target"]
    assert len(res_conns["connections"]) > 0

    # 3. Shared context query
    res_shared = brain.execute_intent("shared context between Piyush and Josh")
    assert res_shared["status"] == "success"
    assert res_shared["action"] == "shared_context"
    assert "desktop-dom" in res_shared["response"]

    # 4. Connect command
    res_link = brain.execute_intent("connect Cyril to Stanford as alumni")
    assert res_link["status"] == "success"
    assert res_link["action"] == "remember_graph_edge"
    assert "Connected" in res_link["response"]


def test_email_draft_grounds_in_knowledge_graph_topic(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    # Simulate active Spotify playing Diljit Dosanjh
    with patch.object(brain.context_feed, "capture_active_context") as mock_cap, patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_cap.return_value = ActiveContextSnapshot(
            timestamp=time.time(),
            frontmost_app="Spotify",
            window_title="Diljit Dosanjh - Lalkara",
            activity_category="Media",
            focused_topic="Diljit Dosanjh - Lalkara",
            suggested_playlist="Deep Focus",
            suggested_genre="Personal",
            browser_name=None,
            browser_url=None,
            browser_title=None,
        )
        res = brain.execute_intent("email Josh")
        assert res.get("status") == "success"
        draft_body = res.get("draft_body", "")

        # Knowledge Graph ground truth: drafts update on shared project desktop-dom
        assert "desktop-dom" in draft_body
        assert "desktop-dom" in res.get("subject", "")
        assert "Diljit" not in draft_body
        assert "Lalkara" not in draft_body
        assert "Piyush Dua" in draft_body


def test_ingest_most_used_apps_scoring_and_categorization(mock_memory):
    from desktop_dom.assistant.local_ingest import LocalMachineIngest
    ingest = LocalMachineIngest(memory=mock_memory)
    apps = ingest.ingest_most_used_apps(limit=10)
    assert len(apps) > 0
    # Must have name, category, role, relation, score
    for a in apps:
        assert "name" in a
        assert "category" in a
        assert "score" in a
        assert "role" in a
        assert "relation" in a
        assert a["score"] >= 5


def test_auto_hydrate_environment_ingests_top_apps_into_graph(mock_memory):
    summary = mock_memory.auto_hydrate_environment()
    assert summary["status"] == "success"
    assert "top_apps" in summary
    assert summary["top_apps_count"] > 0

    # Verify Knowledge Graph has app edges
    graph_edges = mock_memory._graph_edges
    app_edges = [e for e in graph_edges if e["cluster"] == "apps"]
    assert len(app_edges) > 0

    # Verify preferences set
    stored_apps = mock_memory.get_preference("apps.most_used")
    assert stored_apps is not None
    apps_list = json.loads(stored_apps)
    assert len(apps_list) > 0

    # Verify primary defaults
    assert mock_memory.get_preference("apps.primary_browser") in ["Google Chrome", "Safari"]
    assert mock_memory.get_preference("mail.preferred_client") == "Microsoft Outlook"


def test_brain_onboard_and_most_used_apps_intents(mock_memory):
    brain = AssistantBrain(memory=mock_memory)

    # 1. Onboarding command
    res_onboard = brain.execute_intent("/onboard")
    assert res_onboard["status"] == "success"
    assert res_onboard["action"] == "onboard"
    assert "Onboarded" in res_onboard["response"]
    assert "Piyush Dua" in res_onboard["response"]
    assert "Knowledge Graph" in res_onboard["response"]

    # 2. Most-used apps query
    res_apps = brain.execute_intent("most used apps")
    assert res_apps["status"] == "success"
    assert res_apps["action"] == "most_used_apps"
    assert "Your Most-Used Applications" in res_apps["response"]
    assert "Defaults: Browser:" in res_apps["response"]
    assert len(res_apps["apps"]) > 0


def test_intent_guard_youtube_clean_home_feed(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    with patch("webbrowser.open") as mock_open:
        # Generic open youtube must NOT hijack with arbitrary channels
        res = brain.execute_intent("open youtube")
        assert res["status"] == "success"
        assert res["action"] == "youtube_intent"
        assert res["url"] == "https://www.youtube.com"
        assert res["channel"] == "YouTube"
        assert "Opening YouTube Home" in res["response"]

        # Explicit creator watch query must route to requested creator
        res_creator = brain.execute_intent("watch Computerphile")
        assert res_creator["status"] == "success"
        assert res_creator["channel"] == "Computerphile"
        assert "Computerphile" in res_creator["url"]


def test_intent_guard_native_app_over_web_and_category_aliases(mock_memory):
    brain = AssistantBrain(memory=mock_memory)

    # Category alias resolution
    assert brain.resolve_app_name("browser") in ["Google Chrome", "Safari"]
    assert brain.resolve_app_name("mail") == "Microsoft Outlook"
    assert brain.resolve_app_name("music") == "Spotify"
    assert brain.resolve_app_name("terminal") == "Terminal"
    assert brain.resolve_app_name("ai") == "ChatGPT"

    # Native app priority in open_match
    with patch("subprocess.run") as mock_sub, patch("webbrowser.open") as mock_open:
        mock_sub.return_value.returncode = 0
        res = brain.execute_intent("open browser")
        assert res["status"] == "success"
        assert res["action"] == "open_app"
        assert res["target"] in ["Google Chrome", "Safari"]

        res_mail = brain.execute_intent("open mail")
        assert res_mail["status"] == "success"
        assert res_mail["action"] == "open_app"
        assert res_mail["target"] == "Microsoft Outlook"


def test_verified_onboarding_pure_user_data(mock_memory):
    profile_data = {
        "user_name": "Piyush Dua",
        "user_email": "piyush@crcle.ai",
        "user_role": "Staff Backend Engineer",
        "user_company": "Crcle.ai",
        "collaborators": [
            {"name": "Joshua Rayan", "role": "Founder / CTO", "company": "Crcle.ai", "email": "josh@crcle.ai"},
            {"name": "Cyril Rayan", "role": "Founder / CEO", "company": "Crcle.ai", "email": "cyril@crcle.ai"},
        ],
        "app_bindings": {
            "browser": "Google Chrome",
            "mail": "Microsoft Outlook",
            "terminal": "Terminal",
            "ai": "ChatGPT",
            "music": "Spotify",
        },
        "playlists": {
            "focus": "Deep Focus",
            "gaming": "Gaming Soundtrack",
            "personal": "Ambient Chill",
        },
        "work_repos": ["desktop-dom"],
    }

    res = mock_memory.complete_verified_onboarding(profile_data)
    assert res["status"] == "success"
    assert res["verified"] is True
    assert res["mode"] == "pure_user_data"
    assert res["user_name"] == "Piyush Dua"
    assert res["user_role"] == "Staff Backend Engineer"
    assert res["collaborators_count"] == 2
    assert mock_memory.is_onboarding_verified() is True

    # Check habit confidence is 1.0 (pure user ground truth, zero drift)
    with mock_memory._lock, mock_memory._get_connection() as conn:
        row = conn.execute("SELECT confidence, is_explicit FROM habits WHERE habit_key = 'spotify.favorite_playlist';").fetchone()
        assert row is not None
        assert row["confidence"] == 1.0
        assert row["is_explicit"] == 1

    # Check cluster isolation: Work vs Personal Media strictly disjoint
    isolation = mock_memory.find_shared_context("Joshua Rayan", "Ambient Chill")
    assert isolation["status"] == "disjoint"
    assert isolation["distance"] == float("inf")


def test_onboard_intent_response(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    res = brain.execute_intent("/onboard")
    assert res["status"] == "success"
    assert res["action"] == "onboard"
    assert res["verified"] is True
    assert "Knowledge Graph & Intent Engine Onboarded" in res["response"]
    assert "Strictly Disjoint" in res["response"] or "STRICT_DISJOINT" in res["response"]


def test_natural_language_profile_declarations(mock_memory):
    brain = AssistantBrain(memory=mock_memory)

    # 1. Update role
    res_role = brain.execute_intent("set my role to Lead Systems Engineer")
    assert res_role["status"] == "success"
    assert res_role["field"] == "role"
    assert mock_memory.get_preference("user.role") == "Lead Systems Engineer"

    # 2. Update company
    res_comp = brain.execute_intent("set my company to Acme Corp")
    assert res_comp["status"] == "success"
    assert res_comp["field"] == "company"
    assert mock_memory.get_preference("user.company") == "Acme Corp"

    # 3. Update focus playlist
    res_play = brain.execute_intent("set my focus playlist to Synthwave Chill")
    assert res_play["status"] == "success"
    assert res_play["field"] == "playlist"
    assert mock_memory.get_preference("spotify.favorite_playlist") == "Synthwave Chill"

    # 4. Add collaborator
    res_collab = brain.execute_intent("add collaborator Alex Rivera alex@acme.com")
    assert res_collab["status"] == "success"
    assert res_collab["action"] == "add_collaborator"
    assert res_collab["name"] == "Alex Rivera"
    assert mock_memory.resolve_entity("Alex Rivera") is not None


def test_email_draft_strictly_isolates_work_from_personal_media(mock_memory):
    brain = AssistantBrain(memory=mock_memory)
    mock_memory.complete_verified_onboarding()

    # Simulate user being on YouTube watching Diljit Dosanjh
    with patch.object(brain.context_feed, "capture_active_context") as mock_cap:
        mock_cap.return_value = ActiveContextSnapshot(
            timestamp=time.time(),
            frontmost_app="Google Chrome",
            window_title="(6) Diljit Dosanjh latest - YouTube",
            activity_category="Media",
            focused_topic="(6) Diljit Dosanjh latest - YouTube",
            suggested_playlist="Deep Focus",
            suggested_genre="Focus Beats",
            browser_name="Google Chrome",
            browser_url="https://youtube.com/watch?v=123",
            browser_title="(6) Diljit Dosanjh latest - YouTube",
        )
        with patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0, stdout="", stderr="")
            res = brain.execute_intent("message Josh")
            assert res["status"] == "success"
            assert res["recipient"] == "Joshua Rayan"
            assert res["email"] == "josh@crcle.ai"
            # Crucial invariant: Diljit Dosanjh or YouTube MUST NOT be the work_topic!
            assert "Diljit" not in res["subject"]
            assert "YouTube" not in res["subject"]
            assert "desktop-dom" in res["subject"] or "Crcle" in res["subject"]
            assert "PDgit12" not in res.get("response", "")







