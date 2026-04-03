"""
Metabolic dysfunction-associated steatotic liver disease (MASLD) —
formerly NAFLD/NASH — clinical decision support.

Sources:
  - AASLD Practice Guidance: NAFLD/NASH 2023
  - EASL–EASD–EASO Clinical Practice Guidelines for NAFLD 2023
  - FDA approval of resmetirom (Rezdiffra) for MASH F2–F3, March 2024
  - AGA Clinical Practice Guideline on MASLD 2023
"""

from typing import List
from ..models import PatientData, Recommendation, Priority, RecType


def evaluate(pd: PatientData) -> List[Recommendation]:
    recs: List[Recommendation] = []

    # Only evaluate if liver disease is flagged or there are metabolic triggers
    metabolic_risk = (
        pd.has_fatty_liver
        or (pd.bmi is not None and pd.bmi >= 30)
        or pd.has_diabetes
        or (pd.triglycerides is not None and pd.triglycerides >= 150)
        or (pd.alt is not None and pd.alt > _upper_normal_alt(pd))
    )

    if not metabolic_risk:
        return recs

    # ------------------------------------------------------------------ #
    # Liver enzyme screening
    # ------------------------------------------------------------------ #
    if pd.alt is None or pd.ast is None:
        recs.append(Recommendation(
            category="fatty_liver",
            priority=Priority.ROUTINE,
            rec_type=RecType.LAB,
            text="Order ALT and AST to screen for hepatic steatosis/injury in metabolic-risk patient.",
            rationale="Elevated transaminases are common in MASLD and guide risk stratification.",
            guideline="AASLD MASLD Guidance 2023",
        ))
    else:
        ult_alt = _upper_normal_alt(pd)
        if pd.alt > 2 * ult_alt or pd.ast > 2 * ult_alt:
            recs.append(Recommendation(
                category="fatty_liver",
                priority=Priority.ROUTINE,
                rec_type=RecType.LAB,
                text=f"Significantly elevated transaminases (ALT {pd.alt}, AST {pd.ast} U/L): evaluate for MASLD and other etiologies (hepatitis B/C, autoimmune hepatitis, drug-induced).",
                rationale="ALT or AST >2× ULN warrants further workup beyond steatosis.",
                guideline="AASLD MASLD Guidance 2023",
            ))

    # ------------------------------------------------------------------ #
    # FIB-4 score (fibrosis risk stratification)
    # ------------------------------------------------------------------ #
    fib4 = pd.fib4_score()
    if fib4 is not None:
        recs.extend(_fib4_recommendations(pd, fib4))
    elif pd.has_fatty_liver and pd.age is not None and pd.alt is not None and pd.ast is not None:
        if pd.platelets is None:
            recs.append(Recommendation(
                category="fatty_liver",
                priority=Priority.ROUTINE,
                rec_type=RecType.LAB,
                text="Order CBC (platelet count) to calculate FIB-4 fibrosis score.",
                rationale="FIB-4 = (age × AST) / (platelets × √ALT) is validated for non-invasive fibrosis staging in MASLD.",
                guideline="AASLD MASLD Guidance 2023; AGA Guideline 2023",
            ))

    # ------------------------------------------------------------------ #
    # Imaging
    # ------------------------------------------------------------------ #
    if pd.has_fatty_liver or (pd.bmi is not None and pd.bmi >= 35 and pd.has_diabetes):
        recs.append(Recommendation(
            category="fatty_liver",
            priority=Priority.ROUTINE,
            rec_type=RecType.PROCEDURE,
            text="Ensure hepatic steatosis has been confirmed by ultrasound or controlled attenuation parameter (CAP).",
            rationale="Non-invasive imaging confirms steatosis diagnosis before initiating MASLD-specific therapy.",
            guideline="AASLD MASLD Guidance 2023",
        ))

    # ------------------------------------------------------------------ #
    # Weight loss — cornerstone therapy
    # ------------------------------------------------------------------ #
    if pd.bmi is not None and pd.bmi >= 25:
        pct_goal = "≥10%" if pd.has_fatty_liver else "≥5%"
        recs.append(Recommendation(
            category="fatty_liver",
            priority=Priority.ROUTINE,
            rec_type=RecType.LIFESTYLE,
            text=f"Target {pct_goal} body weight reduction through caloric restriction and aerobic exercise.",
            rationale=(
                f"Weight loss of {pct_goal} reduces hepatic fat content; ≥10% loss can resolve MASH and reduce fibrosis. "
                "Hypocaloric diet (500–1000 kcal/day deficit) + 150–200 min/week moderate exercise."
            ),
            guideline="AASLD MASLD Guidance 2023; EASL NAFLD Guidelines 2023",
        ))

    # ------------------------------------------------------------------ #
    # Alcohol counseling
    # ------------------------------------------------------------------ #
    if pd.significant_alcohol:
        recs.append(Recommendation(
            category="fatty_liver",
            priority=Priority.URGENT,
            rec_type=RecType.LIFESTYLE,
            text="Counsel on complete alcohol cessation — alcohol use worsens steatohepatitis and fibrosis.",
            rationale="Alcohol is a direct hepatotoxin that dramatically accelerates MASLD progression to cirrhosis.",
            guideline="AASLD MASLD Guidance 2023",
        ))

    # ------------------------------------------------------------------ #
    # GLP-1 RA: preferred agent in MASLD + T2DM/obesity
    # ------------------------------------------------------------------ #
    if pd.has_diabetes or (pd.bmi is not None and pd.bmi >= 30):
        if not pd.on_glp1():
            recs.append(Recommendation(
                category="fatty_liver",
                priority=Priority.ROUTINE,
                rec_type=RecType.MEDICATION,
                text="Consider GLP-1 receptor agonist (semaglutide subcutaneous) — reduces liver fat and MASH activity.",
                rationale=(
                    "Semaglutide 2.4 mg weekly (NASH trial) reduced MASH resolution at 72 weeks vs. placebo. "
                    "Preferred in MASLD + T2DM or obesity for dual metabolic and hepatic benefit."
                ),
                guideline="AASLD MASLD Guidance 2023; NEJM 2021 (Semaglutide NASH trial)",
            ))

    # ------------------------------------------------------------------ #
    # Resmetirom — FDA-approved 2024 for MASH F2–F3
    # ------------------------------------------------------------------ #
    if pd.has_fatty_liver and fib4 is not None and fib4 >= 1.3:
        recs.append(Recommendation(
            category="fatty_liver",
            priority=Priority.ROUTINE,
            rec_type=RecType.MEDICATION,
            text="Consider resmetirom (Rezdiffra 80–100 mg daily) for confirmed MASH with F2–F3 fibrosis.",
            rationale=(
                "Resmetirom, a liver-directed THRβ agonist, is FDA-approved (March 2024) for MASH with "
                "moderate-to-advanced fibrosis (F2–F3). MAESTRO-NASH trial: 26% MASH resolution and 24% fibrosis "
                "improvement vs. placebo. Liver biopsy confirmation required before prescribing."
            ),
            guideline="FDA Approval 2024; NEJM 2024 MAESTRO-NASH Trial",
        ))

    # ------------------------------------------------------------------ #
    # Avoid hepatotoxic medications
    # ------------------------------------------------------------------ #
    recs.append(Recommendation(
        category="fatty_liver",
        priority=Priority.INFORMATIONAL,
        rec_type=RecType.MONITORING,
        text="Review medication list for hepatotoxic agents (amiodarone, methotrexate, tamoxifen, valproate); monitor LFTs periodically.",
        rationale="Drug-induced liver injury can mimic and exacerbate MASLD; periodic LFT monitoring is appropriate.",
        guideline="AASLD MASLD Guidance 2023",
    ))

    # ------------------------------------------------------------------ #
    # Referral to hepatology
    # ------------------------------------------------------------------ #
    if fib4 is not None and fib4 >= 2.67:
        recs.append(Recommendation(
            category="fatty_liver",
            priority=Priority.ROUTINE,
            rec_type=RecType.REFERRAL,
            text=f"Refer to hepatology: FIB-4 {fib4:.2f} suggests advanced fibrosis (F3–F4). Liver biopsy may be indicated.",
            rationale="FIB-4 ≥2.67 has high positive predictive value for advanced fibrosis (F3–F4). Specialist evaluation and liver biopsy recommended.",
            guideline="AASLD MASLD Guidance 2023; AGA Guideline 2023",
        ))

    return recs


