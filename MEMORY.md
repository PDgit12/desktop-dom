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
- **111 unit and integration tests passing** (`pytest` in 9.82s, 100% pass rate).
- **Level 3 Autonomous Agentic Loop & State Verification:**
  - **O(N) DOM Diffing Engine (`src/desktop_dom/diff.py`):**
    - `compute_dom_diff(before, after)` performs linear comparison in <0.25ms for 300+ elements.
    - `NodeMutation` tracks text values, interactive state changes (`focused`, `checked`, `disabled`, `expanded`, `selected`), and centroid shifts (>2px).
    - `DOMDiff` isolates `added_nodes`, `removed_nodes`, and `mutations` with $O(1)$ change checks.
  - **Empirical State Verification (`src/desktop_dom/app.py`):**
    - `app.execute_and_verify(action_fn, expected_effect)` couples every dispatch with $T_1 - T_0$ diff verification and asynchronous polling to eliminate race conditions.
  - **Autonomous Desktop Agent (`src/desktop_dom/agent.py`):**
    - `AutonomousDesktopAgent` runs closed-loop ReAct: Observe ($T_0$) &rarr; Plan &rarr; Act & Verify &rarr; Observe ($T_1$) &rarr; Reflect & Self-Correct.
    - Deterministic offline goal decomposition for hermetic testing + pluggable local SLM tool-calling.
    - Self-correcting reflection upon unverified mutations (consecutive misses detection & recovery).
  - **Minimalist Headless Daemon (`desktop-dom serve` in `src/desktop_dom/server.py`):**
    - Multi-threaded standard-library HTTP/JSON-RPC daemon on `http://127.0.0.1:8484` with zero external dependencies.
    - Sub-millisecond endpoints for Crcle's proprietary Mac frontend: `GET /health`, `POST /tree`, `POST /action`, `POST /diff`, `POST /intent`, `POST /agent/run`.
  - **CLI Commands:** Added `desktop-dom serve` and `desktop-dom run "<goal>"`.
- **Level 2 Personal Intent & Memory Engine (`src/desktop_dom/assistant/memory.py`):**
  - Persistent SQLite in WAL mode (`~/.desktop_dom/aura_memory.db`) with sub-millisecond dual-layer in-memory caching (<0.5ms lookups).
  - **5-Tier Entity Disambiguation Engine:** Direct email parsing (100), exact alias (100), first name & role match (92–94), typo-tolerant Levenshtein (80–88), and SequenceMatcher fuzzy similarity (70+).
  - **Zero-Click Ambient Onboarding & Cold-Start Hydration (`desktop-dom onboard`):** Auto-harvests macOS user, Git identity, mail client, music player, and co-authors in <50ms. Pre-seeds Crcle VIPs (Joshua Rayan, Cyril Rayan).
- **Comprehensive 14-Page Master Technical Guide & Curriculum:**
  - `docs/Desktop_DOM_Comprehensive_Technical_Master_Guide.pdf` (mirrored at `/Users/piyushdua/Desktop_DOM_Comprehensive_Technical_Master_Guide.pdf` and brain artifacts).
  - `docs/DESKTOP_DOM_MASTER_DEEP_DIVE_CURRICULUM.md` with exhaustive system call breakdowns and founder defense playbook.
- Branches: `main` (stable) and `develop` (integration) synced on `PDgit12/desktop-dom`.
- Remote repository live on GitHub at `https://github.com/PDgit12/desktop-dom` with 100% sole contributor attribution for PDgit12.




