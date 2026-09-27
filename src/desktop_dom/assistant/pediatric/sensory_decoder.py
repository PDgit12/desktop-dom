"""
RhythmBridge Sensory & Behavioral Intent Decoder
================================================

Analyzes longitudinal home observations to differentiate between behavioral refusal
and underlying sensory/motor dysregulation (postural instability, tactile defensiveness,
auditory overload). Surfaces hidden clinical root causes to the therapist.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
from collections import defaultdict

from desktop_dom.assistant.pediatric.models import (
    ParentObservation,
    ClinicalGoal,
    AssistanceLevel,
)


class SensoryIntentDecoder:
    """
    Decodes the child's behavioral resistance into actionable sensory & motor insights.
    """

    @classmethod
    def analyze_sensory_patterns(
        cls,
        observations: List[ParentObservation],
    ) -> Dict[str, Any]:
        """
        Analyzes observations to discover environmental and sensory correlations with meltdowns/refusals.
        """
        if not observations:
            return {
                "total_observations": 0,
                "meltdown_rate_pct": 0.0,
                "top_sensory_triggers": [],
                "postural_correlation": {},
                "clinical_insights": ["Insufficient data: no observations logged."],
                "recommended_adaptations": [],
            }

        total = len(observations)
        meltdowns = [o for o in observations if o.meltdown_occurred]
        meltdown_rate = (len(meltdowns) / total) * 100.0

        # Tally sensory triggers
        trigger_counts: Dict[str, int] = defaultdict(int)
        for o in observations:
            for t in o.sensory_triggers:
                trigger_counts[t] += 1

        # Posture correlation (e.g., standing vs seated)
        posture_meltdowns: Dict[str, int] = defaultdict(int)
        posture_totals: Dict[str, int] = defaultdict(int)

        for o in observations:
            posture = o.environment_context.get("posture", "unspecified")
            posture_totals[posture] += 1
            if o.meltdown_occurred:
                posture_meltdowns[posture] += 1

        posture_analysis = {}
        for p, count in posture_totals.items():
            rate = (posture_meltdowns[p] / count) * 100.0 if count > 0 else 0.0
            posture_analysis[p] = {
                "trials": count,
                "meltdowns": posture_meltdowns[p],
                "meltdown_rate_pct": round(rate, 1),
            }

        # Generate clinical insights
        insights = []
        adaptations = []

        # Check posture impact
        standing_data = posture_analysis.get("standing")
        seated_data = posture_analysis.get("seated")
        if standing_data and seated_data and standing_data["trials"] >= 2 and seated_data["trials"] >= 2:
            if standing_data["meltdown_rate_pct"] > seated_data["meltdown_rate_pct"] + 25:
                insights.append(
                    f"Strong postural correlation: Meltdown rate is {standing_data['meltdown_rate_pct']}% when standing vs {seated_data['meltdown_rate_pct']}% when seated."
                )
                adaptations.append(
                    "Switch task positioning to seated with firm foot support to eliminate balance/vestibular fatigue before fine motor engagement."
                )

        # Check top sensory trigger
        sorted_triggers = sorted(trigger_counts.items(), key=lambda x: x[1], reverse=True)
        if sorted_triggers:
            top_t, count = sorted_triggers[0]
            pct = round((count / total) * 100.0, 1)
            insights.append(f"Primary sensory barrier: '{top_t}' was present in {pct}% of logged sessions.")

            if "tactile" in top_t:
                adaptations.append("Apply deep pressure / firm joint compressions immediately prior to tactile contact; consider seamless clothing or desensitization.")
            elif "auditory" in top_t:
                adaptations.append("Reduce musical tempo to 50–55 BPM and lower volume; provide noise-dampening headphones during transition.")
            elif "vestibular" in top_t:
                adaptations.append("Provide a weighted lap pad or stable pelvic positioning prior to dynamic limb movement.")

        if not insights:
            insights.append(f"Child demonstrated stable behavioral regulation across {total} trials ({round(100 - meltdown_rate, 1)}% success).")

        return {
            "total_observations": total,
            "meltdown_rate_pct": round(meltdown_rate, 1),
            "top_sensory_triggers": [{"trigger": t, "count": c} for t, c in sorted_triggers],
            "postural_correlation": posture_analysis,
            "clinical_insights": insights,
            "recommended_adaptations": adaptations,
        }
