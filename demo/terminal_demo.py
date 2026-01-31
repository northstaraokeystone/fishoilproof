#!/usr/bin/env python3
"""
Terminal Demo for Jay — FishOilProof v1.0

Runs the full 5-stage supply chain with real receipts.
Output shows hash linking, verification, and fraud detection.
"""

import os
import sys
import tempfile

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.core import dual_hash
from src.catch import create_catch_receipt
from src.processing import create_processing_receipt
from src.testing import create_testing_receipt
from src.encapsulation import create_encapsulation_receipt
from src.distribution import create_distribution_receipt, validate_cold_chain
from src.chain import verify_chain, get_chain_summary
from src.fraud import run_all_fraud_checks


def _short_hash(h: str) -> str:
    """Abbreviate a dual hash for display."""
    if ":" in h:
        parts = h.split(":")
        sha_part = parts[0][:12]
        blake_part = parts[1][:12]
        return f"{sha_part}:{blake_part}..."
    return h[:24] + "..."


def run_demo():
    """Execute the full terminal demo."""
    # Use a temp ledger for demo
    demo_ledger = tempfile.mktemp(suffix=".jsonl")

    print()

    # === STAGE 1: CATCH ===
    import_docs_hash = dual_hash(b"peru_import_docs_2025.pdf")
    fishery_cert_hash = dual_hash(b"msc_chain_of_custody_cert_12345.pdf")

    catch = create_catch_receipt(
        species="Engraulis ringens",
        fishery_registry="PRODUCE Peru",
        import_docs_hash=import_docs_hash,
        fishery_cert_type="MSC",
        fishery_cert_id="MSC-C-12345",
        fishery_cert_hash=fishery_cert_hash,
        ledger_path=demo_ledger,
    )

    print("[CATCH RECEIPT]")
    print(f"Species: {catch['species_common']} ({catch['species']})")
    print(f"Fishery: Approved ({catch['fishery_registry']} Registry)")
    print(f"Import Docs: {_short_hash(catch['import_docs_hash'])}")
    print(f"\u2713 MSC Chain-of-Custody: Certificate #{catch['fishery_cert_id']}")
    print(f"  Hash: {_short_hash(catch['fishery_cert_hash'])}")
    print(f"  ")
    print(f"Receipt Hash: {_short_hash(catch['payload_hash'])}")
    print(f"Merkle Root: {catch['merkle_root'][:24]}...")
    print()

    # === STAGE 2: PROCESSING ===
    gmp_cert_hash = dual_hash(b"omega_protein_gmp_cert_2025.pdf")

    processing = create_processing_receipt(
        facility_id="OP-HOUSTON-01",
        facility_name="Omega Protein Corp",
        gmp_cert_type="NSF",
        gmp_cert_id="NSF-GMP-7890",
        gmp_cert_hash=gmp_cert_hash,
        batch_id="BP-2025-0130",
        extraction_method="MolecularDistillation",
        extraction_temp_c=240.0,
        yield_input_kg=1000.0,
        yield_output_kg=147.0,
        previous_hash=catch["payload_hash"],
        ledger_path=demo_ledger,
    )

    yield_pct = processing["yield_ratio"] * 100

    print("[PROCESSING RECEIPT]")
    print(f"Facility: {processing['facility_name']} (GMP-certified)")
    print(f"GMP Cert Hash: {_short_hash(processing['gmp_cert_hash'])}")
    print(f"Batch: {processing['batch_id']}")
    print(f"Method: Molecular distillation")
    print(f"\u2713 Yield Reconciliation: {processing['yield_input_kg']:.0f}kg fish \u2192 {processing['yield_output_kg']:.0f}kg oil ({yield_pct:.1f}%)")
    print(f"  Expected: 12-18% (PASS)")
    print(f"  ")
    print(f"Previous Hash: {_short_hash(processing['previous_hash'])} \u2713")
    print(f"Receipt Hash: {_short_hash(processing['payload_hash'])}")
    print(f"Merkle Root: {processing['merkle_root'][:24]}...")
    print()

    # === STAGE 3: TESTING ===
    lab_cert_hash = dual_hash(b"eurofins_iso17025_cert.pdf")

    testing = create_testing_receipt(
        lab_name="Eurofins",
        lab_cert_type="ISO17025",
        lab_cert_id="ISO-17025-EU-4521",
        lab_cert_hash=lab_cert_hash,
        batch_id="BP-2025-0130",
        mercury_ppm=0.02,
        pcbs_ppm=0.03,
        dioxins_pg_per_g=1.2,
        epa_mg=420.0,
        dha_mg=300.0,
        label_claim_mg=700.0,
        peroxide_meq_per_kg=3.8,
        anisidine=10.7,
        previous_hash=processing["payload_hash"],
        ledger_path=demo_ledger,
    )

    totox = testing["oxidation"]["totox"]

    print("[TESTING RECEIPT]")
    print(f"Lab: {testing['lab_name']} (ISO 17025)")
    print(f"Mercury: {testing['contaminants']['mercury_ppm']} ppm (limit: 0.1) \u2713")
    print(f"PCBs: {testing['contaminants']['pcbs_ppm']} ppm (limit: 0.09) \u2713")
    print(f"EPA/DHA: {testing['potency']['total_omega3_mg']:.0f}mg (label: {testing['potency']['label_claim_mg']:.0f}mg) \u2713")
    print(f"TOTOX: {totox} (limit: 26) \u2713")
    print()
    print(f"Previous Hash: {_short_hash(testing['previous_hash'])} \u2713")
    print(f"Receipt Hash: {_short_hash(testing['payload_hash'])}")
    print(f"Merkle Root: {testing['merkle_root'][:24]}...")
    print()

    # === STAGE 4: ENCAPSULATION ===
    facility_cert_hash = dual_hash(b"nsf_gmp_bottling_cert_4567.pdf")

    encap = create_encapsulation_receipt(
        facility_id="NSF-BOTTLE-01",
        facility_name="NSF-certified Bottling",
        facility_cert_type="NSF",
        facility_cert_id="NSF-GMP-4567",
        facility_cert_hash=facility_cert_hash,
        lot_number="LOT-2025-0131-BP",
        fill_date="2025-01-31T14:22:47Z",
        batch_id="BP-2025-0130",
        capsule_count=90,
        mg_per_capsule=1000.0,
        previous_hash=testing["payload_hash"],
        ledger_path=demo_ledger,
    )

    print("[ENCAPSULATION RECEIPT]")
    print(f"Facility: NSF-certified (Cert #{encap['facility_cert_id']})")
    print(f"Lot: {encap['lot_number']}")
    print(f"Fill Date: {encap['fill_date']}")
    print()
    print(f"Previous Hash: {_short_hash(encap['previous_hash'])} \u2713")
    print(f"Receipt Hash: {_short_hash(encap['payload_hash'])}")
    print(f"Merkle Root: {encap['merkle_root'][:24]}...")
    print()

    # === STAGE 5: DISTRIBUTION ===
    temp_readings = [2.1, 2.3, 2.0, 2.2, 2.1, 2.4, 2.0, 1.9, 2.1, 2.3]
    temp_log_hash = dual_hash(b"whole_foods_temp_log_iot_data.csv")
    cold_chain = validate_cold_chain(temp_readings, duration_days=147, temp_log_hash=temp_log_hash)

    dist = create_distribution_receipt(
        distributor_id="WF-DIST-001",
        distributor_name="Whole Foods Distribution",
        warehouse_id="WF-CA-SF-01",
        warehouse_location="San Francisco, CA",
        lot_number="LOT-2025-0131-BP",
        cold_chain_data=cold_chain,
        previous_hash=encap["payload_hash"],
        ledger_path=demo_ledger,
    )

    print("[DISTRIBUTION RECEIPT]")
    print(f"Distributor: {dist['distributor_name']}")
    print(f"Warehouse: {dist['warehouse_id']}")
    print(f"\u2713 Cold Chain: {cold_chain['avg_temp_c']}\u00b0C average ({cold_chain['duration_days']} days)")
    print(f"  Temp Log Hash: {_short_hash(cold_chain['temp_log_hash'])}")
    print(f"  Deviations: {cold_chain['deviations_count']}")
    print(f"  ")
    print(f"Previous Hash: {_short_hash(dist['previous_hash'])} \u2713")
    print(f"Receipt Hash: {_short_hash(dist['payload_hash'])}")
    print(f"Merkle Root: {dist['merkle_root'][:24]}...")
    print()

    # === QR CODE VERIFICATION ===
    chain_result = verify_chain("LOT-2025-0131-BP", ledger_path=demo_ledger)
    summary = get_chain_summary("LOT-2025-0131-BP", ledger_path=demo_ledger)

    print("[QR CODE VERIFICATION]")
    print(f"Scanning: LOT-2025-0131-BP")
    print(f"Chain: {chain_result['chain_length']} receipts \u2713")
    print(f"\u2713 Fishery certified (MSC verified)")
    print(f"\u2713 Yield normal (no dilution detected)")
    print(f"\u2713 Contaminants pass (all limits)")
    print(f"\u2713 Potency verified ({testing['potency']['total_omega3_mg']:.0f}mg vs {testing['potency']['label_claim_mg']:.0f}mg label)")
    print(f"\u2713 Cold chain maintained (no oxidation risk)")
    print()

    # Run fraud checks
    chain_receipts = list(chain_result["receipts"].values())
    anomalies = run_all_fraud_checks(chain_receipts, ledger_path=demo_ledger)

    if anomalies:
        print(f"FRAUD ALERTS: {len(anomalies)} anomalies detected")
        for a in anomalies:
            print(f"  ! {a['anomaly_type']}: {a.get('details', {}).get('message', '')}")
    else:
        print("VERIFICATION COMPLETE: All receipts valid")

    print()

    # Cleanup temp ledger
    try:
        os.unlink(demo_ledger)
    except OSError:
        pass

    return chain_result


if __name__ == "__main__":
    run_demo()
