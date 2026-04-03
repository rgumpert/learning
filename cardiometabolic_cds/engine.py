"""
CDS Decision Engine — orchestrates all guideline modules and returns
a prioritized, deduplicated recommendation list.
"""

from typing import List
from .models import PatientData, Recommendation, Priority
from .guidelines import diabetes, hypertension, hyperlipidemia, fatty_liver

_PRIORITY_ORDER = {
    Priority.URGENT: 0,
    Priority.ROUTINE: 1,
    Priority.INFORMATIONAL: 2,
}

_CATEGORY_ORDER = {
    "diabetes": 0,
    "hypertension": 1,
    "hyperlipidemia": 2,
    "fatty_liver": 3,
}


def evaluate(pd: PatientData) -> List[Recommendation]:
    """Run all guideline modules and return sorted recommendations."""
    recs: List[Recommendation] = []

    recs.extend(diabetes.evaluate(pd))
    recs.extend(hypertension.evaluate(pd))
    recs.extend(hyperlipidemia.evaluate(pd))
    recs.extend(fatty_liver.evaluate(pd))

    recs.sort(key=lambda r: (
        _PRIORITY_ORDER.get(r.priority, 99),
        _CATEGORY_ORDER.get(r.category, 99),
    ))

    return recs


def format_report(pd: PatientData, recs: List[Recommendation]) -> str:
    """Render a plain-text clinical decision support report."""
    lines = [
        "=" * 70,
        f"  CLINICAL DECISION SUPPORT REPORT",
        f"  Patient: {pd.name}  |  MRN: {pd.mrn}  |  Age: {pd.age} {pd.sex}",
        "=" * 70,
        "",
        "  ACTIVE DATA SNAPSHOT",
        "-" * 70,
    ]

    def row(label, value, unit=""):
        disp = f"{value} {unit}".strip() if value is not None else "—"
        lines.append(f"  {label:<30} {disp}")

    row("A1C", pd.a1c, "%")
    row("Fasting glucose", pd.fasting_glucose, "mg/dL")
    row("eGFR", pd.egfr, "mL/min/1.73m²")
    row("UACR", pd.uacr, "mg/g")
    row("LDL-C", pd.ldl, "mg/dL")
    row("HDL-C", pd.hdl, "mg/dL")
    row("Triglycerides", pd.triglycerides, "mg/dL")
    row("ALT / AST", f"{pd.alt}/{pd.ast}" if pd.alt and pd.ast else None, "U/L")
    row("FIB-4 score", round(pd.fib4_score(), 2) if pd.fib4_score() else None)
    row("Blood pressure", f"{pd.systolic_bp}/{pd.diastolic_bp}" if pd.systolic_bp else None, "mmHg")
    row("BMI", pd.bmi, "kg/m²")

    fib4 = pd.fib4_score()
    if fib4:
        row("FIB-4 score", round(fib4, 2))

    lines.append("")

    if pd.conditions:
        lines.append(f"  Active conditions: {', '.join(pd.conditions)}")
    if pd.medications:
        lines.append(f"  Current medications: {', '.join(pd.medications)}")

    lines.append("")

    if not recs:
        lines.append("  No actionable recommendations at this time.")
        lines.append("=" * 70)
        return "\n".join(lines)

    # Group by priority
    for priority in (Priority.URGENT, Priority.ROUTINE, Priority.INFORMATIONAL):
        group = [r for r in recs if r.priority == priority]
        if not group:
            continue

        label = {
            Priority.URGENT: "!! URGENT",
            Priority.ROUTINE: "   ROUTINE",
            Priority.INFORMATIONAL: "   INFORMATIONAL",
        }[priority]

        lines.append(f"  RECOMMENDATIONS — {label}")
        lines.append("-" * 70)

        for i, rec in enumerate(group, 1):
            category_tag = rec.category.upper().replace("_", " ")
            lines.append(f"  [{i}] [{category_tag}] {rec.text}")
            lines.append(f"      Rationale: {rec.rationale}")
            lines.append(f"      Guideline:  {rec.guideline}")
            lines.append("")

    lines.append("=" * 70)
    lines.append("  ** This tool supports clinical decision-making but does not replace")
    lines.append("     physician judgment. Always apply clinical context. **")
    lines.append("=" * 70)

    return "\n".join(lines)
