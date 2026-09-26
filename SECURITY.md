# Security Policy

## Sovereign Security Architecture & Threat Model

`desktop-dom` and **Aura** are engineered with a strict **local-first, zero-cloud custody** architecture:

1. **Zero External Database Daemons (Zero-Postgres):**
   - 100% of user data, entities, graph edges, and preferences are stored exclusively on-device in SQLite (`~/.desktop_dom/aura_memory.db`).
   - The database operates in Write-Ahead Logging (WAL) mode (`PRAGMA journal_mode=WAL`) with user-isolated file permissions (`0o600` for the database and `0o700` for the directory).
   - No external database daemons (PostgreSQL, MySQL, Supabase) are required or listened on network sockets.

2. **Zero Plaintext Token Custody:**
   - OAuth access tokens and client secrets are never stored in plaintext within SQLite or application state.
   - Cloud integrations utilize Composio's stateless OAuth session exchange. The local database stores only minimal routing metadata (`toolkit`, `status`, `consent_version`, `data_scopes`).

3. **Sovereign Data Scopes & Ingestion Governance:**
   - User-controlled data scopes (`calendar`, `repos`, `contacts`, `notes`, `media`) must be explicitly enabled before background ingestion pipelines process data.
   - Disabling or purging a scope removes associated provenance-tagged entities from the local Knowledge Graph immediately.

4. **Local Neural Model Isolation:**
   - When running local LLMs via Ollama (`ministral-3:8b`, `qwen3:8b`), all prompt synthesis, context injection, and reasoning occur strictly on `localhost:11434` without internet transit.
   - Hardened anti-hallucination guardrails prevent models from attempting web searches for personal data.

5. **Local Storage Audit Engine:**
   - Verify your database integrity, file permissions, and token custody anytime using:
     ```bash
     desktop-dom audit
     ```
   - Or programmatically via JSON:
     ```bash
     desktop-dom audit --json
     ```

---

## Supported Versions

| Version | Supported |
| :--- | :--- |
| `0.2.x` | :white_check_mark: Active security & stability maintenance |
| `< 0.2.0` | :x: End of life |

---

## Reporting a Vulnerability

If you discover a security vulnerability or potential token leakage, please report it privately:

- **Email:** `security@desktop-dom.dev` or directly to repository maintainer `piyushdua01@gmail.com`.
- **GPG Key:** Maintainer key available on keybase / GitHub profile.
- Please include reproduction steps, environment details, and affected components.
- We acknowledge reports within 24 hours and aim to release patches within 72 hours for critical issues.
