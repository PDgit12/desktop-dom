"""
Tests for RhythmBridge Pediatric Clinical-to-Home Neuro-Therapy Platform
========================================================================

Verifies the bidirectional Intent Layer:
  1. Forward Compiler: Clinical Goal ──► 15-second NMT music-cued routine
  2. Reverse Compiler: Parent Micro-Log ──► Assistance Level & SOAP Note
  3. Sensory Intent Decoder: Posture & sensory barrier pattern detection
  4. RTM Compliance Tracker: CPT 98977/98980 & Payer Re-Authorization Packet
"""

import time
import pytest
from datetime import datetime, timedelta

from desktop_dom.assistant.pediatric.models import (
    ClinicalGoal,
    ClinicalGoalCategory,
    AssistanceLevel,
    DailyRoutineType,
    AuditoryAnchorType,
    MusicCue,
    MicroRoutine,
    ParentObservation,
    SOAPNote,
    RTMComplianceRecord,
)
from desktop_dom.assistant.pediatric.routine_compiler import (
    ForwardRoutineCompiler,
    NMT_TEMPO_REGISTRY,
)
from desktop_dom.assistant.pediatric.observation_compiler import (
    ReverseObservationCompiler,
)
from desktop_dom.assistant.pediatric.sensory_decoder import (
    SensoryIntentDecoder,
)
from desktop_dom.assistant.pediatric.rtm_tracker import (
    RTMComplianceTracker,
)


@pytest.fixture
def sample_goal() -> ClinicalGoal:
    return ClinicalGoal(
        id="goal_bilateral_001",
        patient_id="patient_leo_123",
        title="Bilateral Dressing Integration",
        description="Child will stabilize garment with non-dominant hand while manipulating zipper with dominant hand.",
        category=ClinicalGoalCategory.BILATERAL_COORDINATION,
        target_milestone="Independent coat zipping with bilateral engagement",
        baseline_assistance=AssistanceLevel.MAXIMUM_ASSIST,
        current_assistance=AssistanceLevel.MODERATE_ASSIST,
        target_assistance=AssistanceLevel.INDEPENDENT,
    )


def test_forward_routine_compiler_bilateral_nmt(sample_goal):
    """Verifies that Forward Routine Compiler generates correct NMT BPM and cues."""
    routine = ForwardRoutineCompiler.compile_routine(
        goal=sample_goal,
        routine_type=DailyRoutineType.SHOES_AND_COAT,
        custom_child_interest="Dinosaur",
    )

    assert routine.goal_id == sample_goal.id
    assert routine.routine_type == DailyRoutineType.SHOES_AND_COAT
    assert "Dinosaur Zipper Launch" in routine.title
    assert "non-dominant hand" in routine.parent_instruction
    assert "Dinosaur rocket" in routine.child_prompt
    assert routine.music_cue.tempo_bpm == 76
    assert routine.music_cue.auditory_anchor_type == AuditoryAnchorType.METRONOME_PACING
    assert routine.expected_duration_seconds == 15


def test_forward_routine_compiler_fine_motor_pincer():
    """Verifies fine motor pincer compiles to 64 BPM steady cadence."""
    goal = ClinicalGoal(
        id="goal_pincer_002",
        patient_id="patient_emma",
        title="Radial Pincer Grasp",
        description="Pick up small food bites with distal pads of thumb and index.",
        category=ClinicalGoalCategory.FINE_MOTOR_PINCER,
        target_milestone="Pincer grasp on small solids",
        baseline_assistance=AssistanceLevel.MODERATE_ASSIST,
        current_assistance=AssistanceLevel.MODERATE_ASSIST,
        target_assistance=AssistanceLevel.INDEPENDENT,
    )

    routine = ForwardRoutineCompiler.compile_routine(
        goal=goal,
        routine_type=DailyRoutineType.BREAKFAST_FEEDING,
        custom_child_interest="Super Mario",
    )

    assert routine.music_cue.tempo_bpm == 64
    assert "Laser Pinch" in routine.title
    assert "thumb and pointer" in routine.child_prompt


