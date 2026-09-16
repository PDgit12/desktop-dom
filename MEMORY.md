# Project Memory: desktop-dom

## Core Mission
"Playwright for Desktop: Semantic Accessibility DOM and Deterministic Action Engine for AI Agents"
Eliminates vision agent flaws (>90% token waste, 3–6 second latency, pixel coordinate hallucinations) by querying OS native accessibility trees and dispatching deterministic centroid clicks and native keystrokes.

## Technical Architecture & Design Decisions
1. **Platform Adapters:**
   - macOS (`src/desktop_dom/adapters/macos.py`): ApplicationServices `AXUIElement` + Quartz `CGEvent`. Unpack PyObjC out-parameters by passing `None` as pointer arg. Send `AXEnhancedUserInterface` to hydrate Electron/Chromium accessibility.
   - Windows (`src/desktop_dom/adapters/windows.py`): COM `CUIAutomation8` with `ControlViewWalker` and `IUIAutomationCacheRequest` for batch IPC prefetch. Hardware simulation via Win32 `SendInput`.
   - Linux (`src/desktop_dom/adapters/linux.py`): AT-SPI2 over user session D-Bus. Discards zero-area subtrees immediately to avoid redundant roundtrips.
   - Test Fixture (`tests/conftest.py`): In-memory calculator UI tree adapter fixture recording clicks/types/keys for hermetic CI without OS window servers.

2. **Normalizer & Pruner (`src/desktop_dom/pruner.py`):**
   - Eliminates zero-area elements, offscreen bounds, and passive unlabeled layout containers.
   - Generates deterministic ephemeral IDs: `<role_prefix>_<slug>_<hash4>` with collision avoidance.
   - `FuzzyResolver` handles generational stale ID recovery via weighted semantic and spatial similarity.
3. **High-Level SDK (`src/desktop_dom/app.py`):**
   - `DesktopApp.attach(target)` / `launch(command)`
   - `get_tree()`, `click(element_id)`, `type(element_id, text)`, `press(chord)`
   - Auto delta-refresh on cache miss.
4. **Agent & CLI Tooling:**
   - LangChain / LangGraph standard toolset (`src/desktop_dom/integrations/langchain.py`).
   - Stdio MCP Server (`src/desktop_dom/integrations/mcp.py`).
   - Reactive Engine (`DesktopApp.wait_for`, `wait_until_hidden`, `observe`).
   - Visual HUD Overlay & HTML Snapshot (`desktop-dom overlay`, `desktop-dom snapshot`).
   - CLI (`desktop-dom doctor --fix`, `apps`, `inspect`, `click`, `type-text`, `press`, `record`, `wait-for`, `snapshot`, `overlay`, `serve`, `install-mcp`).
4. **Personal Desktop Assistant (Aura & Floating Omnibar):**
   - Package: `src/desktop_dom/assistant/`
   - Floating Spotlight Omnibar (`omnibar.py`): Native borderless Cocoa `NSPanel` (`NSFloatingWindowLevel`), `WKWebView` with liquid glass blur (`backdrop-filter: blur(40px) saturate(210%)`), dynamic frame height expansion via `setFrame_display_animate_`, live contextual suggestion tray (with instant arithmetic computation), full keyboard navigation (`↑`/`↓`/`Tab`/`↵`/`Esc`), triple-harmonic canvas waveform visualizer, and native macOS menu bar status item (`NSStatusItem`) with `⚡` icon.
   - Dual-Engine Brain (`brain.py`): Sub-50ms deterministic fast-paths for:
     - Screen introspection ("what is on my screen / inspect active window") extracting semantic DOM hierarchies in <50ms without multimodal vision tokens.
     - Appearance mode toggling (Dark/Light mode) via macOS System Events.
     - Apple Notes creation with automated title and body parsing.
     - Clipboard read/write inspection and native system notification dispatch.
     - Window management (minimize, maximize, close).
     - Semantic UI actions: click, type, and press by role or name with pixel-accurate centroid resolution.
     - Spotify playback/search/controls, Calculator GUI sync, system audio volume, app switching, web search, screenshots.
     - Context-enriched ReAct fallback to local Ollama models (`ministral-3:8b`, `qwen3:8b`) with active application DOM injected into the prompt.
   - Local Audio Manager (`audio.py`): Native OS TTS (`say`) and local STT (`faster-whisper` `tiny.en` on CPU/int8) for zero cloud cost and full privacy.
   - Continuous Wake-Word Engine (`audio.py`): `WakeWordListener` with sliding audio capture and RMS energy thresholding (<0.5% idle CPU). Listens for "Hey Aura" / "Aura" and activates the Omnibar or assistant callback on-device.
   - High-Level Coordinator (`__init__.py`): `DesktopAssistant` with `launch_omnibar(enable_wake_word=True)`, `start_wake_word()`, `run_cli_session()`, and `ask()`.
