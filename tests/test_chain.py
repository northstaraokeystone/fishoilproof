"""Tests for Chain Verification + QR Generation."""

import json
import os
import tempfile
import pytest

from src.core import dual_hash
from src.catch import create_catch_receipt
from src.processing import create_processing_receipt
from src.testing import create_testing_receipt
from src.encapsulation import create_encapsulation_receipt
from src.distribution import create_distribution_receipt, validate_cold_chain
from src.chain import verify_chain, verify_single_receipt, get_chain_summary, generate_qr_payload


@pytest.fixture
def ledger():
    path = tempfile.mktemp(suffix=".jsonl")
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


def _build_full_chain(ledger_path: str, lot_number: str = "LOT-TEST-CHAIN-01"):
    """Helper: build a complete 5-receipt chain."""
    catch = create_catch_receipt(
        species="Engraulis ringens",
        fishery_registry="PRODUCE Peru",
        import_docs_hash=dual_hash(b"import_docs"),
        fishery_cert_type="MSC",
        fishery_cert_id="MSC-TEST",
        fishery_cert_hash=dual_hash(b"msc_cert"),
        ledger_path=ledger_path,
    )

    processing = create_processing_receipt(
        facility_id="FAC-01",
        facility_name="Test Facility",
        gmp_cert_type="NSF",
        gmp_cert_id="NSF-001",
        gmp_cert_hash=dual_hash(b"gmp_cert"),
        batch_id="BP-CHAIN-TEST",
        extraction_method="MolecularDistillation",
        extraction_temp_c=240.0,
        yield_input_kg=1000.0,
        yield_output_kg=147.0,
        previous_hash=catch["payload_hash"],
        ledger_path=ledger_path,
    )

    testing = create_testing_receipt(
        lab_name="Test Lab",
        lab_cert_type="ISO17025",
        lab_cert_id="ISO-001",
        lab_cert_hash=dual_hash(b"lab_cert"),
        batch_id="BP-CHAIN-TEST",
        mercury_ppm=0.02,
        pcbs_ppm=0.03,
        dioxins_pg_per_g=1.2,
        epa_mg=420,
        dha_mg=300,
        label_claim_mg=700,
        peroxide_meq_per_kg=3.0,
        anisidine=10.0,
        previous_hash=processing["payload_hash"],
        ledger_path=ledger_path,
    )

    encap = create_encapsulation_receipt(
        facility_id="BOT-01",
        facility_name="Test Bottling",
        facility_cert_type="NSF",
        facility_cert_id="NSF-BOT-001",
        facility_cert_hash=dual_hash(b"bottle_cert"),
        lot_number=lot_number,
        fill_date="2025-01-31T14:00:00Z",
        batch_id="BP-CHAIN-TEST",
        capsule_count=90,
        mg_per_capsule=1000.0,
        previous_hash=testing["payload_hash"],
        ledger_path=ledger_path,
    )

    cold_chain = validate_cold_chain([2.1, 2.3, 2.0], 90)
    dist = create_distribution_receipt(
        distributor_id="DIST-01",
        distributor_name="Test Dist",
        warehouse_id="WH-01",
        warehouse_location="Test City",
        lot_number=lot_number,
        cold_chain_data=cold_chain,
        previous_hash=encap["payload_hash"],
        ledger_path=ledger_path,
    )

    return catch, processing, testing, encap, dist


class TestVerifySingleReceipt:
    def test_valid_receipt(self, ledger):
        catch, *_ = _build_full_chain(ledger)
        assert verify_single_receipt(catch) is True

    def test_tampered_receipt(self, ledger):
        catch, *_ = _build_full_chain(ledger)
        catch["species"] = "Tampered Species"
        assert verify_single_receipt(catch) is False


class TestVerifyChain:
    def test_valid_chain(self, ledger):
        _build_full_chain(ledger)
        result = verify_chain("LOT-TEST-CHAIN-01", ledger_path=ledger)
        assert result["chain_valid"] is True
        assert result["chain_length"] == 5
        assert len(result["errors"]) == 0

    def test_nonexistent_lot(self, ledger):
        result = verify_chain("LOT-DOESNT-EXIST", ledger_path=ledger)
        assert result["chain_valid"] is False
        assert len(result["errors"]) > 0

    def test_tampered_chain(self, ledger):
        _build_full_chain(ledger)
        # Tamper with the ledger
        with open(ledger, "r") as f:
            lines = f.readlines()
        tampered = json.loads(lines[1])
        tampered["yield_output_kg"] = 999.0
        lines[1] = json.dumps(tampered) + "\n"
        with open(ledger, "w") as f:
            f.writelines(lines)

        result = verify_chain("LOT-TEST-CHAIN-01", ledger_path=ledger)
        # Chain should detect the tamper (hash mismatch)
        assert result["chain_valid"] is False


class TestGetChainSummary:
    def test_valid_summary(self, ledger):
        _build_full_chain(ledger)
        summary = get_chain_summary("LOT-TEST-CHAIN-01", ledger_path=ledger)
        assert summary["valid"] is True
        assert summary["species"] == "Peruvian Anchoveta"
        assert summary["fishery_certified"] is True
        assert summary["fishery_cert"] == "MSC"
        assert summary["contaminants_pass"] is True
        assert summary["potency_pass"] is True
        assert summary["yield_normal"] is True
        assert summary["cold_chain_verified"] is True

    def test_invalid_lot_summary(self, ledger):
        summary = get_chain_summary("LOT-NOPE", ledger_path=ledger)
        assert summary["valid"] is False


class TestGenerateQrPayload:
    def test_valid_qr(self, ledger):
        _build_full_chain(ledger)
        payload_str = generate_qr_payload("LOT-TEST-CHAIN-01", ledger_path=ledger)
        payload = json.loads(payload_str)
        assert payload["lot"] == "LOT-TEST-CHAIN-01"
        assert payload["chain_length"] == 5
        assert payload["species"] == "Peruvian Anchoveta"
        assert payload["fishery_certified"] is True
        assert payload["contaminants_pass"] is True
        assert payload["yield_normal"] is True
        assert payload["cold_chain_verified"] is True
        assert "verification_url" in payload

    def test_invalid_lot_qr(self, ledger):
        payload_str = generate_qr_payload("LOT-NOPE", ledger_path=ledger)
        payload = json.loads(payload_str)
        assert payload["valid"] is False
