#!/usr/bin/env python3
"""
Native Windows Packager for Aura & desktop-dom.
Generates a standalone portable bundle, multi-resolution .ico, WiX .msi installer spec, and release ZIP.
"""
from __future__ import annotations
import os
import sys
import shutil
import zipfile
from pathlib import Path
from PIL import Image, ImageDraw

VERSION = "0.2.0"
APP_NAME = "Aura"

def generate_windows_icon(output_path: Path):
    """Generates a high-resolution multi-size Windows icon (.ico)."""
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    images = []
    for w, h in sizes:
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        rad = max(2, w // 5)
        draw.rounded_rectangle([0, 0, w - 1, h - 1], radius=rad, fill=(13, 17, 23, 255), outline=(56, 189, 248, 255), width=max(1, w // 32))
        cx, cy = w // 2, h // 2
        pts = [
            (cx + int(w * 0.05), cy - int(h * 0.35)),
            (cx - int(w * 0.25), cy + int(h * 0.05)),
            (cx - int(w * 0.05), cy + int(h * 0.05)),
            (cx - int(w * 0.1), cy + int(h * 0.38)),
            (cx + int(w * 0.25), cy - int(h * 0.05)),
            (cx + int(w * 0.05), cy - int(h * 0.05)),
        ]
        draw.polygon(pts, fill=(56, 189, 248, 255))
        images.append(img)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    images[-1].save(output_path, format="ICO", sizes=[(im.width, im.height) for im in images])
    print(f"✓ Generated Windows icon: {output_path}")

def generate_wix_installer_spec(output_path: Path):
    """Generates WiX Toolset XML specification for compiling an enterprise .msi installer."""
    wxs_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Wix xmlns="http://schemas.microsoft.com/wix/2006/wi">
    <Product Id="*" 
             Name="{APP_NAME} Personal Desktop Assistant" 
             Language="1033" 
             Version="{VERSION}.0" 
             Manufacturer="PDgit12" 
             UpgradeCode="9C8E7366-66C6-4F1C-B001-61BE7BCAA9DF">
        
        <Package InstallerVersion="500" Compressed="yes" InstallScope="perUser" />
        <MajorUpgrade DowngradeErrorMessage="A newer version of {APP_NAME} is already installed." />
        <MediaTemplate EmbedCab="yes" />

        <Directory Id="TARGETDIR" Name="SourceDir">
            <Directory Id="LocalAppDataFolder">
                <Directory Id="INSTALLFOLDER" Name="{APP_NAME}">
                    <Component Id="MainExecutable" Guid="A1B2C3D4-E5F6-7890-1234-567890ABCDEF">
                        <File Id="AuraBat" Source="Aura.bat" KeyPath="yes" />
                        <File Id="AuraVbs" Source="Aura.vbs" />
                        <File Id="AuraIcon" Source="aura.ico" />
                    </Component>
                </Directory>
            </Directory>
            <Directory Id="ProgramMenuFolder">
                <Component Id="ApplicationShortcut" Guid="B2C3D4E5-F6A1-8901-2345-678901BCDEFG">
                    <Shortcut Id="ApplicationStartMenuShortcut" 
                              Name="{APP_NAME}" 
                              Description="{APP_NAME} Desktop Assistant"
                              Target="[INSTALLFOLDER]Aura.vbs"
                              Icon="AuraIcon.ico"
                              WorkingDirectory="INSTALLFOLDER" />
                    <RemoveFolder Id="CleanUpShortCut" Directory="ProgramMenuFolder" On="uninstall" />
                    <RegistryValue Root="HKCU" Key="Software\\PDgit12\\{APP_NAME}" Name="installed" Type="integer" Value="1" KeyPath="yes" />
                </Component>
            </Directory>
        </Directory>

        <Icon Id="AuraIcon.ico" SourceFile="aura.ico" />
        <Property Id="ARPPRODUCTICON" Value="AuraIcon.ico" />

        <Feature Id="ProductFeature" Title="{APP_NAME}" Level="1">
            <ComponentRef Id="MainExecutable" />
            <ComponentRef Id="ApplicationShortcut" />
        </Feature>
    </Product>
</Wix>
"""
    output_path.write_text(wxs_content, encoding="utf-8")
    print(f"✓ Generated WiX .msi installer spec: {output_path}")

def build_windows_package(output_dir: Path) -> Path:
    """Assembles the full Windows distribution package."""
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle_dir = output_dir / f"{APP_NAME}-Windows"
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True)

    ico_path = bundle_dir / "aura.ico"
    generate_windows_icon(ico_path)

    bat_content = "@echo off\r\ntitle Aura Assistant\r\npython -m desktop_dom assistant %*\r\n"
    (bundle_dir / "Aura.bat").write_text(bat_content, encoding="utf-8")

    vbs_content = "CreateObject(\"Wscript.Shell\").Run \"Aura.bat\", 0, True\r\n"
    (bundle_dir / "Aura.vbs").write_text(vbs_content, encoding="utf-8")

    generate_wix_installer_spec(bundle_dir / "AuraInstaller.wxs")

    readme_content = f"""# {APP_NAME} v{VERSION} for Windows
Personal Desktop Assistant & Native Automation Engine.

## Quick Start
- Double-click `Aura.bat` or `Aura.vbs` to launch.
- Or run via terminal: `python -m desktop_dom assistant`
- To compile into an MSI installer, run: `candle AuraInstaller.wxs` and `light AuraInstaller.wixobj`
"""
    (bundle_dir / "README.txt").write_text(readme_content, encoding="utf-8")

    zip_path = output_dir / f"{APP_NAME}-v{VERSION}-Windows.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(bundle_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(output_dir)
                zf.write(file_path, arcname)

    print(f"✓ Created Windows ZIP archive: {zip_path} ({zip_path.stat().st_size // 1024} KB)")
    return zip_path

if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent.parent / "dist"
    build_windows_package(out_dir)
