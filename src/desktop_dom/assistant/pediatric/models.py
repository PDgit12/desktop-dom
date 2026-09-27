"""
RhythmBridge Data Models & Schemas
==================================

Defines the core data structures for pediatric clinical-to-home occupational therapy,
including clinical goals, music-cued routines, parent observations, sensory decoding,
and Medicare/Medicaid Remote Therapeutic Monitoring (RTM) compliance.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Any


class ClinicalGoalCategory(str, Enum):
    BILATERAL_COORDINATION = "bilateral_coordination"
    FINE_MOTOR_PINCER = "fine_motor_pincer"
    SENSORY_TOLERANCE = "sensory_tolerance"
    VESTIBULAR_REGULATION = "vestibular_regulation"
    POSTURAL_CONTROL = "postural_control"
    SELF_CARE_ADL = "self_care_adl"
    MOTOR_PLANNING_PRAXIS = "motor_planning_praxis"


class AssistanceLevel(str, Enum):
    INDEPENDENT = "independent"                        # 100% independent, safe, timely
    MODIFIED_INDEPENDENT = "modified_independent"      # Uses assistive device or extra time
    MINIMAL_ASSIST = "minimal_assist"                  # Patient does 75%+, needs 25% help
    MODERATE_ASSIST = "moderate_assist"                # Patient does 50%–74%, needs 50% help
    MAXIMUM_ASSIST = "maximum_assist"                  # Patient does 25%–49%, needs 75% help
    TOTAL_DEPENDENCE = "total_dependence"              # Patient does <25%, full physical assist

    @property
    def score(self) -> int:
        """Numeric rank from 1 (total dependence) to 6 (independent) for progress graphing."""
        scores = {
            AssistanceLevel.TOTAL_DEPENDENCE: 1,
            AssistanceLevel.MAXIMUM_ASSIST: 2,
            AssistanceLevel.MODERATE_ASSIST: 3,
            AssistanceLevel.MINIMAL_ASSIST: 4,
            AssistanceLevel.MODIFIED_INDEPENDENT: 5,
            AssistanceLevel.INDEPENDENT: 6,
        }
        return scores.get(self, 1)


class DailyRoutineType(str, Enum):
    MORNING_DRESSING = "morning_dressing"
    BREAKFAST_FEEDING = "breakfast_feeding"
    TEETH_BRUSHING = "teeth_brushing"
    SHOES_AND_COAT = "shoes_and_coat"
    BATH_TIME = "bath_time"
    BEDTIME_TRANSITION = "bedtime_transition"
    FREE_PLAY = "free_play"


class AuditoryAnchorType(str, Enum):
    ALERTING = "alerting"             # High energy, faster tempo (90–100 BPM) for morning motor arousal
    CALMING = "calming"               # Slow tempo (50–60 BPM) for sensory soothing and bedtime
    METRONOME_PACING = "metronome"     # Steady rhythmic pulse (70–80 BPM) for motor entrainment
    TRANSITION_CUE = "transition"     # Melodic chime to signal task switching


@dataclass
class MusicCue:
    title: str
    tempo_bpm: int
    rhythm_pattern: str
    duration_seconds: int
    auditory_anchor_type: AuditoryAnchorType
    key_signature: str = "C_Major"
    audio_asset_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["auditory_anchor_type"] = self.auditory_anchor_type.value
        return d


@dataclass
class ClinicalGoal:
    id: str
    patient_id: str
    title: str
    description: str
    category: ClinicalGoalCategory
    target_milestone: str
    baseline_assistance: AssistanceLevel
    current_assistance: AssistanceLevel
    target_assistance: AssistanceLevel
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "target_milestone": self.target_milestone,
            "baseline_assistance": self.baseline_assistance.value,
            "current_assistance": self.current_assistance.value,
            "target_assistance": self.target_assistance.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class MicroRoutine:
    id: str
    goal_id: str
    routine_type: DailyRoutineType
    title: str
    parent_instruction: str
    child_prompt: str
    music_cue: MusicCue
    expected_duration_seconds: int = 15
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "goal_id": self.goal_id,
            "routine_type": self.routine_type.value,
            "title": self.title,
            "parent_instruction": self.parent_instruction,
            "child_prompt": self.child_prompt,
            "music_cue": self.music_cue.to_dict(),
            "expected_duration_seconds": self.expected_duration_seconds,
            "created_at": self.created_at,
        }


@dataclass
class ParentObservation:
    id: str
    goal_id: str
    micro_routine_id: str
    patient_id: str
    timestamp: float = field(default_factory=time.time)
    duration_seconds: int = 15
    media_type: str = "video_clip"  # "video_clip", "voice_memo", "tap_only"
    media_uri: str = ""
    parent_notes: str = ""
    assistance_level_observed: AssistanceLevel = AssistanceLevel.MODERATE_ASSIST
    sensory_triggers: List[str] = field(default_factory=list)
    compensatory_movements: List[str] = field(default_factory=list)
    task_completed: bool = True
    meltdown_occurred: bool = False
    environment_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "goal_id": self.goal_id,
            "micro_routine_id": self.micro_routine_id,
            "patient_id": self.patient_id,
            "timestamp": self.timestamp,
            "duration_seconds": self.duration_seconds,
            "media_type": self.media_type,
            "media_uri": self.media_uri,
            "parent_notes": self.parent_notes,
            "assistance_level_observed": self.assistance_level_observed.value,
            "sensory_triggers": self.sensory_triggers,
            "compensatory_movements": self.compensatory_movements,
            "task_completed": self.task_completed,
            "meltdown_occurred": self.meltdown_occurred,
            "environment_context": self.environment_context,
        }


@dataclass
class SOAPNote:
    id: str
    patient_id: str
    therapist_id: str
    date_range_start: float
    date_range_end: float
    subjective: str
    objective: str
    assessment: str
    plan: str
    rtm_days_logged: int
    rtm_compliant_98977: bool
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "therapist_id": self.therapist_id,
            "date_range_start": self.date_range_start,
            "date_range_end": self.date_range_end,
            "subjective": self.subjective,
            "objective": self.objective,
            "assessment": self.assessment,
            "plan": self.plan,
            "rtm_days_logged": self.rtm_days_logged,
            "rtm_compliant_98977": self.rtm_compliant_98977,
            "created_at": self.created_at,
        }


@dataclass
class RTMComplianceRecord:
    patient_id: str
    month_year: str  # e.g. "2026-09"
    days_logged: int
    compliance_threshold_days: int = 16
    is_compliant_98977: bool = False
    minutes_reviewed: int = 0
    is_compliant_98980: bool = False
    payer_name: str = "Medicaid"
    last_updated: float = field(default_factory=time.time)

    def evaluate_compliance(self) -> None:
        self.is_compliant_98977 = self.days_logged >= self.compliance_threshold_days
        self.is_compliant_98980 = self.minutes_reviewed >= 20
        self.last_updated = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "month_year": self.month_year,
            "days_logged": self.days_logged,
            "compliance_threshold_days": self.compliance_threshold_days,
            "is_compliant_98977": self.is_compliant_98977,
            "minutes_reviewed": self.minutes_reviewed,
            "is_compliant_98980": self.is_compliant_98980,
            "payer_name": self.payer_name,
            "last_updated": self.last_updated,
        }
