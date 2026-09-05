from __future__ import annotations
from typing import List, Optional, Tuple, Literal, Any, Dict
from pydantic import BaseModel, Field, computed_field

CanonicalRole = Literal[
    "button",
    "input",
    "checkbox",
    "radio",
    "combobox",
    "menuitem",
    "menu",
    "menubar",
    "tab",
    "tab_group",
    "table",
    "table_row",
    "table_cell",
    "text",
    "link",
    "image",
    "slider",
    "scrollbar",
    "window",
    "dialog",
    "group",
    "pane",
    "unknown",
]

class BoundingBox(BaseModel):
    x: int = Field(description="Top-left X coordinate in absolute desktop space (points)")
    y: int = Field(description="Top-left Y coordinate in absolute desktop space (points)")
    width: int = Field(description="Width in points/pixels")
    height: int = Field(description="Height in points/pixels")

    @computed_field
    @property
    def centroid_x(self) -> int:
        return self.x + max(0, self.width) // 2

    @computed_field
    @property
    def centroid_y(self) -> int:
        return self.y + max(0, self.height) // 2

    @property
    def centroid(self) -> Tuple[int, int]:
        return (self.centroid_x, self.centroid_y)

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)

    def contains(self, px: int, py: int) -> bool:
        return (self.x <= px <= self.x + self.width) and (self.y <= py <= self.y + self.height)

    def intersects(self, other: BoundingBox) -> bool:
        return not (
            self.x + self.width < other.x
            or other.x + other.width < self.x
            or self.y + self.height < other.y
            or other.y + other.height < self.y
        )

    def scale(self, factor: float) -> BoundingBox:
        """Scales bounds for high-DPI/Retina display coordinate calibration."""
        if factor == 1.0:
            return self
        return BoundingBox(
            x=int(round(self.x * factor)),
            y=int(round(self.y * factor)),
            width=int(round(self.width * factor)),
            height=int(round(self.height * factor)),
        )

    def to_display_local(self, display: "DisplayInfo") -> BoundingBox:
        """Converts global desktop coordinates to local coordinates relative to a specific display's origin."""
        return BoundingBox(
            x=self.x - display.bounds.x,
            y=self.y - display.bounds.y,
            width=self.width,
            height=self.height,
        )

    def find_display(self, displays: List["DisplayInfo"]) -> Optional["DisplayInfo"]:
        """Identifies which display contains this bounding box centroid."""
        cx, cy = self.centroid
        for disp in displays:
            if disp.bounds.contains(cx, cy):
                return disp
        # Fallback to primary if centroid is outside detected monitors
        for disp in displays:
            if disp.is_primary:
                return disp
        return displays[0] if displays else None

class DisplayInfo(BaseModel):
    id: int = Field(description="Display identifier or index")
    name: str = Field(default="", description="Display name or model identifier")
    is_primary: bool = Field(default=False, description="Whether this is the primary system display")
    bounds: BoundingBox = Field(description="Display bounds in global desktop coordinates (origin can be negative)")
    scale_factor: float = Field(default=1.0, description="Display backing/DPI scaling multiplier (e.g. 2.0 for Retina)")
    is_active_space: bool = Field(default=True, description="Whether display currently hosts the active virtual space")

class SubregionCapture(BaseModel):
    element_id: Optional[str] = Field(default=None, description="Element ID if captured from a DesktopNode")
    bbox: BoundingBox = Field(description="Captured bounding box in global desktop coordinates")
    image_base64: str = Field(description="Base64-encoded image data")
    mime_type: str = Field(default="image/png", description="MIME type of image (image/png or image/jpeg)")
    width: int = Field(description="Captured image width in physical pixels")
    height: int = Field(description="Captured image height in physical pixels")
    estimated_tokens: int = Field(description="Estimated multimodal vision tokens required for LLM prompt")

    def to_llm_payload(self) -> Dict[str, Any]:
        """Formats sub-region image for Claude/OpenAI multimodal message payload."""
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": self.mime_type,
                "data": self.image_base64,
            },
        }

    def save(self, filepath: str) -> None:
        """Saves binary image to local disk."""
        import base64
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(self.image_base64))

