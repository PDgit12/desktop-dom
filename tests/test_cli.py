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
    assert '"role": "window"' in result.output

