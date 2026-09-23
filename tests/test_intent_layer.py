import pytest
import json
import time
from unittest.mock import patch, MagicMock
from desktop_dom.assistant.memory import AuraMemory
from desktop_dom.assistant.brain import AssistantBrain


@pytest.fixture
def intent_env(tmp_path):
    """Initializes isolated AuraMemory and AssistantBrain with dual-cluster context."""
    db_file = tmp_path / "intent_layer_test.db"
    mem = AuraMemory(db_path=str(db_file))
    
    # Complete verified onboarding with founder/engineer profile
    mem.complete_verified_onboarding({
        "user_name": "Piyush Dua",
        "user_role": "Backend Engineer",
        "user_company": "Crcle.ai",
        "playlists": {"focus": "Synthwave Chill", "personal": "Ambient Chill"},
        "app_bindings": {"meeting": "Granola", "browser": "Google Chrome", "mail": "Microsoft Outlook"},
        "collaborators": [
            {"name": "Joshua Rayan", "email": "josh@crcle.ai", "role": "Co-Founder & CTO", "company": "Crcle.ai"},
            {"name": "Cyril Rayan", "email": "cyril@crcle.ai", "role": "Co-Founder & CEO", "company": "Crcle.ai"},
            {"name": "Hannah Vance", "email": "hannah.vance@crcle.ai", "role": "Lead Designer", "company": "Crcle.ai"}
        ]
    })
    
    # Add a personal contact sharing the same first name "Hannah"
    mem.add_entity(
        name="Hannah Miller",
        email="hannah.miller@gmail.com",
        category="personal",
        role="Friend",
        metadata={"cluster": "personal"}
    )

    brain = AssistantBrain(preferred_model="ministral-3:8b", memory=mem)
    return mem, brain


def test_meeting_intent_is_never_vague_and_executes_autonomously(intent_env):
    """
    Verifies:
    1. 'I have a meeting' is a direct, primary intent (NOT vague).
    2. Opens Granola autonomously with confidence >= 0.95 and tier='autonomous'.
    3. Zero clarifying questions asked.
    """
    mem, brain = intent_env

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        res = brain.execute_intent("I have a meeting")

        assert res["status"] == "success"
        assert res["action"] == "meeting_intent"
        assert res["tool"] == "Granola"
        assert res["confidence"] >= 0.95
        assert res["tier"] == "autonomous"
        assert "Granola" in res["response"]


def test_meeting_intent_with_colleague_and_personal_routing(intent_env):
    """
    Verifies:
    1. 'Meeting with Cyril' routes to work meeting tool (Granola).
    2. 'Meetup with Mom' routes to personal communication tool (Messages).
    """
    mem, brain = intent_env

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        
        # Professional meeting
        res_work = brain.execute_intent("meeting with Cyril")
        assert res_work["status"] == "success"
        assert res_work["tool"] == "Granola"
        assert res_work["participant"] == "Cyril Rayan"
        assert res_work["confidence"] >= 0.95

        # Personal meetup
        res_personal = brain.execute_intent("meetup with Mom")
        assert res_personal["status"] == "success"
        assert res_personal["context_type"] == "personal"
        assert res_personal["tool"] == "Messages"
        assert res_personal["confidence"] >= 0.95


def test_text_hannah_resolves_autonomously_via_context_symmetry_breaking(intent_env):
    """
    Verifies:
    1. 'Text Hannah' in a work/engineering context breaks symmetry using cluster affinity.
    2. Resolves directly to Hannah Vance (Crcle.ai) with confidence >= 0.95.
    3. Does NOT stop to ask 'Which Hannah?' (No disambiguation stall).
    """
    mem, brain = intent_env

    # Active context in IDE / Crcle repo
    with patch.object(brain, "_get_current_context_dict", return_value={"frontmost_app": "Zed", "activity_category": "work"}):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            res = brain.execute_intent("text hannah reviewing the pr now")

            assert res["status"] == "success"
            assert res["action"] == "send_message"
            assert "Hannah Vance" in res["recipient"]
            assert res["email"] == "hannah.vance@crcle.ai"
            assert res["confidence"] >= 0.95


