"""
FHIR R4 EHR integration client.

Connects to any FHIR R4-compliant server (Epic, Cerner, MEDITECH, etc.)
and assembles a PatientData object from the patient's active record.

Authentication: supports Bearer token (SMART on FHIR) or Basic auth.
Set via environment variables:
    FHIR_BASE_URL  — base URL of the FHIR server, e.g. https://ehr.example.org/fhir
    FHIR_TOKEN     — Bearer token (preferred)
    FHIR_USER / FHIR_PASS — for Basic auth fallback
"""

import os
import re
import requests
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from ..models import PatientData

# --------------------------------------------------------------------------- #
# LOINC codes used for lab / vital lookups
# --------------------------------------------------------------------------- #

LOINC = {
    "a1c":               ["4548-4", "17856-6"],
    "fasting_glucose":   ["1558-6", "76629-5", "2339-0"],
    "egfr":              ["98979-8", "62238-1", "88293-6"],
    "uacr":              ["14959-1", "32294-1"],
    "creatinine":        ["2160-0", "38483-4"],
    "ldl":               ["2089-1", "13457-7", "18262-6"],
    "hdl":               ["2085-9"],
    "total_cholesterol": ["2093-3"],
    "triglycerides":     ["2571-8"],
    "alt":               ["1742-6", "1743-4"],
    "ast":               ["1920-8"],
    "platelets":         ["777-3"],
    "potassium":         ["2823-3"],
    "systolic_bp":       ["8480-6"],
    "diastolic_bp":      ["8462-4"],
    "bmi":               ["39156-5"],
    "weight_kg":         ["29463-7", "3141-9"],
}

# --------------------------------------------------------------------------- #
# ICD-10 prefix patterns for condition flags
# --------------------------------------------------------------------------- #

CONDITION_FLAGS = {
    "has_diabetes":      re.compile(r"^E1[0-3]"),
    "has_hypertension":  re.compile(r"^I1[0-6]"),
    "has_hyperlipidemia": re.compile(r"^E78"),
    "has_ascvd":         re.compile(r"^(I2[01234]|I6[0-6]|I70|I73|I74|Z86\.7[39])"),
    "has_heart_failure": re.compile(r"^I50"),
    "has_ckd":           re.compile(r"^N18"),
    "has_fatty_liver":   re.compile(r"^K76\.0|^K75\.81"),
}

SMOKING_CODES = re.compile(r"^(F17|Z87\.891|Z72\.0)")
ALCOHOL_CODES = re.compile(r"^(F10|Z72\.1)")

# --------------------------------------------------------------------------- #
# Medication keywords for each drug class (lowercase match)
# --------------------------------------------------------------------------- #


