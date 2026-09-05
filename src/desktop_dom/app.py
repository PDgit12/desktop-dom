from __future__ import annotations
import subprocess
import time
import logging
from typing import Optional, List, Dict, Any, Literal, Union

from desktop_dom.adapters import get_platform_adapter
from desktop_dom.adapters.base import BasePlatformAdapter
from desktop_dom.schema import DesktopNode
from desktop_dom.pruner import TreePruner, FuzzyResolver

logger = logging.getLogger("desktop_dom.app")

class DesktopApp:
    """
    High-level developer SDK wrapper for inspecting desktop application accessibility trees
    and dispatching deterministic, sub-millisecond hardware actions.
    """

    def __init__(
        self,
        target: str | int,
        adapter: Optional[BasePlatformAdapter] = None,
        pruner: Optional[TreePruner] = None,
    ):
        self.target = target
        self.adapter = adapter or get_platform_adapter()
        self.pruner = pruner or TreePruner()
        self._last_tree: Optional[DesktopNode] = None
        self._node_lookup: Dict[str, DesktopNode] = {}
        self._cached_nodes_history: Dict[str, DesktopNode] = {}
        self._generation: int = 0

    @classmethod
    def launch(cls, command: str, app_name: Optional[str] = None, wait_seconds: float = 1.5) -> DesktopApp:
        """
        Spawns an application subprocess, waits briefly for the window to render, and attaches.
        """
        logger.info(f"Launching application command: {command}")
        proc = subprocess.Popen(command, shell=True)
        time.sleep(wait_seconds)
        target = app_name or proc.pid
        return cls(target)

    @classmethod
    def attach(
        cls,
        app_name_or_pid: str | int,
        adapter: Optional[BasePlatformAdapter] = None,
    ) -> DesktopApp:
        """
        Attaches to an already running desktop application.
        """
        return cls(app_name_or_pid, adapter=adapter)

    def get_tree(
        self,
        max_depth: int = 10,
        prune: bool = True,
        as_dict: bool = True,
    ) -> Union[Dict[str, Any], DesktopNode]:
        """
        Extracts, normalizes, and prunes the element tree.
        Caches internal node lookup table for subsequent action resolution.
        """
        raw_root = self.adapter.get_root_window(self.target)

        if prune:
            root = self.pruner.prune_and_normalize(raw_root) or raw_root
        else:
            root = raw_root

        self._node_lookup.clear()
        self._index_nodes(root)
        self._last_tree = root
        self._generation += 1

        if as_dict:
            return root.to_token_dict(include_children=True, max_child_depth=max_depth)
        return root

    def click(self, element_id: str, button: Literal["left", "right", "double"] = "left") -> Dict[str, Any]:
        """
        Resolves node from internal lookup (with automatic stale ID recovery)
        and dispatches an absolute OS-level hardware click to its centroid.
        """
        node = self._resolve_node(element_id)
        cx, cy = node.bbox.centroid
        self.adapter.click(node, button=button)
        return {
            "status": "success",
            "action": "click",
            "element_id": node.id,
            "role": node.role,
            "name": node.name,
            "centroid": [cx, cy],
            "button": button,
        }

    def click_at(self, x: int, y: int, button: Literal["left", "right", "double"] = "left") -> Dict[str, Any]:
        """
        Dispatches synthetic hardware click to explicit desktop coordinates.
        """
        self.adapter.click_coords(x, y, button=button)
        return {"status": "success", "action": "click_coords", "coords": [x, y], "button": button}

    def type(self, element_id: Optional[str], text: str, clear_first: bool = False) -> Dict[str, Any]:
        """
        Focuses element (if specified) and sends native keyboard character events.
        """
        node = self._resolve_node(element_id) if element_id else None
        self.adapter.type_text(node, text, clear_first=clear_first)
        return {
            "status": "success",
            "action": "type",
            "element_id": node.id if node else None,
            "text": text,
            "clear_first": clear_first,
        }

    def press(self, key_combination: str) -> Dict[str, Any]:
        """
        Sends hotkeys, chords, or special keys (e.g. 'cmd+s', 'ctrl+shift+p', 'return').
        """
        self.adapter.press_key(key_combination)
        return {"status": "success", "action": "press", "key": key_combination}

    def find(self, role: Optional[str] = None, name: Optional[str] = None) -> Optional[DesktopNode]:
        """Finds the first node matching role and/or name substring."""
        if self._last_tree is None:
            self.get_tree()
        assert self._last_tree is not None
        matches = self._last_tree.find_all(role=role, name=name)
        return matches[0] if matches else None

    def find_all(self, role: Optional[str] = None, name: Optional[str] = None) -> List[DesktopNode]:
        """Finds all nodes matching role and/or name substring."""
        if self._last_tree is None:
            self.get_tree()
        assert self._last_tree is not None
        return self._last_tree.find_all(role=role, name=name)

    def _resolve_node(self, element_id: str) -> DesktopNode:
        """
        Resolves element ID from memory.
        If stale, triggers an automatic delta-refresh and fuzzy semantic recovery.
        """
        # 1. Direct hit in active tree
        if element_id in self._node_lookup:
            return self._node_lookup[element_id]

        logger.info(f"Element ID '{element_id}' missing in cache. Performing automatic delta-refresh...")
        cached_node = self._cached_nodes_history.get(element_id)

        # 2. Refresh tree
        self.get_tree(as_dict=False)

        if element_id in self._node_lookup:
            return self._node_lookup[element_id]

        # 3. Fuzzy semantic fallback
        if self._last_tree:
            fallback = FuzzyResolver.resolve_stale(element_id, cached_node, self._last_tree)
            if fallback:
                logger.warning(
                    f"Recovered stale ID '{element_id}' via fuzzy semantic fallback -> "
                    f"'{fallback.id}' [{fallback.role}] '{fallback.name}'"
                )
                return fallback

        raise KeyError(
            f"Element ID '{element_id}' is invalid or stale. "
            f"Available elements: {list(self._node_lookup.keys())[:10]}..."
        )

    def _index_nodes(self, node: DesktopNode):
        self._node_lookup[node.id] = node
        self._cached_nodes_history[node.id] = node
        for child in node.children:
            self._index_nodes(child)

    def as_tools(self) -> List[Dict[str, Any]]:
        """
        Exposes callable dictionary schemas suitable for standard LLM Tool Calling loops.
        """
        from desktop_dom.integrations.langchain import create_desktop_tools
        return create_desktop_tools(self)