5. **Distribution, Packaging & Multi-Platform Matrix:**
   - Unified Packager (`scripts/build_app.py` & `desktop-dom package --platform [macos|windows|linux|all]`):
     - macOS: Standalone `Aura.app` bundle, PIL-rendered `AppIcon.icns`, installed to `~/Applications`, and native `.dmg` drag-and-drop installer (202 KB) via `hdiutil`.
     - Windows: Standalone `Aura-Windows` bundle, multi-size `aura.ico`, WiX Toolset `.msi` installer spec (`AuraInstaller.wxs`), and `.zip` archive.
     - Linux: Debian package structure (`DEBIAN/control`, `/usr/bin/aura`, `/usr/share/applications/aura.desktop`), `AppRun` for AppImage, and `.tar.gz` archive.
   - Single-command installer: `install.sh` (`curl -fsSL ... | bash`).
   - 1-click MCP configurator: `desktop-dom install-mcp` (Claude Desktop / Cursor).
   - Git Flow branching: `main` (production-ready stable) and `develop` (active integration) with `CONTRIBUTING.md`.
   - Pre-flight scripts: `scripts/publish_pypi.sh` and `scripts/publish_npm.sh`.
   - CI/CD workflows: `.github/workflows/ci.yml` (multi-OS test matrix) and `.github/workflows/publish.yml` (tag release automation).

## Test & Integration Status
- **135 unit and integration tests passing** (`pytest` in 16.55s, 100% pass rate, 100% hermetic).
- **Zero-Touch Local Persona & Machine Ingestion (`local_ingest.py`):**
  - Replaces synthetic demo mocks with real user data: ingests actual Chrome SQLite history (`~/Library/Application Support/Google/Chrome/Default/History`), actual top visited web apps (`bloom.diy`, `luna.amazon.com`, `crcle.ai`), actual YouTube watch history, and local Git identity (`PDgit12 <piyushdua01@gmail.com>`).
- **Level 1 Polish & Dynamic OS Catalog (`src/desktop_dom/assistant/brain.py`):**
  - Dynamic application scanner indexes 100+ native apps across `/Applications`, `/System/Applications`, `/System/Applications/Utilities`, `~/Applications`.
  - `SequenceMatcher` typo tolerance (&ge;0.68) resolves typos (`spotfy` &rarr; Spotify, `safri` &rarr; Safari, `crome` &rarr; Google Chrome, `calc` &rarr; Calculator, `notse` &rarr; Notes) without erroneous browser fallbacks.
  - Native folder navigation (`open downloads`, `open documents`, `open desktop`) & safe app lifecycle control (`quit Spotify`, `close Chrome`).
