"""
Hyperlipidemia / dyslipidemia clinical decision support.

Source: 2019 ACC/AHA Guideline on the Primary Prevention of Cardiovascular Disease
        2018 ACC/AHA Guideline on the Management of Blood Cholesterol
        2023 ACC Expert Consensus Decision Pathway on Novel Therapies for LDL Lowering
"""

from typing import List
from ..models import PatientData, Recommendation, Priority, RecType


def evaluate(pd: PatientData) -> List[Recommendation]:
    recs: List[Recommendation] = []

    # ------------------------------------------------------------------ #
    # Missing labs
    # ------------------------------------------------------------------ #
    if pd.ldl is None and pd.total_cholesterol is None:
        recs.append(Recommendation(
            category="hyperlipidemia",
            priority=Priority.ROUTINE,
            rec_type=RecType.LAB,
            text="Order fasting lipid panel (LDL-C, HDL-C, TG, total cholesterol) — no results on file.",
            rationale="Lipid panel is required for ASCVD risk stratification and treatment decisions.",
            guideline="ACC/AHA 2018 Cholesterol Guideline",
        ))
        return recs

    risk_category = _risk_category(pd)
    ldl_target = _ldl_target(risk_category, pd)

    # ------------------------------------------------------------------ #
    # Triglycerides
    # ------------------------------------------------------------------ #
    if pd.triglycerides is not None:
        if pd.triglycerides >= 500:
            recs.append(Recommendation(
                category="hyperlipidemia",
                priority=Priority.URGENT,
                rec_type=RecType.MEDICATION,
                text=f"Severe hypertriglyceridemia (TG {pd.triglycerides} mg/dL): initiate fibrate or prescription omega-3 to reduce pancreatitis risk.",
                rationale="TG ≥500 mg/dL significantly raises risk of acute pancreatitis; fibrate therapy is first priority.",
                guideline="ACC/AHA 2018 Cholesterol Guideline, Section 7",
            ))
        elif pd.triglycerides >= 200:
            recs.append(Recommendation(
                category="hyperlipidemia",
                priority=Priority.ROUTINE,
                rec_type=RecType.LIFESTYLE,
                text=f"Elevated triglycerides ({pd.triglycerides} mg/dL): counsel on low-refined-carbohydrate diet, reduced alcohol, and weight loss.",
                rationale="Lifestyle modification is first-line for TG 200–499 mg/dL.",
                guideline="ACC/AHA 2018 Cholesterol Guideline, Section 7",
            ))

    # ------------------------------------------------------------------ #
    # LDL goal assessment
    # ------------------------------------------------------------------ #
    if pd.ldl is not None and ldl_target is not None:
        if pd.ldl > ldl_target:
            pct_reduction_needed = round(100 * (pd.ldl - ldl_target) / pd.ldl)
            recs.append(Recommendation(
                category="hyperlipidemia",
                priority=Priority.URGENT if risk_category == "very_high" and pd.ldl > 100 else Priority.ROUTINE,
                rec_type=RecType.MEDICATION,
                text=(
                    f"LDL {pd.ldl} mg/dL above goal (<{ldl_target} mg/dL) for {_risk_label(risk_category)} risk — "
                    f"~{pct_reduction_needed}% LDL reduction needed."
                ),
                rationale=f"Patient is {_risk_label(risk_category)} ASCVD risk. {_statin_guidance(pd, risk_category)}",
                guideline="ACC/AHA 2018 Cholesterol Guideline",
            ))

    # ------------------------------------------------------------------ #
    # Statin initiation / intensification
    # ------------------------------------------------------------------ #
    if not pd.on_statin():
        if risk_category in ("very_high", "high"):
            recs.append(Recommendation(
                category="hyperlipidemia",
                priority=Priority.ROUTINE,
                rec_type=RecType.MEDICATION,
                text=f"Initiate high-intensity statin (atorvastatin 40–80 mg or rosuvastatin 20–40 mg) for {_risk_label(risk_category)} ASCVD risk.",
                rationale="High-intensity statin reduces LDL ~50% and is guideline-recommended for very high / high ASCVD risk.",
                guideline="ACC/AHA 2018 Cholesterol Guideline, Section 4",
            ))
        elif risk_category == "intermediate":
            recs.append(Recommendation(
                category="hyperlipidemia",
                priority=Priority.ROUTINE,
                rec_type=RecType.MEDICATION,
                text="Initiate moderate-intensity statin (atorvastatin 10–20 mg, rosuvastatin 5–10 mg, or equivalent) for intermediate ASCVD risk.",
                rationale="10-year ASCVD risk ≥7.5–10% benefits from moderate-to-high intensity statin therapy.",
                guideline="ACC/AHA 2018 Cholesterol Guideline, Section 4",
            ))
    else:
        if risk_category in ("very_high", "high") and not pd.on_high_intensity_statin():
            recs.append(Recommendation(
                category="hyperlipidemia",
                priority=Priority.ROUTINE,
                rec_type=RecType.MEDICATION,
                text="Intensify to high-intensity statin (atorvastatin 40–80 mg or rosuvastatin 20–40 mg).",
                rationale=f"Patient is {_risk_label(risk_category)} ASCVD risk; high-intensity statin is recommended.",
                guideline="ACC/AHA 2018 Cholesterol Guideline",
            ))

    # ------------------------------------------------------------------ #
    # Add-on therapy: ezetimibe
    # ------------------------------------------------------------------ #
    if (
        pd.on_high_intensity_statin()
        and pd.ldl is not None
        and ldl_target is not None
        and pd.ldl > ldl_target
        and not pd.on_ezetimibe()
        and risk_category in ("very_high", "high")
    ):
        recs.append(Recommendation(
            category="hyperlipidemia",
            priority=Priority.ROUTINE,
            rec_type=RecType.MEDICATION,
            text="Add ezetimibe 10 mg: LDL remains above goal on maximally tolerated statin.",
            rationale="Ezetimibe reduces LDL an additional ~15–20% and reduces CV events when added to statin (IMPROVE-IT trial).",
            guideline="ACC/AHA 2018 Cholesterol Guideline; 2023 ACC Expert Consensus",
        ))

    # ------------------------------------------------------------------ #
    # PCSK9 inhibitor escalation
    # ------------------------------------------------------------------ #
    if (
        risk_category == "very_high"
        and pd.ldl is not None
        and pd.ldl > 70
        and pd.on_high_intensity_statin()
        and pd.on_ezetimibe()
        and not pd.on_pcsk9i()
    ):
        recs.append(Recommendation(
            category="hyperlipidemia",
            priority=Priority.ROUTINE,
            rec_type=RecType.MEDICATION,
            text="Consider PCSK9 inhibitor (evolocumab or alirocumab): LDL >70 mg/dL despite max statin + ezetimibe in very-high-risk patient.",
            rationale="PCSK9 inhibitors reduce LDL ~50–60% on top of statin; proven to reduce CV events (FOURIER, ODYSSEY trials).",
            guideline="2023 ACC Expert Consensus Decision Pathway on Novel Therapies for LDL Lowering",
        ))

    # ------------------------------------------------------------------ #
    # Lifestyle
    # ------------------------------------------------------------------ #
    recs.append(Recommendation(
        category="hyperlipidemia",
        priority=Priority.INFORMATIONAL,
        rec_type=RecType.LIFESTYLE,
        text="Reinforce heart-healthy diet (Mediterranean or DASH) and aerobic exercise ≥150 min/week.",
        rationale="Dietary and lifestyle modification reduces LDL 10–20% and should accompany pharmacotherapy.",
        guideline="ACC/AHA 2018 Cholesterol Guideline, Section 3",
    ))

    return recs


