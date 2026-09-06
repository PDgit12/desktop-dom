# desktop-dom

<p align="center">
  <strong>Playwright for Desktop: Semantic Accessibility DOM and Deterministic Action Engine for AI Agents</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/desktop-dom/"><img src="https://img.shields.io/pypi/v/desktop-dom.svg?style=flat-square&color=3776AB&label=PyPI" alt="PyPI version" /></a>
  <a href="https://www.npmjs.com/package/@desktop-dom/core"><img src="https://img.shields.io/npm/v/@desktop-dom/core.svg?style=flat-square&color=CB3837&label=npm" alt="npm version" /></a>
  <a href="https://pypi.org/project/desktop-dom/"><img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg?style=flat-square" alt="Python versions" /></a>
  <a href="https://github.com/PDgit12/desktop-dom/actions"><img src="https://img.shields.io/github/actions/workflow/status/PDgit12/desktop-dom/ci.yml?branch=main&label=CI&style=flat-square" alt="CI status" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-green.svg?style=flat-square" alt="License" /></a>
  <a href="https://x.com/PDgit12"><img src="https://img.shields.io/badge/X-Follow%20%40PDgit12-black.svg?style=flat-square&logo=x&logoColor=white" alt="Follow on X" /></a>
  <a href="https://github.com/PDgit12/desktop-dom/stargazers"><img src="https://img.shields.io/github/stars/PDgit12/desktop-dom?style=flat-square&logo=github" alt="GitHub stars" /></a>
</p>

---

`desktop-dom` is an open-source, embeddable SDK and CLI that transforms native desktop applications (**macOS**, **Windows**, **Linux**) into structured, token-pruned JSON trees ("Desktop DOM") and executes deterministic, sub-millisecond OS actions without vision model guessing.

---

## 1. Why `desktop-dom`?

### The Problem: Why Vision Agents Break on Desktop
Traditional "computer-use" AI agents capture fullscreen screenshots, compress multi-megabyte PNGs, and ask multimodal vision models to guess coordinate pixels:

```
[4K Desktop Screen] ──> [Encode PNG (3-8 MB)] ──> [Upload to Vision LLM]
                                                          │ (3-5s latency, 2,000+ tokens)
                                                          ▼
[Physical OS Click] <── [Simulated Click] <── [Model Guesses (X, Y) Coordinates]
                                                (Fragile: HiDPI drift, anti-aliased icons)
```

* **High Token Cost:** Burns 1,500 to 2,500 vision tokens per step ($0.03–$0.08/step).
* **High Latency:** 3,000–6,000 ms per turn for encoding, transit, and vision inference.
* **Coordinate Drift:** Models hallucinate pixel coordinates on Retina (2x) and Windows HiDPI displays.

### The Solution: Semantic Accessibility DOM
`desktop-dom` queries the native OS accessibility bus directly from the kernel and window manager:

```
[Native OS a11y Bus] ──> [Prune & Flatten] ──> [Semantic JSON (~150 tokens)]
                                                          │ (<300ms latency, pure text)
                                                          ▼
[Physical OS Click] <── [Deterministic Centroid Dispatch] <── [Model Emits {"target": "btn_save"}]
```

* **>90% Token Reduction:** Compresses trees to 100–250 tokens per step ($0.001–$0.003/step).
* **Sub-Second Speed:** Local OS tree query completes in 15–80 ms; text LLM inference completes in 200–500 ms.
* **100% Geometric Accuracy:** Targets exact bounding box centroids with zero pixel guessing.
* **Cross-Toolkit Native Support:** Works with Cocoa, Qt, GTK, WPF, Win32, Electron, Flutter, and Java Swing.

---

## 2. Feature & Architecture Comparison

