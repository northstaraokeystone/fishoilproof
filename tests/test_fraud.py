"""Tests for Fraud Detection Algorithms."""

import os
import tempfile
import pytest

from src.core import dual_hash
from src.catch import create_catch_receipt
from src.processing import create_processing_receipt
from src.testing import create_testing_receipt
from src.encapsulation import create_encapsulation_receipt
from src.distribution import create_distribution_receipt, validate_cold_chain
from src.fraud import (
    detect_yield_anomaly,
    detect_label_fraud,
    detect_contaminant_exceed,
    detect_cold_chain_degradation,
    run_all_fraud_checks,
)


@pytest.fixture
def ledger():
    path = tempfile.mktemp(suffix=".jsonl")
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


def _make_processing_receipt(yield_status, yield_ratio, ledger_path):
    """Helper to make a processing receipt with specific yield."""
    return {
        "receipt_type": "processing",
        "tenant_id": "test",
        "yield_status": yield_status,
        "yield_ratio": yield_ratio,
        "yield_input_kg": 1000,
        "yield_output_kg": yield_ratio * 1000,
        "yield_expected_min": 0.12,
        "yield_expected_max": 0.18,
        "payload_hash": dual_hash(b"test_processing"),
    }


def _make_testing_receipt(potency_pass, total_mg, label_mg, contaminants_pass=True):
    """Helper to make a testing receipt."""
    return {
        "receipt_type": "testing",
        "tenant_id": "test",
        "potency": {
            "potency_pass": potency_pass,
            "total_omega3_mg": total_mg,
            "label_claim_mg": label_mg,
            "epa_mg": total_mg * 0.583,
            "dha_mg": total_mg * 0.417,
        },
        "contaminants": {
            "all_pass": contaminants_pass,
            "mercury_pass": contaminants_pass,
            "pcbs_pass": contaminants_pass,
            "dioxins_pass": contaminants_pass,
            "mercury_ppm": 0.02 if contaminants_pass else 0.15,
            "pcbs_ppm": 0.03,
            "dioxins_pg_per_g": 1.2,
        },
        "payload_hash": dual_hash(b"test_testing"),
    }


def _make_distribution_receipt(enabled, max_temp, deviations):
    """Helper to make a distribution receipt."""
    return {
        "receipt_type": "distribution",
        "tenant_id": "test",
        "cold_chain": {
            "enabled": enabled,
            "max_temp_c": max_temp,
            "avg_temp_c": max_temp - 1 if max_temp else None,
            "deviations_count": deviations,
        },
        "payload_hash": dual_hash(b"test_distribution"),
    }


class TestDetectYieldAnomaly:
    def test_normal_yield_no_anomaly(self, ledger):
        receipt = _make_processing_receipt("NORMAL", 0.147, ledger)
        result = detect_yield_anomaly(receipt, ledger_path=ledger)
        assert result is None

    def test_high_yield_detected(self, ledger):
        receipt = _make_processing_receipt("HIGH_DILUTION_FLAG", 0.22, ledger)
        result = detect_yield_anomaly(receipt, ledger_path=ledger)
        assert result is not None
        assert result["anomaly_type"] == "YIELD_HIGH"
        assert result["severity"] == "FLAG"

    def test_low_yield_detected(self, ledger):
        receipt = _make_processing_receipt("LOW", 0.10, ledger)
        result = detect_yield_anomaly(receipt, ledger_path=ledger)
        assert result is not None
        assert result["anomaly_type"] == "YIELD_LOW"
        assert result["severity"] == "WARNING"


class TestDetectLabelFraud:
    def test_no_fraud(self, ledger):
        receipt = _make_testing_receipt(True, 720, 700)
        result = detect_label_fraud(receipt, ledger_path=ledger)
        assert result is None

    def test_fraud_detected(self, ledger):
        receipt = _make_testing_receipt(False, 600, 700)
        result = detect_label_fraud(receipt, ledger_path=ledger)
        assert result is not None
        assert result["anomaly_type"] == "LABEL_FRAUD"
        assert result["severity"] == "FLAG"
        assert result["details"]["actual_mg"] == 600
        assert result["details"]["label_claim_mg"] == 700


class TestDetectContaminantExceed:
    def test_no_exceed(self, ledger):
        receipt = _make_testing_receipt(True, 720, 700, contaminants_pass=True)
        result = detect_contaminant_exceed(receipt, ledger_path=ledger)
        assert result is None

    def test_exceed_detected(self, ledger):
        receipt = _make_testing_receipt(True, 720, 700, contaminants_pass=False)
        result = detect_contaminant_exceed(receipt, ledger_path=ledger)
        assert result is not None
        assert result["anomaly_type"] == "CONTAMINANT_EXCEED"
        assert result["severity"] == "REJECT"


class TestDetectColdChainDegradation:
    def test_no_cold_chain(self, ledger):
        receipt = _make_distribution_receipt(False, None, 0)
        result = detect_cold_chain_degradation(receipt, ledger_path=ledger)
        assert result is None

    def test_normal_cold_chain(self, ledger):
        receipt = _make_distribution_receipt(True, 4.0, 0)
        result = detect_cold_chain_degradation(receipt, ledger_path=ledger)
        assert result is None

    def test_high_temp_detected(self, ledger):
        receipt = _make_distribution_receipt(True, 12.0, 1)
        result = detect_cold_chain_degradation(receipt, ledger_path=ledger)
        assert result is not None
        assert result["anomaly_type"] == "COLD_CHAIN_DEGRADATION"
        assert result["severity"] == "FLAG"

    def test_many_deviations_detected(self, ledger):
        receipt = _make_distribution_receipt(True, 7.0, 5)
        result = detect_cold_chain_degradation(receipt, ledger_path=ledger)
        assert result is not None
        assert result["anomaly_type"] == "COLD_CHAIN_DEGRADATION"
        assert result["severity"] == "WARNING"

    def test_three_deviations_ok(self, ledger):
        receipt = _make_distribution_receipt(True, 7.0, 3)
        result = detect_cold_chain_degradation(receipt, ledger_path=ledger)
        assert result is None


class TestRunAllFraudChecks:
    def test_clean_chain(self, ledger):
        chain = [
            _make_processing_receipt("NORMAL", 0.147, ledger),
            _make_testing_receipt(True, 720, 700),
            _make_distribution_receipt(True, 4.0, 0),
        ]
        anomalies = run_all_fraud_checks(chain, ledger_path=ledger)
        assert len(anomalies) == 0

    def test_multiple_anomalies(self, ledger):
        chain = [
            _make_processing_receipt("HIGH_DILUTION_FLAG", 0.22, ledger),
            _make_testing_receipt(False, 600, 700),
            _make_distribution_receipt(True, 12.0, 5),
        ]
        anomalies = run_all_fraud_checks(chain, ledger_path=ledger)
        assert len(anomalies) == 3
        types = {a["anomaly_type"] for a in anomalies}
        assert "YIELD_HIGH" in types
        assert "LABEL_FRAUD" in types
        assert "COLD_CHAIN_DEGRADATION" in types