def test_reverse_observation_compiler_assistance_inference():
    """Verifies that the reverse compiler maps parent vernacular to clinical WeeFIM levels."""
    # Independent
    obs_indep = ReverseObservationCompiler.compile_observation(
        goal_id="g1",
        micro_routine_id="r1",
        patient_id="p1",
        raw_parent_notes="He did it all by himself today! So proud!",
    )
    assert obs_indep.assistance_level_observed == AssistanceLevel.INDEPENDENT
    assert obs_indep.task_completed is True
    assert obs_indep.meltdown_occurred is False

    # Minimal assist
    obs_min = ReverseObservationCompiler.compile_observation(
        goal_id="g1",
        micro_routine_id="r1",
        patient_id="p1",
        raw_parent_notes="Just gave a tiny verbal cue to hold the bottom.",
    )
    assert obs_min.assistance_level_observed == AssistanceLevel.MINIMAL_ASSIST

    # Maximum assist with meltdown
    obs_max = ReverseObservationCompiler.compile_observation(
        goal_id="g1",
        micro_routine_id="r1",
        patient_id="p1",
        raw_parent_notes="Had to do hand over hand the whole time, and he screamed because the seam was scratchy.",
    )
    assert obs_max.assistance_level_observed == AssistanceLevel.MAXIMUM_ASSIST
    assert obs_max.meltdown_occurred is True
    assert "tactile_defensiveness" in obs_max.sensory_triggers


def test_reverse_observation_compiler_compensations():
    """Verifies extraction of motor compensation patterns."""
    obs = ReverseObservationCompiler.compile_observation(
        goal_id="g1",
        micro_routine_id="r1",
        patient_id="p1",
        raw_parent_notes="He only used left hand and held the jacket with teeth!",
    )
    assert "unilateral_avoidance" in obs.compensatory_movements
    assert "mouth_holding" in obs.compensatory_movements


def test_soap_note_generation(sample_goal):
    """Verifies that longitudinal observations produce an audit-proof clinical SOAP note."""
    now = time.time()
    observations = []

    # Generate 18 days of synthetic parent logs
    for day in range(18):
        ts = now - ((18 - day) * 86400)
        obs = ParentObservation(
            id=f"obs_{day}",
            goal_id=sample_goal.id,
            micro_routine_id="r_01",
            patient_id=sample_goal.patient_id,
            timestamp=ts,
            parent_notes="Practiced morning coat zipper with music cue.",
            assistance_level_observed=AssistanceLevel.MINIMAL_ASSIST if day > 10 else AssistanceLevel.MODERATE_ASSIST,
            sensory_triggers=["tactile_defensiveness"] if day < 5 else [],
            compensatory_movements=[],
            task_completed=True,
            meltdown_occurred=day < 3,
        )
        observations.append(obs)

    soap = ReverseObservationCompiler.generate_soap_note(
        patient_id=sample_goal.patient_id,
        therapist_id="therapist_dr_claire",
        goal=sample_goal,
        observations=observations,
        date_range_start=now - (30 * 86400),
        date_range_end=now,
    )

    assert soap.patient_id == sample_goal.patient_id
    assert soap.rtm_days_logged == 18
    assert soap.rtm_compliant_98977 is True
    assert "Goal Focus: Bilateral Dressing Integration" in soap.objective
    assert "Task Completion Rate: 18/18 (100%)" in soap.objective
    assert "demonstrated measurable positive functional progress" in soap.assessment
    assert "Remote Therapeutic Monitoring (CPT 98977/98980)" in soap.plan


