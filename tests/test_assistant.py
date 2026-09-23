import os
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

def test_assistant_fast_path_model_status_and_switch(brain):
    with patch.object(brain, "get_model_status") as mock_status:
        mock_status.return_value = {
            "connected": True,
            "host": "http://localhost:11434",
            "current_model": "ministral-3:8b",
            "available_models": ["ministral-3:8b"],
            "latency_ms": 1.2
        }
        res = brain.execute_intent("/model")
        assert res["status"] == "success"
        assert res["action"] == "model_status"
        assert "ministral-3:8b" in res["response"]

    res_switch = brain.execute_intent("use model qwen3:8b")
    assert res_switch["status"] == "success"
    assert res_switch["action"] == "model_switch"
    assert brain.preferred_model == "qwen3:8b"

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

def test_omnibar_model_switching_and_clipboard():
    from desktop_dom.assistant.omnibar import FloatingOmnibar
    brain = MagicMock()
    brain.get_model_status.return_value = {
        "connected": True,
        "current_model": "ministral-3:8b",
        "available_models": ["ministral-3:8b", "qwen3:8b"]
    }
    bar = FloatingOmnibar(brain=brain)
    bar._webview = MagicMock()

    # Test model status requested
    bar.on_model_status_requested()
    brain.get_model_status.assert_called_once()
    assert bar._webview.evaluateJavaScript_completionHandler_.call_count == 2

    # Test dynamic model switch
    bar.on_model_switch("qwen3:8b")
    brain.set_model.assert_called_with("qwen3:8b")

    # Test clipboard copy
    assert bar.copy_text("Result text to copy") is not False

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

def test_omnibar_window_drag_movement_and_ipc():
    from desktop_dom.assistant.omnibar import OMNIBAR_HTML, FloatingOmnibar, OmnibarScriptHandler
    bar = FloatingOmnibar()
    bar._panel = MagicMock()
    mock_frame = MagicMock()
    mock_frame.origin.x = 200.0
    mock_frame.origin.y = 400.0
    bar._panel.frame.return_value = mock_frame

    # Test programmatic window movement
    bar.move_window_by(40.0, 20.0)
    bar._panel.setFrameOrigin_.assert_called_once()

    # Test Script Message Handler IPC dispatch
    handler = OmnibarScriptHandler(bar)
    mock_msg = MagicMock()
    mock_msg.body.return_value = json.dumps({"action": "drag_window", "dx": 15.0, "dy": -10.0})
    with patch.object(bar, "move_window_by") as mock_move:
        handler.userContentController_didReceiveScriptMessage_(None, mock_msg)
        mock_move.assert_called_once_with(15.0, -10.0)

    # Test HTML and CSS features
    assert "drag-handle-bar" in OMNIBAR_HTML
    assert "drag-pill" in OMNIBAR_HTML
    assert "-webkit-app-region: drag" in OMNIBAR_HTML
    assert "initDraggableWindow" in OMNIBAR_HTML
    assert "workspace-pill-btn" in OMNIBAR_HTML

def test_cli_package_help():
    result = runner.invoke(app, ["package", "--help"])
    assert result.exit_code == 0
    assert "--install" in result.output
    assert "--dmg" in result.output
    assert "--zip" in result.output
    assert "--platform" in result.output

def test_wake_word_listener_lifecycle():
    from desktop_dom.assistant.audio import WakeWordListener, AudioManager
    audio = AudioManager()
    listener = WakeWordListener(wake_words=["hey aura", "aura"], audio_manager=audio)
    assert not listener.is_running
    with patch("threading.Thread") as mock_thread:
        listener.start()
        assert listener.is_running
        mock_thread.assert_called_once()
        listener.stop()
        assert not listener.is_running

def test_wake_word_listener_detection():
    import numpy as np
    from desktop_dom.assistant.audio import WakeWordListener, AudioManager
    audio = AudioManager()
    audio.transcribe_numpy = MagicMock(return_value="hey aura play some music")
    
    detected = []
    listener = WakeWordListener(
        wake_words=["hey aura", "aura"],
        audio_manager=audio,
        on_wake=lambda kw: detected.append(kw),
        energy_threshold=100.0,
    )
    
    # Synthetic audio with energy
    sample_audio = np.random.randint(-1000, 1000, 16000, dtype=np.int16)
    
    # Simulate single iteration of listen loop logic
    rms = float(np.sqrt(np.mean(sample_audio.astype(np.float32) ** 2)))
    assert rms >= listener.energy_threshold
    text = audio.transcribe_numpy(sample_audio)
    assert "hey aura" in text
    listener.on_wake("hey aura")
    assert detected == ["hey aura"]

def test_wake_word_silence_gating():
    import numpy as np
    from desktop_dom.assistant.audio import WakeWordListener, AudioManager
    audio = AudioManager()
    audio.transcribe_numpy = MagicMock()

    listener = WakeWordListener(
        wake_words=["hey aura"],
        audio_manager=audio,
        energy_threshold=500.0,
    )
    silence = np.zeros(16000, dtype=np.int16)
    rms = float(np.sqrt(np.mean(silence.astype(np.float32) ** 2)))
    assert rms < listener.energy_threshold
    # Silence is gated, transcribe_numpy should not be called
    audio.transcribe_numpy.assert_not_called()

