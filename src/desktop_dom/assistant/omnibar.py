from __future__ import annotations
import sys
import json
import time
import logging
import threading
from typing import Optional

logger = logging.getLogger("desktop_dom.assistant.omnibar")

# HTML Template for Glassmorphic Spotlight / Raycast Omnibar
OMNIBAR_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    user-select: none;
    -webkit-user-select: none;
  }
  body {
    width: 100vw;
    height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Instrument Sans", sans-serif;
    overflow: hidden;
  }
  .omnibar-container {
    width: 700px;
    height: 70px;
    border-radius: 24px;
    background: rgba(14, 16, 24, 0.88);
    backdrop-filter: blur(32px) saturate(200%);
    -webkit-backdrop-filter: blur(32px) saturate(200%);
    border: 1px solid rgba(0, 240, 255, 0.35);
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.7), 0 0 24px rgba(0, 240, 255, 0.18);
    display: flex;
    align-items: center;
    padding: 0 20px;
    gap: 14px;
    transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .omnibar-container.executing {
    border-color: rgba(57, 255, 20, 0.6);
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.7), 0 0 30px rgba(57, 255, 20, 0.25);
  }
  .brand-orb {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: linear-gradient(135deg, #00f0ff, #7000ff);
    box-shadow: 0 0 14px rgba(0, 240, 255, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 16px;
    font-weight: 700;
    flex-shrink: 0;
    cursor: pointer;
  }
  .brand-orb:hover {
    transform: scale(1.05);
  }
  .input-wrapper {
    flex: 1;
    position: relative;
    display: flex;
    align-items: center;
  }
  input#query-input {
    width: 100%;
    background: transparent;
    border: none;
    outline: none;
    color: #ffffff;
    font-size: 18px;
    font-weight: 500;
    letter-spacing: -0.2px;
  }
  input#query-input::placeholder {
    color: rgba(255, 255, 255, 0.38);
    font-size: 16px;
  }
  #waveform-canvas {
    width: 70px;
    height: 28px;
    flex-shrink: 0;
    border-radius: 8px;
  }
  .mic-btn {
    width: 34px;
    height: 34px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
    color: #00f0ff;
  }
  .mic-btn:hover {
    background: rgba(0, 240, 255, 0.2);
    transform: scale(1.05);
  }
  .mic-btn.active {
    background: #ff007f;
    border-color: #ff007f;
    color: white;
    box-shadow: 0 0 15px rgba(255, 0, 127, 0.6);
    animation: pulse 1s infinite alternate;
  }
  @keyframes pulse {
    0% { transform: scale(1); }
    100% { transform: scale(1.1); }
  }
  .status-badge {
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    background: rgba(0, 240, 255, 0.12);
    color: #00f0ff;
    border: 1px solid rgba(0, 240, 255, 0.25);
    flex-shrink: 0;
  }
