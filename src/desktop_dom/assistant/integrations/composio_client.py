"""
Composio HTTP Client Adapter.
Provides zero-rigid-dependency REST access to Composio's authentication,
connected account management, and tool execution APIs.
Gracefully degrades with informative status dictionaries when offline or unconfigured.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from .contracts import ConnectedAccountState

logger = logging.getLogger("desktop_dom.assistant.integrations.composio")

DEFAULT_COMPOSIO_BASE_URL = "https://backend.composio.dev/api/v1"


class ComposioHttpClient:
    """
    Lightweight, robust client for Composio REST API.
    Does not require external third-party packages, ensuring maximum portability
    across macOS desktop installations while supporting full OAuth lifecycle.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_COMPOSIO_BASE_URL,
        timeout: float = 8.0,
    ):
        self.api_key = (api_key or os.environ.get("COMPOSIO_API_KEY", "")).strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def is_configured(self) -> bool:
        """Returns True if a valid API key is present."""
        return bool(self.api_key and len(self.api_key) > 5)

    def _request(
        self,
        method: str,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Performs an authenticated HTTP request to the Composio API."""
        if not self.is_configured():
            return {
                "status": "error",
                "code": "UNCONFIGURED",
                "message": "COMPOSIO_API_KEY is not configured in environment or settings.",
            }

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        if params:
            query_str = urllib.parse.urlencode(params)
            url = f"{url}?{query_str}"

        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "Aura-Desktop-DOM/0.1.0 (macOS)",
        }

        body_bytes = None
        if payload is not None:
            body_bytes = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method.upper())

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_bytes = resp.read()
                return json.loads(resp_bytes.decode("utf-8"))
        except urllib.error.HTTPError as err:
            err_body = ""
            try:
                err_body = err.read().decode("utf-8")
                err_json = json.loads(err_body)
                return {
                    "status": "error",
                    "code": f"HTTP_{err.code}",
                    "message": err_json.get("message") or str(err),
                    "details": err_json,
                }
            except Exception:
                return {
                    "status": "error",
                    "code": f"HTTP_{err.code}",
                    "message": f"Composio HTTP Error {err.code}: {err.reason}",
                    "raw": err_body,
                }
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            logger.debug(f"Composio network error: {err}")
            return {
                "status": "error",
                "code": "NETWORK_UNAVAILABLE",
                "message": f"Network error connecting to Composio: {err}",
            }
        except Exception as err:
            logger.warning(f"Unexpected error in Composio request: {err}")
            return {
                "status": "error",
                "code": "INTERNAL_CLIENT_ERROR",
                "message": str(err),
            }

    def initiate_connection(
        self,
        app_name: str,
        entity_id: str,
        redirect_url: Optional[str] = None,
    ) -> ConnectedAccountState:
        """
        Initiates an OAuth connection flow for a specific app (e.g. googlecalendar, github, gmail).
        Returns ConnectedAccountState containing the auth_url to open in user's browser.
        """
        clean_app = app_name.strip().lower()
        if not self.is_configured():
            return ConnectedAccountState(
                app=clean_app,
                status="FAILED",
                error_message="COMPOSIO_API_KEY is not set.",
            )

        payload = {
            "appName": clean_app,
            "entityId": entity_id,
        }
        if redirect_url:
            payload["redirectUrl"] = redirect_url

        res = self._request("POST", "/connectedAccounts", payload=payload)

        if res.get("status") == "error":
            return ConnectedAccountState(
                app=clean_app,
                status="FAILED",
                error_message=res.get("message", "Failed to initiate connection"),
            )

        # Parse Composio standard response
        account_id = res.get("connectedAccountId") or res.get("id")
        auth_url = res.get("redirectUrl") or res.get("authUrl")
        raw_status = (res.get("status") or "INITIATING").upper()

        mapped_status = "AWAITING_USER_AUTH" if auth_url else raw_status
        if raw_status in ["ACTIVE", "CONNECTED"]:
            mapped_status = "ACTIVE"

        return ConnectedAccountState(
            app=clean_app,
            status=mapped_status,
            account_id=account_id,
            auth_url=auth_url,
            metadata=res,
        )

    def get_connection_status(self, connected_account_id: str) -> ConnectedAccountState:
        """Checks current status of a connected account."""
        if not self.is_configured():
            return ConnectedAccountState(
                app="unknown",
                status="FAILED",
                error_message="COMPOSIO_API_KEY is not set.",
            )

        res = self._request("GET", f"/connectedAccounts/{connected_account_id}")
        if res.get("status") == "error":
            return ConnectedAccountState(
                app="unknown",
                status="FAILED",
                account_id=connected_account_id,
                error_message=res.get("message"),
            )

        app_name = res.get("appName") or res.get("app", "unknown")
        raw_status = (res.get("status") or "DISCONNECTED").upper()
        mapped_status = "ACTIVE" if raw_status in ["ACTIVE", "CONNECTED"] else raw_status

        user_ident = (
            res.get("userIdentifier")
            or res.get("email")
            or (res.get("connectionParams") or {}).get("email")
        )

        return ConnectedAccountState(
            app=app_name.lower(),
            status=mapped_status,
            account_id=connected_account_id,
            user_identifier=user_ident,
            last_synced=time.time() if mapped_status == "ACTIVE" else None,
            metadata=res,
        )

    def list_connections(self, entity_id: str) -> List[ConnectedAccountState]:
        """Lists all active and pending connected accounts for the given user entity."""
        if not self.is_configured():
            return []

        res = self._request("GET", "/connectedAccounts", params={"entityId": entity_id})
        if res.get("status") == "error":
            return []

        items = res.get("items") or (res if isinstance(res, list) else [])
        results: List[ConnectedAccountState] = []

        for itm in items:
            if not isinstance(itm, dict):
                continue
            app_name = (itm.get("appName") or itm.get("app") or "unknown").lower()
            raw_status = (itm.get("status") or "DISCONNECTED").upper()
            mapped_status = "ACTIVE" if raw_status in ["ACTIVE", "CONNECTED"] else raw_status
            acc_id = itm.get("connectedAccountId") or itm.get("id")

            results.append(
                ConnectedAccountState(
                    app=app_name,
                    status=mapped_status,
                    account_id=acc_id,
                    user_identifier=itm.get("userIdentifier") or itm.get("email"),
                    last_synced=time.time() if mapped_status == "ACTIVE" else None,
                    metadata=itm,
                )
            )

        return results

    def disconnect_account(self, connected_account_id: str) -> bool:
        """Revokes and disconnects an integration."""
        if not self.is_configured():
            return False

        res = self._request("DELETE", f"/connectedAccounts/{connected_account_id}")
        return res.get("status") != "error"

    def execute_read_action(
        self,
        action_name: str,
        entity_id: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a read-only tool action on Composio (e.g. GOOGLECALENDAR_FIND_EVENTS, GITHUB_LIST_ISSUES).
        """
        if not self.is_configured():
            return {
                "status": "error",
                "code": "UNCONFIGURED",
                "message": "COMPOSIO_API_KEY is not configured.",
            }

        payload = {
            "entityId": entity_id,
            "input": params or {},
        }

        res = self._request("POST", f"/actions/{action_name}/execute", payload=payload)
        return res
