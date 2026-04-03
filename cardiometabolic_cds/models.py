"""
Data models for the cardiometabolic CDS tool.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum
import math


class Priority(str, Enum):
    URGENT = "urgent"
    ROUTINE = "routine"
    INFORMATIONAL = "informational"


class RecType(str, Enum):
    LAB = "lab"
    MEDICATION = "medication"
    REFERRAL = "referral"
    MONITORING = "monitoring"
    LIFESTYLE = "lifestyle"
    PROCEDURE = "procedure"


@dataclass
class Recommendation:
    category: str          # "diabetes", "hypertension", "hyperlipidemia", "fatty_liver"
    priority: Priority
    rec_type: RecType
    text: str
    rationale: str
    guideline: str         # citation / source


@dataclass
class PatientData:
    # Demographics
    mrn: str
    name: str
    age: int
    sex: str               # "M" or "F"

    # Glycemia
    a1c: Optional[float] = None          # %
    fasting_glucose: Optional[float] = None  # mg/dL

    # Renal
    egfr: Optional[float] = None         # mL/min/1.73 m²
    uacr: Optional[float] = None         # mg/g
    creatinine: Optional[float] = None   # mg/dL

    # Lipids
    ldl: Optional[float] = None          # mg/dL
    hdl: Optional[float] = None          # mg/dL
    total_cholesterol: Optional[float] = None  # mg/dL
    triglycerides: Optional[float] = None     # mg/dL

    # Liver function
    alt: Optional[float] = None          # U/L
    ast: Optional[float] = None          # U/L
    platelets: Optional[float] = None    # K/µL

    # Electrolytes
    potassium: Optional[float] = None    # mEq/L

    # Vitals
    systolic_bp: Optional[float] = None  # mmHg
    diastolic_bp: Optional[float] = None # mmHg
    bmi: Optional[float] = None          # kg/m²
    weight_kg: Optional[float] = None

    # Active conditions (ICD-10 codes or SNOMED descriptions)
    conditions: List[str] = field(default_factory=list)

    # Active medications (generic names or RxNorm descriptions)
    medications: List[str] = field(default_factory=list)

    # Derived clinical flags — set by the FHIR client or manually
    has_diabetes: bool = False
    has_hypertension: bool = False
    has_hyperlipidemia: bool = False
    has_ascvd: bool = False          # MI, stroke, PAD, CAD
    has_heart_failure: bool = False
    has_ckd: bool = False
    has_fatty_liver: bool = False    # MASLD/NAFLD
    smoking: bool = False
    significant_alcohol: bool = False

    # ------------------------------------------------------------------ #
    # Derived calculations
    # ------------------------------------------------------------------ #

    def fib4_score(self) -> Optional[float]:
        """FIB-4 index for hepatic fibrosis risk stratification.

        Formula: (age × AST) / (platelets [K/µL] × √ALT)
        """
        if any(v is None for v in (self.age, self.ast, self.platelets, self.alt)):
            return None
        if self.alt <= 0 or self.platelets <= 0:
            return None
        return (self.age * self.ast) / (self.platelets * math.sqrt(self.alt))

    def traditional_cv_risk_factors(self) -> int:
        """Count of major traditional ASCVD risk factors."""
        count = 0
        if self.has_diabetes:
            count += 1
        if self.has_hypertension:
            count += 1
        if self.smoking:
            count += 1
        if self.hdl is not None and self.hdl < 40:
            count += 1
        return count

    # ------------------------------------------------------------------ #
    # Medication class helpers
    # ------------------------------------------------------------------ #

    def _on_any(self, *names: str) -> bool:
        meds_lower = [m.lower() for m in self.medications]
        return any(n in m for n in names for m in meds_lower)

    def on_metformin(self) -> bool:
        return self._on_any("metformin")

    def on_glp1(self) -> bool:
        return self._on_any(
            "semaglutide", "liraglutide", "dulaglutide",
            "tirzepatide", "exenatide", "albiglutide"
        )

    def on_sglt2(self) -> bool:
        return self._on_any(
            "empagliflozin", "dapagliflozin",
            "canagliflozin", "ertugliflozin"
        )

    def on_insulin(self) -> bool:
        return self._on_any("insulin")

    def on_sulfonylurea(self) -> bool:
        return self._on_any(
            "glipizide", "glyburide", "glimepiride",
            "glibenclamide", "tolbutamide"
        )

    def on_acei_arb(self) -> bool:
        return self._on_any(
            "lisinopril", "enalapril", "ramipril", "benazepril",
            "captopril", "quinapril", "fosinopril",
            "losartan", "valsartan", "olmesartan", "irbesartan",
            "candesartan", "telmisartan", "azilsartan"
        )

    def on_statin(self) -> bool:
        return self._on_any(
            "atorvastatin", "rosuvastatin", "simvastatin",
            "pravastatin", "lovastatin", "fluvastatin", "pitavastatin"
        )

    def on_high_intensity_statin(self) -> bool:
        meds_lower = [m.lower() for m in self.medications]
        for m in meds_lower:
            if "atorvastatin" in m:
                # high-intensity: 40–80 mg
                for dose in ["40", "80"]:
                    if dose in m:
                        return True
            if "rosuvastatin" in m:
                for dose in ["20", "40"]:
                    if dose in m:
                        return True
        return False

    def on_ezetimibe(self) -> bool:
        return self._on_any("ezetimibe")

    def on_pcsk9i(self) -> bool:
        return self._on_any("evolocumab", "alirocumab", "inclisiran")
