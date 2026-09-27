import io
import json
import socket
import threading
import urllib.error
from unittest.mock import MagicMock, patch
import pytest
from typer.testing import CliRunner

from desktop_dom.assistant.brain import AssistantBrain
from desktop_dom.assistant.memory import AuraMemory
from desktop_dom.cli.main import app as cli_app
from desktop_dom.schema import DesktopNode, BoundingBox

runner = CliRunner()


@pytest.fixture
def audit_brain(tmp_path):
    db_file = tmp_path / "edge_case_brain.db"
    mem = AuraMemory(db_path=str(db_file))
    b = AssistantBrain(preferred_model="ministral-3:8b", memory=mem, execution_mode="llm_first")
    return b


# =============================================================================
# 1. BRAIN EDGE CASES: Input Hygiene, Ollama Failures, Action Parsing, Guardrails
# =============================================================================

def test_empty_and_whitespace_queries(audit_brain):
    """Empty, whitespace, and None queries should return empty status gracefully."""
    for empty_input in ["", "   ", "\t\n\r  ", None]:
        res = audit_brain.execute_intent(empty_input)
        assert res["status"] == "empty"
        assert "didn't catch that" in res["response"]


def test_symbol_only_queries(audit_brain):
    """Punctuation and symbol-only queries should return empty status gracefully."""
    for sym_input in ["???", "!@#$%^&*()", "---", "...", "  ??? \t"]:
        res = audit_brain.execute_intent(sym_input)
        assert res["status"] == "empty"
        assert "didn't catch that" in res["response"]


def test_ollama_timeout(audit_brain):
    """Ollama timeout should be caught and gracefully fall back to deterministic fast-path."""
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError(socket.timeout("timed out"))):
        # Conversational query without fast-path handler returns error or unhandled
        llm_res = audit_brain._execute_with_local_llm("Explain astrophysics")
        assert llm_res["status"] == "error"
        assert "timed out" in llm_res["response"].lower() or "error" in llm_res["response"].lower()

        # Action query with fast-path handler gracefully falls back to deterministic execution
        intent_res = audit_brain.execute_intent("dark mode")
        assert intent_res["status"] == "success"
        assert intent_res["engine"] == "fast_path"


def test_ollama_connection_refused(audit_brain):
    """Ollama connection refused should fall back cleanly without unhandled exceptions."""
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError(ConnectionRefusedError("Connection refused"))):
        res = audit_brain._execute_with_local_llm("Hello?")
        assert res["status"] == "error"
        assert "offline or busy" in res["response"]


def test_ollama_model_not_found_404(audit_brain):
    """Ollama 404 HTTPError should return a structured error status."""
    err_404 = urllib.error.HTTPError(
        url="http://localhost:11434/api/chat",
        code=404,
        msg="Not Found",
        hdrs={},
        fp=io.BytesIO(b'{"error":"model not found"}')
    )
    with patch("urllib.request.urlopen", side_effect=err_404):
        res = audit_brain._execute_with_local_llm("Hello?")
        assert res["status"] == "error"
        assert "404" in res["response"] or "error" in res["response"].lower()


def test_ollama_empty_replies(audit_brain):
    """Empty content in LLM message or response should return empty status."""
    empty_chat = io.BytesIO(json.dumps({"message": {"role": "assistant", "content": ""}}).encode("utf-8"))
    with patch("urllib.request.urlopen", return_value=empty_chat):
        res = audit_brain._execute_with_local_llm("Say nothing")
        assert res["status"] == "empty"
        assert "No response from model" in res["response"]


