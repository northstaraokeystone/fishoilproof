"""Tests for Stage 5: Distribution Receipt."""

import os
import tempfile
import pytest

from src.core import dual_hash
from src.distribution import (
    create_distribution_receipt,
    validate_cold_chain,
    COLD_CHAIN_TARGET_MAX,
    COLD_CHAIN_MAX_DEVIATIONS,
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
def previous_hash():
    return dual_hash(b"previous_encapsulation_receipt")


class TestValidateColdChain:
    def test_normal_temps(self):
        temps = [2.1, 2.3, 2.0, 2.2, 2.1]
        result = validate_cold_chain(temps, 90)
        assert result["enabled"] is True
        assert result["cold_chain_pass"] is True
        assert result["deviations_count"] == 0
        assert result["avg_temp_c"] == pytest.approx(2.14, abs=0.01)

    def test_high_temp_fail(self):
        temps = [2.1, 2.3, 12.0, 2.2, 2.1]
        result = validate_cold_chain(temps, 90)
        assert result["cold_chain_pass"] is False
        assert result["max_temp_c"] == 12.0
        assert result["deviations_count"] == 1

    def test_multiple_deviations_fail(self):
        temps = [2.1, 9.0, 10.0, 11.0, 12.0]
        result = validate_cold_chain(temps, 90)
        assert result["cold_chain_pass"] is False
        assert result["deviations_count"] == 4

    def test_three_deviations_pass(self):
        """3 deviations is the threshold — should still pass if max <= 8."""
        temps = [2.1, 2.3, 2.0, 1.0, 1.5, 1.8, 7.9, 8.0, 8.0]
        result = validate_cold_chain(temps, 90)
        assert result["cold_chain_pass"] is True

    def test_empty_temps(self):
        result = validate_cold_chain([], 90)
        assert result["enabled"] is False
        assert result["cold_chain_pass"] is False

    def test_with_temp_log_hash(self):
        temps = [2.1, 2.3]
        h = dual_hash(b"temp_log.csv")
        result = validate_cold_chain(temps, 90, temp_log_hash=h)
        assert result["temp_log_hash"] == h

    def test_below_min_counts_as_deviation(self):
        temps = [1.0, 2.5, 3.0]  # 1.0 is below 2.0 target min
        result = validate_cold_chain(temps, 90)
        assert result["deviations_count"] == 1


class TestCreateDistributionReceipt:
    def test_basic_receipt_no_cold_chain(self, ledger, previous_hash):
        receipt = create_distribution_receipt(
            distributor_id="DIST-01",
            distributor_name="Test Dist",
            warehouse_id="WH-01",
            warehouse_location="Test City",
            lot_number="LOT-TEST-001",
            cold_chain_data=None,
            previous_hash=previous_hash,
            ledger_path=ledger,
        )
        assert receipt["receipt_type"] == "distribution"
        assert receipt["cold_chain"]["enabled"] is False
        assert "payload_hash" in receipt

    def test_receipt_with_cold_chain(self, ledger, previous_hash):
        cold_chain = validate_cold_chain([2.1, 2.3, 2.0], 90)
        receipt = create_distribution_receipt(
            distributor_id="DIST-01",
            distributor_name="Test Dist",
            warehouse_id="WH-01",
            warehouse_location="Test City",
            lot_number="LOT-TEST-002",
            cold_chain_data=cold_chain,
            previous_hash=previous_hash,
            ledger_path=ledger,
        )
        assert receipt["cold_chain"]["enabled"] is True
        assert receipt["cold_chain"]["cold_chain_pass"] is True

    def test_receipt_with_failed_cold_chain(self, ledger, previous_hash):
        cold_chain = validate_cold_chain([2.1, 15.0, 2.0], 90)
        receipt = create_distribution_receipt(
            distributor_id="DIST-01",
            distributor_name="Test Dist",
            warehouse_id="WH-01",
            warehouse_location="Test City",
            lot_number="LOT-TEST-003",
            cold_chain_data=cold_chain,
            previous_hash=previous_hash,
            ledger_path=ledger,
        )
        assert receipt["cold_chain"]["cold_chain_pass"] is False