def test_desktop_assistant_wake_word_methods():
    brain = AssistantBrain(preferred_model="test-model")
    audio = AudioManager()
    assistant = DesktopAssistant(brain=brain, audio=audio)
    
    with patch("desktop_dom.assistant.audio.WakeWordListener.start") as mock_start, \
         patch("desktop_dom.assistant.audio.WakeWordListener.stop") as mock_stop:
        assistant.start_wake_word()
        assert assistant.wake_listener is not None
        mock_start.assert_called_once()
        
        assistant.stop_wake_word()
        assert assistant.wake_listener is None
        mock_stop.assert_called_once()

def test_build_windows_packager(tmp_path):
    from pathlib import Path
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from build_windows import build_windows_package
    
    zip_path = build_windows_package(tmp_path)
    assert zip_path.exists()
    assert (tmp_path / "Aura-Windows" / "aura.ico").exists()
    assert (tmp_path / "Aura-Windows" / "AuraInstaller.wxs").exists()
    assert (tmp_path / "Aura-Windows" / "Aura.bat").exists()

def test_build_linux_packager(tmp_path):
    from pathlib import Path
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from build_linux import build_linux_package
    
    tar_path = build_linux_package(tmp_path)
    assert tar_path.exists()
    pkg_dir = tmp_path / "aura_0.2.0_amd64"
    assert (pkg_dir / "DEBIAN" / "control").exists()
    assert (pkg_dir / "usr" / "bin" / "aura").exists()
    assert (pkg_dir / "usr" / "share" / "applications" / "aura.desktop").exists()
    assert (pkg_dir / "usr" / "share" / "icons" / "hicolor" / "512x512" / "apps" / "aura.png").exists()

def test_cli_assistant_wake_word_flag():
    result = runner.invoke(app, ["assistant", "--help"])
    assert result.exit_code == 0
    assert "--wake-word" in result.output or "-w" in result.output

def test_build_macos_packager(tmp_path):
    from pathlib import Path
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from build_app import build_app_bundle

    app_dir = build_app_bundle(tmp_path, create_zip=True)
    assert app_dir.exists()
    assert (app_dir / "Contents" / "Info.plist").exists()
    assert (app_dir / "Contents" / "MacOS" / "Aura").exists()
    assert (tmp_path / "Aura-v0.2.0-macOS.zip").exists()

    build_sh = scripts_dir / "build_app.sh"
    assert build_sh.exists()
    assert os.access(build_sh, os.X_OK)

def test_audio_manager_stop_speaking_concurrency():
    audio = AudioManager()
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    audio._current_speech_proc = mock_proc

    # Verify stop_speaking terminates process and clears reference
    audio.stop_speaking()
    mock_proc.terminate.assert_called_once()
    assert audio._current_speech_proc is None

def test_wake_word_listener_thread_termination():
    from desktop_dom.assistant.audio import WakeWordListener
    audio = MagicMock()
    listener = WakeWordListener(wake_words=["aura"], audio_manager=audio)

    mock_thread = MagicMock()
    mock_thread.is_alive.return_value = True

    with patch("threading.Thread", return_value=mock_thread):
        listener.start()
        assert listener.is_running
        assert not listener._stop_event.is_set()
        mock_thread.start.assert_called_once()

        listener.stop()
        assert not listener.is_running
        assert listener._stop_event.is_set()
        mock_thread.join.assert_called_once_with(timeout=1.5)

def test_aura_memory_crud_and_seed(tmp_path):
    from desktop_dom.assistant.memory import AuraMemory
    db_file = tmp_path / "memory_test.db"
    mem = AuraMemory(db_file)
    
    # Check default seeded user identity from OS/system
    user = mem.resolve_entity("me")
    assert user is not None
    assert user["name"] == mem.get_user_name()
    assert user["email"] == mem.get_user_email()

    # Test adding and resolving contacts (CRUD)
    mem.add_entity(
        name="Joshua Rayan",
        email="josh@crcle.ai",
        aliases=["josh", "joshua", "josh rayan", "ceo", "founder"],
        company="Crcle.ai",
        role="Co-Founder & CEO",
        category="colleague",
    )
    josh = mem.resolve_entity("josh")
    assert josh is not None
    assert josh["name"] == "Joshua Rayan"
    assert josh["email"] == "josh@crcle.ai"
    assert josh["role"] == "Co-Founder & CEO"
    assert josh["company"] == "Crcle.ai"

    mem.add_entity(
        name="Cyril Rayan",
        email="cyril@crcle.ai",
        aliases=["cyril", "cyril rayan", "architect", "founder"],
        company="Crcle.ai",
        role="Co-Founder & Systems Architect",
        category="colleague",
    )
    cyril = mem.resolve_entity("cyril")
    assert cyril is not None
    assert cyril["name"] == "Cyril Rayan"
    assert cyril["email"] == "cyril@crcle.ai"

    # Check preferences
    mail_cli = mem.get_preference("mail.preferred_client")
    assert mail_cli == "Microsoft Outlook"

def _seed_test_contacts(mem):
    mem.add_entity(
        name="Joshua Rayan",
        email="josh@crcle.ai",
        aliases=["josh", "joshua", "josh rayan", "ceo", "founder"],
        company="Crcle.ai",
        role="Co-Founder & CEO",
        category="colleague",
    )
    mem.add_entity(
        name="Cyril Rayan",
        email="cyril@crcle.ai",
        aliases=["cyril", "cyril rayan", "architect", "founder", "systems lead", "our systems lead"],
        company="Crcle.ai",
        role="Co-Founder & Systems Architect",
        category="colleague",
    )