# --------------------------------------------------------------------------- #
# FIB-4 interpretation
# --------------------------------------------------------------------------- #

def _fib4_recommendations(pd: PatientData, fib4: float) -> List[Recommendation]:
    recs: List[Recommendation] = []

    # Age-adjusted cutoffs (patients ≥65 use higher thresholds)
    low_cutoff = 2.0 if pd.age >= 65 else 1.3
    high_cutoff = 2.67

    if fib4 < low_cutoff:
        recs.append(Recommendation(
            category="fatty_liver",
            priority=Priority.INFORMATIONAL,
            rec_type=RecType.MONITORING,
            text=f"FIB-4 score {fib4:.2f} — low risk of advanced fibrosis. Repeat in 1–2 years.",
            rationale="FIB-4 <1.3 (or <2.0 if age ≥65) has high negative predictive value for advanced fibrosis in MASLD.",
            guideline="AASLD MASLD Guidance 2023",
        ))
    elif fib4 < high_cutoff:
        recs.append(Recommendation(
            category="fatty_liver",
            priority=Priority.ROUTINE,
            rec_type=RecType.PROCEDURE,
            text=f"FIB-4 score {fib4:.2f} — indeterminate range. Obtain liver stiffness measurement (FibroScan/MRE) for further stratification.",
            rationale="Indeterminate FIB-4 (1.3–2.67) requires secondary non-invasive testing before biopsy decision.",
            guideline="AGA Clinical Practice Guideline 2023",
        ))

    return recs


def _upper_normal_alt(pd: PatientData) -> float:
    """Sex-specific ALT upper limit of normal (AASLD 2023)."""
    return 25.0 if pd.sex == "F" else 35.0
