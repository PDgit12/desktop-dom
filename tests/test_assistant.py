import sys
import json
import io
from unittest.mock import MagicMock, patch
import pytest
from typer.testing import CliRunner

from desktop_dom.assistant.brain import AssistantBrain
from desktop_dom.assistant.audio import AudioManager
from desktop_dom.assistant import DesktopAssistant
from desktop_dom.cli.main import app

runner = CliRunner()

@pytest.fixture
def brain():
    b = AssistantBrain(preferred_model="test-model")
    return b

def test_assistant_fast_path_spotify(brain):
    with patch("subprocess.run") as mock_run:
        res = brain.execute_intent("play Starboy on Spotify")
        assert res["status"] == "success"
        assert res["action"] == "spotify_play"
        assert "Starboy" in res["query"]

        res_pause = brain.execute_intent("pause music")
        assert res_pause["status"] == "success"
        assert res_pause["action"] == "spotify_playpause"

        res_skip = brain.execute_intent("skip track")
        assert res_skip["status"] == "success"
        assert res_skip["action"] == "spotify_next track"

def test_assistant_fast_path_calculator(brain):
    res = brain.execute_intent("calculate 125 * 40 + 15")
    assert res["status"] == "success"
    assert res["action"] == "calculate"
    assert res["result"] == "5015"

    res_div = brain.execute_intent("what is 250 / 5")
    assert res_div["status"] == "success"
    assert res_div["action"] == "calculate"
    assert res_div["result"] == "50"

def test_assistant_fast_path_volume(brain):
    with patch("subprocess.run") as mock_run:
        res_set = brain.execute_intent("set volume to 80")
        assert res_set["status"] == "success"
        assert res_set["action"] == "set_volume"
        assert res_set["volume"] == 80

        res_mute = brain.execute_intent("mute volume")
        assert res_mute["status"] == "success"
        assert res_mute["action"] == "mute"

        res_unmute = brain.execute_intent("unmute volume")
        assert res_unmute["status"] == "success"
        assert res_unmute["action"] == "unmute"

        res_up = brain.execute_intent("volume up")
        assert res_up["status"] == "success"
        assert res_up["action"] == "volume_up"

        res_down = brain.execute_intent("volume down")
        assert res_down["status"] == "success"
        assert res_down["action"] == "volume_down"

def test_assistant_fast_path_app_open(brain):
    with patch("subprocess.run") as mock_run:
        res = brain.execute_intent("open Calculator")
        assert res["status"] == "success"
        assert res["action"] == "open_app"
        assert res["target"].lower() == "calculator"

def test_assistant_fast_path_web_search(brain):
    with patch("webbrowser.open") as mock_browser:
        res = brain.execute_intent("search for quantum computing")
        assert res["status"] == "success"
        assert res["action"] == "web_search"
        assert res["query"] == "quantum computing"
        mock_browser.assert_called_once()
        assert "quantum%20computing" in mock_browser.call_args[0][0]

def test_assistant_action_callback(brain):
    events = []
    brain.set_action_callback(lambda action_type, msg: events.append((action_type, msg)))
    res = brain.execute_intent("calculate 2 + 2")
    assert len(events) >= 2
    assert events[0][0] == "thinking"
    assert events[1][0] == "completed"

def test_assistant_fast_path_dark_mode(brain):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "true\n"
        res = brain.execute_intent("toggle dark mode")
        assert res["status"] == "success"
        assert res["action"] == "toggle_dark_mode"
        assert res["dark_mode"] is True

        res_light = brain.execute_intent("switch to light mode")
        assert res_light["status"] == "success"
        assert res_light["action"] == "toggle_dark_mode"

def test_assistant_fast_path_notes(brain):
    with patch("subprocess.run") as mock_run:
        res = brain.execute_intent("create note Standup: Completed sprint roadmap")
        assert res["status"] == "success"
        assert res["action"] == "create_note"
        assert res["title"] == "Standup"
        assert res["body"] == "Completed sprint roadmap"

        res_quick = brain.execute_intent("take a note: pick up package")
        assert res_quick["status"] == "success"
        assert res_quick["action"] == "create_note"
        assert "package" in res_quick["body"]

def test_assistant_fast_path_clipboard(brain):
    with patch("subprocess.Popen") as mock_popen, patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "desktop-dom-v0.2.0"
        res_copy = brain.execute_intent("copy 42981 to clipboard")
        assert res_copy["status"] == "success"
        assert res_copy["action"] == "copy_clipboard"
        assert res_copy["text"] == "42981"

        res_read = brain.execute_intent("what is on my clipboard")
        assert res_read["status"] == "success"
        assert res_read["action"] == "read_clipboard"
        assert "42" in res_read["response"] or "desktop-dom" in res_read["response"]

def test_assistant_fast_path_notification(brain):
    with patch("subprocess.run") as mock_run:
        res = brain.execute_intent("notify me Task completed successfully")
        assert res["status"] == "success"
        assert res["action"] == "notify"
        assert res["message"] == "Task completed successfully"

def test_assistant_fast_path_window_management(brain):
    with patch("subprocess.run") as mock_run:
        res_min = brain.execute_intent("minimize window")
        assert res_min["status"] == "success"
        assert res_min["action"] == "window_minimize"

        res_max = brain.execute_intent("maximize window")
        assert res_max["status"] == "success"
        assert res_max["action"] == "window_maximize"