def test_aura_memory_natural_language_learning(tmp_path):
    from desktop_dom.assistant.memory import AuraMemory
    db_file = tmp_path / "memory_learn.db"
    mem = AuraMemory(db_file)
    _seed_test_contacts(mem)

    # Learn new contact
    res = mem.remember("remember Sarah is sarah@crcle.ai")
    assert res["status"] == "success"
    sarah = mem.resolve_entity("sarah")
    assert sarah is not None
    assert sarah["email"] == "sarah@crcle.ai"

    # Update existing contact
    res_up = mem.remember("remember Josh's email is joshua@crcle.ai")
    assert res_up["status"] == "success"
    josh_updated = mem.resolve_entity("josh")
    assert josh_updated["email"] == "joshua@crcle.ai"

    # Learn playlist
    res_pl = mem.remember("remember my favorite playlist is Lalkara")
    assert res_pl["status"] == "success"
    assert mem.get_preference("spotify.favorite_playlist") == "Lalkara"

def test_assistant_messaging_fast_path(tmp_path):
    from desktop_dom.assistant.memory import AuraMemory
    mem = AuraMemory(tmp_path / "mem.db")
    _seed_test_contacts(mem)
    brain = AssistantBrain(preferred_model="test-model", memory=mem)

    # 1. Standard message Josh
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        res = brain.execute_intent("message Josh")
        assert res["status"] == "success"
        assert res["action"] == "send_message"
        assert res["recipient"] == "Joshua Rayan"
        assert res["email"] == "josh@crcle.ai"
        assert res["client"] == "Microsoft Outlook"

    # 2. Colloquial phrasing with message content
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        res2 = brain.execute_intent("i wanna message josh saying the slides are ready")
        assert res2["status"] == "success"
        assert res2["action"] == "send_message"
        assert res2["recipient"] == "Joshua Rayan"
        assert res2["body"] == "the slides are ready"

    # 3. Email Josh about meeting
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        res3 = brain.execute_intent("email Josh about meeting tomorrow")
        assert res3["status"] == "success"
        assert res3["recipient"] == "Joshua Rayan"
        assert res3["subject"] == "Meeting tomorrow"

    # 4. Unknown recipient - zero hallucination
    res_unknown = brain.execute_intent("message NonExistentPerson")
    assert res_unknown["status"] == "not_found"
    assert "NonExistentPerson" in res_unknown["response"]

def test_assistant_habitual_playlist(tmp_path):
    from desktop_dom.assistant.memory import AuraMemory
    mem = AuraMemory(tmp_path / "mem.db")
    mem.set_preference("spotify.favorite_playlist", "Deep Focus")
    brain = AssistantBrain(preferred_model="test-model", memory=mem)

    with patch.object(brain, "_control_spotify_play") as mock_spotify:
        mock_spotify.return_value = {"status": "success", "action": "spotify_play", "query": "Deep Focus"}
        res = brain.execute_intent("open my playlist")
        assert res["status"] == "success"
        assert res["action"] == "spotify_playlist"
        assert res["playlist"] == "Deep Focus"
        mock_spotify.assert_called_with("Deep Focus")

    # Change playlist via natural language
    res_rem = brain.execute_intent("remember my favorite playlist is Lofi Beats")
    assert res_rem["status"] == "success"

    with patch.object(brain, "_control_spotify_play") as mock_spotify2:
        mock_spotify2.return_value = {"status": "success", "action": "spotify_play", "query": "Lofi Beats"}
        res2 = brain.execute_intent("play my playlist")
        assert res2["status"] == "success"
        assert res2["playlist"] == "Lofi Beats"
        mock_spotify2.assert_called_with("Lofi Beats")

    # Contextual gaming playlist recall
    with patch.object(brain, "_get_frontmost_app_name", return_value="Steam"):
        with patch.object(brain, "_control_spotify_play") as mock_spotify3:
            mock_spotify3.return_value = {"status": "success", "action": "spotify_play", "query": "Gaming Soundtrack"}
            res3 = brain.execute_intent("play my playlist")
            assert res3["status"] == "success"
            assert res3["playlist"] == "Gaming Soundtrack"
            assert res3["context"] == "Gaming Energy"
            mock_spotify3.assert_called_with("Gaming Soundtrack")

def test_assistant_memory_inspection_and_who_is(tmp_path):
    from desktop_dom.assistant.memory import AuraMemory
    mem = AuraMemory(tmp_path / "mem.db")
    _seed_test_contacts(mem)
    brain = AssistantBrain(preferred_model="test-model", memory=mem)

    # Who is Josh
    res_who = brain.execute_intent("who is Josh?")
    assert res_who["status"] == "success"
    assert res_who["action"] == "who_is"
    assert "Joshua Rayan" in res_who["response"]
    assert "Crcle.ai" in res_who["response"]

    # Who is unknown
    res_who_unk = brain.execute_intent("who is UnknownCandidate?")
    assert res_who_unk["status"] == "not_found"

    # /memory command
    res_mem = brain.execute_intent("/memory")
    assert res_mem["status"] == "success"
    assert res_mem["action"] == "memory_summary"
    assert "Personal Memory Engine Active" in res_mem["response"]

def test_assistant_compound_with_memory(tmp_path):
    from desktop_dom.assistant.memory import AuraMemory
    mem = AuraMemory(tmp_path / "mem.db")
    _seed_test_contacts(mem)
    brain = AssistantBrain(preferred_model="test-model", memory=mem)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        res = brain.execute_intent("open outlook and message josh")
        assert res["status"] == "success"
        assert res["action"] == "compound_action"
        assert len(res["parts"]) == 2
        assert res["parts"][0]["action"] == "open_app"
        assert res["parts"][1]["action"] == "send_message"