- **Level 2 Continuous Intent Cycle & Temporal Routine Engine (`context_feed.py` & `memory.py`):**
  - Temporal Habit & Routine Engine: When screen offers zero signal (empty desktop), Aura arbitrates intent via diurnal time vectors (Morning Kickoff `05:00-12:00`, Deep Focus `12:00-18:00`, Gaming `18:00-05:00`).
  - Composite Routine Flow: "start my day", "morning routine", "work mode" orchestrates multi-app workflows (VS Code, GitHub repo, Spotify focus beats).
  - Data Ingestion: Frontmost application and window title capture via Cocoa/NSWorkspace (<10ms). Live browser tab and URL ingestion from Chrome/Brave/Arc/Safari via AppleScript (<15ms).
  - Meaning Synthesis: Activity classification into Gaming, Engineering, Communication, Design, Research. Habit mapping: FIFA gaming &rarr; "FIFA Soundtrack" (Gaming Energy), coding &rarr; "Deep Focus" (Focus Beats).
  - Context Introspection: "What was I doing?", "What am I looking at?", "Summarize my context" extracts active context without vision tokens.
  - Multi-Modal Intent Routing:
    - YouTube & Video Streaming: Dynamic contextual channel recommendations (Gaming &rarr; EA SPORTS FC / FIFA tactics, Coding &rarr; ThePrimeagen / Fireship), watch history memory recall, and Chrome tab intelligence (activates existing YouTube tab instead of creating duplicate tabs).
    - Developer Repository Binding: Resolves "open my repo", "view pull requests" to the active git repository (`PDgit12/desktop-dom`) mapped from active telemetry or SQLite preferences.
    - Calendar & Schedule Introspection: "Check my schedule" opens native Calendar.
  - 5-Tier sub-millisecond entity disambiguation (<0.5ms): direct email (100), exact alias (100), role match (92–94), Levenshtein (80–88), SequenceMatcher (70+).
- **The Cursor-Free ("Virtual Ghost Cursor") Architecture (`src/desktop_dom/adapters/macos.py`):**
  - **Tier 1 (Zero-Movement OS Action):** Direct `AXUIElementPerformAction(kAXPressAction)` dispatches events without moving the user's physical mouse.
  - **Tier 2 (Microsecond Cursor Warp & Restore):** Saves physical mouse coordinates, executes click, and warps back via `CGWarpMouseCursorPosition` in <0.8ms (imperceptible to user).
  - **Tier 3 (In-Memory Value Mutation):** Sets text fields directly via `kAXValueAttribute` without stealing active keyboard focus or disrupting typing.
- **Level 2.5 Autonomous Execution Zone (Between Level 2 and Level 3):**
  - Native AppleScript/JXA in-app IPC for Microsoft Outlook and Apple Mail: populates recipient, subject, and body into a single clean draft without spawning phantom/duplicate processes or empty windows.
  - Lightweight before-and-after DOM diffing ($T_1 - T_0$) in <0.25ms certifies state mutation without multi-step loop latency.
- **Level 3 Autonomous Agentic Loop & State Verification:**
  - $O(N)$ linear DOM diffing in `diff.py` (<0.25ms), `execute_and_verify()` state verification in `app.py`, `AutonomousDesktopAgent` ReAct loop in `agent.py`, and `desktop-dom serve` headless daemon on port 8484.
- **Executive Documentation & PDFs:**
  - `Desktop_DOM_One_Pager_Architecture.pdf`: Verified **exactly 1 page** executive architecture blueprint with Level 2.5 Execution Zone, syscall paths, memory hierarchy, and founder alignment.
  - `Desktop_DOM_Comprehensive_Technical_Master_Guide.pdf`: 15-page comprehensive technical manual with founder defense playbook, evolutionary journey, and Level 2.5 architecture.
  - `docs/DESKTOP_DOM_MASTER_DEEP_DIVE_CURRICULUM.md`: Complete markdown curriculum enriched with Section 15 detailing the Continuous Intent Cycle, Multi-Modal Intent, and certified metrics.
- Branches: `main` (stable) and `develop` (integration) synced on `PDgit12/desktop-dom`.
- Remote repository live on GitHub at `https://github.com/PDgit12/desktop-dom` with 100% sole contributor attribution for PDgit12.




