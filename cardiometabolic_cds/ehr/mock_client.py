"""
Mock EHR client with pre-built patient scenarios for local testing.

Usage:
    from cardiometabolic_cds.ehr.mock_client import MockEHRClient
    client = MockEHRClient()
    patient = client.get_patient("pt_complex_dm")
"""

from ..models import PatientData

MOCK_PATIENTS: dict[str, PatientData] = {

    # ------------------------------------------------------------------ #
    # 1. Well-controlled type 2 diabetic on metformin only
    # ------------------------------------------------------------------ #
    "pt_dm_controlled": PatientData(
        mrn="pt_dm_controlled",
        name="Maria Gomez",
        age=54,
        sex="F",
        a1c=6.8,
        fasting_glucose=112,
        egfr=72,
        uacr=18,
        ldl=98,
        hdl=52,
        total_cholesterol=168,
        triglycerides=130,
        systolic_bp=128,
        diastolic_bp=78,
        bmi=29.1,
        conditions=["E11.9", "E78.5", "I10"],
        medications=["Metformin 1000mg"],
        has_diabetes=True,
        has_hypertension=True,
        has_hyperlipidemia=True,
    ),

    # ------------------------------------------------------------------ #
    # 2. Poorly-controlled T2DM with CKD, hypertension, high CV risk
    # ------------------------------------------------------------------ #
    "pt_complex_dm": PatientData(
        mrn="pt_complex_dm",
        name="Robert Chen",
        age=67,
        sex="M",
        a1c=9.4,
        fasting_glucose=238,
        egfr=38,
        uacr=450,
        creatinine=1.9,
        ldl=142,
        hdl=36,
        total_cholesterol=210,
        triglycerides=310,
        alt=42,
        ast=38,
        platelets=185,
        systolic_bp=158,
        diastolic_bp=92,
        bmi=33.8,
        conditions=["E11.65", "N18.3", "I10", "E78.5", "K76.0"],
        medications=["Metformin 500mg", "Lisinopril 10mg", "Amlodipine 5mg"],
        has_diabetes=True,
        has_hypertension=True,
        has_ckd=True,
        has_hyperlipidemia=True,
        has_fatty_liver=True,
    ),

    # ------------------------------------------------------------------ #
    # 3. Post-MI patient with hyperlipidemia, on moderate statin
    # ------------------------------------------------------------------ #
    "pt_post_mi": PatientData(
        mrn="pt_post_mi",
        name="James Williams",
        age=61,
        sex="M",
        a1c=6.1,
        ldl=88,
        hdl=41,
        total_cholesterol=155,
        triglycerides=148,
        systolic_bp=122,
        diastolic_bp=74,
        bmi=27.4,
        conditions=["I21.9", "E78.5", "Z87.39"],
        medications=["Simvastatin 20mg", "Aspirin 81mg", "Metoprolol 50mg"],
        has_ascvd=True,
        has_hyperlipidemia=True,
        smoking=True,
    ),

    # ------------------------------------------------------------------ #
    # 4. Metabolic syndrome: obesity, fatty liver, borderline lipids, HTN
    # ------------------------------------------------------------------ #
    "pt_metabolic": PatientData(
        mrn="pt_metabolic",
        name="Angela Torres",
        age=45,
        sex="F",
        a1c=5.9,
        fasting_glucose=104,
        egfr=88,
        ldl=118,
        hdl=38,
        total_cholesterol=192,
        triglycerides=285,
        alt=68,
        ast=52,
        platelets=215,
        systolic_bp=138,
        diastolic_bp=88,
        bmi=37.2,
        weight_kg=102,
        conditions=["E66.01", "K76.0", "I10", "E78.1"],
        medications=["Hydrochlorothiazide 25mg"],
        has_hypertension=True,
        has_hyperlipidemia=True,
        has_fatty_liver=True,
    ),

    # ------------------------------------------------------------------ #
    # 5. Young T1DM with microalbuminuria, no statin
    # ------------------------------------------------------------------ #
    "pt_t1dm": PatientData(
        mrn="pt_t1dm",
        name="Priya Patel",
        age=32,
        sex="F",
        a1c=8.1,
        fasting_glucose=188,
        egfr=82,
        uacr=42,
        ldl=105,
        hdl=58,
        total_cholesterol=172,
        triglycerides=88,
        systolic_bp=134,
        diastolic_bp=84,
        bmi=23.1,
        conditions=["E10.65"],
        medications=["Insulin glargine 20 units", "Insulin lispro"],
        has_diabetes=True,
        has_hypertension=False,
    ),
}


class MockEHRClient:
    """Returns pre-built PatientData objects for testing and demonstration."""

    def get_patient(self, patient_id: str) -> PatientData:
        if patient_id not in MOCK_PATIENTS:
            raise KeyError(
                f"Unknown mock patient '{patient_id}'. "
                f"Available: {list(MOCK_PATIENTS.keys())}"
            )
        return MOCK_PATIENTS[patient_id]

    @staticmethod
    def list_patients() -> list[str]:
        return list(MOCK_PATIENTS.keys())
