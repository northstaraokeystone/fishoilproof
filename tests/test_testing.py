"""Tests for Stage 3: Testing Receipt."""

import os
import tempfile
import pytest

from src.core import dual_hash, StopRule
from src.testing import (
    create_testing_receipt,
    validate_contaminants,
    validate_potency,
    validate_oxidation,
    LIMITS,
    POTENCY_THRESHOLD,
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
def lab_hash():
    return dual_hash(b"test_lab_cert.pdf")


@pytest.fixture
def previous_hash():
    return dual_hash(b"previous_processing_receipt")


class TestValidateContaminants:
    def test_all_pass(self):
        result = validate_contaminants(0.02, 0.03, 1.2)
        assert result["all_pass"] is True
        assert result["mercury_pass"] is True
        assert result["pcbs_pass"] is True
        assert result["dioxins_pass"] is True

    def test_mercury_fail(self):
        result = validate_contaminants(0.15, 0.03, 1.2)
        assert result["all_pass"] is False
        assert result["mercury_pass"] is False

    def test_pcbs_fail(self):
        result = validate_contaminants(0.02, 0.10, 1.2)
        assert result["all_pass"] is False
        assert result["pcbs_pass"] is False

    def test_dioxins_fail(self):
        result = validate_contaminants(0.02, 0.03, 3.5)
        assert result["all_pass"] is False
        assert result["dioxins_pass"] is False

    def test_all_fail(self):
        result = validate_contaminants(0.15, 0.10, 3.5)
        assert result["all_pass"] is False

    def test_at_limit_pass(self):
        result = validate_contaminants(0.1, 0.09, 3.0)
        assert result["all_pass"] is True


class TestValidatePotency:
    def test_pass(self):
        result = validate_potency(420, 300, 700)
        assert result["potency_pass"] is True
        assert result["total_omega3_mg"] == 720

    def test_fail_below_95pct(self):
        result = validate_potency(350, 250, 700)
        assert result["potency_pass"] is False

    def test_exact_threshold(self):
        # 95% of 700 = 665
        result = validate_potency(365, 300, 700)
        assert result["potency_pass"] is True

    def test_just_below_threshold(self):
        # 95% of 700 = 665, total = 664
        result = validate_potency(364, 300, 700)
        assert result["potency_pass"] is False


class TestValidateOxidation:
    def test_pass(self):
        result = validate_oxidation(3.8, 10.7)
        assert result["oxidation_pass"] is True
        assert result["totox"] == pytest.approx(18.3, abs=0.1)

    def test_totox_calculation(self):
        result = validate_oxidation(5.0, 16.0)
        assert result["totox"] == 26.0  # 2*5 + 16

    def test_fail_peroxide(self):
        result = validate_oxidation(6.0, 10.0)
        assert result["oxidation_pass"] is False

    def test_fail_anisidine(self):
        result = validate_oxidation(3.0, 21.0)
        assert result["oxidation_pass"] is False

    def test_fail_totox(self):
        result = validate_oxidation(5.0, 17.0)
        assert result["oxidation_pass"] is False
        assert result["totox"] == 27.0


class TestCreateTestingReceipt:
    def test_passing_receipt(self, ledger, lab_hash, previous_hash):
        receipt = create_testing_receipt(
            lab_name="Eurofins",
            lab_cert_type="ISO17025",
            lab_cert_id="ISO-001",
            lab_cert_hash=lab_hash,
            batch_id="BP-TEST",
            mercury_ppm=0.02,
            pcbs_ppm=0.03,
            dioxins_pg_per_g=1.2,
            epa_mg=420,
            dha_mg=300,
            label_claim_mg=700,
            peroxide_meq_per_kg=3.8,
            anisidine=10.7,
            previous_hash=previous_hash,
            ledger_path=ledger,
        )
        assert receipt["receipt_type"] == "testing"
        assert receipt["overall_pass"] is True
        assert receipt["contaminants"]["all_pass"] is True
        assert receipt["potency"]["potency_pass"] is True
        assert receipt["oxidation"]["oxidation_pass"] is True

    def test_contaminant_exceed_raises(self, ledger, lab_hash, previous_hash):
        with pytest.raises(StopRule, match="CONTAMINANT_EXCEED"):
            create_testing_receipt(
                lab_name="Lab",
                lab_cert_type="ISO17025",
                lab_cert_id="ISO-001",
                lab_cert_hash=lab_hash,
                batch_id="BP-FAIL",
                mercury_ppm=0.15,
                pcbs_ppm=0.03,
                dioxins_pg_per_g=1.2,
                epa_mg=420,
                dha_mg=300,
                label_claim_mg=700,
                peroxide_meq_per_kg=3.8,
                anisidine=10.7,
                previous_hash=previous_hash,
                ledger_path=ledger,
            )

    def test_totox_exceed_raises(self, ledger, lab_hash, previous_hash):
        with pytest.raises(StopRule, match="TOTOX_EXCEED"):
            create_testing_receipt(
                lab_name="Lab",
                lab_cert_type="ISO17025",
                lab_cert_id="ISO-001",
                lab_cert_hash=lab_hash,
                batch_id="BP-RANCID",
                mercury_ppm=0.02,
                pcbs_ppm=0.03,
                dioxins_pg_per_g=1.2,
                epa_mg=420,
                dha_mg=300,
                label_claim_mg=700,
                peroxide_meq_per_kg=5.0,
                anisidine=17.0,
                previous_hash=previous_hash,
                ledger_path=ledger,
            )

    def test_invalid_lab_cert_type_raises(self, ledger, lab_hash, previous_hash):
        with pytest.raises(StopRule, match="Invalid lab cert type"):
            create_testing_receipt(
                lab_name="Lab",
                lab_cert_type="INVALID",
                lab_cert_id="X",
                lab_cert_hash=lab_hash,
                batch_id="BP-TEST",
                mercury_ppm=0.02,
                pcbs_ppm=0.03,
                dioxins_pg_per_g=1.2,
                epa_mg=420,
                dha_mg=300,
                label_claim_mg=700,
                peroxide_meq_per_kg=3.0,
                anisidine=10.0,
                previous_hash=previous_hash,
                ledger_path=ledger,
            )

    def test_bad_lab_hash_format_raises(self, ledger, previous_hash):
        with pytest.raises(StopRule, match="dual-hash format"):
            create_testing_receipt(
                lab_name="Lab",
                lab_cert_type="ISO17025",
                lab_cert_id="X",
                lab_cert_hash="not_dual_hash",
                batch_id="BP-TEST",
                mercury_ppm=0.02,
                pcbs_ppm=0.03,
                dioxins_pg_per_g=1.2,
                epa_mg=420,
                dha_mg=300,
                label_claim_mg=700,
                peroxide_meq_per_kg=3.0,
                anisidine=10.0,
                previous_hash=previous_hash,
                ledger_path=ledger,
            )

    def test_label_fraud_receipt_emitted(self, ledger, lab_hash, previous_hash):
        """When potency fails but contaminants pass, receipt should still emit."""
        receipt = create_testing_receipt(
            lab_name="Lab",
            lab_cert_type="ISO17025",
            lab_cert_id="ISO-001",
            lab_cert_hash=lab_hash,
            batch_id="BP-LABEL",
            mercury_ppm=0.02,
            pcbs_ppm=0.03,
            dioxins_pg_per_g=1.2,
            epa_mg=300,
            dha_mg=200,
            label_claim_mg=700,
            peroxide_meq_per_kg=3.0,
            anisidine=10.0,
            previous_hash=previous_hash,
            ledger_path=ledger,
        )
        assert receipt["overall_pass"] is False
        assert receipt["potency"]["potency_pass"] is False
