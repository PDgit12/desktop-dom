import os
import plistlib
import subprocess
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
BUILD_SH = SCRIPTS_DIR / "build_app.sh"
BUILD_PY = SCRIPTS_DIR / "build_app.py"
INSTALLED_APP = Path.home() / "Applications" / "Aura.app"


def test_build_app_sh_exists_and_executable():
    """Verify scripts/build_app.sh exists, is executable, and has valid bash syntax."""
    assert BUILD_SH.exists(), "scripts/build_app.sh does not exist"
    assert os.access(BUILD_SH, os.X_OK), "scripts/build_app.sh is not executable"
    
    # Validate bash syntax
    res = subprocess.run(["bash", "-n", str(BUILD_SH)], capture_output=True, text=True)
    assert res.returncode == 0, f"bash -n failed: {res.stderr}"


def test_build_app_py_exists():
    """Verify scripts/build_app.py exists and is executable."""
    assert BUILD_PY.exists(), "scripts/build_app.py does not exist"
    assert os.access(BUILD_PY, os.X_OK), "scripts/build_app.py is not executable"


def test_installed_aura_app_bundle_structure():
    """Verify the installed native macOS bundle at ~/Applications/Aura.app is structurally valid."""
    assert INSTALLED_APP.exists(), f"Installed bundle not found at {INSTALLED_APP}"
    assert INSTALLED_APP.is_dir()
    
    contents_dir = INSTALLED_APP / "Contents"
    assert contents_dir.exists()
    
    # 1. Info.plist verification
    plist_file = contents_dir / "Info.plist"
    assert plist_file.exists()
    with open(plist_file, "rb") as f:
        plist_data = plistlib.load(f)
    
    assert plist_data.get("CFBundleExecutable") == "Aura"
    assert plist_data.get("CFBundleIdentifier") == "com.pdgit12.desktopdom.aura"
    assert plist_data.get("CFBundleName") == "Aura"
    assert plist_data.get("LSUIElement") is True
    assert plist_data.get("NSHighResolutionCapable") is True
    
    # 2. Executable launcher verification
    launcher = contents_dir / "MacOS" / "Aura"
    assert launcher.exists()
    assert os.access(launcher, os.X_OK)
    
    # 3. Resources verification
    resources_dir = contents_dir / "Resources"
    assert resources_dir.exists()
    assert (resources_dir / "AppIcon.icns").exists()
    assert (resources_dir / "AppIcon.icns").stat().st_size > 1000
    
    # 4. Bundled source verification
    assert (resources_dir / "src" / "desktop_dom").exists()


def test_build_app_sh_execution_help():
    """Verify scripts/build_app.sh responds to --help cleanly."""
    res = subprocess.run([str(BUILD_SH), "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "Aura" in res.stdout or "help" in res.stdout.lower()