| Capability | Traditional Vision Agents (e.g. Anthropic/OpenAI) | Scripted Automation (PyAutoGUI / PyWinAuto) | `desktop-dom` Semantic Engine |
| :--- | :---: | :---: | :---: |
| **Token Cost per Step** | ❌ 1,500 – 2,500 vision tokens | ❌ Not AI-native (hardcoded scripts) | ✅ **100 – 250 text tokens (<$0.002)** |
| **Execution Latency** | ❌ 3,000 – 6,000 ms | ❌ ~50 ms (non-adaptive) | ✅ **15 – 80 ms native query** |
| **Centroid & Click Accuracy** | ❌ Frequent misclicks on small icons | ❌ Brittle hardcoded pixels | ✅ **100% OS kernel precision** |
| **HiDPI / Retina Coordinate Drift** | ❌ Broken by OS scale factors | ❌ Requires manual offset math | ✅ **Automatic scale factor calibration** |
| **Electron / Chromium Tree Support** | ❌ Opaque pixel canvas | ❌ Unreadable accessibility tree | ✅ **Automatic `AXEnhancedUserInterface` hydration** |
| **Stale ID & Dynamic UI Recovery** | ❌ Re-runs expensive vision reasoning | ❌ Crashes on element shift | ✅ **Generational counter + Fuzzy semantic recovery** |
| **Cross-Platform Unified Schema** | ❌ Untyped images | ❌ Incompatible OS APIs | ✅ **Normalized `DesktopNode` schema** |
| **Reactive State Engine** | ❌ Polling screenshot loop | ❌ Static `time.sleep` calls | ✅ **`wait_for`, `wait_until_hidden`, `observe`** |
| **Visual Debugging HUD & Canvas** | ❌ Raw screenshots | ❌ None | ✅ **Transparent HUD overlay & interactive SVG snapshots** |
| **Native Model Context Protocol (MCP)**| ❌ None | ❌ None | ✅ **Built-in stdio server for Claude, Cursor, Codex** |

---

## 3. Frictionless Quickstart

### One-Line Install (macOS / Linux / Windows)
```bash
curl -fsSL https://raw.githubusercontent.com/PDgit12/desktop-dom/main/install.sh | bash
```

### Python SDK & CLI
```bash
# Core package (SDK, CLI, Normalizer)
pip install desktop-dom

# Or with platform-native backends:
pip install "desktop-dom[macos]"    # macOS (PyObjC, Quartz, Cocoa)
pip install "desktop-dom[windows]"  # Windows (comtypes, CUIAutomation8)
pip install "desktop-dom[linux]"    # Linux (jeepney, AT-SPI2 D-Bus)

# With all AI agent integrations (LangChain, MCP):
pip install "desktop-dom[all]"
```

### TypeScript SDK
```bash
npm install @desktop-dom/core
```

### Zero-Friction Setup: Auto-Fix Permissions & Connect MCP
```bash
# Verify and automatically open OS Accessibility Settings if needed:
desktop-dom doctor --fix

# 1-Click install into Claude Desktop or Cursor:
desktop-dom install-mcp
```

---

## 4. Personal Desktop Assistant (Aura): The Local Spotlight / Raycast Omnibar

`desktop-dom` packages all semantic accessibility and deterministic control capabilities into **Aura** — a completely local, consumer-facing desktop assistant.

Instead of slow, fragile cloud vision models, Aura runs **100% on-device** using local Speech-to-Text (`faster-whisper`), local LLM planning (`Ollama`), native zero-latency speech synthesis (`say`), and direct `desktop-dom` hardware execution.

### The Floating Glassmorphic Omnibar
* **Global Summon Shortcut:** Press `Cmd+Shift+Space` anywhere on macOS to bring up the floating pill bar over any full-screen app or virtual space.
* **Liquid Glass HUD:** Built using a native borderless Cocoa `NSPanel` (`NSFloatingWindowLevel`) and WebKit background blur (`backdrop-filter: blur(32px)` with vibrant cyan/magenta neon glow).
* **Live Audio Waveform:** Real-time animated audio visualizer responsive to speech activity.
* **Sub-50ms Fast-Path Execution:** Eliminates LLM latency entirely for daily tasks (music, math, system settings, window switching, web search).

### Fast-Path Actions vs. Local LLM Reasoning

| Action Category | Example Natural Language Query | Execution Mechanism | Latency |
| :--- | :--- | :--- | :--- |
| **Media Playback** | *"Play Starboy on Spotify"*, *"Pause music"*, *"Next track"* | AppleScript + `desktop-dom` Spotify DOM search | **<120 ms** |
| **Instant Math** | *"Calculate 125 * 40 + 15"*, *"What is 250 / 5"* | Restricted Python AST evaluation + GUI Calculator sync | **<25 ms** |
| **System Audio** | *"Set volume to 80"*, *"Mute volume"*, *"Volume up"* | Native OS Audio Hardware Bus | **<30 ms** |
| **App Launching** | *"Open Calculator"*, *"Switch to Slack"* | `DesktopApp.attach` + Native Window Activation | **<80 ms** |
| **Instant Search** | *"Search for quantum computing"* | Default Web Browser Direct Query | **<90 ms** |
| **Screen Capture** | *"Take a screenshot"* | Native OS Screen Capture | **<100 ms** |
| **Autonomous Reasoning** | *"Summarize the open windows on my screen"* | Local Ollama ReAct Planning (`ministral-3:8b`, `qwen3:8b`) | **~350 ms** |

