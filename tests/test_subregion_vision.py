import pytest
from typer.testing import CliRunner
from desktop_dom.schema import BoundingBox, SubregionCapture, DesktopNode, ElementStates
from desktop_dom.app import DesktopApp
from desktop_dom.cli.main import app

runner = CliRunner()

def test_subregion_capture_model(tmp_path):
    box = BoundingBox(x=50, y=50, width=200, height=100)
    capture = SubregionCapture(
        element_id="canvas_01",
        bbox=box,
        image_base64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
        mime_type="image/png",
        width=400,
        height=200,
        estimated_tokens=106,
    )
    assert capture.estimated_tokens == 106
    payload = capture.to_llm_payload()
    assert payload["type"] == "image"
    assert payload["source"]["data"] == capture.image_base64

    # Test file saving
    save_path = str(tmp_path / "saved.png")
    capture.save(save_path)
    with open(save_path, "rb") as f:
        data = f.read()
    assert len(data) > 0

def test_app_crop_element_and_region(test_adapter):
    app_instance = DesktopApp.attach("Calculator", adapter=test_adapter)
    # Crop known element
    capture = app_instance.crop_element("btn_7")
    assert "btn_7" in capture.element_id
    assert capture.width == int(70 * 2.0)
    assert capture.height == int(60 * 2.0)
    assert capture.estimated_tokens > 0

    # Crop custom region
    box = BoundingBox(x=0, y=0, width=150, height=80)
    reg_capture = app_instance.crop_region(box)
    assert reg_capture.bbox.width == 150
    assert reg_capture.width == 300

def test_hybrid_resolution_fallback(test_adapter):
    # Create tree with an opaque canvas element
    canvas_node = DesktopNode(
        id="gl_canvas_node",
        role="image",
        name="Chart Canvas",
        bbox=BoundingBox(x=100, y=100, width=300, height=200),
        states=ElementStates(),
        children=[],
    )
    test_adapter._tree.children.append(canvas_node)
    app_instance = DesktopApp.attach("Calculator", adapter=test_adapter)

    # 1. Finding normal interactive button should return (node, None)
    node, sub = app_instance.find_or_fallback(role="button", name="7")
    assert node is not None
    assert sub is None

    # 2. Finding opaque canvas should trigger hybrid fallback returning (node, subregion)
    node_canvas, sub_canvas = app_instance.find_or_fallback(role="image", name="Chart Canvas")
    assert node_canvas is not None
    assert sub_canvas is not None
    assert "chart_canvas" in sub_canvas.element_id

    # 3. Missing element with fallback_to_vision should return (None, root_subregion)
    missing_node, root_sub = app_instance.find_or_fallback(name="NonExistentWidget", fallback_to_vision=True)
    assert missing_node is None
    assert root_sub is not None
    assert root_sub.bbox == test_adapter._tree.bbox

def test_cli_crop(test_adapter, tmp_path, monkeypatch):
    monkeypatch.setattr("desktop_dom.cli.main.get_platform_adapter", lambda: test_adapter)
    out_file = str(tmp_path / "cropped_btn.png")
    
    result = runner.invoke(app, ["crop", "--app", "Calculator", "--id", "btn_7", "--out", out_file])
    assert result.exit_code == 0
    assert "Saved subregion image to" in result.output
    assert "Estimated Vision LLM Tokens" in result.output
