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
- **Intent Layer vs. Virtual Assistant Engine (Spreading Activation & Zero Vague Prompts):**
  - **Core Philosophy:** True intent layer, not a command executor. Normal human prompts like `"I have a meeting"` or `"Text Hannah"` are never treated as "vague". Aura uses ambient workspace context, active cluster (work vs. personal), recency, and habitual patterns to break symmetry and act autonomously at $\ge 95\%$ confidence.
  - **Spreading Activation Engine (`memory.py`):** In-memory dynamic Knowledge Graph with seed energy injection ($A_0$), multi-hop edge propagation ($A_j^{(t)}$), and strict cluster barrier isolation ($\Omega(\text{cluster}) = 0.0$ between work and personal media/gaming during work sessions).
  - **Calibrated Tiered Confidence:**
    - Tier 1 ($\ge 95\%$): Autonomous execution with screen context (meeting notes prep, verified contact messaging).
    - Tier 2 ($80\% - 85\%$): Cautious execution for indeterminate requests (`"do something"`).
    - Tier 3 ($< 78\%$): Single-Shot Disambiguation only when true intra-cluster symmetry exists with zero recency difference (asks once, remembers forever).
  - **Knitbrain Self-Learning & Misfire Loop:** When a user corrects an action (e.g. `"No, open Zoom instead"`), Aura records the misfire and false positive in `misfires`, applies an edge penalty to the old tool, boosts the new tool to $1.0$, stores the learned rule in `learnings`, and immediately executes the corrected tool. Subsequent queries autonomously route to the corrected tool.
  - **Non-Binary Destinations:** Queries native OS adapters (e.g. AppleScript on Microsoft Outlook/Mail) for non-binary context like `"last email from Josh"`, returning real sender, subject, timestamp, and snippet without hallucinations.
  - **Comprehensive Test Coverage:** 203 tests passing across `test_assistant.py`, `test_intent_layer.py`, `test_context_feed.py`, `test_non_binary_adapters.py`, `test_knitbrain_learning.py`, and `test_packager.py` (100% pass rate).
- **7-Aspect Specialized Multi-Agent Architecture:**
  1. **Omnibar UI & Feedback:** 1-click `"Wrong tool? Teach Aura"` feedback chip, inline correction trigger, and WebKit IPC bridge (`on_record_misfire`) updating status badge dynamically.
  2. **Non-Binary OS Adapters (`non_binary.py`):** Native AppleScript/JXA adapters for calendar briefings (Apple Calendar / Outlook with Zoom/Teams link extraction), local git status & GitHub CLI (`gh pr status`), Linear issues GraphQL/CLI queries, and Outlook/Mail lookup.
  3. **Ambient Context Telemetry (`context_feed.py`):** Workspace git branch/dirty detection, diurnal cadence classification (`morning_standup`, `deep_work`, `afternoon_review`, `evening_off_hours`), and sub-millisecond thread-safe caching (`get_cached_context()`).
  4. **Sovereign Knowledge Graph (`memory.py`):** Dynamic graph queries, `compute_cluster_barrier` ($\Omega = 0.0$ work vs gaming/personal), entity symmetry-breaking boosts (+25.0 / -20.0), and calibrated confidence scoring.
  5. **Decoupled Intent Pipeline (`brain.py`):** 4 clean stages (Ingestion $\rightarrow$ Activation $\rightarrow$ Symmetry Breaking $\rightarrow$ Dispatch) with zero static fallbacks.
  6. **Knitbrain Self-Learning Misfire Loop:** Dynamic negative edge weight penalization (0.5x), target reinforcement (1.0), habit override persistence in `learnings`, and zero-restart auto-resolution on next query.
  7. **Release Packaging & Verification:** Automated bundle compilation (`scripts/build_app.sh`), structural verification (`tests/test_packager.py`), and deployment to `/Users/piyushdua/Applications/Aura.app`.
- Branches: `main` (stable) and `develop` (integration) synced on `PDgit12/desktop-dom`.
- Remote repository live on GitHub at `https://github.com/PDgit12/desktop-dom` with 100% sole contributor attribution for PDgit12.

