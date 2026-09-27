"""
RhythmBridge Remote Therapeutic Monitoring (RTM) Tracker
=========================================================

Calculates and manages Medicare / Medicaid Remote Therapeutic Monitoring
compliance under CPT codes:
  - CPT 98975: Initial device setup & patient education (~$20)
  - CPT 98977: Monitoring device supply with scheduled recording(s) / transmission(s)
               requiring at least 16 days of data per 30-day monitoring window (~$55/mo)
  - CPT 98980: RTM treatment management services (first 20 mins of clinician time) (~$50/mo)

Also generates 1-click payer re-authorization evidence summaries for Medicaid / Commercial payers.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, List, Optional, Any

from desktop_dom.assistant.pediatric.models import (
    RTMComplianceRecord,
    ParentObservation,
    ClinicalGoal,
    AssistanceLevel,
)


class RTMComplianceTracker:
    """
    Manages RTM compliance logic, billing eligibility, and audit trail generation.
    """

    @classmethod
    def calculate_month_compliance(
        cls,
        patient_id: str,
        month_year: str,  # Format "YYYY-MM"
        observations: List[ParentObservation],
        minutes_reviewed: int = 0,
        payer_name: str = "Medicaid",
    ) -> RTMComplianceRecord:
        """
        Determines if a patient qualifies for CPT 98977 and CPT 98980 for a specific calendar month.
        """
        # Filter observations to target month
        matching_obs = []
        for o in observations:
            dt = datetime.fromtimestamp(o.timestamp)
            if dt.strftime("%Y-%m") == month_year:
                matching_obs.append(o)

        unique_days = len(set(datetime.fromtimestamp(o.timestamp).strftime("%Y-%m-%d") for o in matching_obs))

        record = RTMComplianceRecord(
            patient_id=patient_id,
            month_year=month_year,
            days_logged=unique_days,
            compliance_threshold_days=16,
            minutes_reviewed=minutes_reviewed,
            payer_name=payer_name,
        )
        record.evaluate_compliance()
        return record

    @classmethod
    def generate_payer_reauthorization_packet(
        cls,
        patient_id: str,
        patient_name: str,
        dob: str,
        goal: ClinicalGoal,
        observations: List[ParentObservation],
        compliance_records: List[RTMComplianceRecord],
        therapist_name: str,
        clinic_name: str,
    ) -> Dict[str, Any]:
        """
        Compiles an audit-proof Letter of Medical Necessity / Re-Authorization packet
        to ensure continued coverage from Medicaid Managed Care or Commercial Insurers.
        """
        total_home_sessions = len(observations)
        total_days_logged = len(set(datetime.fromtimestamp(o.timestamp).strftime("%Y-%m-%d") for o in observations))
        
        # Calculate assistance trajectory
        if observations:
            initial_assistance = observations[0].assistance_level_observed
            current_assistance = observations[-1].assistance_level_observed
            baseline_score = goal.baseline_assistance.score
            latest_score = current_assistance.score
            delta_score = latest_score - baseline_score
        else:
            initial_assistance = goal.baseline_assistance
            current_assistance = goal.current_assistance
            delta_score = 0

        # RTM billing eligibility tally
        compliant_months = sum(1 for r in compliance_records if r.is_compliant_98977)

        summary_text = (
            f"LETTER OF MEDICAL NECESSITY & FUNCTIONAL PROGRESS RE-AUTHORIZATION\n"
            f"Patient: {patient_name} (DOB: {dob}) | ID: {patient_id}\n"
            f"Provider: {therapist_name}, MS, OTR/L | Facility: {clinic_name}\n"
            f"Diagnosis / Plan of Care: Outpatient Pediatric Occupational Therapy\n"
            f"Target Goal: {goal.title} ({goal.target_milestone})\n\n"
            f"1. OBJECTIVE HOME ADHERENCE & ENGAGEMENT:\n"
            f"Between in-clinic sessions, patient completed {total_home_sessions} guided home therapy trials "
            f"across {total_days_logged} discrete days via the RhythmBridge neuro-developmental platform. "
            f"Patient achieved Remote Therapeutic Monitoring (CPT 98977) compliance in {compliant_months} billing cycle(s).\n\n"
            f"2. QUANTITATIVE FUNCTIONAL TRAJECTORY:\n"
            f"• Baseline Level of Assist: {goal.baseline_assistance.value.replace('_', ' ').title()}\n"
            f"• Current Verified Level of Assist: {current_assistance.value.replace('_', ' ').title()}\n"
            f"• Target Milestone: {goal.target_assistance.value.replace('_', ' ').title()}\n"
            f"• Functional Score Delta: {('+' if delta_score >= 0 else '')}{delta_score} level(s) toward independence.\n\n"
            f"3. MEDICAL NECESSITY JUSTIFICATION:\n"
            f"The patient demonstrates measurable functional generalization to the home environment when guided by "
            f"rhythmic auditory cues. Continued skilled occupational therapy is medically necessary to advance from "
            f"'{current_assistance.value.replace('_', ' ').title()}' to the target milestone '{goal.target_assistance.value.replace('_', ' ').title()}' "
            f"and eliminate residual sensory-motor compensatory patterns.\n\n"
            f"Recommendation: Authorize an additional 24 sessions of skilled outpatient OT (CPT 97530, 97535) "
            f"and ongoing Remote Therapeutic Monitoring (CPT 98977, 98980)."
        )

        return {
            "patient_id": patient_id,
            "patient_name": patient_name,
            "packet_title": f"Re-Authorization Packet - {patient_name}",
            "generated_at": time.time(),
            "total_home_sessions": total_home_sessions,
            "total_days_logged": total_days_logged,
            "baseline_assistance": goal.baseline_assistance.value,
            "current_assistance": current_assistance.value,
            "target_milestone": goal.target_milestone,
            "delta_score": delta_score,
            "compliant_rtm_months": compliant_months,
            "narrative_text": summary_text,
        }
