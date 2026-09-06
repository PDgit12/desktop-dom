#!/usr/bin/env python3
"""
Native Linux Packager for Aura & desktop-dom.
Generates Debian package structure (.deb), desktop entry, AppRun spec for AppImage, and release tarball.
"""
from __future__ import annotations
import os
import sys
import shutil
import tarfile
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw

VERSION = "0.2.0"
APP_NAME = "aura"

def generate_linux_icon(output_path: Path):
    """Generates a high-resolution 512x512 Linux PNG icon."""
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, 511, 511], radius=100, fill=(13, 17, 23, 255), outline=(56, 189, 248, 255), width=16)
    cx, cy = 256, 256
    pts = [
        (cx + 25, cy - 180),
        (cx - 130, cy + 25),
        (cx - 25, cy + 25),
        (cx - 50, cy + 195),
        (cx + 130, cy - 25),
        (cx + 25, cy - 25),
    ]
    draw.polygon(pts, fill=(56, 189, 248, 255))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    print(f"✓ Generated Linux icon: {output_path}")

def build_linux_package(output_dir: Path) -> Path:
    """Assembles Linux Debian package (.deb) and portable tarball."""
    output_dir.mkdir(parents=True, exist_ok=True)
    pkg_root = output_dir / f"{APP_NAME}_{VERSION}_amd64"
    if pkg_root.exists():
        shutil.rmtree(pkg_root)

    # 1. Directory Structure
    debian_dir = pkg_root / "DEBIAN"
    bin_dir = pkg_root / "usr" / "bin"
    app_dir = pkg_root / "usr" / "share" / "applications"
    icon_dir = pkg_root / "usr" / "share" / "icons" / "hicolor" / "512x512" / "apps"
    
    for d in [debian_dir, bin_dir, app_dir, icon_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 2. DEBIAN/control
    control_content = f"""Package: {APP_NAME}
Version: {VERSION}
Section: utils
Priority: optional
Architecture: amd64
Maintainer: PDgit12 <piyushdua01@gmail.com>
Depends: python3 (>= 3.9), python3-pip, libatspi2-0
Description: Personal Desktop Assistant & Native Automation Substrate
 Aura is an autonomous, on-device desktop assistant powered by desktop-dom.
 Executes sub-50ms actions via native accessibility trees (AT-SPI2 / D-Bus).
"""
    (debian_dir / "control").write_text(control_content, encoding="utf-8")

    # 3. /usr/bin/aura Launcher
    launcher_content = """#!/bin/bash
exec python3 -m desktop_dom assistant "$@"
"""
    launcher_path = bin_dir / "aura"
    launcher_path.write_text(launcher_content, encoding="utf-8")
    launcher_path.chmod(0o755)

    # 4. /usr/share/applications/aura.desktop
    desktop_content = f"""[Desktop Entry]
Name=Aura
Comment=Personal Desktop Assistant & Native Automation Engine
Exec=/usr/bin/aura
Icon=aura
Terminal=false
Type=Application
Categories=Utility;System;Development;
Keywords=Assistant;Automation;Desktop;AI;
"""
    (app_dir / "aura.desktop").write_text(desktop_content, encoding="utf-8")

    # 5. Icon
    generate_linux_icon(icon_dir / "aura.png")

    # 6. AppRun for AppImage
    apprun_content = """#!/bin/sh
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:${PATH}"
exec "${HERE}/usr/bin/aura" "$@"
"""
    apprun_path = pkg_root / "AppRun"
    apprun_path.write_text(apprun_content, encoding="utf-8")
    apprun_path.chmod(0o755)

    # 7. Compile .deb if dpkg-deb exists, else tar.gz
    deb_path = output_dir / f"{APP_NAME}_{VERSION}_amd64.deb"
    if shutil.which("dpkg-deb"):
        subprocess.run(["dpkg-deb", "--build", str(pkg_root), str(deb_path)], check=True)
        print(f"✓ Built Debian package: {deb_path}")
    
    # Also create portable tar.gz
    tar_path = output_dir / f"Aura-v{VERSION}-Linux-x86_64.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(pkg_root, arcname=f"aura-{VERSION}")
    print(f"✓ Created Linux release tarball: {tar_path} ({tar_path.stat().st_size // 1024} KB)")

    return tar_path

if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent.parent / "dist"
    build_linux_package(out_dir)