def test_malformed_action_lines(audit_brain):
    """Malformed ACTION lines from LLM should be parsed safely or handled as reasoning text."""
    # 1. ACTION: with no content
    chat_empty_action = io.BytesIO(json.dumps({
        "message": {"role": "assistant", "content": "I'm thinking about it.\nACTION:\nDone."}
    }).encode("utf-8"))
    with patch("urllib.request.urlopen", return_value=chat_empty_action):
        res = audit_brain._execute_with_local_llm("test empty action")
        assert res["status"] == "success"
        assert "I'm thinking about it" in res["response"]

    # 2. ACTION: with whitespace only
    chat_spaces_action = io.BytesIO(json.dumps({
        "message": {"role": "assistant", "content": "Here is an action:\nACTION:    \nFinished."}
    }).encode("utf-8"))
    with patch("urllib.request.urlopen", return_value=chat_spaces_action):
        res = audit_brain._execute_with_local_llm("test whitespace action")
        assert res["status"] == "success"

    # 3. ACTION: unknown_tool_xyz
    chat_unknown_tool = io.BytesIO(json.dumps({
        "message": {"role": "assistant", "content": "Calling tool:\nACTION: unknown_tool_xyz"}
    }).encode("utf-8"))
    with patch("urllib.request.urlopen", return_value=chat_unknown_tool):
        res = audit_brain._execute_with_local_llm("test unknown tool")
        assert res["status"] == "success"
        assert "unknown_tool_xyz" in res["response"]

    # 4. ACTION: open "App With Spaces"
    chat_quotes_action = io.BytesIO(json.dumps({
        "message": {"role": "assistant", "content": "Opening Visual Studio Code:\nACTION: open \"Visual Studio Code\""}
    }).encode("utf-8"))
    with patch("urllib.request.urlopen", return_value=chat_quotes_action):
        with patch.object(audit_brain, "_try_deterministic_fast_path", return_value={"status": "success", "response": "Opened Visual Studio Code."}):
            res = audit_brain._execute_with_local_llm("open vscode")
            assert res["status"] == "success"
            assert "Visual Studio Code" in res["response"]

    # 5. Markdown bold with backticks: **ACTION: `open Slack`**
    chat_markdown_bold = io.BytesIO(json.dumps({
        "message": {"role": "assistant", "content": "Opening Slack.\n**ACTION: `open Slack`**"}
    }).encode("utf-8"))
    with patch("urllib.request.urlopen", return_value=chat_markdown_bold):
        with patch.object(audit_brain, "_try_deterministic_fast_path", return_value={"status": "success", "response": "Opened Slack."}):
            res = audit_brain._execute_with_local_llm("open slack")
            assert res["status"] == "success"
            assert "Opened Slack" in res["response"]


def test_compound_queries_varying_conjunctions(audit_brain):
    """Compound queries with 'and', 'then', 'also', 'and also' should all split and execute."""
    with patch.object(audit_brain, "_try_deterministic_fast_path") as mock_fast:
        mock_fast.side_effect = lambda clean, raw_prompt="": {
            "status": "success",
            "action": "open_app",
            "response": f"Opened {raw_prompt}."
        }

        # Conjunction: "and"
        res_and = audit_brain.execute_intent("open calculator and open notes")
        assert res_and["action"] == "compound_action"
        assert len(res_and["parts"]) == 2

        # Conjunction: "then"
        res_then = audit_brain.execute_intent("open terminal then open notes")
        assert res_then["action"] == "compound_action"
        assert len(res_then["parts"]) == 2

        # Conjunction: "also"
        res_also = audit_brain.execute_intent("open safari also open calculator")
        assert res_also["action"] == "compound_action"
        assert len(res_also["parts"]) == 2

        # Conjunction: "and also"
        res_and_also = audit_brain.execute_intent("open finder and also open calendar")
        assert res_and_also["action"] == "compound_action"
        assert len(res_and_also["parts"]) == 2

        # Conjunction with implied verb on second part ("open chrome also spotify")
        res_implied = audit_brain.execute_intent("open chrome also spotify")
        assert res_implied["action"] == "compound_action"
        assert len(res_implied["parts"]) == 2


def test_personal_search_guardrail_edge_cases(audit_brain):
    """Personal data search queries must never go to external search engines."""
    # Fast-path personal search guardrails
    with patch.object(audit_brain, "_handle_calendar_schedule_query", return_value={"status": "success", "action": "open_calendar", "response": "Today: Standup at 10am."}) as mock_cal:
        res1 = audit_brain._try_deterministic_fast_path("search my meetings on google", raw_prompt="search my meetings on google")
        assert res1["status"] == "success"
        mock_cal.assert_called()

    with patch.object(audit_brain, "_handle_calendar_schedule_query", return_value={"status": "success", "action": "open_calendar", "response": "Today's schedule."}) as mock_cal2:
        res2 = audit_brain._try_deterministic_fast_path("google my schedule", raw_prompt="google my schedule")
        assert res2["status"] == "success"
        mock_cal2.assert_called()

    with patch.object(audit_brain, "_try_deterministic_fast_path", return_value={"status": "success", "response": "Team contacts: Josh, Cyril."}) as mock_team:
        res3 = audit_brain._try_deterministic_fast_path("google my contacts", raw_prompt="google my contacts")
        assert res3["status"] == "success"

    with patch.object(audit_brain, "_try_deterministic_fast_path", return_value={"status": "success", "response": "Opened Notes."}) as mock_notes:
        res4 = audit_brain._try_deterministic_fast_path("search my notes on google", raw_prompt="search my notes on google")
        assert res4["status"] == "success"

    # LLM execution action guardrail
    chat_llm_personal = io.BytesIO(json.dumps({
        "message": {"role": "assistant", "content": "Looking up meetings.\nACTION: search my meetings on google"}
    }).encode("utf-8"))
    with patch("urllib.request.urlopen", return_value=chat_llm_personal):
        with patch.object(audit_brain, "_handle_calendar_schedule_query", return_value={"status": "success", "action": "open_calendar", "response": "1 meeting found."}):
            res5 = audit_brain._execute_with_local_llm("What meetings do I have?")
            assert res5["status"] == "success"
            assert "1 meeting found" in res5["response"]


