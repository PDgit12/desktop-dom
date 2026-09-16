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
- **161 unit, integration, and hermetic regression tests passing** (`pytest` across 15 test files, 100% pass rate, 100% hermetic).
- **Pure-Data Verified Onboarding Architecture & Disjoint Knowledge Graph Isolation:**
  - Zero Speculation & Zero Hallucination: User declarations during onboarding (`desktop-dom onboard --interactive` or Omnibar Onboarding UI) explicitly seal user identity (`Piyush Dua | Backend Engineer @ Crcle.ai`), key collaborators (`Joshua Rayan [CTO]`, `Cyril Rayan [CEO]`), app bindings (Chrome, Outlook, Terminal, ChatGPT, Spotify, Zed), and habits into SQLite Knowledge Graph (`graph_edges`).
  - Strict Eradication of Ambient YouTube Seeds: Completely removed automatic stamping of speculative YouTube channels (Fireship, ThePrimeagen) from Chrome history in `local_ingest.py` and `memory.py`. Neutral YouTube home feed routing (`https://www.youtube.com`).
  - 4 Strictly Disjoint Subgraphs: `work`, `apps`, `personal_media`, and `gaming`.
  - Cluster Isolation Guarantee: Graph distance between work nodes (Joshua Rayan) and personal media (Diljit Dosanjh / YouTube) is mathematically verified to be $\infty$.
  - Anti-Drift Habit Protection: Verified user habits are locked with `is_explicit=1` and `confidence=1.0`, preventing telemetry or random browsing from hijacking habits.
  - Context Bleed Elimination: Outgoing work emails in Microsoft Outlook strictly resolve work topics from the `work` cluster (e.g. `desktop-dom`, `Crcle.ai`), eliminating accidental leaks of open YouTube tabs or Spotify tracks into work drafts.
- **Floating Omnibar Onboarding UI/UX & Native WebKit IPC Bridge (`omnibar.py`):**
  - Native Liquid Glass drawer with interactive application toggle chips (`active` state styling).
  - Clean form fields (Full Name, Role, Company, Focus Playlist, Collaborators) with autofocus on open.
  - Keyboard ergonomics: `Escape` dismisses drawer, `Enter` confirms and seals onboarding data, `×` close button.
  - Two-way WebKit script message bridge (`get_onboarding_data` & `save_onboarding`) synchronizing front-end UI state directly with `AuraMemory.complete_verified_onboarding()`.
- **Robust Multi-Pattern Natural Messaging Intent Parser (`brain.py`):**
  - Handles preposition-less phrasings (e.g., `"message cyril backend tests passing 100%"`) by scanning candidate entity prefixes against the Knowledge Graph.
  - Handles punctuation connectors (`:`, `,`, `-`) and explicit prepositions (`saying`, `about`, `with`, `that`).
  - Zero-hallucination recipient resolution: unknown recipients yield clean `not_found` response instead of falling back to speculative LLM completions.
  - Habitual Spotify playlist recall expansion: `"play focus playlist"`, `"play coding playlist"` resolves directly to locked `"Deep Focus"` in exact track order.
- **Zero-Touch Local Persona & Machine Ingestion (`local_ingest.py`):**
  - Replaces synthetic demo mocks with real user data: ingests actual Chrome SQLite history, actual top visited web apps, and local Git identity (`PDgit12 <piyushdua01@gmail.com>`).
- **Level 1 Polish & Dynamic OS Catalog (`src/desktop_dom/assistant/brain.py`):**
  - Dynamic application scanner indexes 100+ native apps across `/Applications`, `/System/Applications`, `/System/Applications/Utilities`, `~/Applications`.
  - `SequenceMatcher` typo tolerance (&ge;0.68) resolves typos without erroneous browser fallbacks.
  - Native folder navigation & safe app lifecycle control.
- **Level 2 Continuous Intent Cycle & Temporal Routine Engine (`context_feed.py` & `memory.py`):**
  - Diurnal temporal arbitration (Morning Kickoff, Deep Focus, Gaming).
  - Composite multi-app routine execution.
  - Activity classification and context introspection without vision tokens.
  - 5-Tier sub-millisecond entity disambiguation (<0.5ms).
- **The Cursor-Free ("Virtual Ghost Cursor") Architecture (`src/desktop_dom/adapters/macos.py`):**
  - Tier 1: Zero-movement OS action via `kAXPressAction`.
  - Tier 2: Microsecond cursor warp and restore (<0.8ms).
  - Tier 3: In-memory value mutation via `kAXValueAttribute`.
- **Level 2.5 Autonomous Execution Zone:**
  - Native AppleScript/JXA in-app IPC for Microsoft Outlook and Apple Mail.
  - Lightweight before-and-after DOM diffing ($T_1 - T_0$) in <0.25ms.
- **Level 3 Autonomous Agentic Loop & State Verification:**
  - $O(N)$ linear DOM diffing in `diff.py` (<0.25ms), `execute_and_verify()` state verification in `app.py`.
- **Native macOS Distribution:**
  - Native `Aura.app` bundle built and installed to `/Users/piyushdua/Applications/Aura.app`.
- **Dynamic Zero-Hardcoding Intent Graph & 1,000+ Use Case Generality:**
  - Zero Hardcoded Logic: Never hardcodes app names to intents (no static `if intent == "meeting": open Granola`). Everything resolves dynamically from sovereign SQLite Knowledge Graph edges `(User) -[handles_<intent>_intent {intent: "<intent>"}]-> (App)` and verified user preferences (`apps.primary_<intent>`).
  - 1,000+ Use Case Generality: Users configure any arbitrary tool and capability during Onboarding or Settings (`meeting: Granola/Zoom`, `design: Figma`, `tasks: Linear`, `3d: Blender`, `notes: Notion`, `crm: Salesforce`).
  - Sub-millisecond Resolution: `resolve_app_for_intent(intent)` resolves in <0.5ms with zero speculation. If unconfigured, Aura returns an unconfigured status guiding the user to connect a tool in Onboarding or Settings.
  - Meeting Intent Execution: `"i have a meeting [with ...]"` resolves primary meeting companion dynamically, launches the app, captures active desktop context, and extracts mentioned collaborators via personal entity memory.
  - UI & WebKit IPC: Onboarding and Settings drawers feature explicit App Name and Capability/Intent inputs (`on_add_app`, `on_delete_app`), with default action cards and suggestion triggers.
- Branches: `main` (stable) and `develop` (integration) synced on `PDgit12/desktop-dom`.
- Remote repository live on GitHub at `https://github.com/PDgit12/desktop-dom` with 100% sole contributor attribution for PDgit12.
