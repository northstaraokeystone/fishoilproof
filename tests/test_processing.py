"""Tests for Stage 2: Processing Receipt."""

import os
import tempfile
import pytest

from src.core import dual_hash, StopRule
from src.processing import (
    create_processing_receipt,
    validate_yield,
    YIELD_MIN,
    YIELD_MAX,
)


@pytest.fixture
def ledger():
    path = tempfile.mktemp(suffix=".jsonl")
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def gmp_hash():
    return dual_hash(b"test_gmp_cert.pdf")


@pytest.fixture
def previous_hash():
    return dual_hash(b"previous_catch_receipt")


class TestValidateYield:
    def test_normal_yield(self):
        ratio, status = validate_yield(1000, 147)
        assert ratio == pytest.approx(0.147, abs=0.001)
        assert status == "NORMAL"

    def test_low_yield(self):
        ratio, status = validate_yield(1000, 100)
        assert ratio == pytest.approx(0.1, abs=0.001)
        assert status == "LOW"

    def test_high_yield_dilution(self):
        ratio, status = validate_yield(1000, 220)
        assert ratio == pytest.approx(0.22, abs=0.001)
        assert status == "HIGH_DILUTION_FLAG"

    def test_boundary_low(self):
        ratio, status = validate_yield(1000, 120)
        assert status == "NORMAL"

    def test_boundary_high(self):
        ratio, status = validate_yield(1000, 180)
        assert status == "NORMAL"

    def test_just_below_min(self):
        ratio, status = validate_yield(1000, 119)
        assert status == "LOW"

    def test_just_above_max(self):
        ratio, status = validate_yield(1000, 181)
        assert status == "HIGH_DILUTION_FLAG"

    def test_zero_input_raises(self):
        with pytest.raises(StopRule, match="Invalid yield values"):
            validate_yield(0, 100)

    def test_negative_output_raises(self):
        with pytest.raises(StopRule, match="Invalid yield values"):
            validate_yield(1000, -10)


class TestCreateProcessingReceipt:
    def test_basic_receipt(self, ledger, gmp_hash, previous_hash):
        receipt = create_processing_receipt(
            facility_id="FAC-01",
            facility_name="Test Facility",
            gmp_cert_type="NSF",
            gmp_cert_id="NSF-001",
            gmp_cert_hash=gmp_hash,
            batch_id="BP-2025-TEST",
            extraction_method="MolecularDistillation",
            extraction_temp_c=240.0,
            yield_input_kg=1000.0,
            yield_output_kg=147.0,
            previous_hash=previous_hash,
            ledger_path=ledger,
        )
        assert receipt["receipt_type"] == "processing"
        assert receipt["facility_id"] == "FAC-01"
        assert receipt["yield_ratio"] == pytest.approx(0.147, abs=0.001)
        assert receipt["yield_status"] == "NORMAL"
        assert receipt["previous_hash"] == previous_hash
        assert "payload_hash" in receipt

    def test_dilution_flag(self, ledger, gmp_hash, previous_hash):
        receipt = create_processing_receipt(
            facility_id="FAC-01",
            facility_name="Test Facility",
            gmp_cert_type="NSF",
            gmp_cert_id="NSF-001",
            gmp_cert_hash=gmp_hash,
            batch_id="BP-2025-DIL",
            extraction_method="MolecularDistillation",
            extraction_temp_c=240.0,
            yield_input_kg=1000.0,
            yield_output_kg=220.0,
            previous_hash=previous_hash,
            ledger_path=ledger,
        )
        assert receipt["yield_status"] == "HIGH_DILUTION_FLAG"

    def test_invalid_gmp_type_raises(self, ledger, gmp_hash, previous_hash):
        with pytest.raises(StopRule, match="Invalid GMP cert type"):
            create_processing_receipt(
                facility_id="FAC-01",
                facility_name="Test",
                gmp_cert_type="INVALID",
                gmp_cert_id="X",
                gmp_cert_hash=gmp_hash,
                batch_id="BP-TEST",
                extraction_method="MolecularDistillation",
                extraction_temp_c=240.0,
                yield_input_kg=1000.0,
                yield_output_kg=147.0,
                previous_hash=previous_hash,
                ledger_path=ledger,
            )

    def test_invalid_extraction_method_raises(self, ledger, gmp_hash, previous_hash):
        with pytest.raises(StopRule, match="Invalid extraction method"):
            create_processing_receipt(
                facility_id="FAC-01",
                facility_name="Test",
                gmp_cert_type="NSF",
                gmp_cert_id="X",
                gmp_cert_hash=gmp_hash,
                batch_id="BP-TEST",
                extraction_method="MagicExtraction",
                extraction_temp_c=240.0,
                yield_input_kg=1000.0,
                yield_output_kg=147.0,
                previous_hash=previous_hash,
                ledger_path=ledger,
            )

    def test_bad_gmp_hash_format_raises(self, ledger, previous_hash):
        with pytest.raises(StopRule, match="dual-hash format"):
            create_processing_receipt(
                facility_id="FAC-01",
                facility_name="Test",
                gmp_cert_type="NSF",
                gmp_cert_id="X",
                gmp_cert_hash="not_a_dual_hash",
                batch_id="BP-TEST",
                extraction_method="MolecularDistillation",
                extraction_temp_c=240.0,
                yield_input_kg=1000.0,
                yield_output_kg=147.0,
                previous_hash=previous_hash,
                ledger_path=ledger,
            )

    def test_all_extraction_methods(self, ledger, gmp_hash, previous_hash):
        for method in ["MolecularDistillation", "Winterization", "SupercriticalCO2"]:
            receipt = create_processing_receipt(
                facility_id="FAC-01",
                facility_name="Test",
                gmp_cert_type="NSF",
                gmp_cert_id="X",
                gmp_cert_hash=gmp_hash,
                batch_id=f"BP-{method}",
                extraction_method=method,
                extraction_temp_c=240.0,
                yield_input_kg=1000.0,
                yield_output_kg=150.0,
                previous_hash=previous_hash,
                ledger_path=ledger,
            )
            assert receipt["extraction_method"] == method
