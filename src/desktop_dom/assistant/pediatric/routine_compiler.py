"""
RhythmBridge Forward Routine Compiler
=====================================

Compiles complex pediatric clinical occupational therapy goals (e.g. bilateral
integration, fine motor pincer, sensory tolerance) into 15-second music-cued
routines that parents can effortlessly deliver within everyday household moments.
"""

from __future__ import annotations

import uuid
from typing import Dict, List, Optional, Any

from desktop_dom.assistant.pediatric.models import (
    ClinicalGoal,
    ClinicalGoalCategory,
    DailyRoutineType,
    MicroRoutine,
    MusicCue,
    AuditoryAnchorType,
    AssistanceLevel,
)


# Neurologic Music Therapy (NMT) Tempo & Rhythmic Anchors
NMT_TEMPO_REGISTRY: Dict[ClinicalGoalCategory, Dict[str, Any]] = {
    ClinicalGoalCategory.BILATERAL_COORDINATION: {
        "bpm": 76,
        "anchor": AuditoryAnchorType.METRONOME_PACING,
        "pattern": "quarter_pulse_alternating",
        "rationale": "Moderate 76 BPM pulse stabilizes motor timing between left and right hemispheres.",
    },
    ClinicalGoalCategory.FINE_MOTOR_PINCER: {
        "bpm": 64,
        "anchor": AuditoryAnchorType.METRONOME_PACING,
        "pattern": "steady_eighth_notes",
        "rationale": "Slower 64 BPM allows fine motor planning and distal finger isolation without rush.",
    },
    ClinicalGoalCategory.SENSORY_TOLERANCE: {
        "bpm": 58,
        "anchor": AuditoryAnchorType.CALMING,
        "pattern": "legato_soothing_arpeggio",
        "rationale": "Down-regulating 58 BPM reduces autonomic nervous system arousal during tactile exposure.",
    },
    ClinicalGoalCategory.VESTIBULAR_REGULATION: {
        "bpm": 88,
        "anchor": AuditoryAnchorType.ALERTING,
        "pattern": "sway_rhythm_3_4",
        "rationale": "Waltz 3/4 sway cadence provides organized vestibular input for balance.",
    },
    ClinicalGoalCategory.POSTURAL_CONTROL: {
        "bpm": 72,
        "anchor": AuditoryAnchorType.METRONOME_PACING,
        "pattern": "grounded_bass_pulse",
        "rationale": "Heavy downbeat reinforces core muscular engagement and proprioception.",
    },
    ClinicalGoalCategory.SELF_CARE_ADL: {
        "bpm": 80,
        "anchor": AuditoryAnchorType.TRANSITION_CUE,
        "pattern": "syncopated_playful",
        "rationale": "Playful 80 BPM cadence transforms self-care chores into game-like micro-rituals.",
    },
    ClinicalGoalCategory.MOTOR_PLANNING_PRAXIS: {
        "bpm": 68,
        "anchor": AuditoryAnchorType.METRONOME_PACING,
        "pattern": "call_and_response_percussion",
        "rationale": "Call-and-response rhythm breaks motor sequencing into digestible step-by-step units.",
    },
}


