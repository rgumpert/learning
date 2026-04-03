"""
Diabetes clinical decision support.

Source: ADA Standards of Care in Diabetes — 2025
        (Diabetes Care, Vol 48, Supplement 1)
"""

from typing import List
from ..models import PatientData, Recommendation, Priority, RecType


def evaluate(pd: PatientData) -> List[Recommendation]:
    """Return diabetes-related recommendations for this patient."""
    recs: List[Recommendation] = []

    if not pd.has_diabetes:
        # Screening check for pre-diabetes risk
        if pd.a1c is not None and 5.7 <= pd.a1c <= 6.4:
            recs.append(Recommendation(
                category="diabetes",
                priority=Priority.ROUTINE,
                rec_type=RecType.MONITORING,
                text="A1C in pre-diabetes range (5.7–6.4%): initiate intensive lifestyle intervention.",
                rationale=f"A1C {pd.a1c}% indicates pre-diabetes. Metformin may be considered in high-risk individuals (BMI ≥35, prior GDM, age <60).",
                guideline="ADA 2025, Section 3: Prevention or Delay of Type 2 Diabetes",
            ))
        return recs

    # ------------------------------------------------------------------ #
    # A1C monitoring frequency
    # ------------------------------------------------------------------ #
    if pd.a1c is None:
        recs.append(Recommendation(
            category="diabetes",
            priority=Priority.URGENT,
            rec_type=RecType.LAB,
            text="Order A1C — no result on file.",
            rationale="A1C is essential to assess glycemic control and guide therapy.",
            guideline="ADA 2025, Section 6: Glycemic Goals",
        ))
    else:
        a1c_target = _a1c_target(pd)
        if pd.a1c > 9.0:
            recs.append(Recommendation(
                category="diabetes",
                priority=Priority.URGENT,
                rec_type=RecType.MEDICATION,
                text=f"A1C critically elevated ({pd.a1c}%): intensify therapy urgently. Consider adding injectable agent (GLP-1 RA or insulin).",
                rationale=f"A1C >9% indicates severe hyperglycemia. Patient-specific target is <{a1c_target}%.",
                guideline="ADA 2025, Section 9: Pharmacologic Approaches to Glycemic Treatment",
            ))
        elif pd.a1c > a1c_target:
            recs.append(Recommendation(
                category="diabetes",
                priority=Priority.ROUTINE,
                rec_type=RecType.MEDICATION,
                text=f"A1C {pd.a1c}% above goal (<{a1c_target}%): consider adding or intensifying glucose-lowering agent.",
                rationale="Step-up therapy per ADA algorithm when A1C above individualized target.",
                guideline="ADA 2025, Section 9",
            ))

    # ------------------------------------------------------------------ #
    # Medication selection
    # ------------------------------------------------------------------ #
    if not pd.on_metformin() and not _metformin_contraindicated(pd):
        recs.append(Recommendation(
            category="diabetes",
            priority=Priority.ROUTINE,
            rec_type=RecType.MEDICATION,
            text="Initiate metformin if not already prescribed (first-line agent).",
            rationale="Metformin remains first-line unless contraindicated (eGFR <30 is a contraindication; use caution eGFR 30–45).",
            guideline="ADA 2025, Section 9",
        ))

    # GLP-1 / SGLT2 preference in high-risk patients
    if pd.has_ascvd or pd.has_heart_failure or pd.has_ckd:
        if not pd.on_glp1() and not pd.on_sglt2():
            driver = "established ASCVD" if pd.has_ascvd else ("heart failure" if pd.has_heart_failure else "CKD")
            recs.append(Recommendation(
                category="diabetes",
                priority=Priority.ROUTINE,
                rec_type=RecType.MEDICATION,
                text=f"Add GLP-1 RA or SGLT2 inhibitor: patient has {driver}.",
                rationale=(
                    "GLP-1 RAs (semaglutide, liraglutide) and SGLT2 inhibitors (empagliflozin, dapagliflozin) "
                    "reduce major adverse cardiovascular events and/or CKD progression independent of glucose lowering. "
                    "SGLT2i preferred if HFrEF or CKD (eGFR 20–45+)."
                ),
                guideline="ADA 2025, Section 10: Cardiovascular Disease and Risk Management",
            ))
        elif pd.has_ckd and not pd.on_sglt2():
            recs.append(Recommendation(
                category="diabetes",
                priority=Priority.ROUTINE,
                rec_type=RecType.MEDICATION,
                text="Add SGLT2 inhibitor (e.g., dapagliflozin or empagliflozin) for CKD protection.",
                rationale="SGLT2 inhibitors reduce CKD progression and cardiovascular death in T2DM with CKD (eGFR ≥20).",
                guideline="ADA 2025, Section 11: Chronic Kidney Disease and Risk Management",
            ))

    # Obesity + T2DM: prefer GLP-1 RA
    if pd.bmi is not None and pd.bmi >= 30 and not pd.on_glp1():
        recs.append(Recommendation(
            category="diabetes",
            priority=Priority.ROUTINE,
            rec_type=RecType.MEDICATION,
            text=f"Consider GLP-1 RA or dual GIP/GLP-1 RA (tirzepatide) for weight-related benefit (BMI {pd.bmi}).",
            rationale="GLP-1 receptor agonists provide clinically significant weight loss (5–15%) in addition to glucose lowering.",
            guideline="ADA 2025, Section 8: Obesity and Weight Management",
        ))

    # Avoid sulfonylurea in elderly
    if pd.age >= 65 and pd.on_sulfonylurea():
        recs.append(Recommendation(
            category="diabetes",
            priority=Priority.URGENT,
            rec_type=RecType.MEDICATION,
            text="Consider deprescribing sulfonylurea: high hypoglycemia risk in patient ≥65 years.",
            rationale="Sulfonylureas carry elevated hypoglycemia and fall risk in older adults. Prefer safer agents.",
            guideline="ADA 2025, Section 13: Older Adults",
        ))

    # ------------------------------------------------------------------ #
    # Kidney monitoring
    # ------------------------------------------------------------------ #
    if pd.egfr is None:
        recs.append(Recommendation(
            category="diabetes",
            priority=Priority.ROUTINE,
            rec_type=RecType.LAB,
            text="Order eGFR (serum creatinine) — no result on file.",
            rationale="Annual kidney function assessment is standard of care in diabetes.",
            guideline="ADA 2025, Section 11",
        ))
    elif pd.egfr < 30:
        recs.append(Recommendation(
            category="diabetes",
            priority=Priority.URGENT,
            rec_type=RecType.REFERRAL,
            text=f"Refer to nephrology: eGFR {pd.egfr} mL/min/1.73m² (CKD stage 4–5).",
            rationale="eGFR <30 warrants nephrology co-management to plan for renal replacement therapy.",
            guideline="ADA 2025, Section 11",
        ))
    elif pd.egfr < 45 and pd.on_metformin():
        recs.append(Recommendation(
            category="diabetes",
            priority=Priority.URGENT,
            rec_type=RecType.MEDICATION,
            text=f"Review metformin dose: eGFR {pd.egfr} (caution <45, contraindicated <30).",
            rationale="Metformin accumulation risk increases as eGFR declines; reduce dose and monitor closely at eGFR 30–45.",
            guideline="ADA 2025, Section 11",
        ))

    if pd.uacr is None:
        recs.append(Recommendation(
            category="diabetes",
            priority=Priority.ROUTINE,
            rec_type=RecType.LAB,
            text="Order urine albumin-to-creatinine ratio (UACR) — no result on file.",
            rationale="Annual UACR screens for diabetic kidney disease.",
            guideline="ADA 2025, Section 11",
        ))
    elif pd.uacr >= 30:
        severity = "macroalbuminuria" if pd.uacr >= 300 else "microalbuminuria"
        recs.append(Recommendation(
            category="diabetes",
            priority=Priority.ROUTINE,
            rec_type=RecType.MEDICATION,
            text=f"UACR {pd.uacr} mg/g ({severity}): ensure ACEi/ARB is prescribed for renoprotection.",
            rationale="ACEi or ARB reduces progression of diabetic nephropathy in patients with albuminuria.",
            guideline="ADA 2025, Section 11",
        ))
        if not pd.on_acei_arb():
            recs.append(Recommendation(
                category="diabetes",
                priority=Priority.ROUTINE,
                rec_type=RecType.MEDICATION,
                text="Initiate ACE inhibitor or ARB for albuminuria and renoprotection.",
                rationale="First-line antihypertensive/renoprotective choice in diabetes with albuminuria.",
                guideline="ADA 2025, Section 11",
            ))

    # ------------------------------------------------------------------ #
    # Preventive monitoring
    # ------------------------------------------------------------------ #
    recs.append(Recommendation(
        category="diabetes",
        priority=Priority.ROUTINE,
        rec_type=RecType.REFERRAL,
        text="Ensure annual dilated eye exam (diabetic retinopathy screening).",
        rationale="Annual ophthalmic evaluation recommended for all patients with diabetes.",
        guideline="ADA 2025, Section 12: Retinopathy, Neuropathy, and Foot Care",
    ))
    recs.append(Recommendation(
        category="diabetes",
        priority=Priority.ROUTINE,
        rec_type=RecType.MONITORING,
        text="Perform comprehensive foot examination at each visit (monofilament, pulses, inspection).",
        rationale="Diabetic foot complications are largely preventable with regular clinical evaluation.",
        guideline="ADA 2025, Section 12",
    ))

    return recs


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _a1c_target(pd: PatientData) -> float:
    """Return the individualized A1C goal."""
    if pd.age >= 75 or (pd.has_ckd and pd.egfr is not None and pd.egfr < 30):
        return 8.5   # Less stringent for frail/advanced disease
    if pd.age >= 65 or pd.has_heart_failure:
        return 8.0
    return 7.0


def _metformin_contraindicated(pd: PatientData) -> bool:
    return pd.egfr is not None and pd.egfr < 30
