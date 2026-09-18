# Dispatch: E2E Test Suite Creation Track

## Identity
- Role: E2E Test Suite Architect & Writer
- Type: teamwork_preview_test_writer
- Working directory: /Users/piyushdua/desktop-dom/.agents/test_writer_e2e_1
- Project root: /Users/piyushdua/desktop-dom

## Inputs
- /Users/piyushdua/desktop-dom/.agents/ORIGINAL_REQUEST.md
- /Users/piyushdua/desktop-dom/PROJECT.md

## Objective
Design and implement a comprehensive opaque-box E2E test suite for Aura (desktop-dom) following the 4-Tier Test Case Design Methodology:
- **Tier 1 (Feature Coverage)**: >=5 tests per feature covering representative happy-path inputs (e.g., onboarding detection, "I have a meeting", "Text Hannah", non-binary calendar/git/linear/email briefings, WebKit IPC actions, packaging integrity).
- **Tier 2 (Boundary & Corner Cases)**: Edge cases, unhandled permissions, missing tools/CLI (`gh`, `linear`, AppleScript `-1743`), empty/invalid prompts, multi-display negative coords, socket collisions.
- **Tier 3 (Cross-Feature Combinations)**: Pairwise interactions (e.g., onboarding -> meeting intent -> misfire correction -> subsequent meeting query; IDE context -> "Text Hannah" -> draft email -> calendar briefing).
- **Tier 4 (Real-World Application Scenarios)**: Full real-world developer workflows from fresh launch to ambient switching and intent resolution.

## Constraints & Requirements
- Put test cases in `tests/test_e2e_opaque_box.py` or dedicated `tests/e2e/` folder.
- Ensure tests are completely independent of internal mock details where possible; exercise the user-facing CLI and brain/memory contracts directly.
- Create `/Users/piyushdua/desktop-dom/TEST_INFRA.md` and `/Users/piyushdua/desktop-dom/TEST_READY.md` upon completion.
- Verify tests pass with `pytest`.
- Write handoff report to `/Users/piyushdua/desktop-dom/.agents/test_writer_e2e_1/handoff.md`.
- Send completion message to orchestrator.

## 2026-09-17T05:18:53Z
You are test_writer_e2e_1, an E2E Test Suite Architect & Writer subagent for desktop-dom.
Your working directory is: /Users/piyushdua/desktop-dom/.agents/test_writer_e2e_1
The user request is at: /Users/piyushdua/desktop-dom/.agents/ORIGINAL_REQUEST.md
Your dispatch instructions are at: /Users/piyushdua/desktop-dom/.agents/test_writer_e2e_1/DISPATCH.md
Project plan is at: /Users/piyushdua/desktop-dom/PROJECT.md
Project root: /Users/piyushdua/desktop-dom

Read ORIGINAL_REQUEST.md, PROJECT.md, and DISPATCH.md first.
Design and implement a comprehensive opaque-box E2E test suite for Aura (desktop-dom) following the 4-Tier Test Case Design Methodology:
- Tier 1 (Feature Coverage): >=5 tests per feature covering representative happy-path inputs (e.g. onboarding detection, "I have a meeting", "Text Hannah", non-binary calendar/git/linear/email briefings, WebKit IPC actions, packaging integrity).
- Tier 2 (Boundary & Corner Cases): Edge cases, unhandled permissions, missing tools/CLI (gh, linear, AppleScript -1743), empty/invalid prompts, multi-display negative coords, socket collisions.
- Tier 3 (Cross-Feature Combinations): Pairwise interactions (e.g. onboarding -> meeting intent -> misfire correction -> subsequent meeting query; IDE context -> "Text Hannah" -> draft email -> calendar briefing).
- Tier 4 (Real-World Application Scenarios): Full real-world developer workflows from fresh launch to ambient switching and intent resolution.

Write tests to tests/test_e2e_opaque_box.py.
Publish TEST_INFRA.md and TEST_READY.md at project root when complete.
Run pytest on the test suite to verify tests pass.
Write your handoff report to /Users/piyushdua/desktop-dom/.agents/test_writer_e2e_1/handoff.md following Handoff Protocol.
When finished, send a completion message to orchestrator.

