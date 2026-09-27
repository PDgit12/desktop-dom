"""
RhythmBridge Pediatric Neuro-Therapy Package
============================================

Transforms clinical occupational therapy goals into 15-second music-cued
daily routines with bidirectional Intent Layer compilation:
  - Forward: Clinical Goal ──► 15-second Routine with NMT music anchors
  - Reverse: Parent Micro-Log ──► Objective Clinical SOAP & RTM billing
"""

from desktop_dom.assistant.pediatric.models import (
    ClinicalGoalCategory,
    AssistanceLevel,
    DailyRoutineType,
    AuditoryAnchorType,
    MusicCue,
    ClinicalGoal,
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

__all__ = [
    "ClinicalGoalCategory",
    "AssistanceLevel",
    "DailyRoutineType",
    "AuditoryAnchorType",
    "MusicCue",
    "ClinicalGoal",
    "MicroRoutine",
    "ParentObservation",
    "SOAPNote",
    "RTMComplianceRecord",
    "ForwardRoutineCompiler",
    "NMT_TEMPO_REGISTRY",
    "ReverseObservationCompiler",
    "SensoryIntentDecoder",
    "RTMComplianceTracker",
]
