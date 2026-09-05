#!/usr/bin/env bash
set -e

# ==============================================================================
# desktop-dom: One-Line Zero-Friction Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/PDgit12/desktop-dom/main/install.sh | bash
# ==============================================================================

BOLD='\033[1m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BOLD}${CYAN}=== Installing desktop-dom ===${NC}"
echo -e "${CYAN}Playwright for Desktop: Semantic Accessibility DOM and Deterministic Action Engine${NC}\n"

# 1. Check Python installation
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}Error: python3 is not installed. Please install Python 3.10 or newer.${NC}"
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
    echo -e "${RED}Error: Python >= 3.10 required (found Python $PY_VERSION).${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Found Python $PY_VERSION${NC}"

# 2. Detect OS and select package target
OS="$(uname -s)"
EXTRA="all"
case "${OS}" in
    Darwin*)
        EXTRA="macos"
        echo -e "${GREEN}✓ Detected platform: macOS (Apple Quartz & AXUIElement)${NC}"
        ;;
    Linux*)
        EXTRA="linux"
        echo -e "${GREEN}✓ Detected platform: Linux (AT-SPI2 D-Bus)${NC}"
        ;;
    CYGWIN*|MINGW*|MSYS*)
        EXTRA="windows"
        echo -e "${GREEN}✓ Detected platform: Windows (CUIAutomation8 COM)${NC}"
        ;;
    *)
        EXTRA="all"
        echo -e "${YELLOW}! Unknown OS, installing standard bundle${NC}"
        ;;
esac

# 3. Install desktop-dom via pip
echo -e "\n${BOLD}Installing desktop-dom[${EXTRA}] via pip...${NC}"
python3 -m pip install --upgrade "desktop-dom[${EXTRA}]" 2>/dev/null || python3 -m pip install --upgrade ."[${EXTRA}]"

# 4. Verify installation & permissions
echo -e "\n${BOLD}Running doctor check...${NC}"
if command -v desktop-dom &>/dev/null; then
    desktop-dom doctor || {
        echo -e "${YELLOW}Accessibility permissions need to be enabled.${NC}"
        echo -e "Run ${BOLD}desktop-dom doctor --fix${NC} to automatically open OS settings."
    }
else
    echo -e "${YELLOW}Notice: desktop-dom CLI installed into user binary path. Ensure ~/.local/bin is in your PATH.${NC}"
fi

# 5. Offer 1-click MCP setup for Claude Desktop / Cursor
echo -e "\n${BOLD}${GREEN}✓ desktop-dom installed successfully!${NC}"
echo -e "Quickstart commands:"
echo -e "  ${CYAN}desktop-dom doctor --fix${NC}       Verify or grant OS accessibility permissions"
echo -e "  ${CYAN}desktop-dom apps${NC}               List running desktop apps"
echo -e "  ${CYAN}desktop-dom inspect --app Finder${NC} Inspect semantic accessibility tree"
echo -e "  ${CYAN}desktop-dom install-mcp${NC}        Auto-wire into Claude Desktop or Cursor"
echo -e ""
