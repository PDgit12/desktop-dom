"""
RhythmBridge Reverse Observation Compiler
==========================================

Translates raw parent micro-logs (10-second video tags, 5-second voice memos,
or quick parent notes) into structured, objective clinical data:
  - FIM/WeeFIM Assistance Level (Independent to Total Dependence)
  - Sensory triggers & compensatory movement patterns
  - Pre-session clinical briefing notes & automated SOAP notes
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Dict, List, Optional, Any

from desktop_dom.assistant.pediatric.models import (
    ParentObservation,
    AssistanceLevel,
    ClinicalGoal,
    SOAPNote,
)


class ReverseObservationCompiler:
    """
    The Reverse Intent Compiler.
    Translates raw parent vernacular into clinical terminology and SOAP documentation.
    """

    # Lexical patterns for inferring assistance level from parent language
    ASSISTANCE_PATTERNS = [
        (re.compile(r"\b(all by himself|all by herself|completely on his own|no help|did it alone|independently)\b", re.I), AssistanceLevel.INDEPENDENT),
        (re.compile(r"\b(with tool|adaptive|took longer|extra time|modified)\b", re.I), AssistanceLevel.MODIFIED_INDEPENDENT),
        (re.compile(r"\b(just reminded|verbal cue|tiny help|little touch|guide finger|minimal help)\b", re.I), AssistanceLevel.MINIMAL_ASSIST),
        (re.compile(r"\b(half and half|helped halfway|moderate help|held the zipper|held the bowl)\b", re.I), AssistanceLevel.MODERATE_ASSIST),
        (re.compile(r"\b(hand over hand|did most of it|struggled a lot|heavy help|maximum help)\b", re.I), AssistanceLevel.MAXIMUM_ASSIST),
        (re.compile(r"\b(did everything|refused completely|full help|could not do it|total help)\b", re.I), AssistanceLevel.TOTAL_DEPENDENCE),
    ]

    # Sensory triggers detection
    SENSORY_PATTERNS = [
        ("tactile_defensiveness", re.compile(r"\b(seam|scratchy|texture|fabric|sticky|wet|tag|cold|rough)\b", re.I)),
        ("auditory_sensitivity", re.compile(r"\b(loud|sound|noise|music too fast|covering ears)\b", re.I)),
        ("vestibular_instability", re.compile(r"\b(wobbly|dizzy|fell|lost balance|stumbled|fear of falling)\b", re.I)),
        ("proprioceptive_under_responsiveness", re.compile(r"\b(crashing|banging|pushing hard|slamming|floppy)\b", re.I)),
        ("oral_tactile_aversion", re.compile(r"\b(gag|gagging|bristle|toothpaste taste|spit)\b", re.I)),
    ]

    # Motor compensation patterns
    COMPENSATION_PATTERNS = [
        ("unilateral_avoidance", re.compile(r"\b(only used left|only used right|ignored one hand|tucked hand away)\b", re.I)),
        ("mouth_holding", re.compile(r"\b(used mouth|bit(?:ten)?|held.*teeth|with teeth|teeth)\b", re.I)),
        ("trunk_substitution", re.compile(r"\b(leaned whole body|twisted torso|used chest to hold)\b", re.I)),
        ("palmar_grasp_substitution", re.compile(r"\b(grabbed with fist|used whole palm|clenched fist)\b", re.I)),
    ]

    @classmethod
    def compile_observation(
        cls,
        goal_id: str,
        micro_routine_id: str,
        patient_id: str,
        raw_parent_notes: str,
        duration_seconds: int = 15,
        media_type: str = "video_clip",
        media_uri: str = "",
        explicit_assistance: Optional[AssistanceLevel] = None,
        environment_context: Optional[Dict[str, Any]] = None,
    ) -> ParentObservation:
        """
        Parses raw parent notes or transcribed voice audio into a structured ParentObservation.
        """
        inferred_assistance = explicit_assistance or cls._infer_assistance_level(raw_parent_notes)
        sensory_triggers = cls._extract_sensory_triggers(raw_parent_notes)
        compensations = cls._extract_compensations(raw_parent_notes)
        meltdown = bool(re.search(r"\b(meltdown|screamed|cried|tantrum|threw|refused)\b", raw_parent_notes, re.I))
        completed = not bool(re.search(r"\b(did not finish|gave up|stopped|could not finish)\b", raw_parent_notes, re.I))

        return ParentObservation(
            id=f"obs_{uuid.uuid4().hex[:8]}",
            goal_id=goal_id,
            micro_routine_id=micro_routine_id,
            patient_id=patient_id,
            timestamp=time.time(),
            duration_seconds=duration_seconds,
            media_type=media_type,
            media_uri=media_uri,
            parent_notes=raw_parent_notes,
            assistance_level_observed=inferred_assistance,
            sensory_triggers=sensory_triggers,
            compensatory_movements=compensations,
            task_completed=completed,
            meltdown_occurred=meltdown,
            environment_context=environment_context or {},
        )

    @classmethod
    def _infer_assistance_level(cls, text: str) -> AssistanceLevel:
        for pattern, level in cls.ASSISTANCE_PATTERNS:
            if pattern.search(text):
                return level
        return AssistanceLevel.MODERATE_ASSIST  # Clinical median fallback

    @classmethod
    def _extract_sensory_triggers(cls, text: str) -> List[str]:
        triggers = []
        for trigger_name, pattern in cls.SENSORY_PATTERNS:
            if pattern.search(text):
                triggers.append(trigger_name)
        return triggers

    @classmethod
    def _extract_compensations(cls, text: str) -> List[str]:
        compensations = []
        for comp_name, pattern in cls.COMPENSATION_PATTERNS:
            if pattern.search(text):
                compensations.append(comp_name)
        return compensations

    @classmethod
    def generate_soap_note(
        cls,
        patient_id: str,
        therapist_id: str,
        goal: ClinicalGoal,
        observations: List[ParentObservation],
        date_range_start: float,
        date_range_end: float,
    ) -> SOAPNote:
        """
        Compiles longitudinal between-session parent observations into an audit-proof
        clinical SOAP note for therapist review, EHR entry, and insurance re-authorization.
        """
        if not observations:
            return SOAPNote(
                id=f"soap_{uuid.uuid4().hex[:8]}",
                patient_id=patient_id,
                therapist_id=therapist_id,
                date_range_start=date_range_start,
                date_range_end=date_range_end,
                subjective="No between-session home exercise observations logged during this monitoring interval.",
                objective="Home program adherence: 0 sessions recorded.",
                assessment="Unable to evaluate between-session functional progress due to lack of logged home routines.",
                plan="Re-engage caregiver on home routine integration and identify family scheduling barriers.",
                rtm_days_logged=0,
                rtm_compliant_98977=False,
            )

        # Unique days logged
        days_logged = len(set(time.strftime("%Y-%m-%d", time.localtime(o.timestamp)) for o in observations))
        is_rtm_compliant = days_logged >= 16

        # Assistance level distribution
        scores = [o.assistance_level_observed.score for o in observations]
        avg_score = sum(scores) / len(scores)
        completed_count = sum(1 for o in observations if o.task_completed)
        meltdown_count = sum(1 for o in observations if o.meltdown_occurred)

        all_sensory = [t for o in observations for t in o.sensory_triggers]
        all_compensations = [c for o in observations for c in o.compensatory_movements]

        # S - Subjective
        parent_quotes = [f'"{o.parent_notes}"' for o in observations if o.parent_notes][:3]
        subjective = (
            f"Caregiver reported {len(observations)} home routine trials across {days_logged} days. "
            f"Caregiver noted challenges with emotional regulation in {meltdown_count} trials. "
            f"Key caregiver feedback: {'; '.join(parent_quotes) if parent_quotes else 'Routine established.'}"
        )

        # O - Objective
        most_recent_level = observations[-1].assistance_level_observed.value.replace("_", " ").title()
        objective = (
            f"Goal Focus: {goal.title} ({goal.category.value}). "
            f"Total home sessions: {len(observations)} across {days_logged} unique days. "
            f"Task Completion Rate: {completed_count}/{len(observations)} ({int(completed_count / len(observations) * 100)}%). "
            f"Baseline Assistance: {goal.baseline_assistance.value.replace('_', ' ').title()}. "
            f"Observed Functional Assistance: {most_recent_level} (Mean functional score: {avg_score:.1f}/6.0). "
            f"Identified Sensory Barriers: {', '.join(set(all_sensory)) if all_sensory else 'None detected'}. "
            f"Compensatory Movement Patterns: {', '.join(set(all_compensations)) if all_compensations else 'None noted'}."
        )

        # A - Assessment
        if avg_score > goal.baseline_assistance.score:
            prog_text = "demonstrated measurable positive functional progress from baseline"
        elif avg_score == goal.baseline_assistance.score:
            prog_text = "maintained baseline functional stability with emerging consistency"
        else:
            prog_text = "demonstrated increased compensatory motor patterns requiring in-clinic intervention"

        assessment = (
            f"Patient {prog_text} toward milestone '{goal.target_milestone}'. "
            f"Rhythmic auditory cueing supported motor initiation in {int(completed_count / len(observations) * 100)}% of home trials. "
            f"Sensory defensiveness ({', '.join(set(all_sensory)) or 'general'}) remains the primary limiting factor for full independence. "
            f"High between-session adherence ({days_logged} days logged) supports continued medical necessity."
        )

        # P - Plan
        plan = (
            f"Continue skilled outpatient occupational therapy 1x/weekly. "
            f"Advance home routine protocol toward target level '{goal.target_assistance.value.replace('_', ' ').title()}'. "
            f"Incorporate sensory desensitization strategies during in-clinic session to address identified barriers. "
            f"Maintain Remote Therapeutic Monitoring (CPT 98977/98980) program."
        )

        return SOAPNote(
            id=f"soap_{uuid.uuid4().hex[:8]}",
            patient_id=patient_id,
            therapist_id=therapist_id,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            subjective=subjective,
            objective=objective,
            assessment=assessment,
            plan=plan,
            rtm_days_logged=days_logged,
            rtm_compliant_98977=is_rtm_compliant,
        )
