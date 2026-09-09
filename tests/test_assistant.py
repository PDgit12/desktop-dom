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
    
    # Check default seeded contacts
    josh = mem.resolve_entity("josh")
    assert josh is not None
    assert josh["name"] == "Joshua Rayan"
    assert josh["email"] == "josh@crcle.ai"
    assert josh["role"] == "Co-Founder & CEO"
    assert josh["company"] == "Crcle.ai"

    cyril = mem.resolve_entity("cyril")
    assert cyril is not None
    assert cyril["name"] == "Cyril Rayan"
    assert cyril["email"] == "cyril@crcle.ai"

    piyush = mem.resolve_entity("piyush")
    assert piyush is not None
    assert piyush["name"] == "Piyush Dua"
    assert piyush["email"] == "piyushdua01@gmail.com"

    # Check preferences
    fav_pl = mem.get_preference("spotify.favorite_playlist")
    assert fav_pl == "Deep Focus"
    mail_cli = mem.get_preference("mail.preferred_client")
    assert mail_cli == "Microsoft Outlook"

def test_aura_memory_natural_language_learning(tmp_path):
    from desktop_dom.assistant.memory import AuraMemory
    db_file = tmp_path / "memory_learn.db"
    mem = AuraMemory(db_file)

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

def test_assistant_memory_inspection_and_who_is(tmp_path):
    from desktop_dom.assistant.memory import AuraMemory
    mem = AuraMemory(tmp_path / "mem.db")
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
    
    start_t = time.perf_counter()
    ent = mem.resolve_entity("josh")
    elapsed_ms = (time.perf_counter() - start_t) * 1000
    assert ent is not None
    # Sub-millisecond budget
    assert elapsed_ms < 2.0, f"Memory lookup took {elapsed_ms:.3f}ms, expected < 2.0ms"

def test_aura_memory_typo_and_role_disambiguation(tmp_path):
    from desktop_dom.assistant.memory import AuraMemory
    mem = AuraMemory(tmp_path / "mem_disambig.db")
    
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





