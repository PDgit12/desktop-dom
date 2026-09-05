import sys
import pytest
from typer.testing import CliRunner
from desktop_dom.cli.main import app

runner = CliRunner()

def test_cli_doctor():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "desktop-dom Doctor Check" in result.output
    assert "OS Accessibility API" in result.output

def test_cli_apps():
    result = runner.invoke(app, ["apps"])
    assert result.exit_code == 0
    assert "Running Desktop Applications" in result.output

@pytest.mark.skipif(sys.platform != "darwin", reason="Requires native macOS Finder session")
def test_cli_inspect_app():
    # Inspect running Finder on macOS
    result = runner.invoke(app, ["inspect", "--app", "Finder"])
    assert result.exit_code == 0
    assert "Finder" in result.output

@pytest.mark.skipif(sys.platform != "darwin", reason="Requires native macOS Finder session")
def test_cli_inspect_json():
    result = runner.invoke(app, ["inspect", "--app", "Finder", "--format", "json"])
    assert result.exit_code == 0
@pytest.mark.skipif(sys.platform != "darwin", reason="Requires native macOS Finder session")
def test_cli_wait_for():
    result = runner.invoke(app, ["wait-for", "--app", "Finder", "--role", "window", "--timeout", "2.0"])
    assert result.exit_code == 0
    assert "Found element" in result.output

@pytest.mark.skipif(sys.platform != "darwin", reason="Requires native macOS Finder session")
def test_cli_snapshot(tmp_path):
    out_file = str(tmp_path / "snap.html")
    result = runner.invoke(app, ["snapshot", "--app", "Finder", "--out", out_file])
    assert result.exit_code == 0
    assert "Generated visual HUD snapshot" in result.output
    with open(out_file, "r") as f:
        content = f.read()
    assert "<!DOCTYPE html>" in content
    assert "svg" in content

def test_cli_doctor_fix():
    result = runner.invoke(app, ["doctor", "--help"])
    assert result.exit_code == 0
    assert "--fix" in result.output

def test_cli_install_mcp(tmp_path, monkeypatch):
    mock_home = tmp_path / "userhome"
    mock_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: mock_home)
    result = runner.invoke(app, ["install-mcp", "--client", "claude"])
    assert result.exit_code == 0
    assert "Successfully configured desktop-dom MCP" in result.output