def test_sensory_intent_decoder():
    """Verifies detection of postural stability and sensory correlations."""
    obs_list = [
        ParentObservation(
            id="1", goal_id="g1", micro_routine_id="r1", patient_id="p1",
            meltdown_occurred=True, sensory_triggers=["tactile_defensiveness"],
            environment_context={"posture": "standing"},
        ),
        ParentObservation(
            id="2", goal_id="g1", micro_routine_id="r1", patient_id="p1",
            meltdown_occurred=True, sensory_triggers=["tactile_defensiveness"],
            environment_context={"posture": "standing"},
        ),
        ParentObservation(
            id="3", goal_id="g1", micro_routine_id="r1", patient_id="p1",
            meltdown_occurred=False, sensory_triggers=[],
            environment_context={"posture": "seated"},
        ),
        ParentObservation(
            id="4", goal_id="g1", micro_routine_id="r1", patient_id="p1",
            meltdown_occurred=False, sensory_triggers=[],
            environment_context={"posture": "seated"},
        ),
    ]

    analysis = SensoryIntentDecoder.analyze_sensory_patterns(obs_list)
    assert analysis["total_observations"] == 4
    assert analysis["meltdown_rate_pct"] == 50.0
    assert analysis["postural_correlation"]["standing"]["meltdown_rate_pct"] == 100.0
    assert analysis["postural_correlation"]["seated"]["meltdown_rate_pct"] == 0.0

    # Ensure postural correlation insight generated
    insights = " ".join(analysis["clinical_insights"])
    assert "postural correlation" in insights.lower()
    adaptations = " ".join(analysis["recommended_adaptations"])
    assert "seated" in adaptations.lower()


def test_rtm_compliance_tracker_cpt_98977_and_98980():
    """Verifies that RTM 16-day and 20-minute compliance calculations are precise."""
    now = datetime.now()
    month_str = now.strftime("%Y-%m")

    # Case 1: 10 days logged (<16) -> Not compliant
    obs_10 = [
        ParentObservation(
            id=f"o_{i}", goal_id="g1", micro_routine_id="r1", patient_id="p1",
            timestamp=(now - timedelta(days=i)).timestamp(),
        )
        for i in range(10)
    ]
    rec_non_compliant = RTMComplianceTracker.calculate_month_compliance(
        patient_id="p1",
        month_year=month_str,
        observations=obs_10,
        minutes_reviewed=15,
    )
    assert rec_non_compliant.is_compliant_98977 is False
    assert rec_non_compliant.is_compliant_98980 is False

    # Case 2: 17 unique days logged (>=16) + 25 mins reviewed (>=20) -> Fully compliant
    obs_17 = [
        ParentObservation(
            id=f"o_{i}", goal_id="g1", micro_routine_id="r1", patient_id="p1",
            timestamp=(now - timedelta(days=i)).timestamp(),
        )
        for i in range(17)
    ]
    rec_compliant = RTMComplianceTracker.calculate_month_compliance(
        patient_id="p1",
        month_year=month_str,
        observations=obs_17,
        minutes_reviewed=25,
    )
    assert rec_compliant.is_compliant_98977 is True
    assert rec_compliant.is_compliant_98980 is True


def test_payer_reauthorization_packet(sample_goal):
    """Verifies full Letter of Medical Necessity / Re-Authorization packet creation."""
    obs_list = [
        ParentObservation(
            id="1", goal_id=sample_goal.id, micro_routine_id="r1", patient_id=sample_goal.patient_id,
            timestamp=time.time() - (20 * 86400), assistance_level_observed=AssistanceLevel.MAXIMUM_ASSIST,
        ),
        ParentObservation(
            id="2", goal_id=sample_goal.id, micro_routine_id="r1", patient_id=sample_goal.patient_id,
            timestamp=time.time() - (5 * 86400), assistance_level_observed=AssistanceLevel.MINIMAL_ASSIST,
        ),
    ]

    compliance_records = [
        RTMComplianceRecord(
            patient_id=sample_goal.patient_id,
            month_year="2026-09",
            days_logged=17,
            is_compliant_98977=True,
            minutes_reviewed=22,
            is_compliant_98980=True,
        )
    ]

    packet = RTMComplianceTracker.generate_payer_reauthorization_packet(
        patient_id=sample_goal.patient_id,
        patient_name="Leo Vance",
        dob="2021-04-12",
        goal=sample_goal,
        observations=obs_list,
        compliance_records=compliance_records,
        therapist_name="Dr. Claire Robinson",
        clinic_name="Pediatric Step Ahead Therapy Center",
    )

    assert packet["patient_name"] == "Leo Vance"
    assert packet["delta_score"] == 2  # Min assist (4) - Max assist (2) = +2
    assert packet["compliant_rtm_months"] == 1
    assert "LETTER OF MEDICAL NECESSITY" in packet["narrative_text"]
    assert "CPT 98977" in packet["narrative_text"]
    assert "Pediatric Step Ahead Therapy Center" in packet["narrative_text"]