class ElementStates(BaseModel):
    focused: bool = Field(default=False, description="Whether the element currently holds keyboard focus")
    focusable: bool = Field(default=False, description="Whether the element can receive keyboard focus")
    editable: bool = Field(default=False, description="Whether text content can be directly typed or edited")
    clickable: bool = Field(default=False, description="Whether element responds to mouse clicks or taps")
    checked: Optional[bool] = Field(default=None, description="Check state for checkboxes/radios")
    disabled: bool = Field(default=False, description="Whether the control is currently disabled/greyed out")
    expanded: Optional[bool] = Field(default=None, description="Expansion state for accordions/trees/combos")
    selected: Optional[bool] = Field(default=None, description="Selection state for tabs/list items")

    @property
    def is_actionable(self) -> bool:
        return (
            not self.disabled
            and (
                self.clickable
                or self.editable
                or self.focusable
                or self.checked is not None
                or self.selected is not None
            )
        )

class DesktopNode(BaseModel):
    id: str = Field(description="Deterministic ephemeral hash for agent referencing (e.g. 'btn_save_4f2b')")
    role: str = Field(description="Normalized canonical element role")
    name: str = Field(default="", description="Accessible label, title, or tooltip")
    value: Optional[str] = Field(default=None, description="Current text content, entry value, or selected text")
    bbox: BoundingBox = Field(description="Absolute bounding box in desktop coordinates")
    states: ElementStates = Field(default_factory=ElementStates, description="Interactive and accessibility states")
    children: List[DesktopNode] = Field(default_factory=list, description="Child accessibility elements")
    raw_role: Optional[str] = Field(default=None, description="Platform native role string (e.g. AXButton)")
    depth: int = Field(default=0, description="Nesting depth relative to target application root")

    def to_token_dict(self, include_children: bool = False, max_child_depth: int = 2) -> Dict[str, Any]:
        """
        Serializes the node into a token-pruned dictionary ideal for LLM context windows.
        Strips redundant defaults, empty strings, and empty structures.
        """
        res: Dict[str, Any] = {
            "id": self.id,
            "role": self.role,
        }
        if self.name:
            res["name"] = self.name
        if self.value:
            res["value"] = self.value
        
        # Compact centroid and dimensions
        res["bbox"] = [self.bbox.x, self.bbox.y, self.bbox.width, self.bbox.height]
        
        # State flags (only non-defaults)
        active_states = {}
        if self.states.focused:
            active_states["focused"] = True
        if self.states.disabled:
            active_states["disabled"] = True
        if self.states.checked is not None:
            active_states["checked"] = self.states.checked
        if self.states.selected is not None:
            active_states["selected"] = self.states.selected
        if self.states.expanded is not None:
            active_states["expanded"] = self.states.expanded
        if active_states:
            res["states"] = active_states

        if include_children and self.children and max_child_depth > 0:
            res["children"] = [
                c.to_token_dict(include_children=True, max_child_depth=max_child_depth - 1)
                for c in self.children
            ]

        return res

    def find_by_id(self, target_id: str) -> Optional[DesktopNode]:
        """Performs recursive search for an element ID."""
        if self.id == target_id:
            return self
        for child in self.children:
            found = child.find_by_id(target_id)
            if found is not None:
                return found
        return None

    def flatten(self) -> List[DesktopNode]:
        """Flattens hierarchy into a linear list of all nodes."""
        nodes = [self]
        for child in self.children:
            nodes.extend(child.flatten())
        return nodes

    def find_all(self, role: Optional[str] = None, name: Optional[str] = None) -> List[DesktopNode]:
        """Queries all descendants matching role and/or case-insensitive name."""
        results: List[DesktopNode] = []
        name_lower = name.lower() if name else None

        def _traverse(node: DesktopNode):
            role_match = (role is None) or (node.role.lower() == role.lower())
            name_match = (name_lower is None) or (name_lower in node.name.lower())
            if role_match and name_match:
                results.append(node)
            for child in node.children:
                _traverse(child)

        _traverse(self)
        return results

    def find_element_at(self, px: int, py: int) -> Optional[DesktopNode]:
        """
        Locates the deepest actionable or leaf node containing the coordinate (px, py).
        Traverses children in reverse order to respect visual z-order.
        """
        if not self.bbox.contains(px, py):
            return None

        # Prioritize children
        for child in reversed(self.children):
            hit = child.find_element_at(px, py)
            if hit is not None:
                return hit

        return self

    def total_count(self) -> int:
        return 1 + sum(child.total_count() for child in self.children)
