# Dispatch: Explorer M1-2 (Pyproject, WebKit Dependency & Pytest Config Strategy)

## Identity
- Role: Build & Config Explorer
- Type: teamwork_preview_explorer
- Working directory: /Users/piyushdua/desktop-dom/.agents/explorer_m1_2
- Project root: /Users/piyushdua/desktop-dom

## Inputs
- /Users/piyushdua/desktop-dom/.agents/ORIGINAL_REQUEST.md
- /Users/piyushdua/desktop-dom/PROJECT.md
- /Users/piyushdua/desktop-dom/pyproject.toml

## Objective
Analyze `pyproject.toml` to design exact configuration fixes:
1. Examine `[tool.pytest.ini_options]` and determine the exact placement and syntax for `asyncio_default_fixture_loop_scope = "function"` to eliminate the deprecation warning without breaking any of the 203 existing tests.
2. Examine `[project.optional-dependencies].macos` and determine the exact syntax for adding `pyobjc-framework-WebKit>=10.0` required by `src/desktop_dom/assistant/omnibar.py:2473`.
3. Check `[tool.ruff]` and package metadata for any other build/packaging discrepancies.
4. Formulate the verification method.

Write your report to `/Users/piyushdua/desktop-dom/.agents/explorer_m1_2/handoff.md`.
Send completion message to orchestrator.