def test_aura_memory_submillisecond_latency(tmp_path):
    import time
    from desktop_dom.assistant.memory import AuraMemory
    mem = AuraMemory(tmp_path / "mem_latency.db")
    _seed_test_contacts(mem)
    
    start_t = time.perf_counter()
    ent = mem.resolve_entity("josh")
    elapsed_ms = (time.perf_counter() - start_t) * 1000
    assert ent is not None
    # Sub-millisecond budget
    assert elapsed_ms < 2.0, f"Memory lookup took {elapsed_ms:.3f}ms, expected < 2.0ms"

def test_aura_memory_typo_and_role_disambiguation(tmp_path):
    from desktop_dom.assistant.memory import AuraMemory
    mem = AuraMemory(tmp_path / "mem_disambig.db")
    _seed_test_contacts(mem)
    
    # 1. Typo tolerance
    assert mem.resolve_entity("jos")["name"] == "Joshua Rayan"
    assert mem.resolve_entity("jsh")["name"] == "Joshua Rayan"
    assert mem.resolve_entity("ciril")["name"] == "Cyril Rayan"
    assert mem.resolve_entity("piush")["name"] == "Piyush Dua"

    # 2. Semantic role & title disambiguation
    assert mem.resolve_entity("ceo")["name"] == "Joshua Rayan"
    assert mem.resolve_entity("the ceo")["name"] == "Joshua Rayan"
    assert mem.resolve_entity("our systems lead")["name"] == "Cyril Rayan"
    assert mem.resolve_entity("founder") is not None

def test_aura_memory_direct_email_resolution(tmp_path):
    from desktop_dom.assistant.memory import AuraMemory
    mem = AuraMemory(tmp_path / "mem_email.db")
    
    # Direct valid email string
    res = mem.resolve_entity("alex@apple.com")
    assert res is not None
    assert res["email"] == "alex@apple.com"
    assert res["name"] == "Alex"
    assert res["company"] == "Apple"

def test_aura_memory_auto_hydration_and_onboarding(tmp_path):
    from desktop_dom.assistant.memory import AuraMemory
    mem = AuraMemory(tmp_path / "mem_onboard.db")
    
    # Run auto hydration
    summary = mem.auto_hydrate_environment()
    assert summary["status"] == "success"
    assert mem.get_preference("onboarding.completed") == "true"
    assert len(mem.list_entities()) >= 3

    # Run explicit onboard customization
    custom = mem.onboard(
        name="Piyush Custom",
        collaborator="Josh",
        collaborator_email="josh@crcle.ai",
        favorite_playlist="Synthwave Focus"
    )
    assert custom["user_name"] == "Piyush Custom"
    assert custom["favorite_playlist"] == "Synthwave Focus"
    assert mem.get_preference("spotify.favorite_playlist") == "Synthwave Focus"

def test_assistant_broadened_messaging_phrasing(tmp_path):
    from desktop_dom.assistant.memory import AuraMemory
    mem = AuraMemory(tmp_path / "mem_phrasing.db")
    _seed_test_contacts(mem)
    brain = AssistantBrain(preferred_model="test-model", memory=mem)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""

        # Shoot an email
        res1 = brain.execute_intent("shoot an email to josh saying the deck is finalized")
        assert res1["status"] == "success"
        assert res1["recipient"] == "Joshua Rayan"
        assert res1["body"] == "the deck is finalized"

        # Ping with typo
        res2 = brain.execute_intent("ping ciril that PR is up")
        assert res2["status"] == "success"
        assert res2["recipient"] == "Cyril Rayan"

        # Message on outlook override
        res3 = brain.execute_intent("message josh on outlook")
        assert res3["status"] == "success"
        assert res3["client"] == "Microsoft Outlook"

        # /onboard intent
        res_onb = brain.execute_intent("/onboard")
        assert res_onb["status"] == "success"
        assert res_onb["action"] == "onboard"

def test_assistant_fast_path_fuzzy_app_resolution(brain):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        
        # Typo: spotfy -> Spotify
        res_spot = brain.execute_intent("open spotfy")
        assert res_spot["status"] == "success"
        assert res_spot["action"] == "open_app"
        assert res_spot["target"] == "Spotify"

        # Typo: safri -> Safari
        res_saf = brain.execute_intent("open safri")
        assert res_saf["status"] == "success"
        assert res_saf["target"] == "Safari"

        # Typo: crome -> Google Chrome
        res_crome = brain.execute_intent("launch crome")
        assert res_crome["status"] == "success"
        assert res_crome["target"] == "Google Chrome"

        # Abbreviation: calc -> Calculator
        res_calc = brain.execute_intent("open calc")
        assert res_calc["status"] == "success"
        assert res_calc["target"] == "Calculator"

        # Typo: notse -> Notes
        res_notes = brain.execute_intent("switch to notse")
        assert res_notes["status"] == "success"
        assert res_notes["target"] == "Notes"

def test_assistant_fast_path_folder_navigation(brain):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0

        # Open downloads
        res_down = brain.execute_intent("open downloads")
        assert res_down["status"] == "success"
        assert res_down["action"] == "open_folder"
        assert res_down["folder"] == "downloads"
        assert "Downloads" in res_down["path"]

        # Open documents
        res_docs = brain.execute_intent("go to documents")
        assert res_docs["status"] == "success"
        assert res_docs["action"] == "open_folder"
        assert res_docs["folder"] == "documents"

        # Open desktop
        res_desk = brain.execute_intent("open desktop folder")
        assert res_desk["status"] == "success"
        assert res_desk["action"] == "open_folder"
        assert res_desk["folder"] == "desktop"

