"""
Hypertension clinical decision support.

Sources:
  - ACC/AHA 2017 High Blood Pressure Guideline
  - AHA/ACC 2023 Guideline for the Management of Patients with Chronic Coronary Disease
  - ADA Standards of Care 2025 (Section 10: Cardiovascular Disease)
  - JNC 8 (James et al., JAMA 2014) for CKD and diabetes targets
"""

from typing import List
from ..models import PatientData, Recommendation, Priority, RecType


def evaluate(pd: PatientData) -> List[Recommendation]:
    recs: List[Recommendation] = []

    sbp = pd.systolic_bp
    dbp = pd.diastolic_bp

    # ------------------------------------------------------------------ #
    # BP measurement available?
    # ------------------------------------------------------------------ #
    if sbp is None or dbp is None:
        if pd.has_hypertension or pd.has_diabetes or pd.has_ckd:
            recs.append(Recommendation(
                category="hypertension",
                priority=Priority.ROUTINE,
                rec_type=RecType.MONITORING,
                text="No BP value on file — obtain blood pressure reading at this visit.",
                rationale="Regular BP monitoring is essential in patients with hypertension, diabetes, or CKD.",
                guideline="ACC/AHA 2017 Hypertension Guideline",
            ))
        return recs

    # ------------------------------------------------------------------ #
    # Classification
    # ------------------------------------------------------------------ #
    stage = _bp_stage(sbp, dbp)
    target_sbp, target_dbp = _bp_target(pd)

    if stage == "crisis":
        recs.append(Recommendation(
            category="hypertension",
            priority=Priority.URGENT,
            rec_type=RecType.PROCEDURE,
            text=f"Hypertensive crisis: BP {sbp}/{dbp} mmHg — evaluate for end-organ damage immediately.",
            rationale="BP ≥180/120 mmHg requires urgent evaluation for hypertensive urgency vs. emergency.",
            guideline="ACC/AHA 2017, Section 10",
        ))
        return recs  # No additional recs until crisis resolved

    if sbp > target_sbp or dbp > target_dbp:
        recs.append(Recommendation(
            category="hypertension",
            priority=Priority.URGENT if stage == "stage2" else Priority.ROUTINE,
            rec_type=RecType.MEDICATION,
            text=f"BP {sbp}/{dbp} mmHg above goal (<{target_sbp}/{target_dbp}): {_intensification_text(pd, sbp)}",
            rationale=_bp_rationale(pd, target_sbp, target_dbp),
            guideline="ACC/AHA 2017; ADA 2025 Section 10",
        ))

    # ------------------------------------------------------------------ #
    # First-line agent recommendations
    # ------------------------------------------------------------------ #
    recs.extend(_med_recommendations(pd, sbp, dbp))

    # ------------------------------------------------------------------ #
    # Potassium monitoring (ACEi/ARB + CKD)
    # ------------------------------------------------------------------ #
    if pd.on_acei_arb() and pd.has_ckd:
        if pd.potassium is None:
            recs.append(Recommendation(
                category="hypertension",
                priority=Priority.ROUTINE,
                rec_type=RecType.LAB,
                text="Order serum potassium — patient on ACEi/ARB with CKD.",
                rationale="ACEi/ARBs can cause hyperkalemia; regular monitoring required in CKD.",
                guideline="ACC/AHA 2017, Section 9",
            ))
        elif pd.potassium > 5.5:
            recs.append(Recommendation(
                category="hypertension",
                priority=Priority.URGENT,
                rec_type=RecType.LAB,
                text=f"Hyperkalemia (K+ {pd.potassium} mEq/L) in patient on ACEi/ARB — reassess renoprotective agent.",
                rationale="K+ >5.5 mEq/L warrants dose reduction or switch to a non-RAASi antihypertensive.",
                guideline="ACC/AHA 2017",
            ))

    return recs


# --------------------------------------------------------------------------- #
# BP staging
# --------------------------------------------------------------------------- #

def _bp_stage(sbp: float, dbp: float) -> str:
    if sbp >= 180 or dbp >= 120:
        return "crisis"
    if sbp >= 160 or dbp >= 100:
        return "stage2"
    if sbp >= 140 or dbp >= 90:
        return "stage1_high"
    if sbp >= 130 or dbp >= 80:
        return "stage1"
    if sbp >= 120:
        return "elevated"
    return "normal"