class ForwardRoutineCompiler:
    """
    The Forward Intent Compiler.
    Translates clinical terminology into a 15-second music-cued household activity.
    """

    @classmethod
    def compile_routine(
        cls,
        goal: ClinicalGoal,
        routine_type: DailyRoutineType,
        custom_child_interest: Optional[str] = None,
    ) -> MicroRoutine:
        """
        Synthesizes a MicroRoutine from clinical goal requirements and daily home routines.
        """
        music_profile = NMT_TEMPO_REGISTRY.get(
            goal.category,
            {
                "bpm": 75,
                "anchor": AuditoryAnchorType.METRONOME_PACING,
                "pattern": "steady_pulse",
                "rationale": "Standard developmental motor entrainment rhythm.",
            },
        )

        interest_theme = (custom_child_interest or "Space Rocket").title()

        title, parent_instruction, child_prompt = cls._generate_content(
            goal=goal,
            routine_type=routine_type,
            theme=interest_theme,
        )

        music_cue = MusicCue(
            title=f"{routine_type.name.replace('_', ' ').title()} - {music_profile['pattern']}",
            tempo_bpm=music_profile["bpm"],
            rhythm_pattern=music_profile["pattern"],
            duration_seconds=15,
            auditory_anchor_type=music_profile["anchor"],
            key_signature="C_Major",
            audio_asset_url=f"/assets/audio/nmt_{goal.category.value}_{music_profile['bpm']}bpm.mp3",
        )

        return MicroRoutine(
            id=f"routine_{uuid.uuid4().hex[:8]}",
            goal_id=goal.id,
            routine_type=routine_type,
            title=title,
            parent_instruction=parent_instruction,
            child_prompt=child_prompt,
            music_cue=music_cue,
            expected_duration_seconds=15,
        )

    @classmethod
    def _generate_content(
        cls,
        goal: ClinicalGoal,
        routine_type: DailyRoutineType,
        theme: str,
    ) -> tuple[str, str, str]:
        """Maps specific routine + clinical goal pairings to engaging micro-activities."""
        # 1. Shoes & Coat + Bilateral Coordination
        if routine_type == DailyRoutineType.SHOES_AND_COAT and goal.category == ClinicalGoalCategory.BILATERAL_COORDINATION:
            return (
                f"{theme} Zipper Launch",
                "Hold the bottom coat hem with your non-dominant hand. Guide the child's left hand to anchor the jacket while their right hand zips.",
                f"Anchor the launchpad with your left hand, and blast the {theme} rocket up with your right hand on the beat!",
            )

        # 2. Breakfast / Feeding + Fine Motor Pincer
        if routine_type == DailyRoutineType.BREAKFAST_FEEDING and goal.category == ClinicalGoalCategory.FINE_MOTOR_PINCER:
            return (
                f"{theme} Food Laser Pinch",
                "Place small bites (berries, cereal) on the plate. Encourage thumb-and-index finger pinch only (no palm raking).",
                f"Use your two {theme} laser pinchers (thumb and pointer) to grab one power fuel bite at a time!",
            )

        # 3. Teeth Brushing + Sensory Tolerance
        if routine_type == DailyRoutineType.TEETH_BRUSHING and goal.category == ClinicalGoalCategory.SENSORY_TOLERANCE:
            return (
                f"{theme} Tooth Polishing Beat",
                "Let the child hold the brush together with you. Brush the back molars for just 5 rhythmic beats, pause, and celebrate.",
                f"Clean the {theme} engines! 1, 2, 3, 4, 5... and freeze! You powered up the engine!",
            )

        # 4. Morning Dressing + Postural Control / Balance
        if routine_type == DailyRoutineType.MORNING_DRESSING and goal.category in (
            ClinicalGoalCategory.POSTURAL_CONTROL,
            ClinicalGoalCategory.VESTIBULAR_REGULATION,
        ):
            return (
                f"{theme} Stork Sock Step",
                "Have the child sit or stand while lifting one leg to slide into the sock. Support hips lightly for balance.",
                f"Lift your left landing gear into the cloud! Hold it steady until the chime rings!",
            )

        # 5. Bath Time + Bilateral / Self-Care
        if routine_type == DailyRoutineType.BATH_TIME:
            return (
                f"{theme} Splash Squeeze",
                "Give the child a damp washcloth. Model two-handed wringing (both hands twisting in opposite directions).",
                f"Two hands together! Squeeze all the water out of the {theme} cloud into the water!",
            )

        # Generic Fallback
        return (
            f"{theme} {routine_type.name.replace('_', ' ').title()}",
            f"Support your child during {routine_type.value.replace('_', ' ')}. Encourage active participation on the rhythmic beat.",
            f"Let's do our {theme} mission together! Follow the beat and finish before the music fades!",
        )