def test_knitbrain_misfire_feedback_and_self_correction_loop(intent_env):
    """
    Verifies:
    1. Initial 'I have a meeting' launches Granola.
    2. User corrects: 'No, open Zoom instead'.
    3. Knitbrain records false positive for Granola, penalizes edge, boosts Zoom to 1.0, and stores learned rule.
    4. Next 'I have a meeting' executes Zoom autonomously with high confidence.
    """
    mem, brain = intent_env

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0

        # Step 1: Initial execution launches Granola
        res1 = brain.execute_intent("I have a meeting")
        assert res1["status"] == "success"
        assert res1["tool"] == "Granola"

        # Step 2: User gives natural language negative feedback / correction
        res2 = brain.execute_intent("No, open Zoom instead")
        assert res2["status"] == "success"
        assert res2["action"] == "misfire_self_correction"
        assert res2["tool"] == "Zoom"
        assert res2["false_positive"] == "Granola"
        assert res2["confidence"] == 1.0

        # Verify Knitbrain persistence
        misfires = mem.list_misfires()
        assert len(misfires) >= 1
        assert misfires[0]["false_positive_target"].lower() == "granola"
        assert misfires[0]["corrected_target"].lower() == "zoom"

        learnings = mem.list_learnings()
        assert any("zoom" in l["target_action"].lower() for l in learnings)

        # Step 3: Next meeting query automatically opens Zoom!
        res3 = brain.execute_intent("I have a meeting")
        assert res3["status"] == "success"
        assert res3["tool"] == "Zoom"
        assert res3["confidence"] >= 0.95


def test_non_binary_destination_last_email_retrieval(intent_env):
    """
    Verifies non-binary intent 'last email from Josh' queries native email client
    and returns subject, timestamp, and snippet without hallucinations.
    """
    mem, brain = intent_env

    mock_applescript_output = "Sprint 42 Architecture Review\n2026-09-16 16:30:00\nHey Piyush, the new backend benchmarks look great. Let's sync tomorrow."
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = mock_applescript_output

        res = brain.execute_intent("last email from josh")
        assert res["status"] == "success"
        assert res["action"] == "last_email_query"
        assert res["sender"] == "Joshua Rayan"
        assert "Sprint 42 Architecture Review" in res["subject"]
        assert "benchmarks look great" in res["snippet"]
        assert res["confidence"] >= 0.95


def test_spreading_activation_cluster_barrier_isolation(intent_env):
    """
    Verifies spreading activation does not bleed across disjoint clusters (Work vs Personal).
    """
    mem, brain = intent_env

    # Joshua Rayan (work) and Ambient Chill (personal playlist) must be disjoint
    shared = mem.find_shared_context("Joshua Rayan", "Ambient Chill")
    assert shared["status"] == "disjoint"
    assert shared["distance"] == float("inf")

    # Spreading activation from 'coding' prompt ignites work nodes, not personal gaming/music
    ignite_res = mem.ignite_graph("coding in zed on desktop-dom", context={"frontmost_app": "Zed"})
    ignited_names = [n["name"].lower() for n in ignite_res["ignited_nodes"]]
    assert any("zed" in n or "crcle" in n or "desktop-dom" in n for n in ignited_names)
    assert not any("ambient chill" in n or "gaming" in n for n in ignited_names)


def test_natural_intent_what_is_on_repository_overview(intent_env):
    """
    Verifies 'what is on desktop-dom' routes directly to repo overview in Knowledge Graph
    and returns live git & PR status without stalling on LLM reasoning.
    """
    mem, brain = intent_env

    mem.add_entity(
        name="desktop-dom",
        role="Code Repository",
        category="project",
        company="Crcle.ai",
        metadata={"verified": True, "provenance": "user_onboarding"}
    )

    with patch("desktop_dom.assistant.non_binary.get_git_pr_status") as mock_git:
        mock_git.return_value = {
            "status": "success",
            "action": "git_pr_status",
            "branch": "develop",
            "response": "Git & PR Status (Branch: 'develop'):\n• Uncommitted Changes: Clean (0 files)\n• Pull Request: #108 Approved",
        }
        res = brain.execute_intent("what is on desktop-dom")
        assert res["status"] == "success"
        assert res["action"] in ("git_pr_status", "repo_overview")
        assert "develop" in res["response"]