# --------------------------------------------------------------------------- #
# Risk stratification
# --------------------------------------------------------------------------- #

def _risk_category(pd: PatientData) -> str:
    """Simplified ACC/AHA ASCVD risk category."""
    if pd.has_ascvd:
        # Very high if recurrent events or multiple high-risk conditions
        if pd.has_diabetes or pd.has_ckd or (pd.ldl is not None and pd.ldl >= 100):
            return "very_high"
        return "high"
    if pd.has_diabetes and pd.age >= 40:
        return "high"
    if pd.has_ckd:
        return "high"
    rf = pd.traditional_cv_risk_factors()
    if rf >= 2:
        return "intermediate"
    if rf >= 1:
        return "borderline"
    return "low"


def _ldl_target(risk_category: str, pd: PatientData) -> int | None:
    targets = {
        "very_high": 55,
        "high": 70,
        "intermediate": 100,
        "borderline": 130,
        "low": None,   # lifestyle only; no specific pharmacologic target
    }
    return targets.get(risk_category)


def _risk_label(risk_category: str) -> str:
    labels = {
        "very_high": "very high",
        "high": "high",
        "intermediate": "intermediate",
        "borderline": "borderline",
        "low": "low",
    }
    return labels.get(risk_category, risk_category)


def _statin_guidance(pd: PatientData, risk_category: str) -> str:
    if not pd.on_statin():
        return "Initiate statin therapy."
    if not pd.on_high_intensity_statin():
        return "Intensify to high-intensity statin."
    if not pd.on_ezetimibe():
        return "Add ezetimibe to maximally tolerated statin."
    return "Consider PCSK9 inhibitor if LDL remains above goal."
