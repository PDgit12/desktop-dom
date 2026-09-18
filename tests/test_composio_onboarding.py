import json

import pytest

from desktop_dom.assistant.memory import AuraMemory
from desktop_dom.integrations.composio import (
    ComposioOnboardingService,
    ConsentRequiredError,
    OnboardingConsent,
)


class FakeComposioClient:
    def __init__(self):
        self.execute_calls = []
        self.disconnected = []

    def create_connect_link(self, user_id, auth_config_id, *, callback_url=None, alias=None):
        return {
            "id": "ca_pending_123",
            "status": "PENDING",
            "redirect_url": "https://connect.example.test/request/123",
            "access_token": "must-never-be-persisted",
            "user_id": user_id,
            "auth_config_id": auth_config_id,
            "alias": alias,
        }

    def execute(self, tool_slug, arguments, *, connected_account_id, user_id):
        self.execute_calls.append({
            "tool_slug": tool_slug,
            "arguments": arguments,
            "connected_account_id": connected_account_id,
            "user_id": user_id,
        })
        return {
            "data": {
                "profile": {
                    "display_name": "Billy",
                    "email": "billy@example.com",
                }
            }
        }

    def disconnect(self, connected_account_id):
        self.disconnected.append(connected_account_id)


def _consent(scopes=("profile",)):
    return OnboardingConsent(
        user_id="user-123",
        toolkit="gmail",
        data_scopes=tuple(scopes),
    )


def test_begin_connection_requires_consent_and_persists_safe_metadata(tmp_path):
    memory = AuraMemory(tmp_path / "composio.db")
    client = FakeComposioClient()
    service = ComposioOnboardingService(memory, client)

    with pytest.raises(ConsentRequiredError):
        service.begin_connection(
            user_id="user-123",
            toolkit="gmail",
            auth_config_id="ac_gmail",
            consent=None,
        )

    result = service.begin_connection(
        user_id="user-123",
        toolkit="gmail",
        auth_config_id="ac_gmail",
        consent=_consent(),
        alias="primary-gmail",
    )

    assert result["status"] == "PENDING"
    assert result["redirect_url"].startswith("https://")
    accounts = memory.list_connected_accounts("user-123")
    assert accounts[0]["external_id"] == "ca_pending_123"
    assert accounts[0]["status"] == "PENDING"
    assert accounts[0]["data_scopes"] == ["profile"]
    assert "access_token" not in json.dumps(accounts[0])


def test_sync_requires_active_connection_and_normalizes_profile_data(tmp_path):
    memory = AuraMemory(tmp_path / "composio.db")
    client = FakeComposioClient()
    service = ComposioOnboardingService(memory, client)

    service.begin_connection(
        user_id="user-123",
        toolkit="gmail",
        auth_config_id="ac_gmail",
        consent=_consent(),
    )
    service.confirm_connection(
        user_id="user-123",
        toolkit="gmail",
        auth_config_id="ac_gmail",
        external_id="ca_active_123",
    )

    result = service.sync_profile(
        user_id="user-123",
        toolkit="gmail",
        connected_account_id="ca_active_123",
        consent=_consent(),
        tool_slug="GMAIL_GET_PROFILE",
        arguments={},
        field_map={
            "user.name": "profile.display_name",
            "user.email": "profile.email",
        },
    )

    assert result["status"] == "success"
    assert result["updated_fields"] == ["user.name", "user.email"]
    assert memory.get_preference("user.name") == "Billy"
    assert memory.get_preference("user.email") == "billy@example.com"
    assert client.execute_calls[0]["connected_account_id"] == "ca_active_123"
    assert memory.list_connected_accounts("user-123")[0]["last_synced_at"] is not None


def test_sync_does_not_call_composio_without_matching_consent(tmp_path):
    memory = AuraMemory(tmp_path / "composio.db")
    client = FakeComposioClient()
    service = ComposioOnboardingService(memory, client)

    service.begin_connection(
        user_id="user-123",
        toolkit="gmail",
        auth_config_id="ac_gmail",
        consent=_consent(),
    )
    service.confirm_connection(
        user_id="user-123",
        toolkit="gmail",
        auth_config_id="ac_gmail",
        external_id="ca_active_123",
    )

    with pytest.raises(ConsentRequiredError):
        service.sync_profile(
            user_id="user-123",
            toolkit="gmail",
            connected_account_id="ca_active_123",
            consent=OnboardingConsent(
                user_id="another-user",
                toolkit="gmail",
                data_scopes=("profile",),
            ),
            tool_slug="GMAIL_GET_PROFILE",
            arguments={},
            field_map={"user.name": "profile.display_name"},
        )

    assert client.execute_calls == []


def test_revoke_marks_local_connection_revoked_without_storing_credentials(tmp_path):
    memory = AuraMemory(tmp_path / "composio.db")
    client = FakeComposioClient()
    service = ComposioOnboardingService(memory, client)

    service.begin_connection(
        user_id="user-123",
        toolkit="gmail",
        auth_config_id="ac_gmail",
        consent=_consent(),
    )
    service.confirm_connection(
        user_id="user-123",
        toolkit="gmail",
        auth_config_id="ac_gmail",
        external_id="ca_active_123",
    )

    result = service.revoke_connection("ca_active_123")

    assert result["status"] == "revoked"
    assert client.disconnected == ["ca_active_123"]
    assert memory.list_connected_accounts("user-123")[0]["status"] == "REVOKED"