def test_assistant_fast_path_inspect_screen(brain):
    with patch("desktop_dom.assistant.brain.AssistantBrain._get_frontmost_app_name", return_value="Finder"):
        with patch("desktop_dom.app.DesktopApp.attach") as mock_attach:
            mock_app = MagicMock()
            from desktop_dom.schema import DesktopNode, BoundingBox
            mock_node = DesktopNode(
                id="win_finder",
                role="window",
                name="Finder",
                bbox=BoundingBox(x=0, y=0, width=800, height=600),
                children=[
                    DesktopNode(
                        id="btn_view",
                        role="button",
                        name="View Options",
                        bbox=BoundingBox(x=50, y=50, width=80, height=30),
                        children=[]
                    )
                ]
            )
            mock_app.get_tree.return_value = mock_node
            mock_attach.return_value = mock_app

            res = brain.execute_intent("what is on my screen")
            assert res["status"] == "success"
            assert res["action"] == "inspect_screen"
            assert res["app"] == "Finder"
            assert "View Options" in res["summary"]

def test_assistant_fast_path_semantic_ui_actions(brain):
    with patch("desktop_dom.app.DesktopApp.attach") as mock_attach:
        mock_app = MagicMock()
        from desktop_dom.schema import DesktopNode, BoundingBox
        target_node = DesktopNode(
            id="btn_submit",
            role="button",
            name="Submit",
            bbox=BoundingBox(x=100, y=200, width=100, height=40),
            children=[]
        )
        mock_app.find.return_value = target_node
        mock_attach.return_value = mock_app

        res_click = brain.execute_intent("click Submit in Finder")
        assert res_click["status"] == "success"
        assert res_click["action"] == "click"
        assert res_click["element"] == "Submit"
        assert res_click["centroid"] == [150, 220]
        mock_app.click.assert_called_once_with("btn_submit")

        res_type = brain.execute_intent("type 'hello world' in Finder")
        assert res_type["status"] == "success"
        assert res_type["action"] == "type"
        assert res_type["text"] == "hello world"

        res_press = brain.execute_intent("press enter in Finder")
        assert res_press["status"] == "success"
        assert res_press["action"] == "press"
        assert res_press["key"] == "enter"

def test_assistant_local_llm_reasoning(brain):
    mock_response = io.BytesIO(json.dumps({"response": "Quantum error correction uses entangled physical qubits."}).encode("utf-8"))
    with patch("urllib.request.urlopen", return_value=mock_response):
        with patch("desktop_dom.assistant.brain.get_platform_adapter") as mock_adapter_getter:
            mock_adapter = MagicMock()
            mock_adapter.list_applications.return_value = [{"name": "Finder"}, {"name": "Terminal"}]
            mock_adapter_getter.return_value = mock_adapter

            res = brain.execute_intent("explain how quantum error correction works in one sentence")
            assert res["status"] == "success"
            assert res["action"] == "llm_reasoning"
            assert "Quantum error correction" in res["response"]

def test_audio_manager_speak():
    audio = AudioManager()
    mock_proc = MagicMock()
    with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        audio.speak("Testing speech playback", wait=True)
        assert mock_popen.called
        mock_proc.wait.assert_called_once()

    # Test stop_speaking
    audio._current_speech_proc = mock_proc
    mock_proc.poll.return_value = None
    audio.stop_speaking()
    mock_proc.terminate.assert_called_once()

def test_desktop_assistant_ask():
    brain = AssistantBrain(preferred_model="test-model")
    audio = AudioManager()
    audio.speak = MagicMock()

    assistant = DesktopAssistant(brain=brain, audio=audio)
    reply = assistant.ask("calculate 50 * 2")
    assert reply == "The answer is 100."
    audio.speak.assert_called_once_with("The answer is 100.")

def test_cli_assistant_help():
    result = runner.invoke(app, ["assistant", "--help"])
    assert result.exit_code == 0
    assert "--mode" in result.output
    assert "--cli" in result.output
    assert "--ollama-host" in result.output

def test_cli_assistant_cli_mode():
    result = runner.invoke(app, ["assistant", "--cli", "--mute"], input="calculate 10 + 5\nexit\n")
    assert result.exit_code == 0
    assert "Aura: Personal Desktop Assistant" in result.output
    assert "The answer is 15." in result.output

def test_floating_omnibar_logic():
    from desktop_dom.assistant.omnibar import FloatingOmnibar
    brain = MagicMock()
    brain.execute_intent.return_value = {"response": "8"}
    audio = MagicMock()
    bar = FloatingOmnibar(brain=brain, audio=audio)

    # Test toggle show / hide state
    bar._panel = MagicMock()
    assert not bar._is_visible
    bar.toggle()
    assert bar._is_visible
    bar._panel.makeKeyAndOrderFront_.assert_called_once()

    bar.toggle()
    assert not bar._is_visible
    bar._panel.orderOut_.assert_called_once()

    # Test query submission
    bar.on_query_submitted("calculate 4 + 4")
    import time
    time.sleep(0.25)
    brain.execute_intent.assert_called_with("calculate 4 + 4")

def test_omnibar_resize_and_status_item():
    from desktop_dom.assistant.omnibar import FloatingOmnibar
    bar = FloatingOmnibar()
    bar._panel = MagicMock()
    bar._webview = MagicMock()
    mock_frame = MagicMock()
    mock_frame.size.height = 80
    mock_frame.size.width = 720
    mock_frame.origin.x = 100
    mock_frame.origin.y = 500
    bar._panel.frame.return_value = mock_frame

    bar.resize_window(360.0)
    bar._panel.setFrame_display_animate_.assert_called_once()

def test_cli_package_help():
    result = runner.invoke(app, ["package", "--help"])
    assert result.exit_code == 0
    assert "--install" in result.output
    assert "--dmg" in result.output
    assert "--zip" in result.output
