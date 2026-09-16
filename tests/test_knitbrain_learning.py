import pytest
import sqlite3
import time
from unittest.mock import patch, MagicMock

from desktop_dom.assistant.memory import AuraMemory
from desktop_dom.assistant.brain import AssistantBrain


@pytest.fixture
def clean_memory(tmp_path):
    db_file = tmp_path / "test_knitbrain.db"
    mem = AuraMemory(db_path=db_file)
    mem.set_preference("apps.primary_meeting", "Granola", category="intent_binding")
    mem.add_entity("Granola", category="application", role="meeting_assistant", metadata={"cluster": "work", "intent": "meeting"})
    mem.add_entity("Zoom", category="application", role="meeting_client", metadata={"cluster": "work", "intent": "meeting"})
    mem.add_edge(
        source="User",
        target="Granola",
        relation="handles_meeting_intent",
        weight=0.90,
        metadata={"intent": "meeting", "cluster": "work"}
    )
    return mem


def test_misfire_recording_and_edge_penalization(clean_memory):
    """Verifies that record_misfire reduces false positive weight by 0.5x and reinforces target to 1.0."""
    # Pre-condition: Granola has weight 0.90
    initial_app = clean_memory.resolve_app_for_intent("meeting")
    assert initial_app == "Granola"

    # Record misfire: user wanted Zoom instead of Granola
    correction = clean_memory.record_misfire(
        query="i have a meeting",
        false_positive_target="Granola",
        corrected_target="Zoom",
        intended_intent="meeting",
        user_feedback="Clicked teach aura chip",
    )

    assert correction["status"] == "success"
    assert correction["false_positive"] == "Granola"
    assert correction["corrected_to"] == "Zoom"
    assert correction["graph_adjustment"]["reinforced"] == "Zoom"

    # Verify that preferences table updated immediately
    assert clean_memory.get_preference("apps.primary_meeting") == "Zoom"

    # Verify that resolve_app_for_intent immediately returns Zoom
    new_app = clean_memory.resolve_app_for_intent("meeting")
    assert new_app == "Zoom"

    # Verify misfire was persisted
    misfires = clean_memory.get_misfires()
    assert len(misfires) >= 1
    assert misfires[0]["false_positive_target"] == "Granola"
    assert misfires[0]["corrected_target"] == "Zoom"

    # Verify learning was persisted
    learnings = clean_memory.get_learnings()
    assert len(learnings) >= 1
    assert any(l["target_action"] == "Zoom" for l in learnings)


def test_conversational_misfire_self_correction_in_brain(clean_memory):
    """Verifies that brain handles conversational corrections ('no open zoom instead') seamlessly."""
    brain = AssistantBrain(memory=clean_memory)

    with patch("subprocess.run") as mock_sub:
        mock_sub.return_value = MagicMock(returncode=0)

        # Step 1: User says "I have a meeting" -> opens Granola initially
        res1 = brain.execute_intent("i have a meeting")
        assert res1["status"] == "success"
        assert res1["action"] == "meeting_intent"
        assert res1["tool"] == "Granola"

        # Step 2: User says "No, open Zoom instead"
        res2 = brain.execute_intent("No, open Zoom instead")
        assert res2["status"] == "success"
        assert "from Granola to Zoom" in res2["response"]

        # Step 3: Next time user says "I have a meeting" -> opens Zoom with >= 95% confidence!
        res3 = brain.execute_intent("i have a meeting")
        assert res3["status"] == "success"
        assert res3["action"] == "meeting_intent"
        assert res3["tool"] == "Zoom"
        assert res3["confidence"] >= 0.95
        assert res3["tier"] == "autonomous"


def test_omnibar_teach_aura_misfire_callback(clean_memory):
    """Verifies that FloatingOmnibar.on_record_misfire triggers the learning loop."""
    brain = AssistantBrain(memory=clean_memory)

    # Simulate omnibar controller
    from desktop_dom.assistant.omnibar import FloatingOmnibar
    omnibar = FloatingOmnibar(brain=brain)

    with patch.object(omnibar, "evaluate_js") as mock_eval:
        omnibar.on_record_misfire(
            query="i have a meeting",
            wrong_app="Granola",
            correct_app="Zoom",
        )

        # Verify memory was updated
        assert clean_memory.get_preference("apps.primary_meeting") == "Zoom"
        assert clean_memory.resolve_app_for_intent("meeting") == "Zoom"

        # Verify JS feedback was dispatched to WebKit
        assert mock_eval.called
