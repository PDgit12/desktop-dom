# desktop-dom

<p align="center">
  <img src="https://raw.githubusercontent.com/PDgit12/desktop-dom/main/assets/banner.png" alt="desktop-dom banner" width="100%" onerror="this.style.display='none'" />
</p>

<p align="center">
  <strong>Playwright for Desktop: Semantic Accessibility DOM, Deterministic Action Engine, & Sovereign On-Device Assistant for AI Agents</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/desktop-dom/"><img src="https://img.shields.io/pypi/v/desktop-dom.svg?style=flat-square&color=3776AB&label=PyPI" alt="PyPI version" /></a>
  <a href="https://www.npmjs.com/package/@desktop-dom/core"><img src="https://img.shields.io/npm/v/@desktop-dom/core.svg?style=flat-square&color=CB3837&label=npm" alt="npm version" /></a>
  <a href="https://pypi.org/project/desktop-dom/"><img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg?style=flat-square" alt="Python versions" /></a>
  <a href="https://github.com/PDgit12/desktop-dom/actions"><img src="https://img.shields.io/github/actions/workflow/status/PDgit12/desktop-dom/ci.yml?branch=main&label=CI&style=flat-square" alt="CI status" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-green.svg?style=flat-square" alt="License" /></a>
  <a href="SECURITY.md"><img src="https://img.shields.io/badge/security-sovereign%20zero--cloud-emerald.svg?style=flat-square" alt="Security Policy" /></a>
  <a href="https://x.com/PDgit12"><img src="https://img.shields.io/badge/X-Follow%20%40PDgit12-black.svg?style=flat-square&logo=x&logoColor=white" alt="Follow on X" /></a>
  <a href="https://github.com/PDgit12/desktop-dom/stargazers"><img src="https://img.shields.io/github/stars/PDgit12/desktop-dom?style=flat-square&logo=github" alt="GitHub stars" /></a>
</p>

---

`desktop-dom` is a unified, cross-platform engine (**macOS**, **Windows**, **Linux**) that solves desktop automation for the AI era. It operates as two complementary layers:

1. **Developer SDK & CLI ("Playwright for Desktop"):** Converts native desktop applications into token-pruned JSON trees ("Desktop DOM") and executes deterministic, sub-millisecond centroid clicks without vision model guessing.
2. **Aura (Sovereign Desktop Assistant):** A consumer-facing Spotlight / Raycast floating HUD running **100% on-device** via local models (Ollama `ministral-3:8b`, `qwen3:8b`), local speech-to-text (`faster-whisper`), and sovereign SQLite storage (`~/.desktop_dom/aura_memory.db`) with **zero external database dependencies** (Zero-Postgres).

```
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                               AURA HUD                                   │
 │       Spotlight / Raycast Glassmorphic Window (Cmd+Shift+Space)          │
 └────────────────────────────────────┬─────────────────────────────────────┘
                                      │
 ┌────────────────────────────────────▼─────────────────────────────────────┐
 │                       DESKTOP-DOM DUAL ENGINE                            │
 ├─────────────────────────────────────┬────────────────────────────────────┤
 │  ENGINE 1: DEVELOPER OS SDK & MCP   │  ENGINE 2: LOCAL AI BRAIN & MEMORY │
 │  • Kernel Accessibility Bus (Cocoa) │  • Local Ollama (ministral, qwen3) │
 │  • Token Pruning (>90% reduction)   │  • Dual /api/chat + Fallback       │
 │  • 100% Centroid OS Clicks (<80ms)  │  • Sovereign SQLite (WAL, 0o600)   │
 │  • Reactive DOM (wait_for, observe) │  • Zero Plaintext Token Custody    │
 │  • Multi-Display & Retina HiDPI     │  • 45-Toolkit Integration Catalog  │
 │  • Built-in Stdio MCP Server        │  • Built-in Audit Engine (CLI)     │
 └─────────────────────────────────────┴────────────────────────────────────┘
```

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

## 2. Feature & Architecture Matrix