### Assistant CLI Commands
```bash
# Launch the floating Spotlight Omnibar (summon with Cmd+Shift+Space)
desktop-dom assistant

# Launch conversational terminal HUD mode
desktop-dom assistant --cli

# Point to custom Ollama endpoint or preferred local model
desktop-dom assistant --ollama-host http://localhost:11434 --model qwen3:8b

# Disable voice synthesis (text-only)
desktop-dom assistant --mute
```

### Python Assistant API
```python
from desktop_dom.assistant import DesktopAssistant

assistant = DesktopAssistant()

# Ask questions or execute commands programmatically
response = assistant.ask("Calculate 125 * 40")
print(response)  # "The answer is 5000."
```

---

## 5. Python SDK Quickstart

### Basic Automation
```python
from desktop_dom import DesktopApp

# Attach to running desktop application
app = DesktopApp.attach("Spotify")

# 1. Fetch token-pruned JSON tree (~150 tokens)
tree = app.get_tree(max_depth=8, as_dict=True)

# 2. Search for elements semantically
play_btn = app.find(role="button", name="Play")

# 3. Deterministic click
if play_btn:
    app.click(play_btn.id)

# 4. Type text and send keyboard shortcuts
search_bar = app.find(role="input")
if search_bar:
    app.type(search_bar.id, text="Diljit Dosanjh", clear_first=True)
    app.press("return")
```

### Reactive State Engine
Eliminate flaky `time.sleep()` calls with built-in reactive synchronization:

```python
# Wait for an async UI element to appear
save_btn = app.wait_for(role="button", name="Save Changes", timeout=5.0)
app.click(save_btn.id)

# Wait for a modal dialog or spinner to disappear
app.wait_until_hidden(role="dialog", timeout=5.0)

# Stream live UI mutations in real time
for mutation in app.observe(interval=0.25):
    print(f"UI mutated: {mutation['action']} element {mutation['node'].id}")
    if mutation["node"].name == "Download Complete":
        break
```

### Multi-Display & Virtual Space Awareness
Handle complex multi-monitor arrangements (including negative coordinate monitors) and verify virtual desktop visibility:

```python
# Enumerate all connected displays with physical/virtual bounds
displays = app.get_displays()
for d in displays:
    print(f"Display {d.id}: {d.name} bounds=({d.bounds.x},{d.bounds.y}) scale={d.scale_factor}x")

# Check if window is currently visible on the active virtual space/desktop
if not app.is_on_active_space():
    print("Warning: App window is minimized or hosted on an inactive virtual desktop!")
```

### Hybrid DOM + Sub-Region Vision Fallback
For custom WebGL, HTML5 Canvas, or game viewports without accessibility child nodes, crop only the target subregion to retain **>90% token savings** compared to full 4K screen captures:

```python
# Crop only the canvas element bounding box (e.g. 300x200px = ~100 tokens vs 2,500 for 4K)
capture = app.crop_element("canvas_viewport_01")
print(f"Subregion image: {capture.width}x{capture.height}px | Est. Tokens: ~{capture.estimated_tokens}")

# Feed directly into Claude / OpenAI multimodal messages
multimodal_message = {
    "role": "user",
    "content": [
        {"type": "text", "text": "What is the current value on this chart?"},
        capture.to_llm_payload(),
    ],
}
```

---

## 6. TypeScript SDK Quickstart

`@desktop-dom/core` provides a type-safe TypeScript client that connects directly to the `desktop-dom` engine:

```typescript
import { DesktopApp } from "@desktop-dom/core";

// Attach to application
const app = DesktopApp.attach("Calculator");

// Extract token-pruned accessibility DOM
const tree = await app.getTree();
console.log(`Root window: ${tree.name} (${tree.bbox.width}x${tree.bbox.height})`);

// Dispatch deterministic clicks and keystrokes
await app.click("btn_seven_8a12");
await app.press("enter");
```

---

## 7. Developer CLI & Visual Tooling

### Health Check & Permissions
```bash
desktop-dom doctor
```
Verifies OS accessibility permissions (macOS TCC / Windows UIA), display backing scale factors, and platform drivers.

### List Active Applications
```bash
desktop-dom apps
```

### Inspect Semantic DOM
Render a terminal tree with element roles, names, bounding boxes, and deterministic IDs:
```bash
desktop-dom inspect --app "Finder"
```

Or export raw token-minimized JSON for LLMs:
```bash
desktop-dom inspect --app "Spotify" --format json
```

### Interactive SVG / HTML Snapshot
Generate a standalone visual canvas with highlighted bounding boxes and element metadata:
```bash
desktop-dom snapshot --app "Calculator" --out calc_snapshot.svg
```

### Transparent Debug Overlay HUD
Launch a transparent Cocoa click-through HUD overlay directly on top of the target application to visualize bounding boxes in real time:
```bash
desktop-dom overlay --app "Spotify"
```

