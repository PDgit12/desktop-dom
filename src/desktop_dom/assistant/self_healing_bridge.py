"""Opt-in adapter to self-healing-ml's learning API; recommendations cannot execute."""

from __future__ import annotations

from typing import Any


class SelfHealingIntentBridge:
    def __init__(self, healer: Any):
        self.healer = healer

    def predict(self, query: str, scope: str) -> dict[str, Any]:
        return self.healer.predict(query, scope)

    def record_correction(self, *, query: str, scope: str, predicted: str, target: str) -> None:
        from self_healing_intent import Example

        self.healer.record_feedback(Example(query, scope, target), predicted, confirmed=True)