| Capability | Vision Agents (Anthropic/OpenAI) | Scripted Automation (PyAutoGUI) | `desktop-dom` Engine |
| :--- | :---: | :---: | :---: |
| **Token Cost per Step** | ❌ 1,500 – 2,500 vision tokens | ❌ Not AI-native | ✅ **100 – 250 text tokens (<$0.002)** |
| **Execution Latency** | ❌ 3,000 – 6,000 ms | ❌ ~50 ms (non-adaptive) | ✅ **15 – 80 ms native query** |
| **Centroid & Click Accuracy** | ❌ Frequent misclicks on small icons | ❌ Brittle hardcoded pixels | ✅ **100% OS kernel precision** |
| **HiDPI / Retina Coordinate Drift** | ❌ Broken by OS scale factors | ❌ Requires manual offset math | ✅ **Automatic scale factor calibration** |
| **Electron / Chromium Tree Support** | ❌ Opaque pixel canvas | ❌ Unreadable accessibility tree | ✅ **Automatic `AXEnhancedUserInterface` hydration** |
| **Stale ID & Dynamic UI Recovery** | ❌ Re-runs expensive vision reasoning | ❌ Crashes on element shift | ✅ **Generational counter + Fuzzy semantic recovery** |
| **Cross-Platform Unified Schema** | ❌ Untyped images | ❌ Incompatible OS APIs | ✅ **Normalized `DesktopNode` schema** |
| **Reactive State Engine** | ❌ Polling screenshot loop | ❌ Static `time.sleep` calls | ✅ **`wait_for`, `wait_until_hidden`, `observe`** |
| **Local Model Reasoning** | ❌ Cloud-only API | ❌ None | ✅ **Local Ollama (`ministral-3:8b`, `qwen3:8b`)** |
| **Zero-Postgres Sovereign Storage** | ❌ Remote cloud databases | ❌ None | ✅ **100% Local SQLite (`0o600` permissions)** |
| **Zero Plaintext Token Custody** | ❌ Tokens in DB | ❌ Stored in config files | ✅ **Stateless OAuth session exchange** |
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

### Verify OS Permissions & Auto-Fix
```bash
# Verify and automatically open OS Accessibility Settings if needed:
desktop-dom doctor --fix

# 1-Click install into Claude Desktop or Cursor:
desktop-dom install-mcp
```

---

## 4. Personal Desktop Assistant (Aura): The Sovereign Spotlight HUD

`desktop-dom` packages its accessibility DOM, deterministic actions, and local memory into **Aura** — a personal desktop assistant with an interface reminiscent of Raycast/Spotlight.

Aura runs **100% on-device** with zero cloud telemetry and zero external database daemons.

### The Glassmorphic HUD Omnibar
* **Global Summon Shortcut:** Press `Cmd+Shift+Space` anywhere on macOS to bring up the floating pill bar over any full-screen app or virtual space.
* **Liquid Glass HUD:** Built using a native borderless Cocoa `NSPanel` (`NSFloatingWindowLevel`) and WebKit background blur (`backdrop-filter: blur(40px) saturate(210%)` with neon cyan/magenta styling).
* **Settings & Sovereign Scopes:** Press `Cmd+,` to manage user profile, toggle data scopes, and configure integrations.
* **Workspace Switcher:** Press `Cmd+P` to quickly switch between projects (`Personal`, `Work`, `Custom`).
* **Active Engine Pill:** Displays real-time model execution badge (`ministral-3:8b · 1.2s`, `Fast-Path · 12ms`, `Memory · 4ms`). Click the pill to open the **Local Model Drawer** and switch models dynamically.

### Local Neural Model Reasoning (Ollama)
Aura connects natively to local LLMs via `localhost:11434`:
* **Auto-Discovery:** Detects installed Ollama models, prioritizing instruction models like `ministral-3:8b-instruct-2512-q4_K_M` and `qwen3:8b`.
* **Dual Chat Protocol:** Employs `/api/chat` with structured role templates (Mistral `[INST]` tags, Qwen ChatML) with automatic fallback to `/api/generate`.
* **Markdown Action Sanitization:** Handles actions emitted by local models (e.g. `**ACTION: open Granola** *(to take notes)*`), stripping formatting artifacts and dispatching deterministic actions to the desktop.
* **Zero-Leakage Markdown HUD:** Renders bullet points, numbered lists, bold text, and code blocks inside the WebKit HUD with clean typography.
* **Anti-Hallucination Search Guardrail:** Strictly blocks local models from performing external web searches for personal schedules, meetings, contacts, emails, or playlists.

### Zero-Postgres Sovereign Local Storage & Auditing
* **100% Local SQLite:** Database stored exclusively at `~/.desktop_dom/aura_memory.db` in Write-Ahead Logging mode (`PRAGMA journal_mode=WAL`).
* **Strict OS Permissions:** Files are locked to user-isolated permissions (`0o600` on the database file, `0o700` on the directory).
* **Zero Plaintext Token Custody:** OAuth tokens are never written to disk in plaintext.
* **Institutional Audit CLI:** Run `desktop-dom audit` anytime to verify storage integrity, table counts, and token isolation:

```bash
desktop-dom audit
```

```
╭──────────────── Sovereign Storage & Security Audit ─────────────────╮
│ Database Path        │ /Users/piyushdua/.desktop_dom/aura_memory.db │
│ Storage Engine       │ Embedded SQLite (Zero-Postgres Sovereign)   │
│ Journal Mode         │ WAL (Write-Ahead Logging)                    │
│ File Permissions     │ 0o600 (User-Isolated Read/Write)             │
│ Plaintext Tokens     │ 0 (Zero-Token Custody Guaranteed)            │
│ SQLite Tables        │ 10 tables verified (entities, preferences…)  │
╰──────────────────────────────────────────────────────────────────────╯
```

