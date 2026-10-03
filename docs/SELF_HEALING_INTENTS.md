# Optional self-healing intent learning

The `self-healing-ml` project now provides a small supervised intent-model
component. `SelfHealingIntentBridge` connects it to Aura's deterministic routing
and explicit correction path. This is opt-in and shadow-only: predictions do not
replace Aura's router or authorize actions. There is no vision/LoRA dependency.

Both source checkouts must be importable. See the self-healing project's
`docs/AURA_INTEGRATION.md` for the API, reproducible evaluation and limitations.
Model and feedback state should use a separate local SQLite file, not the live
Aura knowledge database. Training requires explicit labels; successful tool calls
are not automatically treated as correct intent predictions.

Integration tests use an isolated Aura database and mocked desktop actions. They
verify correction forwarding, preservation of the existing route, and recovery
when the optional model is unavailable.