</style>
</head>
<body>
  <div class="omnibar-container" id="container">
    <div class="brand-orb" title="Aura AI">⚡</div>
    <div class="input-wrapper">
      <input id="query-input" type="text" placeholder="Ask anything, or speak... (e.g. 'Play Starboy on Spotify')" autocomplete="off" autofocus />
    </div>
    <canvas id="waveform-canvas" width="140" height="56"></canvas>
    <div class="mic-btn" id="mic-btn" title="Toggle Microphone">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
        <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
        <line x1="12" x2="12" y1="19" y2="22"/>
      </svg>
    </div>
    <div class="status-badge" id="badge">Ready</div>
  </div>

  <script>
    const input = document.getElementById("query-input");
    const container = document.getElementById("container");
    const badge = document.getElementById("badge");
    const micBtn = document.getElementById("mic-btn");
    const canvas = document.getElementById("waveform-canvas");
    const ctx = canvas.getContext("2d");

    let isListening = false;
    let waveOffset = 0;

    // Animated live waveform canvas
    function drawWave() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const centerY = canvas.height / 2;
      const amplitude = isListening ? 18 : 6;
      const freq = isListening ? 0.08 : 0.04;
      
      ctx.beginPath();
      ctx.lineWidth = 2.5;
      ctx.strokeStyle = isListening ? "#ff007f" : "#00f0ff";

      for (let x = 0; x < canvas.width; x++) {
        const y = centerY + Math.sin(x * freq + waveOffset) * amplitude * Math.sin(x / canvas.width * Math.PI);
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      waveOffset += isListening ? 0.18 : 0.05;
      requestAnimationFrame(drawWave);
    }
    drawWave();

    // Send query on Enter
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const val = input.value.trim();
        if (val) {
          submitQuery(val);
        }
      } else if (e.key === "Escape") {
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "close" }));
      }
    });

    micBtn.addEventListener("click", () => {
      toggleMic();
    });

    function toggleMic() {
      isListening = !isListening;
      if (isListening) {
        micBtn.classList.add("active");
        badge.innerText = "Listening";
        badge.style.color = "#ff007f";
        badge.style.borderColor = "rgba(255, 0, 127, 0.4)";
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "start_listening" }));
      } else {
        micBtn.classList.remove("active");
        badge.innerText = "Ready";
        badge.style.color = "#00f0ff";
        badge.style.borderColor = "rgba(0, 240, 255, 0.25)";
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "stop_listening" }));
      }
    }

    function submitQuery(query) {
      container.classList.add("executing");
      badge.innerText = "Executing";
      badge.style.color = "#39ff14";
      badge.style.borderColor = "rgba(57, 255, 20, 0.4)";
      window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "submit_query", query: query }));
    }

    // Called from Python bridge
    window.updateOmnibar = function(status, text) {
      badge.innerText = status;
      if (text) {
        input.value = text;
      }
    };
  </script>