Output as machine-readable JSON:
```bash
desktop-dom audit --json
```

### 45-Toolkit Integration Catalog & Sovereign Data Scopes
Aura includes an extensive categorized catalog of 45 desktop and cloud toolkits:
* **Meetings & Audio:** Zoom, Google Meet, Granola, Spotify, Krisp, Rewind.
* **Engineering & Code:** GitHub, GitLab, Jira, Linear, Sentry, Postman, Terminal.
* **Communication:** Slack, Discord, Microsoft Teams, Gmail, Microsoft Outlook, WhatsApp.
* **Productivity:** Google Calendar, Notion, Apple Notes, Obsidian, Raycast, Linear.
* **CRM & Business:** HubSpot, Salesforce, Stripe, Zendesk, Intercom.

Users control five sovereign data scopes (`calendar`, `repos`, `contacts`, `notes`, `media`) with instant toggle controls. Background ingestion pipelines strictly verify that a scope is enabled before processing data.

---

## 5. CLI Command Reference

| Command | Description | Example |
| :--- | :--- | :--- |
| `desktop-dom assistant` | Launch the floating Spotlight/Raycast Omnibar | `desktop-dom assistant` |
| `desktop-dom assistant --cli` | Launch conversational terminal HUD mode | `desktop-dom assistant --cli --mute` |
| `desktop-dom audit` | Run sovereign storage, permission & security audit | `desktop-dom audit` |
| `desktop-dom audit --json` | Output machine-readable audit report | `desktop-dom audit --json` |
| `desktop-dom doctor` | Diagnose OS accessibility permissions & display bounds | `desktop-dom doctor --fix` |
| `desktop-dom inspect` | Dump token-pruned JSON tree of an application | `desktop-dom inspect --app "Spotify"` |
| `desktop-dom apps` | List all running and installed desktop applications | `desktop-dom apps` |
| `desktop-dom snapshot` | Generate visual SVG/HTML bounding box snapshot | `desktop-dom snapshot --app "Calculator" --out snap.svg` |
| `desktop-dom overlay` | Display transparent click-through HUD overlay | `desktop-dom overlay --app "Safari"` |
| `desktop-dom click` | Deterministically click element by ID | `desktop-dom click --app "Spotify" --id "btn_play"` |
| `desktop-dom type` | Type text into active or specified element | `desktop-dom type --app "Slack" --text "Hello"` |
| `desktop-dom press` | Send native keyboard shortcut | `desktop-dom press --key "cmd+s"` |
| `desktop-dom wait-for` | Synchronously wait for an element to appear | `desktop-dom wait-for --app "App" --name "Save" --timeout 5.0` |
| `desktop-dom package` | Build native macOS `Aura.app` and DMG installer | `desktop-dom package --install` |
| `desktop-dom serve` | Launch stdio Model Context Protocol (MCP) server | `desktop-dom serve --app "Finder"` |

---

## 6. Python SDK Quickstart

### Basic Automation
```python
from desktop_dom import DesktopApp

# Attach to running desktop application
app = DesktopApp.attach("Spotify")

# 1. Fetch token-pruned JSON tree (~150 tokens)
tree = app.get_tree(max_depth=8, as_dict=True)

# 2. Search for elements semantically
play_btn = app.find(role="button", name="Play")

# 3. Deterministic centroid click
if play_btn:
    app.click(play_btn.id)

# 4. Type text and send keyboard shortcuts
search_bar = app.find(role="input")
if search_bar:
    app.type(search_bar.id, text="Diljit Dosanjh", clear_first=True)
    app.press("return")
```

### Reactive State Engine
Eliminate brittle `time.sleep()` calls with built-in reactive synchronization:

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

### Hybrid DOM + Sub-Region Vision Fallback
For WebGL, HTML5 Canvas, or game viewports without accessibility nodes, crop only the target subregion to retain **>90% token savings** compared to 4K captures:

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

## 7. TypeScript SDK Quickstart

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

## 8. AI Agent Framework Integration

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

## 9. Community & Contributing

We welcome contributions from the community!

- **Follow on X:** Follow [@PDgit12 on X](https://x.com/PDgit12) for announcements, benchmarks, and updates.
- **GitHub Discussions:** Join discussions and share agent workflows on [GitHub Discussions](https://github.com/PDgit12/desktop-dom/discussions).
- **Issues & Bug Reports:** Submit issues or feature requests via [GitHub Issues](https://github.com/PDgit12/desktop-dom/issues).
- **Security Inquiries:** Review [SECURITY.md](SECURITY.md) for vulnerability disclosure and sovereign threat model details.

To set up a local development environment:
```bash
git clone https://github.com/PDgit12/desktop-dom.git
cd desktop-dom
pip install -e ".[dev]"
pytest -v
```

---

## 10. License

[Apache-2.0](LICENSE) © 2026 [PDgit12](https://github.com/PDgit12).