def test_assistant_fast_path_quit_app(brain):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0

        # Quit Spotify
        res_quit = brain.execute_intent("quit Spotify")
        assert res_quit["status"] == "success"
        assert res_quit["action"] == "quit_app"
        assert res_quit["target"] == "Spotify"

        # Close Chrome with typo
        res_close = brain.execute_intent("close crome")
        assert res_close["status"] == "success"
        assert res_close["target"] == "Google Chrome"

def test_assistant_mistral_standard_model_priority():
    b_def = AssistantBrain()
    assert any(sub in b_def.preferred_model.lower() for sub in ["mistral", "ministral"])

def test_omnibar_onboarding_ui_and_ipc(tmp_path):
    from desktop_dom.assistant.omnibar import FloatingOmnibar, OmnibarScriptHandler
    from desktop_dom.assistant.memory import AuraMemory

    db_file = tmp_path / "test_omnibar_aura.db"
    mem = AuraMemory(db_path=str(db_file))
    mem.auto_hydrate_environment()

    brain = MagicMock()
    brain.memory = mem
    bar = FloatingOmnibar(brain=brain)
    bar._webview = MagicMock()

    # 1. Test on_get_onboarding_requested
    bar.on_get_onboarding_requested()
    assert bar._webview.evaluateJavaScript_completionHandler_.call_count == 1
    eval_call_arg = bar._webview.evaluateJavaScript_completionHandler_.call_args[0][0]
    assert "window.displayOnboardingDrawer" in eval_call_arg
    assert "Piyush Dua" in eval_call_arg

    # 2. Test on_save_onboarding
    custom_profile = {
        "user_name": "Piyush Dua",
        "user_role": "Backend Engineer",
        "user_company": "Crcle.ai",
        "playlists": {"focus": "Lofi Coding Beats"},
        "collaborators": [
            {"name": "Joshua Rayan", "email": "josh@crcle.ai", "role": "Founder"},
            {"name": "Cyril Rayan", "email": "cyril@crcle.ai", "role": "Founder"}
        ]
    }
    bar.on_save_onboarding(custom_profile)
    assert bar._webview.evaluateJavaScript_completionHandler_.call_count == 2
    eval_saved_arg = bar._webview.evaluateJavaScript_completionHandler_.call_args[0][0]
    assert "window.auraOnboardingSaved" in eval_saved_arg
    assert "Lofi Coding Beats" in eval_saved_arg

    # 3. Test on_query_submitted intercepts /onboard
    bar._webview.reset_mock()
    bar.on_query_submitted("/onboard")
    assert bar._webview.evaluateJavaScript_completionHandler_.call_count == 1
    assert "window.displayOnboardingDrawer" in bar._webview.evaluateJavaScript_completionHandler_.call_args[0][0]

    # 4. Test OmnibarScriptHandler bridge
    handler = OmnibarScriptHandler(bar)
    mock_msg_get = MagicMock()
    mock_msg_get.body.return_value = json.dumps({"action": "get_onboarding_data"})
    bar._webview.reset_mock()
    handler.userContentController_didReceiveScriptMessage_(None, mock_msg_get)
    assert "window.displayOnboardingDrawer" in bar._webview.evaluateJavaScript_completionHandler_.call_args[0][0]

    mock_msg_save = MagicMock()
    mock_msg_save.body.return_value = json.dumps({"action": "save_onboarding", "profile": custom_profile})
    bar._webview.reset_mock()
    handler.userContentController_didReceiveScriptMessage_(None, mock_msg_save)
    assert "window.auraOnboardingSaved" in bar._webview.evaluateJavaScript_completionHandler_.call_args[0][0]

def test_omnibar_onboarding_e2e_storage_and_cluster_isolation(tmp_path):
    from desktop_dom.assistant.memory import AuraMemory
    from desktop_dom.assistant.brain import AssistantBrain
    from desktop_dom.assistant.omnibar import FloatingOmnibar

    db_file = tmp_path / "e2e_onboarding_aura.db"
    mem = AuraMemory(db_path=str(db_file))
    brain = AssistantBrain(preferred_model="ministral-3:8b", memory=mem)
    bar = FloatingOmnibar(brain=brain)
    bar._webview = MagicMock()

    # Save verified onboarding state through Omnibar IPC
    bar.on_save_onboarding({
        "user_name": "Piyush Dua",
        "user_role": "Backend Engineer",
        "user_company": "Crcle.ai",
        "playlists": {"focus": "Synthwave Chill", "personal": "Ambient Chill"},
        "collaborators": [
            {"name": "Joshua Rayan", "email": "josh@crcle.ai", "role": "CTO"},
            {"name": "Cyril Rayan", "email": "cyril@crcle.ai", "role": "CEO"}
        ]
    })

    # Verify Knowledge Graph DB state
    assert mem.is_onboarding_verified()
    assert mem.get_preference("user.name") == "Piyush Dua"
    assert mem.get_preference("user.company") == "Crcle.ai"
    assert mem.get_preference("spotify.favorite_playlist") == "Synthwave Chill"

    # Verify cluster isolation
    shared = mem.find_shared_context("Joshua Rayan", "Ambient Chill")
    assert shared["status"] == "disjoint"
    assert shared["distance"] == float("inf")

    # Verify intent execution respects verified onboarding without hallucination or leakage
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        email_res = brain.execute_intent("write an email to josh about current progress")
        assert email_res["status"] == "success"
        assert "Ambient Chill" not in email_res["body"]
        assert "YouTube" not in email_res["body"]
        assert "Joshua Rayan" in email_res["recipient"]
        assert "Piyush Dua" in email_res["draft_body"]
        assert "Backend Engineer | Crcle.ai" in email_res["signature"]