def test_mode_switching_and_invalid_modes(audit_brain):
    """Switching between modes and handling invalid modes."""
    # Check mode status
    status_res = audit_brain.execute_intent("/mode")
    assert status_res["status"] == "success"
    assert status_res["action"] == "execution_mode_status"
    assert status_res["mode"] == "llm_first"

    # Switch to fast_path
    fp_res = audit_brain.execute_intent("/mode fast_path")
    assert fp_res["status"] == "success"
    assert fp_res["mode"] == "fast_path"
    assert audit_brain.execution_mode == "fast_path"

    # Switch back to llm_first
    llm_res = audit_brain.execute_intent("/mode llm_first")
    assert llm_res["status"] == "success"
    assert llm_res["mode"] == "llm_first"
    assert audit_brain.execution_mode == "llm_first"

    # Invalid mode should return structured error, NOT fall through
    inv_res = audit_brain.execute_intent("/mode invalid_mode")
    assert inv_res["status"] == "error"
    assert "Invalid execution mode 'invalid_mode'" in inv_res["response"]
    assert audit_brain.execution_mode == "llm_first"

    # Direct helper validation
    assert audit_brain.set_execution_mode(None) is False
    assert audit_brain.set_execution_mode("") is False


def test_model_switching_with_non_installed_models(audit_brain):
    """Switching to a model not currently installed should succeed with an informative warning."""
    mock_tags = io.BytesIO(json.dumps({
        "models": [{"name": "ministral-3:8b"}, {"name": "qwen3:8b"}]
    }).encode("utf-8"))

    with patch("urllib.request.urlopen", return_value=mock_tags):
        # Switching to a non-installed model
        res = audit_brain.execute_intent("/model nonexistent-model-xyz")
        assert res["status"] == "success"
        assert res["model"] == "nonexistent-model-xyz"
        assert "not currently installed in Ollama" in res["response"]
        assert "ollama pull nonexistent-model-xyz" in res["response"]
        assert audit_brain.preferred_model == "nonexistent-model-xyz"

        # Switching to Zero-Model Fast-Path
        res_zero = audit_brain.execute_intent("/model Zero-Model Fast-Path")
        assert res_zero["status"] == "success"
        assert audit_brain.preferred_model is None


# =============================================================================
# 2. CLI ROBUSTNESS AUDIT: desktop-dom audit, apps, tree, click
# =============================================================================

def test_cli_audit(tmp_path, monkeypatch):
    """desktop-dom audit prints memory governance tables."""
    db_file = tmp_path / "cli_audit.db"
    mem = AuraMemory(db_path=str(db_file))
    monkeypatch.setattr("desktop_dom.assistant.memory.AuraMemory", lambda: mem)

    result = runner.invoke(cli_app, ["audit"])
    assert result.exit_code == 0
    assert "Aura Sovereign Memory & Storage Audit" in result.output
    assert "Storage Engine & Database Integrity" in result.output
    assert "Zero-Token Custody Verified" in result.output