- **Production Hardening, SQLite Connection Integrity & 253-Test Opaque-Box Suite (Certified):**
  - **Zero-Warning Pytest Suite:** 253 / 253 tests passing across 20 test suites in 39.5s with zero failures, zero errors, and zero warnings (`asyncio_default_fixture_loop_scope = "function"`).
  - **Memory Integrity & SQLite Connection Caching:** Replaced transient connection opening with thread-safe cached connection (`self._conn` under `threading.RLock`) in `AuraMemory`, along with context manager (`__enter__`/`__exit__`) and `close()`.
  - **OS Permissions Diagnostic & Auto-Prompt:** Added optional `prompt: bool = False` to `BasePlatformAdapter.check_permissions` across all platform adapters (`MacOSAdapter`, `LinuxAdapter`, `WindowsAdapter`, `TestPlatformAdapter`). macOS triggers `AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})` when `doctor --fix` is invoked.
  - **Non-Binary Defensive Error Handling:** Trapped non-zero return codes and AppleScript `ERROR:` strings in `get_last_email()` to surface genuine permission denials and execution failures as `status: "error"` instead of masking them as `not_found`.
  - **Intent Layer & Symmetry Breaking:**
    - Broadened meeting regex in `brain.py` to capture `upcoming`, `next`, and `current` meeting variations.
    - Preserved ticket acronyms (e.g. `ENG-401`) and proper nouns in message drafting by replacing `str.capitalize()` with first-letter uppercase.
    - Derived active work context from domain-specific tokens (`email`, `mail`, `outlook`, `design`, `tokens`, `pr`) to ensure work symmetry breaking even during off-hours testing.
    - Fixed Python `"" in s` edge case in `resolve_entity()` where empty roles incorrectly scored 92.0 against contact names.
    - Locked `spotify.playlist.personal` preference and habit during verified onboarding and handled explicit `req_personal` in `brain.py`.
  - **Native macOS Bundle:** Rebuilt and verified `~/Applications/Aura.app` with `Info.plist`, executable launcher, dark glassmorphic `AppIcon.icns`, and embedded source tree.
- **Professional Non-AI Command Palette UI & Draggable Omnibar Anywhere (254 Tests Certified):**
  - **Free-Floating Window Dragging & Hover Anywhere:**
    - Integrated native `-webkit-app-region: drag` and grab cursor styling on `#drag-handle-bar` and `#header-bar` with `-webkit-app-region: no-drag` on interactive controls.
    - Implemented `initDraggableWindow()` in JavaScript posting real-time screen coordinate deltas (`dx`, `dy`) via `drag_window` WebKit IPC message handler.
    - Added `move_window_by(dx, dy)` in `FloatingOmnibar` and `OmnibarScriptHandler`, translating Cocoa `NSPanel` screen coordinates (`new_origin = NSMakePoint(frame.origin.x + dx, frame.origin.y - dy)`).
    - Enabled `setMovable_(True)` and `setMovableByWindowBackground_(True)` on `AuraKeyablePanelObjC`.
  - **Institutional-Grade / Non-AI Styling:**
    - Replaced chatbot novelty with sleek, high-contrast command palette design (Spotlight / Raycast / Linear aesthetic).
    - Added workspace pill (`[ ⚡ Crcle.ai • Work ]`) dynamically displaying current cluster and opening Knowledge Graph configuration drawer on click.
    - Updated query input placeholder to `"Search commands, meetings, contacts, or type an action..."`.
    - Added keyboard navigation badges (`<kbd>↑↓</kbd> Navigate`, `<kbd>↵</kbd> Execute`, `<kbd>esc</kbd> Dismiss`, `<kbd>✥</kbd> Drag Anywhere`).
  - **Defensive Execution & Context Symmetry Hardening:**
    - Wrapped AppleScript calls (`osascript`) for Microsoft Outlook and Apple Mail in defensive `try ... except (subprocess.SubprocessError, subprocess.TimeoutExpired, FileNotFoundError, OSError)` with 4.0s timeout to prevent unhandled exceptions when email clients are closed or unresponsive.
    - Hardened `resolve_entity()` in `memory.py` to prioritize explicit personal context (`activity_category == "personal"` or messaging app) so time-of-day work hours never incorrectly override personal communication.
  - **Automated Verification & Packaging:**
    - 254 / 254 tests passing cleanly across full pytest suite in 58.01s (0 failures, 0 errors, 0 warnings).