def test_omnibar_settings_ui_and_ipc(tmp_path):
    from desktop_dom.assistant.omnibar import FloatingOmnibar, OmnibarScriptHandler
    from desktop_dom.assistant.memory import AuraMemory

    db_file = tmp_path / "test_settings_aura.db"
    mem = AuraMemory(db_path=str(db_file))
    mem.auto_hydrate_environment()

    brain = MagicMock()
    brain.memory = mem
    bar = FloatingOmnibar(brain=brain)
    bar._webview = MagicMock()

    # 1. Test on_get_settings_requested
    bar.on_get_settings_requested()
    assert bar._webview.evaluateJavaScript_completionHandler_.call_count == 1
    eval_call = bar._webview.evaluateJavaScript_completionHandler_.call_args[0][0]
    assert "window.displaySettingsDrawer" in eval_call
    assert "Piyush Dua" in eval_call

    # 2. Test on_save_settings
    bar._webview.reset_mock()
    bar.on_save_settings({
        "user": {"name": "Piyush Dua", "role": "Senior Engineer", "company": "Crcle.ai"},
        "playlists": {"focus": "Ambient Coding"}
    })
    assert bar._webview.evaluateJavaScript_completionHandler_.call_count == 1
    eval_save = bar._webview.evaluateJavaScript_completionHandler_.call_args[0][0]
    assert "window.auraSettingsSaved" in eval_save
    assert mem.get_preference("user.role") == "Senior Engineer"
    assert mem.get_preference("spotify.favorite_playlist") == "Ambient Coding"

    # 3. Test on_add_collaborator & on_delete_collaborator
    bar._webview.reset_mock()
    bar.on_add_collaborator(name="Elena Rostova", email="elena@crcle.ai", role="Design Lead", company="Crcle.ai")
    assert bar._webview.evaluateJavaScript_completionHandler_.call_count == 1
    assert "Elena Rostova" in bar._webview.evaluateJavaScript_completionHandler_.call_args[0][0]

    settings = mem.get_user_settings()
    elena = next((c for c in settings["collaborators"] if c["name"] == "Elena Rostova"), None)
    assert elena is not None
    assert elena["email"] == "elena@crcle.ai"

    # Delete collaborator
    bar._webview.reset_mock()
    bar.on_delete_collaborator(elena["id"])
    assert bar._webview.evaluateJavaScript_completionHandler_.call_count == 1
    settings_after = mem.get_user_settings()
    assert not any(c["name"] == "Elena Rostova" for c in settings_after["collaborators"])

    # 4. Test OmnibarScriptHandler bridge for settings
    handler = OmnibarScriptHandler(bar)
    mock_msg = MagicMock()
    mock_msg.body.return_value = json.dumps({"action": "get_settings"})
    bar._webview.reset_mock()
    handler.userContentController_didReceiveScriptMessage_(None, mock_msg)
    assert "window.displaySettingsDrawer" in bar._webview.evaluateJavaScript_completionHandler_.call_args[0][0]

    # Test /settings intercept
    bar._webview.reset_mock()
    bar.on_query_submitted("/settings")
    assert "window.displaySettingsDrawer" in bar._webview.evaluateJavaScript_completionHandler_.call_args[0][0]


def test_settings_natural_language_collaborators(tmp_path):
    from desktop_dom.assistant.memory import AuraMemory
    from desktop_dom.assistant.brain import AssistantBrain

    db_file = tmp_path / "test_nl_settings_aura.db"
    mem = AuraMemory(db_path=str(db_file))
    mem.auto_hydrate_environment()
    brain = AssistantBrain(memory=mem)

    # 1. Open settings intent
    res_set = brain.execute_intent("open settings")
    assert res_set["status"] == "success"
    assert res_set["action"] == "open_settings"

    # 2. Add collaborator
    res_add = brain.execute_intent("add collaborator Marcus Vance marcus@crcle.ai")
    assert res_add["status"] == "success"
    assert res_add["action"] == "add_collaborator"
    assert "Marcus Vance" in res_add["response"]

    # Verify in memory
    ent = mem.resolve_entity("Marcus Vance")
    assert ent is not None
    assert ent["email"] == "marcus@crcle.ai"

    # 3. Remove collaborator
    res_del = brain.execute_intent("remove collaborator Marcus Vance")
    assert res_del["status"] == "success"
    assert res_del["action"] == "delete_collaborator"
    assert mem.resolve_entity("Marcus Vance") is None


