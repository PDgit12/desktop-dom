from __future__ import annotations
from typing import TYPE_CHECKING, List, Dict, Any, Optional, Callable
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from desktop_dom.app import DesktopApp

class ClickInput(BaseModel):
    element_id: str = Field(description="Deterministic element ID returned from get_screen_dom (e.g. 'btn_save_4f2b')")
    button: str = Field(default="left", description="'left', 'right', or 'double'")

class TypeInput(BaseModel):
    text: str = Field(description="The string text to type into the element or active focus")
    element_id: Optional[str] = Field(default=None, description="Target element ID (optional; clicks before typing if provided)")
    clear_first: bool = Field(default=False, description="Whether to clear existing text with select-all + backspace before typing")

class KeyInput(BaseModel):
    key_combination: str = Field(description="Hotkey or modifier chord (e.g. 'cmd+s', 'ctrl+c', 'return', 'tab', 'escape')")

class GetDOMInput(BaseModel):
    max_depth: int = Field(default=8, description="Maximum tree traversal depth")

def create_desktop_tools(app: DesktopApp) -> List[Any]:
    """
    Constructs tools compatible with LangChain / LangGraph, OpenAI tool schemas, or custom agent loops.
    """
    try:
        from langchain_core.tools import StructuredTool

        tools = [
            StructuredTool.from_function(
                func=lambda max_depth=8: app.get_tree(max_depth=max_depth, as_dict=True),
                name="desktop_get_screen_dom",
                description="Retrieves the current native desktop accessibility tree pruned to actionable elements in JSON format.",
                args_schema=GetDOMInput,
            ),
            StructuredTool.from_function(
                func=lambda element_id, button="left": app.click(element_id=element_id, button=button),
                name="desktop_click_element",
                description="Dispatches a deterministic hardware click to the exact centroid of a desktop element by ID.",
                args_schema=ClickInput,
            ),
            StructuredTool.from_function(
                func=lambda text, element_id=None, clear_first=False: app.type(element_id=element_id, text=text, clear_first=clear_first),
                name="desktop_type_text",
                description="Focuses an element and types text using native OS keyboard events.",
                args_schema=TypeInput,
            ),
            StructuredTool.from_function(
                func=lambda key_combination: app.press(key_combination=key_combination),
                name="desktop_press_key",
                description="Dispatches modifier keys or shortcuts (e.g. 'cmd+s', 'ctrl+shift+p', 'return').",
                args_schema=KeyInput,
            ),
        ]
        return tools
    except ImportError:
        # Fallback to pure dictionary tool specs for raw OpenAI / Anthropic / AutoGen / CrewAI loops
        return [
            {
                "type": "function",
                "function": {
                    "name": "desktop_get_screen_dom",
                    "description": "Retrieves the current native desktop accessibility tree pruned to actionable elements.",
                    "parameters": GetDOMInput.model_json_schema(),
                },
                "call": lambda max_depth=8: app.get_tree(max_depth=max_depth, as_dict=True),
            },
            {
                "type": "function",
                "function": {
                    "name": "desktop_click_element",
                    "description": "Dispatches a deterministic hardware click to the exact centroid of a desktop element by ID.",
                    "parameters": ClickInput.model_json_schema(),
                },
                "call": lambda element_id, button="left": app.click(element_id=element_id, button=button),
            },
            {
                "type": "function",
                "function": {
                    "name": "desktop_type_text",
                    "description": "Focuses an element and types text using native OS keyboard events.",
                    "parameters": TypeInput.model_json_schema(),
                },
                "call": lambda text, element_id=None, clear_first=False: app.type(element_id=element_id, text=text, clear_first=clear_first),
            },
            {
                "type": "function",
                "function": {
                    "name": "desktop_press_key",
                    "description": "Dispatches modifier keys or shortcuts (e.g. 'cmd+s', 'return').",
                    "parameters": KeyInput.model_json_schema(),
                },
                "call": lambda key_combination: app.press(key_combination=key_combination),
            },
        ]
