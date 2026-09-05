# desktop-dom

> **Playwright for Desktop: Semantic Accessibility DOM and Deterministic Action Engine for AI Agents**

`desktop-dom` is an embeddable Python SDK and developer CLI that transforms native desktop applications (macOS, Windows, Linux) into structured, token-pruned JSON trees ("Desktop DOM") and executes deterministic, sub-millisecond OS actions.

---

## 1. Executive Summary

### The Problem: Why Vision Agents Break on Desktop
Traditional "computer-use" AI agents capture screenshots, encode multi-megabyte PNGs, and ask vision models to guess pixel coordinates:

```
[4K Desktop Screen] ──> [Encode PNG (3-8 MB)] ──> [Upload to Vision LLM]
                                                          │ (3-5 sec latency, 2000+ tokens)
                                                          ▼
[Physical OS Click] <── [Simulated Click] <── [Model Guesses (X, Y) Coordinates]
                                                (Fragile: DPI scaling, shifts, small icons)
```

* **Token Cost:** 1,200 to 2,500 vision tokens per reasoning step ($0.03–$0.08/step).
* **Latency:** 3,000–6,000 ms per step (encoding + upload + vision inference).
* **Brittleness:** Models hallucinate pixel coordinates on Retina (2x) and Windows HiDPI displays.

### The Solution: Semantic Accessibility DOM
`desktop-dom` queries the native OS accessibility bus directly from the kernel and window manager:

```
[Native OS a11y Bus] ──> [Prune & Flatten] ──> [Semantic JSON (~150 tokens)]
                                                          │ (<300ms latency, pure text)
                                                          ▼
[Physical OS Click] <── [Deterministic Centroid Dispatch] <── [Model Emits {"target": "btn_save"}]
```

* **>90% Token Reduction:** 100 to 250 tokens per step ($0.001–$0.003/step).
* **Sub-Second Speed:** Local OS tree query completes in 15–80 ms; text inference in 200–500 ms.
* **100% Geometric Accuracy:** Exact bounding box centroids; no pixel guessing.
* **Cross-Toolkit Non-Invasive:** Works on Cocoa, Qt, GTK, WPF, Win32, Electron, Flutter, and Java Swing without browser runtimes.

---

## 2. Installation

```bash
# Core package (SDK, CLI, Normalizer)
pip install desktop-dom

# Or install with platform-native backends:
# On macOS:
pip install "desktop-dom[macos]"

# On Windows:
pip install "desktop-dom[windows]"

# On Linux:
pip install "desktop-dom[linux]"

# With LangChain / Agent integrations:
pip install "desktop-dom[all]"
```

---

## 3. Developer CLI

### Health Check & Permissions
```bash
desktop-dom doctor
```
Verifies OS accessibility permissions (macOS TCC / Windows UIA), display backing scale factors, and platform drivers.

### List Running Applications
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

### Manual Action Dispatch
```bash
# Click by deterministic element ID
desktop-dom click --app "Spotify" --id "btn_play_4c1e"

# Type into a focused element or specified ID
desktop-dom type --app "TextEdit" --text "Hello world" --clear

# Send keyboard shortcuts
desktop-dom press --key "cmd+s"
```

### Interaction Recorder & Code Generator
Record human interactions and generate ready-to-run Python agent automation scripts:
```bash
desktop-dom record --app "Calculator" --out automate_calc.py
```

### Built-in MCP Server
Expose `desktop-dom` directly to AI coding agents (Claude Code, Codex, Antigravity, Cursor) via Model Context Protocol:
```bash
desktop-dom serve --app "Calculator"
```

---

## 4. Python SDK Quickstart

```python
from desktop_dom import DesktopApp

# Attach to running desktop application
app = DesktopApp.attach("Spotify")

# 1. Fetch token-pruned JSON tree (~150 tokens)
tree = app.get_tree(max_depth=8, as_dict=True)

# 2. Search for elements
play_btn = app.find(role="button", name="Play")

# 3. Deterministic click
app.click(play_btn.id)

# 4. Type into search input
search_bar = app.find(role="input")
if search_bar:
    app.type(search_bar.id, text="Diljit Dosanjh", clear_first=True)
    app.press("return")
```

---

## 5. AI Agent Framework Integration

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
    "messages": [("user", "Export this active document as a PDF named report.pdf")]
})
```

---

## 6. Enterprise Edge-Case Mitigation Matrix

| Edge Case | Root Cause | Engineering Solution |
| :--- | :--- | :--- |
| **Electron / Chromium Blank Tree** | Chrome/Electron apps disable accessibility trees to conserve CPU. | Detects Chromium binary and dispatches `kAXManualAccessibility` / `AXEnhancedUserInterface` to hydrate the tree. |
| **Retina / HiDPI Coordinate Drift** | OS reports accessibility bounds in points; event taps require physical pixels. | Queries display backing scale factor (`NSScreen.backingScaleFactor` / `GetDpiForSystem`) and calibrates coordinates. |
| **Transient State (Stale IDs)** | Dynamic UI changes (dropdowns, popups) invalidate older IDs held by LLMs. | Generational counter + automatic delta-refresh + fuzzy semantic fallback matching nearest role and label. |
| **Modal Focus Traps** | Modal dialog opens, making background window unresponsive. | Adapter dynamically inspects `AXFocusedWindow` / active window rather than relying on stale root handles. |
| **Headless CI & Testing** | Cloud CI environments lack GUI servers. | Headless test fixtures and adapter interfaces enable 100% test coverage hermetically without OS window servers. |

---

## 7. License

Apache-2.0. Created by Piyush Dua.
