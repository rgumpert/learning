"""
Demo: Run the cardiometabolic CDS engine against all mock patients.

Usage:
    cd learning/
    python -m cardiometabolic_cds.demo

To target a specific patient:
    python -m cardiometabolic_cds.demo pt_complex_dm

To use a real FHIR server:
    export FHIR_BASE_URL=https://your-ehr.org/fhir
    export FHIR_TOKEN=your_bearer_token
    python -m cardiometabolic_cds.demo <fhir_patient_id> --live
"""

import sys
from .ehr.mock_client import MockEHRClient
from .ehr.fhir_client import FHIRClient
from . import engine


def run_mock(patient_id: str | None = None) -> None:
    client = MockEHRClient()
    ids = [patient_id] if patient_id else client.list_patients()

    for pid in ids:
        try:
            pd = client.get_patient(pid)
        except KeyError as e:
            print(e)
            sys.exit(1)

        recs = engine.evaluate(pd)
        report = engine.format_report(pd, recs)
        print(report)
        print()


def run_live(patient_id: str) -> None:
    client = FHIRClient()
    pd = client.get_patient(patient_id)
    recs = engine.evaluate(pd)
    report = engine.format_report(pd, recs)
    print(report)


if __name__ == "__main__":
    args = sys.argv[1:]
    live = "--live" in args
    args = [a for a in args if a != "--live"]

    patient_id = args[0] if args else None

    if live:
        if not patient_id:
            print("Error: --live requires a patient ID.")
            sys.exit(1)
        run_live(patient_id)
    else:
        run_mock(patient_id)
