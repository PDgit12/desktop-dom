"""
desktop-dom: Semantic Accessibility DOM and Deterministic Action Engine for AI Agents.
Playwright for Native Desktop Applications (macOS, Windows, Linux).
"""

from desktop_dom.schema import DesktopNode, BoundingBox, ElementStates
from desktop_dom.pruner import TreePruner, FuzzyResolver
from desktop_dom.app import DesktopApp
from desktop_dom.adapters import get_platform_adapter

__version__ = "0.1.0"

__all__ = [
    "DesktopApp",
    "DesktopNode",
    "BoundingBox",
    "ElementStates",
    "TreePruner",
    "FuzzyResolver",
    "get_platform_adapter",
]