class FHIRClient:
    """FHIR R4 client that builds a PatientData from a patient's chart."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 30,
    ):
        self.base_url = (base_url or os.getenv("FHIR_BASE_URL", "")).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/fhir+json"})

        token = token or os.getenv("FHIR_TOKEN")
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        else:
            user = username or os.getenv("FHIR_USER")
            pwd = password or os.getenv("FHIR_PASS")
            if user and pwd:
                self.session.auth = (user, pwd)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def get_patient(self, patient_id: str) -> PatientData:
        """Fetch and assemble a PatientData for the given FHIR patient ID."""
        raw_patient = self._get(f"Patient/{patient_id}")
        name, age, sex = self._parse_demographics(raw_patient)

        pd = PatientData(mrn=patient_id, name=name, age=age, sex=sex)

        # Labs & vitals (most-recent value wins)
        observations = self._all_pages(
            "Observation",
            params={
                "patient": patient_id,
                "status": "final,amended,corrected",
                "_sort": "-date",
                "_count": "200",
            },
        )
        self._apply_observations(pd, observations)

        # Conditions
        conditions = self._all_pages(
            "Condition",
            params={
                "patient": patient_id,
                "clinical-status": "active",
                "_count": "200",
            },
        )
        self._apply_conditions(pd, conditions)

        # Medications
        med_requests = self._all_pages(
            "MedicationRequest",
            params={
                "patient": patient_id,
                "status": "active",
                "_count": "200",
            },
        )
        self._apply_medications(pd, med_requests)

        return pd

    # ------------------------------------------------------------------ #
    # Internal HTTP helpers
    # ------------------------------------------------------------------ #

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict:
        url = f"{self.base_url}/{path}"
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _all_pages(self, resource_type: str, params: Dict) -> List[Dict]:
        """Follow FHIR pagination and collect all entries."""
        entries: List[Dict] = []
        bundle = self._get(resource_type, params=params)
        while bundle:
            for entry in bundle.get("entry", []):
                entries.append(entry.get("resource", {}))
            next_url = next(
                (
                    lnk["url"]
                    for lnk in bundle.get("link", [])
                    if lnk.get("relation") == "next"
                ),
                None,
            )
            if not next_url:
                break
            resp = self.session.get(next_url, timeout=self.timeout)
            resp.raise_for_status()
            bundle = resp.json()
        return entries

    # ------------------------------------------------------------------ #
    # Parsers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_demographics(patient: Dict):
        # Name
        names = patient.get("name", [])
        official = next((n for n in names if n.get("use") == "official"), names[0] if names else {})
        given = " ".join(official.get("given", []))
        family = official.get("family", "Unknown")
        name = f"{given} {family}".strip()

        # Age from birthDate
        dob_str = patient.get("birthDate", "")
        age = 0
        if dob_str:
            dob = datetime.strptime(dob_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - dob).days // 365

        # Sex
        sex_map = {"male": "M", "female": "F", "other": "O", "unknown": "U"}
        sex = sex_map.get(patient.get("gender", "").lower(), "U")

        return name, age, sex

    def _apply_observations(self, pd: PatientData, obs_list: List[Dict]) -> None:
        """Map FHIR Observations to PatientData fields (most-recent first)."""
        seen: set = set()  # track which fields already have a value

        for obs in obs_list:
            coding = []
            code_obj = obs.get("code", {})
            for c in code_obj.get("coding", []):
                if c.get("system", "").endswith("loinc.org"):
                    coding.append(c.get("code", ""))

            for field_name, loinc_codes in LOINC.items():
                if field_name in seen:
                    continue
                if any(code in loinc_codes for code in coding):
                    value = self._obs_value(obs)
                    if value is not None:
                        setattr(pd, field_name, value)
                        seen.add(field_name)

    @staticmethod
    def _obs_value(obs: Dict) -> Optional[float]:
        """Extract numeric value from an Observation resource."""
        if "valueQuantity" in obs:
            return obs["valueQuantity"].get("value")
        if "valueString" in obs:
            try:
                return float(re.search(r"[\d.]+", obs["valueString"]).group())
            except (AttributeError, ValueError):
                return None
        # Component observations (e.g. blood pressure)
        for comp in obs.get("component", []):
            val = comp.get("valueQuantity", {}).get("value")
            if val is not None:
                return val
        return None

    def _apply_conditions(self, pd: PatientData, conditions: List[Dict]) -> None:
        for cond in conditions:
            icd = self._icd10(cond)
            if icd:
                pd.conditions.append(icd)
                for flag, pattern in CONDITION_FLAGS.items():
                    if pattern.match(icd):
                        setattr(pd, flag, True)
                if SMOKING_CODES.match(icd):
                    pd.smoking = True
                if ALCOHOL_CODES.match(icd):
                    pd.significant_alcohol = True

    @staticmethod
    def _icd10(condition: Dict) -> Optional[str]:
        for coding in condition.get("code", {}).get("coding", []):
            system = coding.get("system", "")
            if "icd-10" in system.lower() or "icd10" in system.lower():
                return coding.get("code")
        return None

    def _apply_medications(self, pd: PatientData, med_requests: List[Dict]) -> None:
        for mr in med_requests:
            name = self._med_name(mr)
            if name:
                pd.medications.append(name)

    @staticmethod
    def _med_name(mr: Dict) -> Optional[str]:
        # Try medicationCodeableConcept first
        concept = mr.get("medicationCodeableConcept", {})
        for coding in concept.get("coding", []):
            disp = coding.get("display") or coding.get("code")
            if disp:
                # Append dose if available
                dose = ""
                dosage = mr.get("dosageInstruction", [{}])
                if dosage:
                    dose_qty = dosage[0].get("doseAndRate", [{}])
                    if dose_qty:
                        qty = dose_qty[0].get("doseQuantity", {})
                        val = qty.get("value")
                        unit = qty.get("unit", "mg")
                        if val:
                            dose = f" {val}{unit}"
                return f"{disp}{dose}"
        # Fallback to display text
        return mr.get("medicationReference", {}).get("display")