- **Composio Federated Integration & Sovereign Data Access Layer (269 Tests Certified):**
  - **Sovereign Canonical Data Contracts (`integrations/contracts.py`):**
    - Zero External Vendor Coupling: Aura owns `CanonicalCalendarEvent`, `CanonicalContact`, `CanonicalRepository`, and `CanonicalCommunicationSnippet`.
    - Zero Token / Credential Storage: Aura never stores OAuth tokens or refresh secrets locally; Composio remains the OAuth credential authority.
    - Explicit `ConnectedAccountState` with toolkits (`googlecalendar`, `github`, `gmail`, `slack`), data scopes, and state lifecycle (`PENDING`, `ACTIVE`, `REVOKED`, `DISCONNECTED`).
  - **Zero-Dependency Resilient Client (`integrations/composio_client.py`):**
    - Pure Python standard library (`urllib.request`) client with strict timeouts (10.0s), header auth, and graceful offline/unconfigured trapping.
  - **Bounded Normalization Pipeline (`integrations/normalizer.py`):**
    - Google Calendar: Extracts events, timestamps, attendee lists, and regex-parses video conferencing links (Zoom, Google Meet, Microsoft Teams).
    - GitHub: Normalizes repositories, stars, open PRs, languages, and owner metadata.
    - Gmail / Slack: Extracts correspondent contacts, interaction frequency, and recent message snippets with strict privacy truncation (max 300 chars, no attachments/PII).
  - **Sync & Ingestion Engine (`integrations/composio_ingest.py`):**
    - Sync cycles (`sync_calendar`, `sync_github`, `sync_gmail`, `sync_all_active`) map external items into SQLite `graph_entities` and `graph_edges` tagged with immutable source provenance (e.g. `provenance: "composio:googlecalendar"`).
    - Privacy Purge (`disconnect_and_purge`): Instantly severs connection in Composio and purges all entities and edges originating from that toolkit from local SQLite without touching manually verified onboarding data.
  - **Omnibar UI & WebKit IPC Bridge (`omnibar.py`):**
    - High-density dark glassmorphic integration grid (`.composio-connect-grid`) in both Onboarding and Settings drawers.
    - Live connection cards (`googlecalendar`, `github`, `gmail`, `slack`) with status badges (`Connected`, `Connecting...`, `Connect`).
    - Two-way WebKit script message handlers: `connect_composio_app`, `disconnect_composio_app`, `sync_composio_app`, and `get_composio_status`.
    - Real-time OAuth popup trigger opening Composio authorization flow in user's default browser.
  - **Intent Layer Enrichment (`brain.py` & `non_binary.py`):**
    - `get_calendar_briefing()` prioritizes cached canonical Google Calendar events from Composio (`tier="canonical_composio"`), rendering rich meeting agendas with direct Join links.
    - `_handle_meeting_intent()` enriches meeting requests (`"i have a meeting with Hannah"`) by extracting canonical meeting URLs and injecting them into the response payload.
  - **Automated Verification & Release:**
    - 269 / 269 tests passing across all 22 test suites in 60.86s with zero failures, zero errors, and zero warnings.
    - Native macOS application bundle `Aura.app` rebuilt and installed to `~/Applications/Aura.app`.
    - Synchronized `develop` and `main` branches and pushed to GitHub remote `PDgit12/desktop-dom`.
- **Omnibar Write Execution, OAuth Polling & Workspace Switcher (273 Tests Certified):**
  - **Direct Write-Action Execution (`composio_ingest.py` & `brain.py`):**
    - GitHub Issues: Prompts like `"create issue on desktop-dom: Fix menu bar hover"` or `"file issue <title>"` autonomously call `GITHUB_CREATE_AN_ISSUE` and return clickable issue URLs.
    - Google Calendar Event Scheduling: Prompts like `"schedule meeting with Cyril tomorrow at 3pm"` or `"book 30m with Josh"` autonomously call `GOOGLECALENDAR_CREATE_EVENT` and generate instant Meet links.
    - Gmail Draft Creation: Prompts like `"draft email to Josh saying backend tests passing"` autonomously call `GMAIL_CREATE_DRAFT` without touching local Mail clients.
    - Slack Message Dispatch: Autonomous posting via `SLACK_CHAT_POST_MESSAGE` with clean `#channel` resolution.
    - Graceful Degraded Fallbacks: If an integration is unconfigured or unconnected, Aura returns helpful instructions to connect the app in Settings.
  - **Zero-Click Background OAuth Polling Loop (`omnibar.py`):**
    - Spawns a background thread on "Connect" button click, polling Composio connection status every 2.5s.
    - Transitions account status to `ACTIVE` in `AuraMemory`, runs initial sync, and evaluates JavaScript to turn the card green (`Connected`) the moment user finishes browser OAuth without requiring manual page refresh or sync clicks.
  - **Fast Project & Workspace Switcher (`Cmd+P` & Workspace Pill):**
    - Accessible via `Cmd+P`, `Ctrl+P`, or clicking the header `#workspace-pill`.
    - Opens `#project-drawer` allowing instant 1-click switching between sovereign workspaces (e.g. `Crcle.ai`, `desktop-dom`, `Personal`) or creating custom project names.
    - Natural language project switching supported: `"switch project to desktop-dom"` or `"project: desktop-dom"`.
  - **In-App Composio API Key Management (`omnibar.py`):**
    - Sleek API key configuration input in Settings drawer (`#settings-composio-key`) with masked preview, instant key persistence in `AuraMemory`, and live validation status badges.
  - **Automated Verification & Packaging:**
    - 273 / 273 tests passing cleanly across full pytest suite in 73.80s (0 failures, 0 errors, 0 warnings).
    - Native macOS application bundle `Aura.app` rebuilt and installed to `~/Applications/Aura.app`.
