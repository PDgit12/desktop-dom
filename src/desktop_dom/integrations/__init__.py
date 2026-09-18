"""
AI Agent framework integrations for desktop-dom.
"""
from .langchain import DesktopDOMToolkit, create_desktop_tools
from .mcp import DesktopDomMCPServer
from .composio import (
    ComposioOnboardingService,
    ComposioSDKClient,
    ConsentRequiredError,
    OnboardingConsent,
    normalize_profile_payload,
)

def run_mcp_server(target_app: str = "Finder") -> None:
    server = DesktopDomMCPServer(target_app=target_app)
    server.run_stdio()

__all__ = [
    "DesktopDOMToolkit",
    "create_desktop_tools",
    "DesktopDomMCPServer",
    "run_mcp_server",
    "ComposioOnboardingService",
    "ComposioSDKClient",
    "ConsentRequiredError",
    "OnboardingConsent",
    "normalize_profile_payload",
]
