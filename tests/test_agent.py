import pytest
from desktop_dom.app import DesktopApp
from desktop_dom.agent import AutonomousDesktopAgent, AgentAction, AgentStep, AgentResult
from tests.conftest import TestPlatformAdapter

class AgentTestAdapter(TestPlatformAdapter):
    def __init__(self):
        super().__init__()
        self.typed_values = []
        self.clicked_ids = []

    def type_text(self, node, text, clear_first=False):
        super().type_text(node, text, clear_first)
        self.typed_values.append(text)
        for n in self._tree.flatten():
            if n.role == 'input':
                n.value = text

    def click(self, node, button='left'):
        super().click(node, button)
        self.clicked_ids.append(node.id)

def test_autonomous_agent_deterministic_search():
    adapter = AgentTestAdapter()
    app = DesktopApp(target='Calculator', adapter=adapter)
    agent = AutonomousDesktopAgent(app=app, max_steps=5, settle_delay=0.01)

    result = agent.run('search for 250')
    assert result.status == 'completed'
    assert len(result.steps) >= 1
    assert any(s.action.action_type == 'type' for s in result.steps)
    assert '250' in adapter.typed_values
    
    # Check serialization
    res_dict = result.to_dict()
    assert res_dict['goal'] == 'search for 250'
    assert res_dict['status'] == 'completed'
    assert res_dict['steps_count'] == len(result.steps)
    assert 'diff' in res_dict['steps'][0]

def test_autonomous_agent_custom_planner():
    adapter = AgentTestAdapter()
    app = DesktopApp(target='Calculator', adapter=adapter)

    def custom_planner(goal, tree, history):
        if len(history) == 0:
            btn = tree.find_all(role='button')[0]
            return AgentAction(
                action_type='click',
                target_id=btn.id,
                reasoning='First step: click first button',
                expected_effect={'type': 'any_change'},
            )
        return AgentAction(action_type='finish', reasoning='Task finished by custom logic')

    agent = AutonomousDesktopAgent(app=app, max_steps=5, planner_fn=custom_planner, settle_delay=0.01)
    result = agent.run('do custom flow')
    assert result.status == 'completed'
    assert len(result.steps) == 1
    assert result.steps[0].action.action_type == 'click'

def test_autonomous_agent_max_steps_exceeded():
    adapter = AgentTestAdapter()
    app = DesktopApp(target='Calculator', adapter=adapter)

    # Infinite no-op planner
    def looping_planner(goal, tree, history):
        return AgentAction(action_type='wait', reasoning='Keep waiting')

    agent = AutonomousDesktopAgent(app=app, max_steps=3, planner_fn=looping_planner, settle_delay=0.005)
    result = agent.run('wait indefinitely')
    assert result.status == 'max_steps_exceeded'
    assert len(result.steps) == 3

def test_autonomous_agent_reflection_on_miss():
    adapter = AgentTestAdapter()
    app = DesktopApp(target='Calculator', adapter=adapter)

    # Plan that expects a non-existent mutation
    def non_mutating_planner(goal, tree, history):
        if len(history) == 0:
            btn = tree.find_all(role='button')[0]
            return AgentAction(
                action_type='click',
                target_id=btn.id,
                reasoning='Click button but expect non-existent dialog',
                expected_effect={'type': 'node_added', 'role': 'dialog'},
            )
        return AgentAction(action_type='finish', reasoning='Done after reflection')

    agent = AutonomousDesktopAgent(app=app, max_steps=3, planner_fn=non_mutating_planner, settle_delay=0.01)
    result = agent.run('test reflection')
    assert len(result.steps) == 1
    # First step was unverified because dialog was never added
    assert not result.steps[0].result.verified
    assert 'produced no verified mutation' in result.steps[0].reflection
