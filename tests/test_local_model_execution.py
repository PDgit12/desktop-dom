import io
import json
import time
from unittest.mock import MagicMock, patch
import pytest

from desktop_dom.assistant.brain import AssistantBrain
from desktop_dom.assistant.memory import AuraMemory


@pytest.fixture
def isolated_brain(tmp_path):
    db_file = tmp_path / "test_model_brain.db"
    mem = AuraMemory(db_path=str(db_file))
    b = AssistantBrain(preferred_model="ministral-3:8b", memory=mem)
    return b


def test_detect_ollama_model_mistral_priority(tmp_path):
    mock_tags = io.BytesIO(json.dumps({
        "models": [
            {"name": "llama3.2:3b"},
            {"name": "qwen3:8b"},
            {"name": "ministral-3:8b-instruct-2512-q4_K_M"}
        ]
    }).encode("utf-8"))

    with patch("urllib.request.urlopen", return_value=mock_tags):
        mem = AuraMemory(db_path=str(tmp_path / "detect1.db"))
        b = AssistantBrain(memory=mem)
        assert b.preferred_model == "ministral-3:8b-instruct-2512-q4_K_M"


def test_detect_ollama_model_qwen_priority(tmp_path):
    mock_tags = io.BytesIO(json.dumps({
        "models": [
            {"name": "deepseek-coder:6.7b"},
            {"name": "qwen3:8b"},
            {"name": "phi4:14b"}
        ]
    }).encode("utf-8"))

    with patch("urllib.request.urlopen", return_value=mock_tags):
        mem = AuraMemory(db_path=str(tmp_path / "detect2.db"))
        b = AssistantBrain(memory=mem)
        assert b.preferred_model == "qwen3:8b"


def test_detect_ollama_model_fallback(tmp_path):
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        mem = AuraMemory(db_path=str(tmp_path / "detect3.db"))
        b = AssistantBrain(memory=mem)
        assert b.preferred_model == "mistral"


def test_get_model_status_connected(isolated_brain):
    mock_tags = io.BytesIO(json.dumps({
        "models": [
            {"name": "ministral-3:8b"},
            {"name": "qwen3:8b"}
        ]
    }).encode("utf-8"))

    with patch("urllib.request.urlopen", return_value=mock_tags):
        status = isolated_brain.get_model_status()
        assert status["connected"] is True
        assert status["current_model"] == "ministral-3:8b"
        assert "qwen3:8b" in status["available_models"]
        assert status["latency_ms"] is not None


def test_get_model_status_offline(isolated_brain):
    with patch("urllib.request.urlopen", side_effect=Exception("Server offline")):
        status = isolated_brain.get_model_status()
        assert status["connected"] is False
        assert status["current_model"] == "ministral-3:8b"
        assert status["available_models"] == []
        assert status["latency_ms"] is None


def test_model_switching_and_memory_persistence(tmp_path):
    db_file = tmp_path / "persist_model.db"
    mem = AuraMemory(db_path=str(db_file))
    b = AssistantBrain(preferred_model="ministral-3:8b", memory=mem)

    # Switch to qwen3:8b
    b.set_model("qwen3:8b")
    assert b.preferred_model == "qwen3:8b"
    assert mem.get_preference("llm.preferred_model") == "qwen3:8b"

    # New brain instance restores persisted choice
    b2 = AssistantBrain(memory=mem)
    assert b2.preferred_model == "qwen3:8b"


def test_zero_model_fast_path_selection(tmp_path):
    db_file = tmp_path / "zero_model.db"
    mem = AuraMemory(db_path=str(db_file))
    b = AssistantBrain(preferred_model="ministral-3:8b", memory=mem)

    b.set_model("Zero-Model Fast-Path")
    assert b.preferred_model is None
    assert mem.get_preference("llm.preferred_model") == "Zero-Model Fast-Path"

    status = b.get_model_status()
    assert status["current_model"] == "Zero-Model Fast-Path"

    # Fast path still works without calling Ollama
    with patch("urllib.request.urlopen") as mock_url:
        res = b.execute_intent("calculate 20 + 5")
        assert res["status"] == "success"
        assert res["result"] == "25"
        assert res["engine"] == "fast_path"
        mock_url.assert_not_called()


def test_execute_with_local_llm_chat_api(isolated_brain):
    chat_resp = io.BytesIO(json.dumps({
        "message": {
            "role": "assistant",
            "content": "To optimize database queries, create indexed columns and avoid SELECT *."
        }
    }).encode("utf-8"))

    with patch("urllib.request.urlopen", return_value=chat_resp) as mock_url:
        res = isolated_brain._execute_with_local_llm("How to optimize database queries?")
        assert res["status"] == "success"
        assert "optimize database queries" in res["response"]
        
        # Verify call went to /api/chat
        call_arg = mock_url.call_args[0][0]
        assert call_arg.full_url.endswith("/api/chat")
        sent_payload = json.loads(call_arg.data.decode("utf-8"))
        assert sent_payload["model"] == "ministral-3:8b"
        assert len(sent_payload["messages"]) == 2
        assert sent_payload["messages"][0]["role"] == "system"
        assert sent_payload["messages"][1]["role"] == "user"


