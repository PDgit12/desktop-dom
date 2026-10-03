from unittest.mock import patch

import pytest

from desktop_dom.assistant.brain import AssistantBrain
from desktop_dom.assistant.memory import AuraMemory
from desktop_dom.assistant.self_healing_bridge import SelfHealingIntentBridge


def test_shadow_predictions_never_override_aura_and_corrections_are_forwarded(tmp_path):
    IntentHealer = pytest.importorskip("self_healing_intent").IntentHealer

    healer = IntentHealer(tmp_path / 'healing.db')
    bridge = SelfHealingIntentBridge(healer)
    memory = AuraMemory(tmp_path / 'aura.db')
    memory.complete_verified_onboarding({'user_name': 'Example User',
                                         'app_bindings': {'meeting': 'Granola'}})
    brain = AssistantBrain(memory=memory, preferred_model='Zero-Model Fast-Path',
                           execution_mode='fast_path', intent_healer=bridge)
    with patch('subprocess.run') as run, patch.object(brain, '_get_current_context_dict',
                                                     return_value={'activity_category': 'work'}):
        run.return_value.returncode = 0
        with patch.object(bridge, 'predict', return_value={'target': 'Zoom', 'mode': 'shadow'}):
            result = brain.execute_intent('I have a meeting')
        assert result['tool'] == 'Granola'
        assert result['self_healing_shadow']['target'] == 'Zoom'
        corrected = brain.execute_intent('No, open Zoom instead')
        assert corrected['action'] == 'misfire_self_correction'
        assert healer.feedback_count() == 1
        assert healer.training_examples()[0].query == 'I have a meeting'
        assert healer.training_examples()[0].target == 'Zoom'
        assert healer.training_examples()[0].scope == 'work'
    memory.close()


def test_failed_optional_model_preserves_existing_router(tmp_path):
    memory = AuraMemory(tmp_path / 'aura.db')
    memory.complete_verified_onboarding({'app_bindings': {'meeting': 'Granola'}})
    class Broken:
        def predict(self, *args):
            raise RuntimeError('test model unavailable')
    brain = AssistantBrain(memory=memory, preferred_model='Zero-Model Fast-Path',
                           execution_mode='fast_path', intent_healer=Broken())
    with patch('subprocess.run') as run:
        run.return_value.returncode = 0
        result = brain.execute_intent('I have a meeting')
        assert result['tool'] == 'Granola'
        assert result['status'] == 'success'
    memory.close()
