from __future__ import annotations
import sys
import json
import time
import logging
import threading
from typing import Optional

logger = logging.getLogger("desktop_dom.assistant.omnibar")

# Sophisticated Liquid Glass Spotlight / Raycast Omnibar HTML Template
OMNIBAR_HTML = r"""<!DOCTYPE html>
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
    flex-direction: column;
    align-items: center;
    background: transparent;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", sans-serif;
    overflow: hidden;
  }
  .omnibar-card {
    width: 700px;
    border-radius: 20px;
    background: rgba(12, 14, 22, 0.88);
    backdrop-filter: blur(40px) saturate(210%);
    -webkit-backdrop-filter: blur(40px) saturate(210%);
    border: 1px solid rgba(255, 255, 255, 0.12);
    box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.22), 0 20px 60px rgba(0, 0, 0, 0.65), 0 0 30px rgba(0, 240, 255, 0.12);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: border-color 0.25s ease, box-shadow 0.25s ease;
  }
  .omnibar-card.listening {
    border-color: rgba(255, 0, 127, 0.5);
    box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.22), 0 20px 60px rgba(0, 0, 0, 0.7), 0 0 35px rgba(255, 0, 127, 0.25);
  }
  .omnibar-card.executing {
    border-color: rgba(57, 255, 20, 0.6);
    box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.22), 0 20px 60px rgba(0, 0, 0, 0.7), 0 0 35px rgba(57, 255, 20, 0.25);
  }
  .header-bar {
    height: 70px;
    display: flex;
    align-items: center;
    padding: 0 18px;
    gap: 14px;
    position: relative;
  }
  .brand-orb {
    width: 34px;
    height: 34px;
    border-radius: 50%;
    background: radial-gradient(circle at 30% 30%, #00f0ff, #7000ff 70%, #ff007f 100%);
    box-shadow: 0 0 16px rgba(0, 240, 255, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 15px;
    font-weight: 800;
    flex-shrink: 0;
    cursor: pointer;
    transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .brand-orb:hover {
    transform: scale(1.08);
  }
  .input-wrap {
    flex: 1;
    display: flex;
    align-items: center;
  }
  input#query-input {
    width: 100%;
    background: transparent;
    border: none;
    outline: none;
    color: #ffffff;
    font-size: 17px;
    font-weight: 500;
    letter-spacing: -0.25px;
  }
  input#query-input::placeholder {
    color: rgba(255, 255, 255, 0.35);
    font-weight: 400;
  }
  #waveform-canvas {
    width: 72px;
    height: 28px;
    flex-shrink: 0;
  }
  .mic-btn {
    width: 34px;
    height: 34px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
    color: #00f0ff;
    flex-shrink: 0;
  }
  .mic-btn:hover {
    background: rgba(0, 240, 255, 0.18);
    transform: scale(1.06);
  }
  .mic-btn.active {
    background: #ff007f;
    border-color: #ff007f;
    color: white;
    box-shadow: 0 0 16px rgba(255, 0, 127, 0.7);
    animation: micPulse 1.2s infinite alternate ease-in-out;
  }
  @keyframes micPulse {
    0% { transform: scale(1); }
    100% { transform: scale(1.12); }
  }
  .status-badge {
    padding: 4px 10px;
    border-radius: 10px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    background: rgba(0, 240, 255, 0.1);
    color: #00f0ff;
    border: 1px solid rgba(0, 240, 255, 0.25);
    flex-shrink: 0;
  }
  .tray {
    display: flex;
    flex-direction: column;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(8, 10, 15, 0.4);
    padding: 8px 10px;
    gap: 4px;
    max-height: 240px;
    overflow-y: auto;
  }
  .suggestion-item {
    display: flex;
    align-items: center;
    padding: 8px 12px;
    border-radius: 10px;
    gap: 12px;
    cursor: pointer;
    transition: background 0.15s ease;
  }
  .suggestion-item:hover, .suggestion-item.selected {
    background: rgba(255, 255, 255, 0.08);
  }
  .suggestion-icon {
    font-size: 16px;
    width: 22px;
    text-align: center;
  }
  .suggestion-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .suggestion-title {
    color: #ffffff;
    font-size: 14px;
    font-weight: 500;
  }
  .suggestion-subtitle {
    color: rgba(255, 255, 255, 0.45);
    font-size: 11px;
  }
  .suggestion-badge {
    font-size: 10px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.06);
    color: rgba(255, 255, 255, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
  }
  .suggestion-item.selected .suggestion-badge {
    background: rgba(0, 240, 255, 0.15);
    color: #00f0ff;
    border-color: rgba(0, 240, 255, 0.3);
  }
  .footer-bar {
    height: 34px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
    background: rgba(6, 7, 12, 0.6);
    font-size: 11px;
    color: rgba(255, 255, 255, 0.4);
  }
  .shortcuts {
    display: flex;
    gap: 12px;
    align-items: center;
  }
  .kbd-pill {
    display: inline-flex;
    align-items: center;
    gap: 3px;
  }
  .kbd {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 4px;
    padding: 1px 4px;
    font-size: 9px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.8);
  }
  .local-tag {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .dot-green {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #39ff14;
    box-shadow: 0 0 8px #39ff14;
  }
</style>
</head>
<body>
  <div class="omnibar-card" id="card">
    <div class="header-bar">
      <div class="brand-orb" id="brand-orb" title="Aura AI">⚡</div>
      <div class="input-wrap">
        <input id="query-input" type="text" placeholder="Ask anything, or speak... (e.g. 'Play Starboy on Spotify')" autocomplete="off" autofocus />
      </div>
      <canvas id="waveform-canvas" width="144" height="56"></canvas>
      <div class="mic-btn" id="mic-btn" title="Toggle Voice Microphone">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
          <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
          <line x1="12" x2="12" y1="19" y2="22"/>
        </svg>
      </div>
      <div class="status-badge" id="badge">Ready</div>
    </div>

    <div class="tray" id="tray">
      <!-- Dynamically generated suggestions -->
    </div>

    <div class="footer-bar">
      <div class="shortcuts">
        <span class="kbd-pill"><span class="kbd">↵</span> Execute</span>
        <span class="kbd-pill"><span class="kbd">↑↓</span> Navigate</span>
        <span class="kbd-pill"><span class="kbd">Tab</span> Complete</span>
        <span class="kbd-pill"><span class="kbd">Esc</span> Dismiss</span>
      </div>
      <div class="local-tag">
        <div class="dot-green"></div>
        <span>100% Local • Ollama + Whisper</span>
      </div>
    </div>
  </div>

  <script>
    const input = document.getElementById("query-input");
    const card = document.getElementById("card");
    const badge = document.getElementById("badge");
    const micBtn = document.getElementById("mic-btn");
    const tray = document.getElementById("tray");
    const canvas = document.getElementById("waveform-canvas");
    const ctx = canvas.getContext("2d");

    let isListening = false;
    let waveOffset = 0;
    let selectedIndex = 0;
    let currentSuggestions = [];

    // Multi-harmonic fluid sine wave visualizer
    function drawWave() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const centerY = canvas.height / 2;
      const ampBase = isListening ? 16 : 5;
      const freq = isListening ? 0.09 : 0.045;

      // Harmonic 1: Electric Cyan
      ctx.beginPath();
      ctx.lineWidth = 2.4;
      ctx.strokeStyle = isListening ? "rgba(255, 0, 127, 0.9)" : "rgba(0, 240, 255, 0.85)";
      for (let x = 0; x < canvas.width; x++) {
        const envelope = Math.sin((x / canvas.width) * Math.PI);
        const y = centerY + Math.sin(x * freq + waveOffset) * ampBase * envelope;
        if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();

      // Harmonic 2: Magenta / Violet
      ctx.beginPath();
      ctx.lineWidth = 1.8;
      ctx.strokeStyle = isListening ? "rgba(255, 255, 255, 0.7)" : "rgba(112, 0, 255, 0.6)";
      for (let x = 0; x < canvas.width; x++) {
        const envelope = Math.sin((x / canvas.width) * Math.PI);
        const y = centerY + Math.cos(x * (freq * 1.3) - waveOffset * 1.2) * (ampBase * 0.75) * envelope;
        if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();

      waveOffset += isListening ? 0.22 : 0.05;
      requestAnimationFrame(drawWave);
    }
    drawWave();

    // Default fast-path actions
    const defaultActions = [
      { icon: "🎵", title: "Play on Spotify", subtitle: "Play Starboy on Spotify", query: "Play Starboy on Spotify", badge: "Fast-Path" },
      { icon: "🧮", title: "Instant Math", subtitle: "Calculate 125 * 40 + 15", query: "Calculate 125 * 40 + 15", badge: "AST Eval" },
      { icon: "🔊", title: "Adjust System Volume", subtitle: "Set volume to 80%", query: "Set volume to 80", badge: "Hardware" },
      { icon: "⚡", title: "Launch Application", subtitle: "Open Calculator", query: "Open Calculator", badge: "DesktopApp" },
      { icon: "🌐", title: "Web Search", subtitle: "Search for quantum computing", query: "Search for quantum computing", badge: "Browser" }
    ];

    function updateSuggestions() {
      const q = input.value.trim();
      currentSuggestions = [];

      if (!q) {
        currentSuggestions = defaultActions;
      } else {
        // 1. Math match
        const mathClean = q.replace(/[^0-9+\\-*/.() ]/g, "").trim();
        if (mathClean && /[+\\-*/]/.test(mathClean)) {
          try {
            const evaluated = Function('"use strict";return (' + mathClean + ')')();
            currentSuggestions.push({
              icon: "🧮",
              title: `= ${evaluated}`,
              subtitle: `Calculate ${mathClean}`,
              query: q,
              badge: "Instant Math"
            });
          } catch(e) {}
        }

        // 2. Spotify match
        if (q.toLowerCase().startsWith("play ") || q.toLowerCase().includes("spotify")) {
          currentSuggestions.push({
            icon: "🎵",
            title: `Play "${q.replace(/play/i, "").replace(/on spotify/i, "").trim()}"`,
            subtitle: "Spotify Media Playback (<120ms)",
            query: q,
            badge: "Spotify"
          });
        }

        // 3. Volume match
        if (q.toLowerCase().includes("volume") || q.toLowerCase().includes("mute")) {
          currentSuggestions.push({
            icon: "🔊",
            title: q,
            subtitle: "System Hardware Audio Bus (<30ms)",
            query: q,
            badge: "System"
          });
        }

        // 4. App open
        if (q.toLowerCase().startsWith("open ") || q.toLowerCase().startsWith("launch ")) {
          const appName = q.replace(/^(open|launch)\s+/i, "").trim();
          currentSuggestions.push({
            icon: "⚡",
            title: `Activate ${appName}`,
            subtitle: "DesktopApp Window Attachment (<80ms)",
            query: q,
            badge: "DesktopApp"
          });
        }

        // 5. Web Search
        if (q.toLowerCase().startsWith("search ") || q.toLowerCase().startsWith("google ")) {
          const queryTerm = q.replace(/^(search|google)\s+(for\s+)?/i, "").trim();
          currentSuggestions.push({
            icon: "🌐",
            title: `Search Google for "${queryTerm}"`,
            subtitle: "Default Web Browser Query",
            query: q,
            badge: "Browser"
          });
        }

        // 6. Generic Local LLM reasoning
        currentSuggestions.push({
          icon: "🧠",
          title: `Ask Aura: "${q}"`,
          subtitle: "Local Ollama ReAct Planning Loop",
          query: q,
          badge: "Ollama"
        });
      }

      renderSuggestions();
    }

    function renderSuggestions() {
      tray.innerHTML = "";
      if (selectedIndex >= currentSuggestions.length) {
        selectedIndex = 0;
      }

      currentSuggestions.forEach((item, idx) => {
        const el = document.createElement("div");
        el.className = "suggestion-item" + (idx === selectedIndex ? " selected" : "");
        el.innerHTML = `
          <div class="suggestion-icon">${item.icon}</div>
          <div class="suggestion-content">
            <div class="suggestion-title">${escapeHtml(item.title)}</div>
            <div class="suggestion-subtitle">${escapeHtml(item.subtitle)}</div>
          </div>
          <div class="suggestion-badge">${escapeHtml(item.badge)}</div>
        `;
        el.addEventListener("click", () => {
          submitQuery(item.query);
        });
        tray.appendChild(el);
      });

      // Notify Python to dynamically resize window frame
      const totalHeight = 70 + (currentSuggestions.length * 48) + 34 + 16;
      const targetHeight = Math.min(380, Math.max(80, totalHeight));
      window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({
        action: "resize",
        height: targetHeight
      }));
    }

    function escapeHtml(str) {
      return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    input.addEventListener("input", () => {
      selectedIndex = 0;
      updateSuggestions();
    });

    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        selectedIndex = (selectedIndex + 1) % currentSuggestions.length;
        renderSuggestions();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        selectedIndex = (selectedIndex - 1 + currentSuggestions.length) % currentSuggestions.length;
        renderSuggestions();
      } else if (e.key === "Tab") {
        e.preventDefault();
        if (currentSuggestions[selectedIndex]) {
          input.value = currentSuggestions[selectedIndex].query;
          updateSuggestions();
        }
      } else if (e.key === "Enter") {
        const item = currentSuggestions[selectedIndex];
        const val = item ? item.query : input.value.trim();
        if (val) {
          submitQuery(val);
        }
      } else if (e.key === "Escape") {
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "close" }));
      }
    });

    micBtn.addEventListener("click", toggleMic);

    function toggleMic() {
      isListening = !isListening;
      if (isListening) {
        micBtn.classList.add("active");
        card.classList.add("listening");
        badge.innerText = "Listening";
        badge.style.color = "#ff007f";
        badge.style.borderColor = "rgba(255, 0, 127, 0.4)";
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "start_listening" }));
      } else {
        micBtn.classList.remove("active");
        card.classList.remove("listening");
        badge.innerText = "Ready";
        badge.style.color = "#00f0ff";
        badge.style.borderColor = "rgba(0, 240, 255, 0.25)";
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "stop_listening" }));
      }
    }

    function submitQuery(query) {
      card.classList.remove("listening");
      card.classList.add("executing");
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
        updateSuggestions();
      }
    };

    // Initial render
    updateSuggestions();
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
            elif action == "stop_listening":
                if self.controller.audio:
                    self.controller.audio.stop_speaking()
            elif action == "resize":
                new_h = float(payload.get("height", 80))
                self.controller.resize_window(new_h)
            elif action == "close":
                self.controller.hide()
        except Exception as e:
            logger.warning(f"Error handling script message: {e}")

class FloatingOmnibar:
    """
    Native macOS floating glassmorphic spotlight bar powered by Cocoa & WebKit.
    Floats on top of all windows and spaces on hotkey (Cmd+Shift+Space),
    with dynamic height expansion and menubar status item.
    """

    def __init__(self, brain=None, audio=None):
        self.brain = brain
        self.audio = audio
        self._panel = None
        self._webview = None
        self._app = None
        self._status_item = None
        self._menu_delegate = None
        self._is_visible = False
        self._base_width = 720
        self._base_height = 360

    def setup_ui(self):
        """Initializes the Cocoa window, WebKit view, and status bar item."""
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
        bar_width = self._base_width
        bar_height = self._base_height
        pos_x = (screen_frame.size.width - bar_width) / 2
        pos_y = screen_frame.size.height * 0.58

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
                        elif act == "stop_listening":
                            if self.ctrl.audio:
                                self.ctrl.audio.stop_speaking()
                        elif act == "resize":
                            new_h = float(payload.get("height", 80))
                            self.ctrl.resize_window(new_h)
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
        self.setup_status_item()

    def setup_status_item(self):
        """Sets up a sleek native macOS menu bar status item."""
        try:
            import Cocoa
            import objc
            status_bar = Cocoa.NSStatusBar.systemStatusBar()
            self._status_item = status_bar.statusItemWithLength_(Cocoa.NSVariableStatusItemLength)
            btn = self._status_item.button()
            if btn:
                btn.setTitle_("⚡")
                btn.setToolTip_("Aura Desktop Assistant (Cmd+Shift+Space)")

            try:
                del_cls = objc.lookUpClass("AuraMenuDelegateObjC")
            except Exception:
                del_cls = None

            if del_cls is None:
                class AuraMenuDelegateObjC(Cocoa.NSObject):
                    def initWithController_(self, ctrl):
                        self = objc.super(AuraMenuDelegateObjC, self).init()
                        if self:
                            self.ctrl = ctrl
                        return self

                    def onMenuShow_(self, sender):
                        if self.ctrl:
                            self.ctrl.show()

                    def onMenuQuit_(self, sender):
                        if self.ctrl and self.ctrl._app:
                            self.ctrl._app.stop_(None)
                        sys.exit(0)

                del_cls = AuraMenuDelegateObjC

            self._menu_delegate = del_cls.alloc().initWithController_(self)
            menu = Cocoa.NSMenu.alloc().init()

            item_show = Cocoa.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Show Aura (Cmd+Shift+Space)", "onMenuShow:", ""
            )
            item_show.setTarget_(self._menu_delegate)
            menu.addItem_(item_show)

            menu.addItem_(Cocoa.NSMenuItem.separatorItem())

            model_name = getattr(self.brain, "preferred_model", None) or "Fast-Path Engine"
            item_model = Cocoa.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                f"Model: {model_name}", "", ""
            )
            item_model.setEnabled_(False)
            menu.addItem_(item_model)

            menu.addItem_(Cocoa.NSMenuItem.separatorItem())

            item_quit = Cocoa.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Quit Aura", "onMenuQuit:", "q"
            )
            item_quit.setTarget_(self._menu_delegate)
            menu.addItem_(item_quit)

            self._status_item.setMenu_(menu)
        except Exception as e:
            logger.warning(f"Could not initialize NSStatusItem: {e}")

    def resize_window(self, new_height: float):
        """Dynamically animates the Cocoa NSPanel frame height when suggestions expand."""
        if not self._panel:
            return
        try:
            import Cocoa
            frame = self._panel.frame()
            if abs(frame.size.height - new_height) < 4:
                return
            delta = new_height - frame.size.height
            new_y = frame.origin.y - delta
            new_frame = Cocoa.NSMakeRect(frame.origin.x, new_y, frame.size.width, new_height)
            if self._webview:
                self._webview.setFrame_(Cocoa.NSMakeRect(0, 0, frame.size.width, new_height))
            self._panel.setFrame_display_animate_(new_frame, True, True)
        except Exception as e:
            logger.warning(f"Error resizing omnibar window: {e}")

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
            time.sleep(0.12)
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