def test_execute_with_local_llm_generate_fallback(isolated_brain):
    gen_resp = io.BytesIO(json.dumps({
        "response": "Fallback generation succeeded."
    }).encode("utf-8"))

    def side_effect(req, *args, **kwargs):
        if req.full_url.endswith("/api/chat"):
            raise Exception("404 Not Found")
        return gen_resp

    with patch("urllib.request.urlopen", side_effect=side_effect):
        res = isolated_brain._execute_with_local_llm("test prompt")
        assert res["status"] == "success"
        assert res["response"] == "Fallback generation succeeded."


def test_action_extraction_markdown_bold(isolated_brain):
    model_output = (
        "Opening your workspace communication hub.\n\n"
        "**ACTION: open Slack**"
    )
    chat_resp = io.BytesIO(json.dumps({
        "message": {"role": "assistant", "content": model_output}
    }).encode("utf-8"))

    with patch("urllib.request.urlopen", return_value=chat_resp):
        with patch.object(isolated_brain, "resolve_app_name", return_value="Slack"):
            with patch("subprocess.run") as mock_run:
                res = isolated_brain._execute_with_local_llm("Open Slack for me")
                assert res["status"] == "success"
                assert "Opening your workspace communication hub" in res["response"]
                assert "Opened Slack" in res["response"]


def test_action_extraction_parenthetical_commentary(isolated_brain):
    model_output = (
        "Here are tips for coding focus:\n"
        "1. Work in 25-minute intervals.\n"
        "2. Keep a notebook open.\n\n"
        "**ACTION: open Granola** *(to jot down your session notes)*."
    )
    chat_resp = io.BytesIO(json.dumps({
        "message": {"role": "assistant", "content": model_output}
    }).encode("utf-8"))

    with patch("urllib.request.urlopen", return_value=chat_resp):
        with patch.object(isolated_brain, "resolve_app_name", return_value="Granola"):
            with patch("subprocess.run") as mock_run:
                res = isolated_brain._execute_with_local_llm("Tips for focus")
                assert res["status"] == "success"
                assert "Work in 25-minute intervals" in res["response"]
                assert "Opened Granola" in res["response"]


def test_action_extraction_note_creation(isolated_brain):
    model_output = (
        "Recording your meeting notes.\n\n"
        "ACTION: note Team Standup: Discussed Q4 roadmap and backend speed"
    )
    chat_resp = io.BytesIO(json.dumps({
        "message": {"role": "assistant", "content": model_output}
    }).encode("utf-8"))

    with patch("urllib.request.urlopen", return_value=chat_resp):
        with patch.object(isolated_brain, "_control_notes_create", return_value={"status": "success", "response": "Created note: Team Standup"}):
            res = isolated_brain._execute_with_local_llm("Take a note of our standup")
            assert res["status"] == "success"
            assert "Recording your meeting notes" in res["response"]
            assert "Created note: Team Standup" in res["response"]


def test_action_extraction_spotify_play(isolated_brain):
    model_output = (
        "Playing relaxing lo-fi beats.\n\n"
        "ACTION: play lofi hip hop on spotify"
    )
    chat_resp = io.BytesIO(json.dumps({
        "message": {"role": "assistant", "content": model_output}
    }).encode("utf-8"))

    with patch("urllib.request.urlopen", return_value=chat_resp):
        with patch.object(isolated_brain, "_control_spotify_play", return_value={"status": "success", "response": "Now playing 'lofi hip hop' on Spotify."}):
            res = isolated_brain._execute_with_local_llm("Play some lofi music")
            assert res["status"] == "success"
            assert "Playing relaxing lo-fi beats" in res["response"]
            assert "Now playing 'lofi hip hop' on Spotify" in res["response"]


def test_personal_search_guardrail_diverts_to_schedule(isolated_brain):
    model_output = (
        "Looking up your meetings.\n\n"
        "ACTION: search my schedule"
    )
    chat_resp = io.BytesIO(json.dumps({
        "message": {"role": "assistant", "content": model_output}
    }).encode("utf-8"))

    with patch("urllib.request.urlopen", return_value=chat_resp):
        with patch.object(isolated_brain, "_handle_calendar_schedule_query", return_value={"status": "success", "response": "You have 1 meeting today: Design Sync at 2pm."}):
            res = isolated_brain._execute_with_local_llm("What is on my schedule today?")
            assert res["status"] == "success"
            assert "Design Sync at 2pm" in res["response"]


def test_personal_search_guardrail_diverts_to_team(isolated_brain):
    model_output = (
        "Checking your team roster.\n\n"
        "ACTION: search my team contacts"
    )
    chat_resp = io.BytesIO(json.dumps({
        "message": {"role": "assistant", "content": model_output}
    }).encode("utf-8"))

    with patch("urllib.request.urlopen", return_value=chat_resp):
        with patch.object(isolated_brain, "_try_deterministic_fast_path", return_value={"status": "success", "response": "Your team: Hannah Vance (Designer)."}):
            res = isolated_brain._execute_with_local_llm("Who is on my team?")
            assert res["status"] == "success"
            assert "Hannah Vance" in res["response"]
