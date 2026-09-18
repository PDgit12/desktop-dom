# Project: Aura Desktop Assistant (desktop-dom) Production Hardening

## Architecture
The Aura desktop assistant is a production-grade macOS assistant built across 7 modular layers:
1. **Omnibar WebKit UI**: Floating liquid-glass Cocoa `NSPanel` (`FloatingOmnibar`, `AuraKeyablePanelObjC`), dynamic height expansion (52px–360px), menu bar status item, and single-instance Unix domain socket server (`/tmp/desktop_dom_aura.sock`).
2. **IPC Bridge**: Bi-directional communication between WebKit JavaScript (`window.webkit.messageHandlers.desktopDom`) and Python (`OmnibarScriptHandlerObjC` / `FloatingOmnibar.evaluate_js`). Supports 12 inbound actions and 6 outbound UI methods.
3. **Native macOS OS Adapters**: `MacOSAdapter` using `AXUIElement` accessibility tree traversal, Electron/Chromium tree hydration (`AXEnhancedUserInterface`), multi-display coordinate mapping, zero-cursor ghost clicks (`AXPress` / `CGWarpMouseCursorPosition`), and Unicode keyboard dispatch.
4. **Ambient Context Engine**: `ContextFeedEngine` telemetry collection (<20ms) via AppleScript and meaning synthesis into human activity categories. Non-binary adapters for Apple Calendar/Outlook, GitHub PRs (`gh`), Linear issues, and recent emails.
5. **Knowledge Graph & Spreading Activation (Knitbrain)**: `AuraMemory` SQLite WAL database with 9 core tables. Spreading activation (`ignite_graph`) with distance decay and context symmetry breaking (+25 work boost in IDE context). Real-time misfire learning loop (`record_misfire`) penalizing false positives and reinforcing targets without application restart.
6. **Intent Pipeline**: `AssistantBrain.execute_intent()` with sub-50ms deterministic fast-paths for everyday desktop workflows (meetings, contacts, calendar, music, video, system controls) with local Ollama fallback.
7. **Packager & App Bundle Structure**: `scripts/build_app.py` and `build_app.sh` compiling standalone `Aura.app` (`LSUIElement=true`, dark glassmorphic `AppIcon.icns`, bundled source tree) installing to `~/Applications/Aura.app`.

---