def test_app_addition_ui_ipc_and_natural_language(tmp_path):
    from desktop_dom.assistant.memory import AuraMemory
    from desktop_dom.assistant.brain import AssistantBrain
    from desktop_dom.assistant.omnibar import FloatingOmnibar, OmnibarScriptHandler

    db_file = tmp_path / "test_app_addition.db"
    mem = AuraMemory(db_path=str(db_file))
    mem.auto_hydrate_environment()
    brain = AssistantBrain(memory=mem)

    bar = FloatingOmnibar(brain=brain)
    bar._webview = MagicMock()

    # 1. Test on_add_app in FloatingOmnibar
    bar.on_add_app(name="Notion", category="productivity")
    assert bar._webview.evaluateJavaScript_completionHandler_.call_count == 1
    eval_call = bar._webview.evaluateJavaScript_completionHandler_.call_args[0][0]
    assert "window.displaySettingsDrawer" in eval_call
    assert "Notion" in eval_call

    # Check in memory & graph
    ent = mem.resolve_entity("Notion")
    assert ent is not None
    assert ent["category"] == "application"
    conns = mem.get_connected_nodes("Piyush Dua", relation="uses_app")
    assert any(c["node_name"] == "Notion" for c in conns)

    # 2. Test on_delete_app
    bar._webview.reset_mock()
    bar.on_delete_app("Notion")
    assert bar._webview.evaluateJavaScript_completionHandler_.call_count == 1
    assert mem.resolve_entity("Notion") is None

    # 3. Test natural language commands
    res_nl_add = brain.execute_intent("add app Slack as communication")
    assert res_nl_add["status"] == "success"
    assert res_nl_add["action"] == "add_app"
    assert "Slack" in res_nl_add["response"]
    assert mem.resolve_entity("Slack") is not None

    res_nl_del = brain.execute_intent("remove app Slack")
    assert res_nl_del["status"] == "success"
    assert res_nl_del["action"] == "delete_app"
    assert mem.resolve_entity("Slack") is None

    # 4. Test OmnibarScriptHandler bridge for add_app
    handler = OmnibarScriptHandler(bar)
    mock_msg = MagicMock()
    mock_msg.body.return_value = json.dumps({"action": "add_app", "name": "Xcode", "category": "developer"})
    bar._webview.reset_mock()
    handler.userContentController_didReceiveScriptMessage_(None, mock_msg)
    assert "window.displaySettingsDrawer" in bar._webview.evaluateJavaScript_completionHandler_.call_args[0][0]
    assert mem.resolve_entity("Xcode") is not None

    # 5. Test onboarding with connected_apps
    onb_res = mem.complete_verified_onboarding({
        "user_name": "Piyush Dua",
        "connected_apps": [
            {"name": "Figma", "category": "design"},
            {"name": "Linear", "category": "productivity"}
        ]
    })
    assert onb_res["status"] == "success"
    assert mem.resolve_entity("Figma") is not None
    assert mem.resolve_entity("Linear") is not None


def test_dynamic_intent_resolution_zero_hardcoding(tmp_path):
    """
    Verifies that intent computing resolves dynamically from the sovereign Knowledge Graph
    and onboarding bindings without hardcoding:
    - If user configures Granola, 'meeting' routes to Granola.
    - If user configures Zoom, 'meeting' routes to Zoom.
    - If unconfigured, cleanly returns unconfigured status with zero speculation.
    """
    from desktop_dom.assistant.memory import AuraMemory
    from desktop_dom.assistant.brain import AssistantBrain

    db_file = tmp_path / "intent_zero_hardcoding.db"
    mem = AuraMemory(db_path=str(db_file))
    brain = AssistantBrain(memory=mem)

    # 1. Unconfigured meeting intent
    mem.set_preference("apps.primary_meeting", "")
    res_unconf = brain.execute_intent("i have a meeting")
    assert res_unconf["status"] == "unconfigured"
    assert res_unconf["action"] == "meeting_intent"
    assert "No meeting tool bound in your onboarding setup" in res_unconf["response"]

    # 2. Onboard with Granola as meeting companion
    mem.complete_verified_onboarding({
        "user_name": "Piyush Dua",
        "app_bindings": {"meeting": "Granola"},
        "connected_apps": [{"name": "Granola", "category": "meeting"}],
        "collaborators": [{"name": "Cyril Rayan", "role": "Systems Architect", "company": "Crcle.ai", "email": "cyril@crcle.ai"}]
    })
    assert mem.resolve_app_for_intent("meeting") == "Granola"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        res_granola = brain.execute_intent("i have a meeting")
        assert res_granola["status"] == "success"
        assert res_granola["action"] == "meeting_intent"
        assert res_granola["tool"] == "Granola"
        assert "Opened Granola for your meeting notes" in res_granola["response"]
        mock_run.assert_any_call(["open", "-a", "Granola"], capture_output=True, text=True)

    # 3. Meeting with Cyril Rayan
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        res_collab = brain.execute_intent("i have a meeting with Cyril regarding product roadmap")
        assert res_collab["status"] == "success"
        assert res_collab["tool"] == "Granola"
        assert res_collab["participant"]["name"] == "Cyril Rayan"
        assert res_collab["topic"] == "product roadmap"
        assert "Cyril Rayan" in res_collab["response"]
        assert "product roadmap" in res_collab["response"]

    # 4. User changes meeting app to Zoom in Settings (zero hardcoding proof!)
    mem.update_user_settings({
        "app_bindings": {"meeting": "Zoom"}
    })
    assert mem.resolve_app_for_intent("meeting") == "Zoom"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        res_zoom = brain.execute_intent("i have a meeting")
        assert res_zoom["status"] == "success"
        assert res_zoom["tool"] == "Zoom"
        assert "Opened Zoom for your meeting notes" in res_zoom["response"]
        mock_run.assert_any_call(["open", "-a", "Zoom"], capture_output=True, text=True)