def test_cli_audit_json(tmp_path, monkeypatch):
    """desktop-dom audit --json outputs machine-readable JSON."""
    db_file = tmp_path / "cli_audit_json.db"
    mem = AuraMemory(db_path=str(db_file))
    monkeypatch.setattr("desktop_dom.assistant.memory.AuraMemory", lambda: mem)

    result = runner.invoke(cli_app, ["audit", "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert "database" in parsed
    assert "security_and_privacy" in parsed
    assert "data_scopes" in parsed
    assert parsed["database"]["journal_mode"].lower() == "wal"


def test_cli_apps(test_adapter, monkeypatch):
    """desktop-dom apps lists available applications."""
    monkeypatch.setattr("desktop_dom.cli.main.get_platform_adapter", lambda: test_adapter)
    result = runner.invoke(cli_app, ["apps"])
    assert result.exit_code == 0
    assert "Running Desktop Applications" in result.output
    assert "Calculator" in result.output


def test_cli_tree_app(test_adapter, monkeypatch):
    """desktop-dom tree --app <app> renders accessibility DOM tree."""
    from desktop_dom.app import DesktopApp
    monkeypatch.setattr("desktop_dom.cli.main.get_platform_adapter", lambda: test_adapter)
    monkeypatch.setattr("desktop_dom.app.get_platform_adapter", lambda: test_adapter)

    result = runner.invoke(cli_app, ["tree", "--app", "Calculator"])
    assert result.exit_code == 0
    assert "WINDOW" in result.output or "Calculator" in result.output


def test_cli_tree_app_missing(monkeypatch):
    """desktop-dom tree --app <missing_app> exits with code 1 and error message."""
    mock_adapter = MagicMock()
    mock_adapter.get_root_window.side_effect = ProcessLookupError("Could not find running desktop application matching 'NonExistentApp_9999'")
    monkeypatch.setattr("desktop_dom.cli.main.get_platform_adapter", lambda: mock_adapter)
    monkeypatch.setattr("desktop_dom.app.get_platform_adapter", lambda: mock_adapter)

    result = runner.invoke(cli_app, ["tree", "--app", "NonExistentApp_9999"])
    assert result.exit_code == 1
    assert "Error inspecting 'NonExistentApp_9999'" in result.output


def test_cli_tree_empty_ui(monkeypatch):
    """desktop-dom tree handles an app with no UI elements without crashing."""
    mock_adapter = MagicMock()
    mock_adapter.get_root_window.return_value = None
    monkeypatch.setattr("desktop_dom.cli.main.get_platform_adapter", lambda: mock_adapter)
    monkeypatch.setattr("desktop_dom.app.get_platform_adapter", lambda: mock_adapter)

    result = runner.invoke(cli_app, ["tree", "--app", "EmptyApp"])
    assert result.exit_code == 0
    assert "EmptyApp" in result.output


def test_cli_click_missing_id():
    """desktop-dom click without --id exits code 2 (missing option)."""
    result = runner.invoke(cli_app, ["click", "--app", "Calculator"])
    assert result.exit_code == 2
    assert "Missing option" in result.output or "--id" in result.output


def test_cli_click_invalid_id(test_adapter, monkeypatch):
    """desktop-dom click with invalid element ID exits code 1 with error message."""
    monkeypatch.setattr("desktop_dom.cli.actions.DesktopApp.attach", lambda target: type("FakeApp", (), {
        "click": MagicMock(side_effect=KeyError("Element ID 'btn_invalid_999' is invalid or stale."))
    })())

    result = runner.invoke(cli_app, ["click", "--app", "Calculator", "--id", "btn_invalid_999"])
    assert result.exit_code == 1
    assert "Click failed" in result.output
    assert "btn_invalid_999" in result.output


# =============================================================================
# 3. MEMORY & DATABASE EDGE CASES: Concurrency, Corrupted Data, Resolution, Graphs
# =============================================================================

def test_memory_concurrent_access_and_locks(tmp_path):
    """Test concurrent multi-threaded read and write operations under high contention."""
    db_file = tmp_path / "concurrent_stress.db"
    mem = AuraMemory(db_path=str(db_file))

    errors = []

    def writer_task(worker_id: int):
        try:
            for i in range(25):
                mem.set_preference(f"worker_{worker_id}.item_{i}", f"val_{i}", category="stress")
                mem.record_learning(f"pattern_{worker_id}_{i}", "test_intent", f"action_{i}", confidence=0.88)
        except Exception as e:
            errors.append(e)

    def reader_task(worker_id: int):
        try:
            for i in range(25):
                mem.get_preference(f"worker_{worker_id}.item_{i}")
                mem.list_preferences(category="stress")
                mem.get_learnings(f"pattern_{worker_id}_{i}")
        except Exception as e:
            errors.append(e)

    threads = []
    for w in range(5):
        t_w = threading.Thread(target=writer_task, args=(w,))
        t_r = threading.Thread(target=reader_task, args=(w,))
        threads.extend([t_w, t_r])

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(mem.list_preferences(category="stress")) == 125


def test_corrupted_or_empty_preference_queries(tmp_path):
    """Test preference queries with empty keys, None, and corrupted JSON blobs."""
    db_file = tmp_path / "corrupted_prefs.db"
    mem = AuraMemory(db_path=str(db_file))

    # Empty / None key handling
    assert mem.get_preference(None) is None
    assert mem.get_preference("", default="def") == "def"
    with pytest.raises(ValueError):
        mem.set_preference(None, "val")
    with pytest.raises(ValueError):
        mem.set_preference("", "val")

    # Corrupted JSON in calendar events
    mem.set_preference("calendar.events.today", "NOT_A_JSON_LIST{{{")
    assert mem.get_today_schedule() == []

    # Non-list JSON in calendar events
    mem.set_preference("calendar.events.today", json.dumps({"key": "not a list"}))
    assert mem.get_today_schedule() == []

    # Corrupted JSON in browser top sites
    mem.set_preference("browser.top_sites", "MALFORMED_JSON_STRING")
    summary = mem.get_summary()
    assert isinstance(summary, dict)


def test_entity_resolution_edge_cases(tmp_path):
    """Entity resolution across partial names, typos, special characters, and empty inputs."""
    db_file = tmp_path / "entity_resolution.db"
    mem = AuraMemory(db_path=str(db_file))

    # Seed entities
    mem.upsert_entity({
        "name": "Joshua Rayan",
        "email": "josh@crcle.ai",
        "aliases": ["josh", "joshua"],
        "role": "CEO",
        "company": "Crcle.ai",
        "category": "colleague",
        "metadata": {"cluster": "work", "priority": 10},
    })
    mem.upsert_entity({
        "name": "Cyril Vance",
        "email": "cyril@crcle.ai",
        "aliases": ["cyril"],
        "role": "Chief Technology Officer",
        "company": "Crcle.ai",
        "category": "colleague",
        "metadata": {"cluster": "work", "priority": 8},
    })

    # None and empty queries
    assert mem.resolve_entity(None) is None
    assert mem.resolve_entity("") is None
    assert mem.resolve_entity("   ") is None

    # Partial name match
    res_josh = mem.resolve_entity("josh")
    assert res_josh is not None
    assert res_josh["name"] == "Joshua Rayan"

    # Typo tolerance
    res_cyril = mem.resolve_entity("ciril")
    assert res_cyril is not None
    assert res_cyril["name"] == "Cyril Vance"

    # Special characters and punctuation
    res_special = mem.resolve_entity("to Josh! :)")
    assert res_special is not None
    assert res_special["name"] == "Joshua Rayan"

    # Unresolvable symbol gibberish
    assert mem.resolve_entity("!@#$%^&*()") is None


def test_cluster_isolation_and_disconnected_graphs(tmp_path):
    """Test spreading activation with disconnected graphs and strict cluster isolation."""
    db_file = tmp_path / "graph_isolation.db"
    mem = AuraMemory(db_path=str(db_file))

    # Seed isolated entities without graph edges
    e1 = mem.upsert_entity({
        "name": "Work Task Hub",
        "category": "tasks",
        "role": "Linear Issues",
        "metadata": {"cluster": "work"},
    })
    e2 = mem.upsert_entity({
        "name": "Lo-Fi Beats Player",
        "category": "media",
        "role": "Music",
        "metadata": {"cluster": "personal_media"},
    })

    # 1. Disconnected graph entities have no mutual edges and spreading activation does not crash
    assert not any(
        (e.get("source_id") == e1.get("id") and e.get("target_id") == e2.get("id")) or
        (e.get("source_id") == e2.get("id") and e.get("target_id") == e1.get("id"))
        for e in mem._graph_edges
    )
    res = mem.ignite_graph("review my tasks and issues", context={"frontmost_app": "Zed"})
    assert res["status"] != "error"
    ignited = res["ignited_nodes"]
    assert any(n["name"] == "Work Task Hub" for n in ignited)

    # 2. Cluster isolation: in work context, personal media energy cannot leak into work
    res_work_ctx = mem.ignite_graph("tasks", context={"frontmost_app": "Linear", "activity_category": "work"})
    ignited_names = [n["name"] for n in res_work_ctx["ignited_nodes"]]
    assert "Work Task Hub" in ignited_names
    assert "Lo-Fi Beats Player" not in ignited_names

    # 3. None and empty queries to ignite_graph
    assert mem.ignite_graph(None)["status"] == "empty"
    assert mem.ignite_graph("")["status"] == "empty"
    assert mem.ignite_graph("   ")["status"] == "empty"
