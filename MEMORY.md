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
- **90 unit and integration tests passing** (`pytest -v` in 5.95s, 100% pass rate).
- **Level 2 Personal Intent & Memory Engine (`src/desktop_dom/assistant/memory.py`):**
  - Persistent SQLite in WAL mode (`~/.desktop_dom/aura_memory.db`) with sub-millisecond dual-layer in-memory caching (<0.5ms lookups).
  - 4-Tier entity disambiguation pipeline (exact alias match -> first name token -> substring -> SequenceMatcher fuzzy similarity with frequency/recency boosts).
  - Personal messaging ("message Josh saying the slides are ready" -> resolves Joshua Rayan, josh@crcle.ai, opens Outlook pre-addressed).
  - Habitual media recall ("open my playlist" -> resolves spotify.favorite_playlist "Deep Focus" in 0.1ms).
  - On-the-fly learning ("remember X is Y", "remember my favorite playlist is Z") and system contacts sync (`sync_system_contacts`).
- **Comprehensive 14-Page Master Technical Guide & Curriculum (`docs/Desktop_DOM_Comprehensive_Technical_Master_Guide.pdf`):**
  - Compiled via ReportLab (`scripts/generate_master_pdf.py`) with institutional typography, NumberedCanvas header/footers, and architecture diagrams.
  - Mirrored to `/Users/piyushdua/Desktop_DOM_Comprehensive_Technical_Master_Guide.pdf` and brain artifacts.
  - Contains all 13 chapters: Vision flaws, architecture, kernel bridges, cursor-free execution, O(N) pruner, subregion vision, Level 1 fast-paths, Level 2 memory, Level 3 agentic loop, Cocoa Omnibar, packaging/distribution, Crcle.ai gap analysis, and founder defense playbook.
- Completed 5 comprehensive multi-disciplinary subagent audits:
  1. Security Audit: B+ (81.6/100). Hardened shell=False, escaped PowerShell and AppleScript strings, prevented exponentiation DoS, fixed JS regex syntax error, and removed hardcoded developer paths from distributed launcher.
  2. UI/UX Audit: Aesthetic 88/100, UX 81/100. Liquid glass Omnibar, 3-harmonic audio waveform, result drawer pattern, dynamic frame animations.
  3. Code Quality & Performance Audit: B+ (86/100). Sub-millisecond pruning ($O(N)$ 0.31ms for 1,093 nodes, 96% reduction), bounded DOM cache to 1,000 items, zero-disk in-memory audio transcription.
  4. Testing & QA Audit: 100% pass rate across 90 tests. Hermetic CI fixtures, Chromium hydration, 4-quadrant multi-display calibration, thread concurrency safety.
  5. Product Strategy & Founder Alignment: Tailored thesis for Crcle.ai founders (Joshua Rayan & Cyril Rayan), competitive breakdown vs Claude/Gemini, 3-minute live demo script, and technical defense.
- **Frictionless Local AI Model Switcher & Result Drawer:**
  - 1-Click Model Drawer: Click the brand orb ⚡ or footer model tag, or type `/model`. Live-queries `localhost:11434/api/tags` and presents installed neural weights (`ministral-3:8b`, `qwen3:8b`) alongside the `Zero-Model Fast-Path` (0MB RAM, sub-25ms offline).
  - Native Result Drawer: Expands cleanly beneath the input bar to display the formatted response, latency badge (`⚡ 18ms Fast-Path` vs `🧠 840ms Ollama`), `[📋 Copy]` to clipboard, and `[Done] (Esc)` dismissal. Transient system actions (volume, dark mode) auto-dismiss after 2.8s.
  - Multi-Display Mouse Tracking: Uses `Cocoa.NSEvent.mouseLocation()` to detect the active monitor and center the Omnibar where the user is working.
  - Hardware-Accelerated macOS Vibrancy: Combines `NSVisualEffectView` (`NSVisualEffectMaterialHUDWindow`) with transparent `WKWebView`.
- **Cursor-Free Background Execution ("Don't Disturb My Cursor"):**
  - Priority 1: Direct Accessibility Invocations (`AXUIElementPerformAction(kAXPressAction)` on macOS, `InvokePattern` on Windows, `AtspiAction` on Linux). Executes clicks internally with ZERO physical mouse pointer movement, ZERO window activation, and ZERO focus theft!
  - Priority 2: Ghost Click Coordinate Preservation. Records current cursor position via `Quartz.CGEventGetLocation(CGEventCreate(None))` and seamlessly restores it instantly via `CGWarpMouseCursorPosition`, ensuring the user's cursor remains exactly where they are working.
  - Priority 3: Direct AX Value Injection (`AXUIElementSetAttributeValue(kAXValueAttribute)`). Sets text into input fields in the background without stealing keyboard focus or synthesizing conflicting keystrokes.
- Branches: `main` (stable) and `develop` (integration) in sync at `0648491` on `PDgit12/desktop-dom`.
- Remote repository live on GitHub at `https://github.com/PDgit12/desktop-dom` with 100% sole contributor attribution for PDgit12.