### Multi-Display & Virtual Spaces
```bash
# List all connected displays, coordinates, and scale factors
desktop-dom displays

# Check if an application window is visible on the current active virtual space
desktop-dom spaces --app "Calculator"
```

### Sub-Region Vision Crop
Crop an exact element or coordinate bounding box for vision model fallback with automated token estimation:
```bash
# Crop by element ID
desktop-dom crop --app "Calculator" --id "btn_equals" --out equals.png

# Crop by desktop bounding box (x, y, width, height)
desktop-dom crop --app "Google Chrome" --bbox "100,100,500,300" --out chart.png
```

### Action Dispatch & Reactive Wait
```bash
# Synchronously wait for an element
desktop-dom wait-for --app "Calculator" --name "Equals" --timeout 5.0

# Click by element ID
desktop-dom click --app "Spotify" --id "btn_play_4c1e"

# Type into focused element or specified ID
desktop-dom type --app "TextEdit" --text "Hello world" --clear

# Send keyboard shortcuts
desktop-dom press --key "cmd+s"
```

### Interaction Recorder & Code Generator
Record human interactions and generate ready-to-run Python agent automation scripts:
```bash
desktop-dom record --app "Calculator" --out automate_calc.py
```

### Built-in Model Context Protocol (MCP) Server
Expose `desktop-dom` directly to AI coding agents (Claude Code, Cursor, Codex, Antigravity) via MCP:
```bash
desktop-dom serve --app "Calculator"
```

---

## 8. OS & Window Manager Edge-Case Handling

Desktop environments present unique challenges that break generic automation libraries. `desktop-dom` implements dedicated engineering solutions for each OS edge case:

| Edge Case | Root Cause | Engineering Solution |
| :--- | :--- | :--- |
| **Electron / Chromium Blank Tree** | Chrome and Electron apps disable accessibility trees by default to conserve CPU. | Detects Chromium process and dispatches `kAXManualAccessibility` / `AXEnhancedUserInterface` to hydrate the accessibility tree. |
| **Retina / HiDPI Coordinate Drift** | OS reports accessibility bounds in logical points; hardware event taps require physical pixels. | Queries display backing scale factor (`NSScreen.backingScaleFactor` / `GetDpiForSystem`) and calibrates physical coordinates. |
| **Transient State & Stale IDs** | Dynamic UI changes (dropdowns, popups, lazy lists) invalidate older IDs held by LLMs. | Generational counter + automatic delta-refresh + weighted `FuzzyResolver` matching nearest role, name, and spatial proximity. |
| **Modal Focus Traps** | Modal dialog opens, making background root window unresponsive. | Adapter dynamically inspects `AXFocusedWindow` / active window handle rather than relying on stale root window pointers. |
| **Window Activation & Event Delivery** | Synthetic mouse/keyboard events may be dropped if target application is not active. | WindowServer activation polling (`NSRunningApplication.activate` / `SetForegroundWindow`) ensures reliable event dispatch. |

---

## 9. AI Agent Framework Integration

### LangChain / LangGraph
```python
from desktop_dom import DesktopApp
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic

app = DesktopApp.attach("LibreOffice")

# Exports desktop_get_screen_dom, desktop_click_element, desktop_type_text, desktop_press_key
tools = app.as_tools()

agent = create_react_agent(
    model=ChatAnthropic(model="claude-3-5-sonnet-20241022"),
    tools=tools,
)

agent.invoke({
    "messages": [("user", "Export the active document as a PDF named report.pdf")]
})
```

### Claude Code & Cursor MCP Configuration
Add `desktop-dom` to your `claude.json` or `mcpServers` configuration:

```json
{
  "mcpServers": {
    "desktop-dom": {
      "command": "desktop-dom",
      "args": ["serve", "--app", "Finder"]
    }
  }
}
```

---

## 10. Community & Contributing

We welcome contributions from the community!

- **Follow on X:** Follow [@PDgit12 on X](https://x.com/PDgit12) for announcements, benchmarks, and updates.
- **GitHub Discussions:** Join discussions and share agent workflows on [GitHub Discussions](https://github.com/PDgit12/desktop-dom/discussions).
- **Issues & Bug Reports:** Submit issues or feature requests via [GitHub Issues](https://github.com/PDgit12/desktop-dom/issues).

To contribute code:
```bash
git clone https://github.com/PDgit12/desktop-dom.git
cd desktop-dom
pip install -e ".[dev]"
pytest -v
```

---

## 11. License

[Apache-2.0](LICENSE) © 2026 [PDgit12](https://github.com/PDgit12).
