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

def test_cli_doctor_hermetic(test_adapter, monkeypatch):
    monkeypatch.setattr("desktop_dom.cli.main.get_platform_adapter", lambda: test_adapter)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "TestPlatformAdapter" in result.output
    assert "PASSED" in result.output

def test_cli_apps():
    result = runner.invoke(app, ["apps"])
    assert result.exit_code == 0
    assert "Running Desktop Applications" in result.output

def test_cli_apps_hermetic(test_adapter, monkeypatch):
    monkeypatch.setattr("desktop_dom.cli.main.get_platform_adapter", lambda: test_adapter)
    result = runner.invoke(app, ["apps"])
    assert result.exit_code == 0
    assert "Calculator" in result.output
    assert "48102" in result.output


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

def test_mcp_server_request_handling(test_adapter):
    from desktop_dom.integrations.mcp import DesktopDomMCPServer
    from desktop_dom.app import DesktopApp
    server = DesktopDomMCPServer.__new__(DesktopDomMCPServer)
    server.target_app = "Calculator"
    server.app = DesktopApp.attach("Calculator", adapter=test_adapter)

    # 1. initialize
    init_res = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert init_res["result"]["serverInfo"]["name"] == "desktop-dom-mcp"

    # 2. tools/list
    tools_res = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert len(tools_res["result"]["tools"]) == 4

    # 3. tools/call desktop_get_screen_dom
    call_res = server.handle_request({
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "desktop_get_screen_dom", "arguments": {}}
    })
    assert call_res["result"]["content"][0]["type"] == "text"

    # 4. tools/call desktop_click_element
    click_res = server.handle_request({
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "desktop_click_element", "arguments": {"element_id": "btn_clear"}}
    })
    assert click_res["result"]["content"][0]["type"] == "text"
    assert "success" in click_res["result"]["content"][0]["text"]

    # 5. tools/call desktop_type_text
    type_res = server.handle_request({
        "jsonrpc": "2.0", "id": 5, "method": "tools/call",
        "params": {"name": "desktop_type_text", "arguments": {"text": "42"}}
    })
    assert type_res["result"]["content"][0]["type"] == "text"
    assert "42" in type_res["result"]["content"][0]["text"]


    # 6. tools/call desktop_press_key
    press_res = server.handle_request({
        "jsonrpc": "2.0", "id": 6, "method": "tools/call",
        "params": {"name": "desktop_press_key", "arguments": {"key_combination": "enter"}}
    })
    assert press_res["result"]["content"][0]["type"] == "text"

    # 7. unknown method error response
    unknown_res = server.handle_request({"jsonrpc": "2.0", "id": 7, "method": "unknown/method"})
    assert "error" in unknown_res