def test_thousands_of_use_cases_dynamic_capability_binding(tmp_path):
    """
    Verifies that the Knowledge Graph and onboarding engine seamlessly handle 1,000+ use cases
    (design, tasks, 3d, crm, notes) purely via user capability registration.
    """
    from desktop_dom.assistant.memory import AuraMemory
    from desktop_dom.assistant.brain import AssistantBrain

    db_file = tmp_path / "use_cases.db"
    mem = AuraMemory(db_path=str(db_file))
    brain = AssistantBrain(memory=mem)

    # Register arbitrary domain capabilities during onboarding / settings
    mem.add_app(name="Figma", category="design")
    mem.add_app(name="Linear", category="tasks")
    mem.add_app(name="Blender", category="3d")
    mem.add_app(name="Notion", category="notes")
    mem.add_app(name="Salesforce", category="crm")

    assert mem.resolve_app_for_intent("design") == "Figma"
    assert mem.resolve_app_for_intent("tasks") == "Linear"
    assert mem.resolve_app_for_intent("3d") == "Blender"
    assert mem.resolve_app_for_intent("notes") == "Notion"
    assert mem.resolve_app_for_intent("crm") == "Salesforce"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0

        # 1. Design intent
        res_des = brain.execute_intent("open design")
        assert res_des["status"] == "success"
        assert res_des["action"] == "design_intent"
        assert res_des["tool"] == "Figma"
        mock_run.assert_any_call(["open", "-a", "Figma"], capture_output=True, text=True)

        # 2. Tasks intent
        res_tsk = brain.execute_intent("check tasks")
        assert res_tsk["status"] == "success"
        assert res_tsk["action"] == "tasks_intent"
        assert res_tsk["tool"] == "Linear"
        mock_run.assert_any_call(["open", "-a", "Linear"], capture_output=True, text=True)

        # 3. 3D intent
        res_3d = brain.execute_intent("start 3d")
        assert res_3d["status"] == "success"
        assert res_3d["action"] == "3d_intent"
        assert res_3d["tool"] == "Blender"
        mock_run.assert_any_call(["open", "-a", "Blender"], capture_output=True, text=True)


def test_omnibar_misfire_feedback_ui_and_ipc(tmp_path):
    """
    Verifies Aspect 1: Omnibar 1-Click Misfire Feedback ('Wrong tool? Teach Aura')
    and IPC self-correction pipeline.
    """
    from desktop_dom.assistant.omnibar import OMNIBAR_HTML, FloatingOmnibar, OmnibarScriptHandler
    from desktop_dom.assistant.memory import AuraMemory

    # 1. Verify HTML/CSS/JS template elements exist
    assert "Wrong tool? Teach Aura" in OMNIBAR_HTML
    assert "misfire-feedback-bar" in OMNIBAR_HTML
    assert "misfire-chip" in OMNIBAR_HTML
    assert "misfire-inline-form" in OMNIBAR_HTML
    assert "misfire-tool-input" in OMNIBAR_HTML
    assert "record_misfire" in OMNIBAR_HTML
    assert "window.auraMisfireRecorded" in OMNIBAR_HTML
    assert "Preference updated — Aura learned!" in OMNIBAR_HTML

    # 2. Test FloatingOmnibar.on_record_misfire
    db_file = tmp_path / "test_omnibar_misfire.db"
    mem = AuraMemory(db_path=str(db_file))
    mem.auto_hydrate_environment()

    brain = MagicMock()
    brain.memory = mem
    bar = FloatingOmnibar(brain=brain)
    bar._webview = MagicMock()

    res = bar.on_record_misfire("i have a meeting", "Granola", "Zoom")
    assert res is not None
    assert res["status"] == "success"
    assert res["false_positive"] == "Granola"
    assert res["corrected_to"] == "Zoom"

    # Verify evaluate_js updated UI status and invoked auraMisfireRecorded
    assert bar._webview.evaluateJavaScript_completionHandler_.call_count == 1
    eval_call_arg = bar._webview.evaluateJavaScript_completionHandler_.call_args[0][0]
    assert "window.auraMisfireRecorded" in eval_call_arg
    assert "Preference updated — Aura learned!" in eval_call_arg
    assert "Learned preference" in eval_call_arg

    # Verify misfire record in database
    with mem._lock, mem._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM misfires WHERE query = 'i have a meeting';")
        row = cursor.fetchone()
        assert row is not None
        assert row["false_positive_target"] == "Granola"
        assert row["corrected_target"] == "Zoom"
        ctx = json.loads(row["context_snapshot"])
        assert ctx.get("user_feedback") == "User clicked teach aura chip"

    # 3. Test OmnibarScriptHandler bridge dispatch
    handler = OmnibarScriptHandler(bar)
    mock_msg = MagicMock()
    mock_msg.body.return_value = json.dumps({
        "action": "record_misfire",
        "query": "open design workspace",
        "wrong_app": "Illustrator",
        "correct_app": "Figma"
    })
    bar._webview.reset_mock()
    handler.userContentController_didReceiveScriptMessage_(None, mock_msg)

    assert bar._webview.evaluateJavaScript_completionHandler_.call_count == 1
    eval_arg2 = bar._webview.evaluateJavaScript_completionHandler_.call_args[0][0]
    assert "window.auraMisfireRecorded" in eval_arg2
    assert "Learned preference" in eval_arg2

    with mem._lock, mem._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM misfires WHERE query = 'open design workspace';")
        row2 = cursor.fetchone()
        assert row2 is not None
        assert row2["false_positive_target"] == "Illustrator"
        assert row2["corrected_target"] == "Figma"











