# Contributing to `desktop-dom`

Thank you for your interest in contributing to `desktop-dom`! We are building the open-source semantic DOM and deterministic action engine for desktop AI agents.

---

## 1. Repository Branching Model

`desktop-dom` follows a standard Git Flow branching model:

```
[main]          ───●───────────────────────────●──────── (v0.1.0 Release Tag)
                    ▲                         ▲
[develop]       ────┴──────●─────────●────────┴──────── (Active Integration)
                           ▲         ▲
[feature/fix]   ───────────┴─────────┘                  (PR Branches)
```

* **`main`**: Protected branch. Represents stable, production-ready releases tagged with semantic versioning (`v0.1.0`, etc.). Direct pushes are discouraged.
* **`develop`**: The primary integration branch. All new features, performance improvements, and non-critical bug fixes merge here first via Pull Requests.
* **`feature/<name>`**: Feature development branches branched off `develop`. Example: `feature/multi-display-support`.
* **`fix/<name>`**: Bug fixes branched off `develop`.
* **`hotfix/<name>`**: Urgent production fixes branched directly off `main`.

---

## 2. Local Development Setup

### Clone and Install in Editable Mode
```bash
git clone https://github.com/PDgit12/desktop-dom.git
cd desktop-dom

# Switch to develop branch
git checkout develop

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode with development dependencies
pip install -e ".[all]"
```

### Running Tests
All Pull Requests must pass the 100% hermetic test suite:
```bash
pytest -v
```

### Building the TypeScript SDK
```bash
cd typescript
npm install
npm run build
```

---

## 3. Pull Request Guidelines

1. **Branch off `develop`:** Always create your branch from the latest `develop`.
2. **Atomic Commits:** Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:
   - `feat(...)`: New features or capabilities
   - `fix(...)`: Bug fixes
   - `docs(...)`: Documentation updates
   - `ci(...)`: GitHub Actions or release script changes
   - `chore(...)`: Dependency updates or build tooling
3. **Hermetic Testing:** Ensure all existing and newly added tests pass without requiring an active GUI window server wherever possible (use mocks or the test fixture adapter in `tests/conftest.py`).
4. **Code Quality:** Ensure zero personal paths, zero local filesystem leaks, and adhere to clean code principles.

---

## 4. Packaging & Publishing Guide

### Step 1: PyPI Release (Python SDK)
PyPI releases are automated via GitHub Actions (`.github/workflows/publish.yml`) triggered when a tag matching `v*` is pushed:

```bash
# Verify distributions locally first
./scripts/publish_pypi.sh

# Tag and push release
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```

To configure PyPI Trusted Publishing:
1. Go to [pypi.org/manage/account](https://pypi.org/manage/account/) -> **Publishing**.
2. Add a new GitHub Publisher for `PDgit12/desktop-dom` matching workflow `.github/workflows/publish.yml`.

### Step 2: npm Release (TypeScript SDK)
The TypeScript SDK package `@desktop-dom/core` is published under the `@desktop-dom` scope:

```bash
# Verify TypeScript build locally first
./scripts/publish_npm.sh
```

To enable automated npm publishing in CI:
1. Generate an Access Token with Publish permissions on [npmjs.com](https://www.npmjs.com/).
2. Add the token to GitHub Repository Secrets as `NPM_TOKEN`:
   - Repository Settings -> Secrets and variables -> Actions -> **New repository secret** (`NPM_TOKEN`).

---

## 5. Reporting Issues & Community

- **Bugs & Feature Requests:** Open an issue on [GitHub Issues](https://github.com/PDgit12/desktop-dom/issues).
- **Discussions & Ideas:** Join [GitHub Discussions](https://github.com/PDgit12/desktop-dom/discussions).
- **Follow on X:** Connect with [@PDgit12 on X](https://x.com/PDgit12) for announcements and engineering updates.
