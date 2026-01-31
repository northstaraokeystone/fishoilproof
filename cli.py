#!/usr/bin/env python3
"""
FishOilProof CLI — Command-line interface for supply chain telemetry.

Commands:
  fishoil ingest <stage> <data_file>  — Create receipt for stage
  fishoil verify <lot_number>         — Verify full chain
  fishoil qr <lot_number>             — Generate QR payload
  fishoil demo                        — Run terminal demo
  fishoil --test                      — Emit test receipt
"""

import argparse
import json
import sys

from src.core import dual_hash, emit_receipt
from src.catch import create_catch_receipt
from src.processing import create_processing_receipt
from src.testing import create_testing_receipt
from src.encapsulation import create_encapsulation_receipt
from src.distribution import create_distribution_receipt, validate_cold_chain
from src.chain import verify_chain, generate_qr_payload
from src.fraud import run_all_fraud_checks


def cmd_test():
    """Emit a test receipt to verify core functions work."""
    receipt = emit_receipt("test", {
        "message": "FishOilProof test receipt",
        "dual_hash_check": dual_hash(b"test"),
    })
    print(json.dumps(receipt, indent=2))
    return receipt


def cmd_ingest(stage: str, data_file: str):
    """Ingest data for a given stage from a JSON file."""
    with open(data_file, "r") as f:
        data = json.load(f)

    creators = {
        "catch": _ingest_catch,
        "processing": _ingest_processing,
        "testing": _ingest_testing,
        "encapsulation": _ingest_encapsulation,
        "distribution": _ingest_distribution,
    }

    if stage not in creators:
        print(f"Unknown stage: {stage}. Valid: {', '.join(creators.keys())}", file=sys.stderr)
        sys.exit(1)

    receipt = creators[stage](data)
    print(json.dumps(receipt, indent=2))
    return receipt


def _ingest_catch(data: dict) -> dict:
    return create_catch_receipt(
        species=data["species"],
        fishery_registry=data["fishery_registry"],
        import_docs_hash=data["import_docs_hash"],
        fishery_cert_type=data.get("fishery_cert_type", "None"),
        fishery_cert_id=data.get("fishery_cert_id"),
        fishery_cert_hash=data.get("fishery_cert_hash"),
    )


def _ingest_processing(data: dict) -> dict:
    return create_processing_receipt(
        facility_id=data["facility_id"],
        facility_name=data["facility_name"],
        gmp_cert_type=data["gmp_cert_type"],
        gmp_cert_id=data["gmp_cert_id"],
        gmp_cert_hash=data["gmp_cert_hash"],
        batch_id=data["batch_id"],
        extraction_method=data["extraction_method"],
        extraction_temp_c=data["extraction_temp_c"],
        yield_input_kg=data["yield_input_kg"],
        yield_output_kg=data["yield_output_kg"],
        previous_hash=data["previous_hash"],
    )


def _ingest_testing(data: dict) -> dict:
    return create_testing_receipt(
        lab_name=data["lab_name"],
        lab_cert_type=data["lab_cert_type"],
        lab_cert_id=data["lab_cert_id"],
        lab_cert_hash=data["lab_cert_hash"],
        batch_id=data["batch_id"],
        mercury_ppm=data["mercury_ppm"],
        pcbs_ppm=data["pcbs_ppm"],
        dioxins_pg_per_g=data["dioxins_pg_per_g"],
        epa_mg=data["epa_mg"],
        dha_mg=data["dha_mg"],
        label_claim_mg=data["label_claim_mg"],
        peroxide_meq_per_kg=data["peroxide_meq_per_kg"],
        anisidine=data["anisidine"],
        previous_hash=data["previous_hash"],
    )


def _ingest_encapsulation(data: dict) -> dict:
    return create_encapsulation_receipt(
        facility_id=data["facility_id"],
        facility_name=data["facility_name"],
        facility_cert_type=data["facility_cert_type"],
        facility_cert_id=data["facility_cert_id"],
        facility_cert_hash=data["facility_cert_hash"],
        lot_number=data["lot_number"],
        fill_date=data["fill_date"],
        batch_id=data["batch_id"],
        capsule_count=data["capsule_count"],
        mg_per_capsule=data["mg_per_capsule"],
        previous_hash=data["previous_hash"],
    )


def _ingest_distribution(data: dict) -> dict:
    cold_chain = None
    if "cold_chain_temps" in data:
        cold_chain = validate_cold_chain(
            temps=data["cold_chain_temps"],
            duration_days=data.get("cold_chain_duration_days", 0),
            temp_log_hash=data.get("cold_chain_temp_log_hash"),
        )
    return create_distribution_receipt(
        distributor_id=data["distributor_id"],
        distributor_name=data["distributor_name"],
        warehouse_id=data["warehouse_id"],
        warehouse_location=data["warehouse_location"],
        lot_number=data["lot_number"],
        cold_chain_data=cold_chain,
        previous_hash=data["previous_hash"],
    )


def cmd_verify(lot_number: str):
    """Verify the full chain for a lot number."""
    result = verify_chain(lot_number)
    print(json.dumps(result, indent=2, default=str))

    if result["chain_valid"]:
        # Also run fraud checks
        chain = list(result["receipts"].values())
        anomalies = run_all_fraud_checks(chain)
        if anomalies:
            print(f"\nFraud checks found {len(anomalies)} anomalies:")
            for a in anomalies:
                print(f"  - {a['anomaly_type']}: {a.get('details', {}).get('message', '')}")
    return result


def cmd_qr(lot_number: str):
    """Generate QR payload for a lot number."""
    payload = generate_qr_payload(lot_number)
    print(payload)
    return payload


def cmd_demo():
    """Run the terminal demo."""
    from demo.terminal_demo import run_demo
    run_demo()


def main():
    parser = argparse.ArgumentParser(
        prog="fishoil",
        description="FishOilProof — Supply chain telemetry with receipts-native fraud detection",
    )

    parser.add_argument("--test", action="store_true", help="Emit a test receipt")

    subparsers = parser.add_subparsers(dest="command")

    # ingest
    ingest_parser = subparsers.add_parser("ingest", help="Create receipt for a stage")
    ingest_parser.add_argument("stage", choices=["catch", "processing", "testing", "encapsulation", "distribution"])
    ingest_parser.add_argument("data_file", help="Path to JSON data file")

    # verify
    verify_parser = subparsers.add_parser("verify", help="Verify full chain")
    verify_parser.add_argument("lot_number", help="Lot number to verify")

    # qr
    qr_parser = subparsers.add_parser("qr", help="Generate QR payload")
    qr_parser.add_argument("lot_number", help="Lot number")

    # demo
    subparsers.add_parser("demo", help="Run terminal demo for Jay")

    args = parser.parse_args()

    if args.test:
        cmd_test()
    elif args.command == "ingest":
        cmd_ingest(args.stage, args.data_file)
    elif args.command == "verify":
        cmd_verify(args.lot_number)
    elif args.command == "qr":
        cmd_qr(args.lot_number)
    elif args.command == "demo":
        cmd_demo()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
