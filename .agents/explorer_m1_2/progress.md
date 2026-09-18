# Progress: Explorer M1-2 (Build & Config Explorer)

Last visited: 2026-09-17T05:22:20Z

## Status
- In Progress: Completed deep empirical investigation of `pyproject.toml`, pytest configuration, WebKit dependency, Ruff linter findings, and packaging discrepancies.
- Full regression test run with `asyncio_default_fixture_loop_scope=function` currently running (task-158).

## Steps
- [x] Read ORIGINAL_REQUEST.md, PROJECT.md, and DISPATCH.md
- [x] Initialize BRIEFING.md and progress.md
- [x] Inspect pytest run and observe pytest-asyncio deprecation warning
- [x] Determine exact syntax and placement for `asyncio_default_fixture_loop_scope = "function"`
  - Verified empirically via `-o asyncio_default_fixture_loop_scope=function -W error::pytest.PytestDeprecationWarning`
  - Completely eliminates the PytestDeprecationWarning
- [x] Determine exact syntax for `pyobjc-framework-WebKit>=10.0` in `[project.optional-dependencies].macos`
  - Verified import at `src/desktop_dom/assistant/omnibar.py:2473`
  - Verified system install: `pyobjc-framework-WebKit==12.1`
  - Verified consistent version constraint `>=10.0`
- [x] Check `[tool.ruff]` and package metadata / dependencies
  - Discovered 121 ruff errors under default config; analyzed exact config rules needed
  - Discovered CLI command shadowing: `src/desktop_dom/cli/main.py:511` redefines `serve`, shadowing MCP stdio command at line 231
  - Discovered version discrepancy: `pyproject.toml` specifies `0.1.0` while `scripts/build_app.py` defaults to `0.2.0`
  - Discovered missing `pytest-asyncio` in `[project.optional-dependencies].dev`
- [ ] Complete full regression verification of 203 tests (task-158)
- [ ] Formulate comprehensive verification method
- [ ] Write handoff.md
- [ ] Send completion message to parent
