import pytest
from desktop_dom.adapters.base import BasePlatformAdapter
from desktop_dom.schema import DesktopNode, BoundingBox, ElementStates

class TestPlatformAdapter(BasePlatformAdapter):
    """
    Test fixture adapter used strictly within automated unit test suites.
    """
    __test__ = False


    def __init__(self, custom_tree: DesktopNode | None = None):
        self.dispatched_clicks = []
        self.dispatched_types = []
        self.dispatched_keys = []
        self._tree = custom_tree or self._build_default_tree()

    def _build_default_tree(self) -> DesktopNode:
        return DesktopNode(
            id="test_app_root",
            role="window",
            name="Calculator",
            bbox=BoundingBox(x=100, y=100, width=320, height=480),
            states=ElementStates(focusable=True),
            children=[
                DesktopNode(
                    id="test_display_grp",
                    role="group",
                    name="Display Group",
                    bbox=BoundingBox(x=100, y=140, width=320, height=80),
                    children=[
                        DesktopNode(
                            id="test_display_txt",
                            role="text",
                            name="Display Result",
                            value="0",
                            bbox=BoundingBox(x=120, y=160, width=280, height=40),
                            states=ElementStates(focusable=False),
                        )
                    ],
                ),
                DesktopNode(
                    id="test_keypad_grp",
                    role="group",
                    name="Keypad",
                    bbox=BoundingBox(x=100, y=220, width=320, height=360),
                    children=[
                        DesktopNode(
                            id="btn_clear",
                            role="button",
                            name="Clear",
                            bbox=BoundingBox(x=110, y=230, width=70, height=60),
                            states=ElementStates(clickable=True, focusable=True),
                        ),
                        DesktopNode(
                            id="btn_div",
                            role="button",
                            name="Divide",
                            bbox=BoundingBox(x=190, y=230, width=70, height=60),
                            states=ElementStates(clickable=True, focusable=True),
                        ),
                        DesktopNode(
                            id="btn_7",
                            role="button",
                            name="7",
                            bbox=BoundingBox(x=110, y=300, width=70, height=60),
                            states=ElementStates(clickable=True, focusable=True),
                        ),
                        DesktopNode(
                            id="btn_8",
                            role="button",
                            name="8",
                            bbox=BoundingBox(x=190, y=300, width=70, height=60),
                            states=ElementStates(clickable=True, focusable=True),
                        ),
                        DesktopNode(
                            id="input_field",
                            role="input",
                            name="Formula Bar",
                            value="7 + 8",
                            bbox=BoundingBox(x=110, y=370, width=200, height=30),
                            states=ElementStates(editable=True, focusable=True),
                        ),
                        DesktopNode(
                            id="spacer_0",
                            role="group",
                            name="",
                            bbox=BoundingBox(x=0, y=0, width=0, height=0),
                        ),
                    ],
                ),
            ],
        )

    def check_permissions(self):
        return {"platform": "test", "accessibility_trusted": True, "message": "Test fixture trusted."}

    def list_applications(self):
        return [
            {"pid": 48102, "name": "Calculator", "bundle_id": "com.apple.calculator", "is_active": True},
        ]

    def get_display_scale_factor(self):
        return 2.0

    def get_root_window(self, app_identifier):
        return self._tree

    def get_active_window(self):
        return self._tree

    def click(self, node, button="left"):
        cx, cy = node.bbox.centroid
        self.click_coords(cx, cy, button=button)
        self.dispatched_clicks[-1]["target_id"] = node.id
        self.dispatched_clicks[-1]["target_name"] = node.name

    def click_coords(self, x, y, button="left"):
        self.dispatched_clicks.append({"x": x, "y": y, "button": button})

    def type_text(self, node, text, clear_first=False):
        if node:
            self.click(node)
        self.dispatched_types.append({
            "target_id": node.id if node else None,
            "text": text,
            "clear_first": clear_first,
        })

    def press_key(self, key_combination):
        self.dispatched_keys.append(key_combination)

@pytest.fixture
def test_adapter():
    return TestPlatformAdapter()
