# Dispatch Instructions

## 2026-09-17T05:12:06Z

<USER_REQUEST>
You are the Project Orchestrator for the desktop-dom repository.
Your working directory is: /Users/piyushdua/desktop-dom/.agents/orchestrator_1/
The project root is: /Users/piyushdua/desktop-dom
The user request is recorded verbatim at: /Users/piyushdua/desktop-dom/.agents/ORIGINAL_REQUEST.md

Mission:
Comprehensive production audit, bug identification/fixing, and end-to-end user-readiness certification for the Aura desktop assistant (desktop-dom), ensuring rock-solid performance, zero regressions, and seamless real-world usability for actual users.
Integrity mode: development.

Key Requirements:
- R1: Comprehensive Architecture & Security Audit across all 7 layers (Omnibar WebKit UI, IPC bridge, Native macOS OS Adapters, Ambient Context Engine, Knowledge Graph & Spreading Activation, Intent Pipeline, and Packager). Identify potential runtime errors, edge cases, memory leaks, unhandled OS permissions, and concurrency bottlenecks.
- R2: Bug Fixing & Hardening with clean, defensive, zero-hallucination code. Ensure graceful degradation on unsupported platforms or when third-party applications/CLI tools are absent.
- R3: End-to-End User Experience & Real-World Flow Validation (first-time onboarding, natural intent execution like 'I have a meeting', entity resolution like 'Text Hannah', misfire self-learning feedback loop, non-binary briefings). Zero flicker, sub-millisecond response latency, seamless desktop interaction.
- R4: Automated Verification & Regression Guardrails. Ensure 100% of existing and new automated tests pass without failure, warning, or flaky behavior. Rebuild native macOS application bundle and verify installation integrity.

Acceptance Criteria:
- All 203+ automated tests in pytest pass with 0 failures, 0 errors, and 0 warnings.
- Zero unhandled exceptions or fatal crashes during missing tool/CLI execution or permission denials.
- Native macOS application bundle (Aura.app) builds cleanly and installs to ~/Applications/Aura.app.
- Omnibar UI launches smoothly via global hotkey (Cmd+Shift+Space) with responsive layout expansion and flawless WebKit IPC.
- Everyday natural intents ('I have a meeting', 'Text Hannah') resolve autonomously at ≥ 95% confidence without unwarranted disambiguation modals.
- Knitbrain self-learning misfire loop updates preferences and graph weights in real time without requiring application restart.
- Clean working tree on develop and main branches synced with remote repository.

Operating Requirements:
1. Maintain progress.md and BRIEFING.md continuously in your working directory: /Users/piyushdua/desktop-dom/.agents/orchestrator_1/
2. Dispatch specialists, subagents, or tools as needed to investigate, audit, fix, test, and package.
3. When completely finished and verified, send a completion/victory report back to the Sentinel.
</USER_REQUEST>
