#!/usr/bin/env bash
# ==============================================================================
# Aura Native macOS Application Bundle Build & Deployment Script
# Compiles and deploys Aura.app to /Users/piyushdua/Applications/Aura.app
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DIST_DIR="${REPO_ROOT}/dist"
TARGET_APP_DIR="${HOME}/Applications/Aura.app"

echo "============================================================"
echo "  Aura Desktop Assistant — macOS Application Bundle Packager"
echo "============================================================"
echo "Repository Root : ${REPO_ROOT}"
echo "Target Location : ${TARGET_APP_DIR}"
echo ""

# Ensure Python 3 is available
PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
elif [ -n "$VIRTUAL_ENV" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
    PYTHON_BIN="$VIRTUAL_ENV/bin/python"
else
    echo "Error: python3 not found in PATH." >&2
    exit 1
fi

echo "Using Python runtime: ${PYTHON_BIN} ($(${PYTHON_BIN} --version))"

# Check if PyInstaller mode is explicitly requested
if [[ "$*" == *"--pyinstaller"* ]]; then
    echo "Mode: PyInstaller standalone binary compilation requested."
    if ! "${PYTHON_BIN}" -m PyInstaller --version >/dev/null 2>&1; then
        echo "PyInstaller not found in environment. Falling back to native packager..."
    else
        echo "Compiling with PyInstaller..."
        "${PYTHON_BIN}" -m PyInstaller \
            --name="Aura" \
            --windowed \
            --noconfirm \
            --distpath="${DIST_DIR}" \
            --workpath="${REPO_ROOT}/build" \
            "${REPO_ROOT}/src/desktop_dom/cli/main.py"
    fi
fi

# Execute native macOS bundle packager
echo "Running native macOS application packager (build_app.py)..."
"${PYTHON_BIN}" "${SCRIPT_DIR}/build_app.py" \
    --output-dir "${DIST_DIR}" \
    --platform macos \
    --install \
    "$@"

# Verify bundle structure
echo ""
echo "Verifying installation bundle integrity at ${TARGET_APP_DIR}..."

if [ ! -d "${TARGET_APP_DIR}" ]; then
    echo "Error: Bundle directory not found at ${TARGET_APP_DIR}" >&2
    exit 1
fi

if [ ! -f "${TARGET_APP_DIR}/Contents/Info.plist" ]; then
    echo "Error: Missing Info.plist in ${TARGET_APP_DIR}/Contents" >&2
    exit 1
fi

if [ ! -x "${TARGET_APP_DIR}/Contents/MacOS/Aura" ]; then
    echo "Error: Launcher executable missing or not executable in ${TARGET_APP_DIR}/Contents/MacOS/Aura" >&2
    exit 1
fi

echo "✓ Info.plist present"
echo "✓ Launcher executable verified (chmod +x)"
if [ -f "${TARGET_APP_DIR}/Contents/Resources/AppIcon.icns" ]; then
    echo "✓ AppIcon.icns present"
fi

echo ""
echo "============================================================"
echo "✓ Aura.app successfully packaged and verified at:"
echo "  ${TARGET_APP_DIR}"
echo "============================================================"