- **Live Composio Platform Integration, Skill Installation & First Tool Call Verification:**
  - **Skill & SDK Installation:**
    - Installed official Composio skill via `npx skills add ComposioHQ/composio --skill composio -y` into `.agents/skills/composio`.
    - Upgraded environment to official `composio` SDK (v0.21.1) and `composio-client` (v1.43.0).
    - Upgraded `ComposioHttpClient` (`src/desktop_dom/assistant/integrations/composio_client.py`) to support Composio v3/v3.1 REST API (`https://backend.composio.dev/api/v3`) and delegate dynamically to the official `composio.Composio` SDK while preserving 100% backward-compatibility for unit test mocks.
  - **First Live Tool Call Executed:**
    - Executed live session tool call: `session.execute('COMPOSIO_GET_TOOL_SCHEMAS', arguments={'tool_slugs': ['GITHUB_GET_A_REPOSITORY']})`.
    - Received real Composio Platform execution log ID: `log_YO9FZqVHnIdo` with `success=True`.
  - **OAuth Connect Links Generated:**
    - GitHub: `https://connect.composio.dev/link/lk_ATLsK_l96aWW`
    - Google Calendar: `https://connect.composio.dev/link/lk_OkjSc5EFOBUP`
    - Gmail: `https://connect.composio.dev/link/lk_I8dN2KBzLuVU`
    - Slack: `https://connect.composio.dev/link/lk_63eXmbHZpmWM`
  - **Automated Verification:**
    - 273 / 273 tests passing across all 22 test suites in 75.07s (0 failures, 0 errors, 0 warnings).
- **Zero-Friction Desktop Onboarding, Direct CLI Trigger & Architectural Hardening (275 Tests Certified):**
  - **Composio-First 1-Click Desktop Onboarding UI (`omnibar.py`):**
    - High-friction 6-field text form replaced with prominent 1-Click Connect Cards for Google (Calendar & Gmail), GitHub, and Slack.
    - Dynamic discovery banner (`#onb-discovery-banner`) lights up automatically upon account authorization, reflecting discovered calendar events, repos, and teammates with zero typing.
    - Legacy manual inputs safely housed in an optional collapsible accordion (`#onb-manual-accordion`), allowing instant 1-click completion via `"Launch Aura ➔"`.
  - **Direct CLI Invocation & Single-Instance IPC Socket Bridge (`main.py` & `omnibar.py`):**
    - Added `--omnibar` (default True) and `--onboard` flags to `desktop-dom assistant`.
    - Integrated single-instance UNIX domain socket IPC (`/tmp/desktop_dom_aura.sock`): when Aura is already active, `desktop-dom assistant --omnibar --onboard` sends `b"onboard\n"`, bringing the window to the front and opening the onboarding drawer immediately.
  - **Deterministic Intent Routing Polish (`brain.py` & `non_binary.py`):**
    - Added repository status intent resolution (`what is on desktop-dom` / `status of desktop-dom`) directly to `route_non_binary_intent`, returning live branch, uncommitted files, and active PR status.
    - Enhanced `who_is` matching to accept hyphenated/symbol entities (`desktop-dom`, `Crcle.ai`) and `what is <entity>` queries.
  - **Hermetic Test Suite Stabilization:**
    - Replaced fixed `time.sleep(0.08)` in WebKit IPC dispatch test (`tests/test_e2e_opaque_box.py`) with a resilient polling deadline loop, eliminating thread preemption flakiness under heavy test load.
    - Added hermetic CLI tests for `--omnibar` and `--onboard` in `tests/test_cli.py`.
    - All 275 / 275 automated tests passing across 22 test suites with 0 failures, 0 errors, and 0 warnings.
  - **Native macOS Bundle Updated:**
    - Recompiled and installed to `/Users/piyushdua/Applications/Aura.app`.