## Code Layout
```text
/Users/piyushdua/desktop-dom/
├── src/desktop_dom/
│   ├── adapters/
│   │   ├── base.py            # BasePlatformAdapter contract
│   │   ├── macos.py           # Native macOS AXUIElement & Quartz adapter
│   │   ├── linux.py           # Linux AT-SPI2 adapter
│   │   └── windows.py         # Windows CUIAutomation8 adapter
│   ├── assistant/
│   │   ├── omnibar.py         # Layer 1 & 2: Floating Cocoa NSPanel & WebKit IPC
│   │   ├── brain.py           # Layer 6: Intent execution pipeline & fast paths
│   │   ├── memory.py          # Layer 5: Knowledge Graph & Knitbrain learning
│   │   ├── context_feed.py    # Layer 4: Ambient telemetry ingestion & synthesis
│   │   ├── non_binary.py      # Layer 4: Calendar, Git, Linear, Email adapters
│   │   ├── local_ingest.py    # Chrome/Git/Contacts local machine ingest
│   │   └── audio.py           # TTS/STT faster-whisper audio manager
│   ├── cli/
│   │   ├── main.py            # Typer CLI entry points
│   │   └── doctor.py          # System environment & permissions diagnostic
│   └── models/
│       ├── node.py            # DesktopNode & BoundingBox models
│       └── diff.py            # DOM Tree mutation models
├── tests/                     # 203+ automated pytest suites
├── scripts/
│   ├── build_app.py           # Native macOS Packager & Icon compiler
│   └── build_app.sh           # Packager shell script wrapper
├── pyproject.toml             # Packaging, dependencies, and pytest configuration
└── .github/workflows/ci.yml   # Continuous integration pipeline
```

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | SQLite Connection & Memory Integrity | Fix connection leak in `AuraMemory._get_connection()` by caching `self._conn`, adding thread lock and graceful close | M1 | Survey (explorer_survey_2) |
| 2 | Pytest Warning Elimination | Set `asyncio_default_fixture_loop_scope = "function"` in `pyproject.toml` | M1 | Survey (all explorers) |
| 3 | macOS Optional Dependencies | Add `pyobjc-framework-WebKit>=10.0` to `pyproject.toml:[project.optional-dependencies].macos` | M1 | Survey (explorer_survey_2) |
| 4 | Ambient Telemetry Caching | Thread-safe `get_cached_context` preventing redundant AppleScript subprocess calls | M1 | Survey (explorer_survey_1) |
| 5 | OS Permissions Diagnostic & Auto-Prompt | Add `AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})` to `macos.py` and `doctor.py` for Accessibility & Screen Recording | M2 | Survey (explorer_survey_1) |
| 6 | Non-Binary Graceful Degradation | Defensive handling for missing CLI binaries (`gh`, `linear`) and AppleScript `-1743` permission errors | M2 | Survey (spec_miner_survey_1) |
| 7 | Multi-Display Negative Coordinates | Support display calibration with negative Quartz coordinates | M2 | Survey (explorer_survey_1) |
| 8 | IPC Socket Server Robustness | Single-instance Unix socket `/tmp/desktop_dom_aura.sock` with graceful stale socket cleanup | M2 | Survey (explorer_survey_1) |
| 9 | Omnibar WebKit UI & IPC Contract | 12 inbound actions, 6 outbound JS calls, smooth height expansion (52px to 360px) | M3 | Survey (explorer_survey_1) |
| 10 | Everyday Natural Intent "I have a meeting" | Dynamic companion app resolution from Knowledge Graph at $\ge 95\%$ confidence | M3 | Survey (spec_miner_survey_1) |
| 11 | Entity Resolution "Text Hannah" | Context symmetry breaking (+25 work boost) resolving Hannah Vance without disambiguation | M3 | Survey (spec_miner_survey_1) |
| 12 | Knitbrain Real-Time Self-Learning | Misfire feedback loop penalizing false-positives (-0.40) and updating preferences without restart | M3 | Survey (spec_miner_survey_1) |
| 13 | First-Time User Onboarding Flow | Verification of onboarding drawer, cluster isolation, and pure-data memory sealing | M3 | Survey (spec_miner_survey_1) |
| 14 | CI & Packager Portability Hardening | Add platform guards and auto-build fallback in `test_packager.py`, add `develop` branch to CI | M4 | Survey (explorer_survey_2) |
| 15 | Native macOS Application Bundle Build | Execute `scripts/build_app.sh`, compiling `Aura.app` and installing to `~/Applications/Aura.app` | M4 | Survey (all explorers) |
| 16 | 100% Automated Test & Regression Guardrails | 203+ automated tests passing with 0 failures, 0 errors, 0 warnings | M4 | Survey (all explorers) |
| 17 | Final Forensic Integrity Audit | Complete forensic integrity audit certifying zero cheating, genuine implementation, clean gate | M4 | Original Request |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Core Foundation & Memory Hardening | Fix SQLite FD leak in `AuraMemory`, add `pyobjc-framework-WebKit` in `pyproject.toml`, set `asyncio_default_fixture_loop_scope = "function"` | none | PLANNED |
| M2 | OS Adapters & Permissions Hardening | Native permissions prompt (`AXIsProcessTrustedWithOptions`), graceful degradation for missing tools (`gh`, `linear`, AppleScript `-1743`), socket cleanup | M1 | PLANNED |
| M3 | Intent Pipeline & Knitbrain Verification | Onboarding flow, natural intents ("I have a meeting", "Text Hannah" $\ge 95\%$ confidence), Knitbrain real-time misfire self-learning, WebKit IPC | M1, M2 | PLANNED |
| M4 | Native App Packaging & Final Certification Gate | Packager test hardening, CI `develop` tracking, `Aura.app` build & install to `~/Applications/Aura.app`, 100% test pass (0 failures, 0 warnings), forensic audit | M1, M2, M3 | PLANNED |

---

## Interface Contracts

### Layer 5: AuraMemory SQLite Contract (`src/desktop_dom/assistant/memory.py`)
- `_get_connection() -> sqlite3.Connection`: Must reuse `self._conn` cached connection under `self._lock` with WAL mode enabled.
- `close()`: Explicitly close `self._conn` and set to `None`.
- `record_misfire(query: str, false_positive_target: str, corrected_target: str, intent: str, user_feedback: str = "")`: Persists to SQLite and immediately refreshes in-memory hot caches (`_pref_cache`, `_graph_adj`).

### Layer 3: MacOSAdapter Permissions Contract (`src/desktop_dom/adapters/macos.py`)
- `check_permissions(prompt: bool = False) -> Dict[str, Any]`: When `prompt=True`, must invoke `ApplicationServices.AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})` to trigger the native macOS system dialog if untrusted.

### Layer 1 & 2: Omnibar IPC Contract (`src/desktop_dom/assistant/omnibar.py`)
- Inbound: `window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({action: str, ...}))`
- Outbound: `Cocoa.NSOperationQueue.mainQueue().addOperationWithBlock_(lambda: webview.evaluateJavaScript_completionHandler_(js_code, None))`

### Layer 7: Application Bundle Contract (`scripts/build_app.sh`, `scripts/build_app.py`)
- Invocation: `bash scripts/build_app.sh` compiles `dist/Aura.app` and syncs to `~/Applications/Aura.app`.
- Structure:
  - `~/Applications/Aura.app/Contents/Info.plist` with `LSUIElement=True`.
  - `~/Applications/Aura.app/Contents/MacOS/Aura` executable launcher.
  - `~/Applications/Aura.app/Contents/Resources/AppIcon.icns`.
  - `~/Applications/Aura.app/Contents/Resources/src/desktop_dom`.
