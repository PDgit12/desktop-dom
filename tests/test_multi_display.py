import pytest
from typer.testing import CliRunner
from desktop_dom.schema import BoundingBox, DisplayInfo
from desktop_dom.app import DesktopApp
from desktop_dom.cli.main import app

runner = CliRunner()

def test_display_info_model():
    disp = DisplayInfo(
        id=0,
        name="Main Display",
        is_primary=True,
        bounds=BoundingBox(x=0, y=0, width=1920, height=1080),
        scale_factor=1.0,
        is_active_space=True,
    )
    assert disp.is_primary is True
    assert disp.bounds.centroid == (960, 540)

def test_negative_coordinate_display_calibration():
    # Multi-monitor setup: primary (0,0) and secondary to the left (-1920, 0)
    primary = DisplayInfo(
        id=0,
        name="Primary",
        is_primary=True,
        bounds=BoundingBox(x=0, y=0, width=1920, height=1080),
        scale_factor=2.0,
    )
    secondary = DisplayInfo(
        id=1,
        name="Secondary Left",
        is_primary=False,
        bounds=BoundingBox(x=-1920, y=0, width=1920, height=1080),
        scale_factor=1.0,
    )
    displays = [primary, secondary]

    # Element situated on secondary monitor at x=-500, y=200
    elem_box = BoundingBox(x=-500, y=200, width=100, height=50)
    matched_disp = elem_box.find_display(displays)
    assert matched_disp is not None
    assert matched_disp.id == 1
    assert matched_disp.name == "Secondary Left"

    # Convert to display-local coordinates relative to secondary monitor top-left
    local_box = elem_box.to_display_local(matched_disp)
    assert local_box.x == -500 - (-1920) # 1420
    assert local_box.y == 200 - 0 # 200

def test_app_get_displays_and_space(test_adapter):
    app_instance = DesktopApp.attach("Calculator", adapter=test_adapter)
    displays = app_instance.get_displays()
    assert len(displays) == 2
    assert displays[0].is_primary is True
    assert displays[1].bounds.x == -1920

    is_active = app_instance.is_on_active_space()
    assert is_active is True

def test_cli_displays_and_spaces(test_adapter, monkeypatch):
    monkeypatch.setattr("desktop_dom.cli.main.get_platform_adapter", lambda: test_adapter)
    
    result_disp = runner.invoke(app, ["displays"])
    assert result_disp.exit_code == 0
    assert "Built-in Retina" in result_disp.output
    assert "External 4K" in result_disp.output

    result_spaces = runner.invoke(app, ["spaces", "--app", "Calculator"])
    assert result_spaces.exit_code == 0
    assert "visible on the current active virtual space" in result_spaces.output