def _bp_target(pd: PatientData):
    """Return (systolic_target, diastolic_target) based on patient profile."""
    # Diabetes or CKD: <130/80 (ADA 2025, JNC 8)
    if pd.has_diabetes or pd.has_ckd or pd.has_ascvd or pd.has_heart_failure:
        return 130, 80
    # General population: <130/80 per ACC/AHA 2017
    return 130, 80


# --------------------------------------------------------------------------- #
# Medication guidance
# --------------------------------------------------------------------------- #

def _intensification_text(pd: PatientData, sbp: float) -> str:
    if sbp >= 160 and not pd.on_acei_arb():
        return "initiate antihypertensive therapy; consider 2-drug combination given degree of elevation."
    return "intensify antihypertensive regimen (uptitrate dose or add second agent)."


def _bp_rationale(pd: PatientData, target_sbp: int, target_dbp: int) -> str:
    base = f"Target BP <{target_sbp}/{target_dbp} mmHg"
    if pd.has_diabetes:
        base += " in patients with diabetes (ADA 2025)"
    elif pd.has_ckd:
        base += " in patients with CKD (KDIGO 2021)"
    else:
        base += " per ACC/AHA 2017 guideline"
    return base + ". Each 10 mmHg reduction in SBP reduces major CV events by ~20%."


def _med_recommendations(pd: PatientData, sbp: float, dbp: float) -> List[Recommendation]:
    recs: List[Recommendation] = []
    has_bp_med = pd.on_acei_arb() or pd._on_any(
        "hydrochlorothiazide", "chlorthalidone", "amlodipine",
        "metoprolol", "carvedilol", "bisoprolol", "furosemide",
        "spironolactone", "nifedipine", "diltiazem", "verapamil"
    )

    # Diabetes or CKD: prefer ACEi or ARB
    if (pd.has_diabetes or pd.has_ckd) and not pd.on_acei_arb():
        recs.append(Recommendation(
            category="hypertension",
            priority=Priority.ROUTINE,
            rec_type=RecType.MEDICATION,
            text="Initiate ACE inhibitor or ARB as first-line antihypertensive.",
            rationale=(
                "ACEi/ARBs are preferred first-line agents in patients with diabetes or CKD "
                "due to renoprotective and cardioprotective benefits."
            ),
            guideline="ADA 2025 Section 10; KDIGO 2021",
        ))

    # Heart failure: ACEi/ARB + beta-blocker
    if pd.has_heart_failure:
        if not pd.on_acei_arb():
            recs.append(Recommendation(
                category="hypertension",
                priority=Priority.ROUTINE,
                rec_type=RecType.MEDICATION,
                text="Initiate ACEi/ARB/ARNI for heart failure with reduced ejection fraction (HFrEF).",
                rationale="Neurohormonal blockade with ACEi/ARB reduces mortality in HFrEF.",
                guideline="ACC/AHA/HFSA 2022 Heart Failure Guideline",
            ))
        if not pd._on_any("metoprolol", "carvedilol", "bisoprolol"):
            recs.append(Recommendation(
                category="hypertension",
                priority=Priority.ROUTINE,
                rec_type=RecType.MEDICATION,
                text="Add carvedilol, metoprolol succinate, or bisoprolol for heart failure management.",
                rationale="Evidence-based beta-blockers reduce mortality in HFrEF.",
                guideline="ACC/AHA/HFSA 2022",
            ))

    # ASCVD: beta-blocker after MI
    if pd.has_ascvd and not pd._on_any("metoprolol", "carvedilol", "bisoprolol", "atenolol"):
        recs.append(Recommendation(
            category="hypertension",
            priority=Priority.ROUTINE,
            rec_type=RecType.MEDICATION,
            text="Consider adding beta-blocker post-MI / established ASCVD.",
            rationale="Beta-blockers reduce recurrent MI and sudden cardiac death in ASCVD patients.",
            guideline="AHA/ACC 2023 Chronic Coronary Disease Guideline",
        ))

    # Elderly without compelling indication: prefer thiazide-type or CCB
    if pd.age >= 65 and not has_bp_med and not pd.has_diabetes and not pd.has_ckd:
        recs.append(Recommendation(
            category="hypertension",
            priority=Priority.ROUTINE,
            rec_type=RecType.MEDICATION,
            text="Initiate chlorthalidone or amlodipine as first-line antihypertensive in older adult.",
            rationale="Thiazide-type diuretics and CCBs have strong outcome data in elderly hypertensives (ALLHAT, ACCOMPLISH).",
            guideline="ACC/AHA 2017, Section 8",
        ))

    return recs
