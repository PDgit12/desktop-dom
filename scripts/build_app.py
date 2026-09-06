#!/usr/bin/env python3
"""
Aura Native macOS Application Bundle & DMG Packager
Builds a standalone Aura.app bundle with native AppIcon.icns, Info.plist,
launcher executable, and optional DMG disk image installer.
"""

from __future__ import annotations
import os
import sys
import shutil
import argparse
import subprocess
import tempfile
from pathlib import Path

def generate_app_icon(output_icns_path: Path) -> None:
    """Generates a high-resolution dark glassmorphic AppIcon.icns using PIL and iconutil."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Warning: PIL (Pillow) not installed; skipping custom icon generation.")
        return

    img = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Dark obsidian squircle base with cyan accent rim
    draw.rounded_rectangle(
        [48, 48, 976, 976],
        radius=220,
        fill=(12, 14, 24, 255),
        outline=(0, 240, 255, 230),
        width=16,
    )

    # 2. Glowing outer and inner aura circles
    draw.ellipse([290, 290, 734, 734], fill=(16, 20, 36, 255), outline=(112, 0, 255, 255), width=20)
    draw.ellipse([340, 340, 684, 684], fill=(0, 240, 255, 175), outline=(255, 0, 127, 210), width=10)

    # 3. Electric lightning glyph in pure white
    lightning_poly = [
        (535, 255),
        (405, 515),
        (495, 515),
        (450, 765),
        (625, 475),
        (535, 475),
        (585, 255),
    ]
    draw.polygon(lightning_poly, fill=(255, 255, 255, 255))

    with tempfile.TemporaryDirectory() as tmpdir:
        iconset = Path(tmpdir) / "AppIcon.iconset"
        iconset.mkdir(parents=True, exist_ok=True)
        
        sizes = [(16, 1), (16, 2), (32, 1), (32, 2), (128, 1), (128, 2), (256, 1), (256, 2), (512, 1), (512, 2)]
        for size, scale in sizes:
            px = size * scale
            name = f"icon_{size}x{size}@2x.png" if scale == 2 else f"icon_{size}x{size}.png"
            resized = img.resize((px, px), Image.Resampling.LANCZOS)
            resized.save(iconset / name)

        if shutil.which("iconutil"):
            subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(output_icns_path)], check=True)
            print(f"✓ Compiled native AppIcon.icns ({output_icns_path.stat().st_size // 1024} KB)")

def build_app_bundle(
    output_dir: Path,
    version: str = "0.2.0",
    install: bool = False,
    create_dmg: bool = False,
    create_zip: bool = False,
) -> Path:
    """Builds the native macOS Aura.app bundle."""
    app_dir = output_dir / "Aura.app"
    contents_dir = app_dir / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"

    if app_dir.exists():
        shutil.rmtree(app_dir)

    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate Info.plist
    info_plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>Aura</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.pdgit12.desktopdom.aura</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>Aura</string>
    <key>CFBundleDisplayName</key>
    <string>Aura Desktop Assistant</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>{version}</string>
    <key>CFBundleVersion</key>
    <string>{version}</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSRequiresAquaSystemAppearance</key>
    <false/>
    <key>NSMicrophoneUsageDescription</key>
    <string>Aura requires microphone access for local voice recognition.</string>
    <key>NSSpeechRecognitionUsageDescription</key>
    <string>Aura requires speech recognition to transcribe voice queries locally.</string>
    <key>NSAccessibilityUsageDescription</key>
    <string>Aura uses Accessibility APIs to inspect and interact with desktop applications.</string>
</dict>
</plist>
"""
    with open(contents_dir / "Info.plist", "w", encoding="utf-8") as f:
        f.write(info_plist)

    # 2. Generate AppIcon.icns
    generate_app_icon(resources_dir / "AppIcon.icns")

    # 3. Generate Executable Launcher
    repo_root = Path(__file__).resolve().parent.parent
    launcher_script = f"""#!/bin/bash
set -e

DIR="$( cd "$( dirname "${{BASH_SOURCE[0]}}" )" && pwd )"

# Check if desktop-dom CLI is directly in PATH
if command -v desktop-dom >/dev/null 2>&1; then
    exec desktop-dom assistant "$@"
fi

# Detect Python 3 runtime
PYTHON=""
CANDIDATES=(
    "{sys.executable}"
    "/opt/anaconda3/bin/python3"
    "/usr/local/bin/python3"
    "/opt/homebrew/bin/python3"
    "$HOME/.pyenv/shims/python3"
    "/usr/bin/python3"
)

for p in "${{CANDIDATES[@]}}"; do
    if [ -x "$p" ]; then
        PYTHON="$p"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    osascript -e 'display alert "Python 3 Not Found" message "Aura requires Python 3 to run. Please install Python 3 or desktop-dom via pip."'
    exit 1
fi

export PYTHONPATH="{repo_root / 'src'}:$PYTHONPATH"
exec "$PYTHON" -m desktop_dom.cli.main assistant "$@"
"""
    launcher_path = macos_dir / "Aura"
    with open(launcher_path, "w", encoding="utf-8") as f:
        f.write(launcher_script)
    launcher_path.chmod(0o755)

    print(f"✓ Successfully built macOS Application Bundle: {app_dir}")

    # 4. Optional Install to ~/Applications or /Applications
    if install:
        user_apps = Path.home() / "Applications"
        user_apps.mkdir(parents=True, exist_ok=True)
        target_install = user_apps / "Aura.app"
        if target_install.exists():
            shutil.rmtree(target_install)
        shutil.copytree(app_dir, target_install)
        print(f"✓ Installed Aura.app to {target_install}")

    # 5. Optional ZIP archive
    if create_zip:
        zip_path = output_dir / f"Aura-v{version}-macOS.zip"
        if zip_path.exists():
            zip_path.unlink()
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(app_dir), str(zip_path)], check=True)
        print(f"✓ Created ZIP distribution: {zip_path} ({zip_path.stat().st_size // 1024} KB)")

    # 6. Optional DMG installer
    if create_dmg and shutil.which("hdiutil"):
        dmg_path = output_dir / f"Aura-v{version}-macOS.dmg"
        if dmg_path.exists():
            dmg_path.unlink()
        with tempfile.TemporaryDirectory() as dmg_staging:
            staging_path = Path(dmg_staging)
            shutil.copytree(app_dir, staging_path / "Aura.app")
            # Symlink to /Applications for drag & drop install
            os.symlink("/Applications", staging_path / "Applications")
            subprocess.run([
                "hdiutil", "create",
                "-volname", "Aura Installer",
                "-srcfolder", str(staging_path),
                "-ov",
                "-format", "UDZO",
                str(dmg_path)
            ], check=True, stdout=subprocess.DEVNULL)
        print(f"✓ Created DMG drag-and-drop installer: {dmg_path} ({dmg_path.stat().st_size // 1024} KB)")

    return app_dir

def main():
    parser = argparse.ArgumentParser(description="Build and package native Aura macOS application bundle.")
    parser.add_argument("--output-dir", "-o", default="./dist", help="Output directory for built artifacts")
    parser.add_argument("--version", "-v", default="0.2.0", help="Application version string")
    parser.add_argument("--install", "-i", action="store_true", help="Install to ~/Applications/Aura.app")
    parser.add_argument("--dmg", "-d", action="store_true", help="Build drag-and-drop .dmg installer")
    parser.add_argument("--zip", "-z", action="store_true", help="Build compressed .zip archive")
    args = parser.parse_args()

    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    build_app_bundle(
        output_dir=out,
        version=args.version,
        install=args.install,
        create_dmg=args.dmg,
        create_zip=args.zip,
    )

if __name__ == "__main__":
    main()
