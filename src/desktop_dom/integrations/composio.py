"""Consent-first Composio onboarding for Aura.

Composio owns OAuth credentials and provider-side account state. Aura stores only
connection metadata and the small, normalized profile patch the user consented to
sync. The optional SDK import is lazy so desktop-dom remains local-only unless the
Composio extra is installed and explicitly configured.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Protocol, Sequence, Tuple

from desktop_dom.assistant.memory import AuraMemory


class ConsentRequiredError(ValueError):
    """Raised when a connection or sync is not covered by explicit consent."""


@dataclass(frozen=True)
class OnboardingConsent:
    """The user-approved data boundary for one toolkit during onboarding."""

    user_id: str
    toolkit: str
    data_scopes: Tuple[str, ...]
    version: str = "v1"
    granted_at: float = 0.0

    def __post_init__(self) -> None:
        user_id = self.user_id.strip()
        toolkit = self.toolkit.strip().lower()
        scopes = tuple(sorted({scope.strip().lower() for scope in self.data_scopes if scope.strip()}))
        if not user_id or not toolkit or not scopes:
            raise ValueError("Consent requires a user_id, toolkit, and at least one data scope")
        object.__setattr__(self, "user_id", user_id)
        object.__setattr__(self, "toolkit", toolkit)
        object.__setattr__(self, "data_scopes", scopes)
        if not self.granted_at:
            object.__setattr__(self, "granted_at", time.time())

    def covers(self, *, user_id: str, toolkit: str, required_scopes: Sequence[str]) -> bool:
        return (
            self.user_id == user_id.strip()
            and self.toolkit == toolkit.strip().lower()
            and set(required_scopes).issubset(set(self.data_scopes))
        )


class ComposioClient(Protocol):
    """Small adapter contract so onboarding is testable without network access."""

    def create_connect_link(
        self,
        user_id: str,
        auth_config_id: str,
        *,
        callback_url: Optional[str] = None,
        alias: Optional[str] = None,
    ) -> Mapping[str, Any]: ...

    def execute(
        self,
        tool_slug: str,
        arguments: Mapping[str, Any],
        *,
        connected_account_id: str,
        user_id: str,
    ) -> Mapping[str, Any]: ...

    def disconnect(self, connected_account_id: str) -> Any: ...


class ComposioSDKClient:
    """Thin wrapper around the optional Composio Python SDK.

    The API key is read from ``COMPOSIO_API_KEY`` or passed at construction and
    is never written to AuraMemory. ``allow_tracking=False`` keeps the SDK's
    optional telemetry disabled for this local-first onboarding path.
    """

    def __init__(self, api_key: Optional[str] = None, client: Any = None):
        if client is not None:
            self._client = client
            return
        try:
            from composio import Composio
        except ImportError as exc:  # pragma: no cover - exercised by packaging
            raise RuntimeError(
                "Composio support is optional; install desktop-dom[composio] first"
            ) from exc

        resolved_key = api_key or os.environ.get("COMPOSIO_API_KEY")
        if not resolved_key:
            raise RuntimeError("COMPOSIO_API_KEY is required to use Composio onboarding")
        self._client = Composio(api_key=resolved_key, allow_tracking=False)

    def create_connect_link(
        self,
        user_id: str,
        auth_config_id: str,
        *,
        callback_url: Optional[str] = None,
        alias: Optional[str] = None,
    ) -> Mapping[str, Any]:
        request = self._client.connected_accounts.link(
            user_id,
            auth_config_id,
            callback_url=callback_url,
            alias=alias,
        )
        return {
            "id": getattr(request, "id", None),
            "status": getattr(request, "status", "PENDING"),
            "redirect_url": getattr(request, "redirect_url", None),
        }

    def execute(
        self,
        tool_slug: str,
        arguments: Mapping[str, Any],
        *,
        connected_account_id: str,
        user_id: str,
    ) -> Mapping[str, Any]:
        return self._client.tools.execute(
            tool_slug,
            dict(arguments),
            connected_account_id=connected_account_id,
            user_id=user_id,
        )

    def disconnect(self, connected_account_id: str) -> Any:
        return self._client.connected_accounts.delete(connected_account_id)


def _read_path(payload: Mapping[str, Any], path: str) -> Any:
    """Read a dotted path from a provider response without retaining the response."""
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def normalize_profile_payload(
    payload: Mapping[str, Any],
    field_map: Mapping[str, str],
) -> Dict[str, Any]:
    """Select and normalize only allow-listed profile fields from a tool result."""
    root: Mapping[str, Any] = payload
    if isinstance(payload.get("data"), Mapping):
        root = payload["data"]
    allowed_fields = {
        "user.name",
        "user.email",
        "user.role",
        "user.company",
        "github.default_repo",
        "work.repos",
        "mail.preferred_client",
        "music.preferred_player",
    }
    normalized: Dict[str, Any] = {}
    for destination, source_path in field_map.items():
        if destination not in allowed_fields:
            raise ValueError(f"Unsupported external profile field: {destination}")
        value = _read_path(root, source_path)
        if value is None:
            continue
        if destination == "work.repos":
            if isinstance(value, str):
                value = [value]
            if not isinstance(value, (list, tuple)):
                raise ValueError("work.repos must normalize from a list or string")
            value = [str(item).strip() for item in value if str(item).strip()]
        elif not isinstance(value, (str, int, float, bool)):
            raise ValueError(f"Unsupported value returned for {destination}")
        else:
            value = str(value).strip()
        if value:
            normalized[destination] = value
    return normalized


class ComposioOnboardingService:
    """Coordinates consent, Composio auth, normalization, and memory updates."""

    def __init__(self, memory: AuraMemory, client: ComposioClient):
        self.memory = memory
        self.client = client

    @staticmethod
    def _require_consent(
        consent: Optional[OnboardingConsent],
        *,
        user_id: str,
        toolkit: str,
        required_scopes: Sequence[str],
    ) -> OnboardingConsent:
        if consent is None or not consent.covers(
            user_id=user_id,
            toolkit=toolkit,
            required_scopes=required_scopes,
        ):
            raise ConsentRequiredError(
                f"Explicit consent for {toolkit} scopes {sorted(required_scopes)} is required"
            )
        return consent

    def begin_connection(
        self,
        *,
        user_id: str,
        toolkit: str,
        auth_config_id: str,
        consent: Optional[OnboardingConsent],
        callback_url: Optional[str] = None,
        alias: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Composio Connect Link after the user approves read scopes."""
        grant = self._require_consent(
            consent,
            user_id=user_id,
            toolkit=toolkit,
            required_scopes=("profile",),
        )
        response = dict(self.client.create_connect_link(
            user_id.strip(),
            auth_config_id.strip(),
            callback_url=callback_url,
            alias=alias,
        ))
        account = self.memory.upsert_connected_account({
            "provider": "composio",
            "user_id": grant.user_id,
            "toolkit": grant.toolkit,
            "auth_config_id": auth_config_id,
            "external_id": response.get("id"),
            "status": response.get("status") or "PENDING",
            "consent_version": grant.version,
            "data_scopes": grant.data_scopes,
            "redirect_url": response.get("redirect_url"),
            "metadata": {"alias": alias or "", "provenance": "user_consent"},
        })
        return {
            "status": account.get("status", "PENDING"),
            "toolkit": grant.toolkit,
            "external_id": account.get("external_id"),
            "redirect_url": account.get("redirect_url"),
            "data_scopes": account.get("data_scopes", []),
        }

    def confirm_connection(
        self,
        *,
        user_id: str,
        toolkit: str,
        auth_config_id: str,
        external_id: str,
        status: str = "ACTIVE",
    ) -> Dict[str, Any]:
        """Record the provider-confirmed account ID and lifecycle status."""
        pending = self.memory.get_connected_account(user_id=user_id, toolkit=toolkit)
        if not pending or pending.get("auth_config_id") != auth_config_id:
            raise ValueError("No matching pending Composio connection exists")
        if status.strip().upper() != "ACTIVE":
            raise ValueError("Only ACTIVE connections may enter onboarding sync")
        return self.memory.upsert_connected_account({
            "provider": "composio",
            "user_id": user_id,
            "toolkit": toolkit,
            "auth_config_id": auth_config_id,
            "external_id": external_id,
            "status": "ACTIVE",
            "consent_version": pending.get("consent_version", "v1"),
            "data_scopes": pending.get("data_scopes", []),
            "redirect_url": pending.get("redirect_url"),
            "metadata": {"provenance": "composio_callback"},
        })

    def sync_profile(
        self,
        *,
        user_id: str,
        toolkit: str,
        connected_account_id: str,
        consent: Optional[OnboardingConsent],
        tool_slug: str,
        arguments: Mapping[str, Any],
        field_map: Mapping[str, str],
    ) -> Dict[str, Any]:
        """Run one read tool, normalize its result, and update Aura's profile."""
        destinations = tuple(field_map.keys())
        required_scopes = ("profile",)
        grant = self._require_consent(
            consent,
            user_id=user_id,
            toolkit=toolkit,
            required_scopes=required_scopes,
        )
        account = self.memory.get_connected_account(external_id=connected_account_id)
        if not account or account.get("status") != "ACTIVE":
            raise ValueError("Composio account must be ACTIVE before profile sync")
        if account.get("user_id") != grant.user_id or account.get("toolkit") != grant.toolkit:
            raise ConsentRequiredError("Consent does not match the connected account")
        if not set(grant.data_scopes).issuperset(required_scopes):
            raise ConsentRequiredError("Profile sync is outside the approved data scopes")

        raw_payload = self.client.execute(
            tool_slug,
            arguments,
            connected_account_id=connected_account_id,
            user_id=user_id,
        )
        normalized = normalize_profile_payload(raw_payload, field_map)
        patch = self.memory.apply_external_profile_patch(
            normalized,
            source=f"composio:{toolkit}",
            connected_account_id=connected_account_id,
        )
        updated = self.memory.update_connected_account(
            connected_account_id,
            last_synced_at=time.time(),
            metadata={"last_synced_fields": list(destinations), "sync_status": "success"},
        )
        return {
            "status": "success",
            "toolkit": toolkit.strip().lower(),
            "updated_fields": patch["updated_fields"],
            "account": updated,
        }

    def revoke_connection(self, connected_account_id: str) -> Dict[str, Any]:
        """Revoke at Composio first, then mark the local metadata as revoked."""
        self.client.disconnect(connected_account_id)
        account = self.memory.update_connected_account(
            connected_account_id,
            status="REVOKED",
            revoked_at=time.time(),
            metadata={"provenance": "user_revocation"},
        )
        return {
            "status": "revoked",
            "external_id": connected_account_id,
            "account": account,
        }


__all__ = [
    "ComposioClient",
    "ComposioOnboardingService",
    "ComposioSDKClient",
    "ConsentRequiredError",
    "OnboardingConsent",
    "normalize_profile_payload",
]