</body>
</html>
"""

class OmnibarScriptHandler:
    def __init__(self, omnibar_controller):
        self.controller = omnibar_controller

    def userContentController_didReceiveScriptMessage_(self, ucc, msg):
        try:
            payload = json.loads(str(msg.body()))
            action = payload.get("action")
            if action == "submit_query":
                query = payload.get("query", "")
                self.controller.on_query_submitted(query)
            elif action == "start_listening":
                self.controller.on_voice_requested()
            elif action == "close":
                self.controller.hide()
        except Exception as e:
            logger.warning(f"Error handling script message: {e}")

class FloatingOmnibar:
    """
    Native macOS floating glassmorphic spotlight bar powered by Cocoa & WebKit.
    Floats on top of all windows and spaces on hotkey (Cmd+Shift+Space).
    """

    def __init__(self, brain=None, audio=None):
        self.brain = brain
        self.audio = audio
        self._panel = None
        self._webview = None
        self._app = None
        self._is_visible = False

    def setup_ui(self):
        """Initializes the Cocoa window and WebKit view on the main thread."""
        try:
            import Cocoa
            import WebKit
            import objc
        except ImportError:
            raise RuntimeError("PyObjC Cocoa and WebKit required for native Omnibar.")

        self._app = Cocoa.NSApplication.sharedApplication()
        self._app.setActivationPolicy_(Cocoa.NSApplicationActivationPolicyAccessory)

        screen = Cocoa.NSScreen.mainScreen()
        if screen is None:
            raise RuntimeError("No active display screen found for Cocoa GUI.")
        screen_frame = screen.frame()
        bar_width = 720
        bar_height = 80
        # Position horizontally centered, ~22% from top of screen
        pos_x = (screen_frame.size.width - bar_width) / 2
        pos_y = screen_frame.size.height * 0.72

        # Create frameless floating NSPanel
        self._panel = Cocoa.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            Cocoa.NSMakeRect(pos_x, pos_y, bar_width, bar_height),
            Cocoa.NSWindowStyleMaskBorderless | Cocoa.NSWindowStyleMaskNonactivatingPanel,
            Cocoa.NSBackingStoreBuffered,
            False,
        )

        self._panel.setLevel_(Cocoa.NSFloatingWindowLevel)
        self._panel.setOpaque_(False)
        self._panel.setBackgroundColor_(Cocoa.NSColor.clearColor())
        self._panel.setHasShadow_(True)
        self._panel.setMovableByWindowBackground_(True)
        self._panel.setCollectionBehavior_(
            Cocoa.NSWindowCollectionBehaviorCanJoinAllSpaces |
            Cocoa.NSWindowCollectionBehaviorFullScreenAuxiliary
        )

        # Configure WebKit View
        config = WebKit.WKWebViewConfiguration.alloc().init()
        
        # Script Message Handler Bridge
        try:
            handler_cls = objc.lookUpClass("OmnibarScriptHandlerObjC")
        except Exception:
            handler_cls = None

        if handler_cls is None:
            class OmnibarScriptHandlerObjC(Cocoa.NSObject):
                def initWithController_(self, ctrl):
                    self = objc.super(OmnibarScriptHandlerObjC, self).init()
                    if self:
                        self.ctrl = ctrl
                    return self

                def userContentController_didReceiveScriptMessage_(self, ucc, msg):
                    try:
                        payload = json.loads(str(msg.body()))
                        act = payload.get("action")
                        if act == "submit_query":
                            self.ctrl.on_query_submitted(payload.get("query", ""))
                        elif act == "start_listening":
                            self.ctrl.on_voice_requested()
                        elif act == "close":
                            self.ctrl.hide()
                    except Exception as e:
                        logger.warning(f"Bridge dispatch error: {e}")

            handler_cls = OmnibarScriptHandlerObjC

        handler_obj = handler_cls.alloc().initWithController_(self)
        config.userContentController().addScriptMessageHandler_name_(handler_obj, "desktopDom")

        self._webview = WebKit.WKWebView.alloc().initWithFrame_configuration_(
            Cocoa.NSMakeRect(0, 0, bar_width, bar_height),
            config
        )
        self._webview.setValue_forKey_(False, "drawsBackground")
        self._webview.loadHTMLString_baseURL_(OMNIBAR_HTML, None)

        self._panel.contentView().addSubview_(self._webview)

    def show(self):
        """Displays and focuses the floating Omnibar."""
        if self._panel:
            self._panel.makeKeyAndOrderFront_(None)
            self._panel.setAlphaValue_(1.0)
            self._is_visible = True

    def hide(self):
        """Hides the Omnibar."""
        if self._panel:
            self._panel.orderOut_(None)
            self._is_visible = False

    def toggle(self):
        """Toggles Omnibar visibility."""
        if self._is_visible:
            self.hide()
        else:
            self.show()

    def on_query_submitted(self, query: str):
        """Called when user presses Enter with text."""
        logger.info(f"Omnibar query submitted: '{query}'")
        
        def _execute():
            # Fade or hide bar
            time.sleep(0.15)
            self.hide()
            
            if self.brain:
                res = self.brain.execute_intent(query)
                answer = res.get("response", "Task completed.")
                if self.audio:
                    self.audio.speak(answer)

        threading.Thread(target=_execute, daemon=True).start()

    def on_voice_requested(self):
        """Called when user clicks mic button to speak."""
        logger.info("Voice capture initiated...")
        def _listen():
            if self.audio:
                text = self.audio.record_and_transcribe(duration=3.5)
                if text:
                    self.on_query_submitted(text)
                else:
                    self.audio.speak("I didn't catch that.")
        threading.Thread(target=_listen, daemon=True).start()

    def start_global_hotkey_listener(self):
        """Listens for Cmd+Shift+Space to summon/hide the Omnibar."""
        try:
            from pynput import keyboard
            current_keys = set()

            def on_press(key):
                current_keys.add(key)
                # Check for Cmd + Shift + Space
                cmd_pressed = any(k in current_keys for k in [keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r])
                shift_pressed = any(k in current_keys for k in [keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r])
                space_pressed = (key == keyboard.Key.space)

                if cmd_pressed and shift_pressed and space_pressed:
                    self.toggle()

            def on_release(key):
                current_keys.discard(key)

            listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            listener.daemon = True
            listener.start()
            logger.info("Global hotkey (Cmd+Shift+Space) registered.")
        except Exception as e:
            logger.warning(f"Could not bind global hotkey: {e}")

    def run(self):
        """Starts the native macOS Cocoa event loop."""
        self.setup_ui()
        self.start_global_hotkey_listener()
        self.show()
        if self._app:
            self._app.run()
