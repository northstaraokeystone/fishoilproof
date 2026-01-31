"""Tests for Stage 4: Encapsulation Receipt."""

import os
import tempfile
import pytest

from src.core import dual_hash, StopRule
from src.encapsulation import (
    create_encapsulation_receipt,
    generate_lot_number,
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
def cert_hash():
    return dual_hash(b"test_facility_cert.pdf")


@pytest.fixture
def previous_hash():
    return dual_hash(b"previous_testing_receipt")


class TestGenerateLotNumber:
    def test_format(self):
        lot = generate_lot_number("BP-2025-0130")
        assert lot.startswith("LOT-")
        parts = lot.split("-")
        assert len(parts) == 4

    def test_uses_batch_suffix(self):
        lot = generate_lot_number("BP-2025-0130")
        assert lot.endswith("30")

    def test_short_batch_id(self):
        lot = generate_lot_number("A")
        assert lot.endswith("XX")


class TestCreateEncapsulationReceipt:
    def test_basic_receipt(self, ledger, cert_hash, previous_hash):
        receipt = create_encapsulation_receipt(
            facility_id="BOT-01",
            facility_name="Test Bottling",
            facility_cert_type="NSF",
            facility_cert_id="NSF-BOT-001",
            facility_cert_hash=cert_hash,
            lot_number="LOT-2025-0131-BP",
            fill_date="2025-01-31T14:22:47Z",
            batch_id="BP-2025-0130",
            capsule_count=90,
            mg_per_capsule=1000.0,
            previous_hash=previous_hash,
            ledger_path=ledger,
        )
        assert receipt["receipt_type"] == "encapsulation"
        assert receipt["lot_number"] == "LOT-2025-0131-BP"
        assert receipt["capsule_count"] == 90
        assert receipt["mg_per_capsule"] == 1000.0
        assert "payload_hash" in receipt

    def test_duplicate_lot_raises(self, ledger, cert_hash, previous_hash):
        create_encapsulation_receipt(
            facility_id="BOT-01",
            facility_name="Test",
            facility_cert_type="NSF",
            facility_cert_id="NSF-001",
            facility_cert_hash=cert_hash,
            lot_number="LOT-DUP-TEST",
            fill_date="2025-01-31T14:00:00Z",
            batch_id="BP-DUP",
            capsule_count=90,
            mg_per_capsule=1000.0,
            previous_hash=previous_hash,
            ledger_path=ledger,
        )
        with pytest.raises(StopRule, match="already exists"):
            create_encapsulation_receipt(
                facility_id="BOT-01",
                facility_name="Test",
                facility_cert_type="NSF",
                facility_cert_id="NSF-001",
                facility_cert_hash=cert_hash,
                lot_number="LOT-DUP-TEST",
                fill_date="2025-01-31T15:00:00Z",
                batch_id="BP-DUP-2",
                capsule_count=90,
                mg_per_capsule=1000.0,
                previous_hash=previous_hash,
                ledger_path=ledger,
            )

    def test_invalid_cert_type_raises(self, ledger, cert_hash, previous_hash):
        with pytest.raises(StopRule, match="Invalid facility cert type"):
            create_encapsulation_receipt(
                facility_id="BOT-01",
                facility_name="Test",
                facility_cert_type="INVALID",
                facility_cert_id="X",
                facility_cert_hash=cert_hash,
                lot_number="LOT-TEST",
                fill_date="2025-01-31T14:00:00Z",
                batch_id="BP-TEST",
                capsule_count=90,
                mg_per_capsule=1000.0,
                previous_hash=previous_hash,
                ledger_path=ledger,
            )

    def test_bad_cert_hash_raises(self, ledger, previous_hash):
        with pytest.raises(StopRule, match="dual-hash format"):
            create_encapsulation_receipt(
                facility_id="BOT-01",
                facility_name="Test",
                facility_cert_type="NSF",
                facility_cert_id="X",
                facility_cert_hash="nope",
                lot_number="LOT-TEST",
                fill_date="2025-01-31T14:00:00Z",
                batch_id="BP-TEST",
                capsule_count=90,
                mg_per_capsule=1000.0,
                previous_hash=previous_hash,
                ledger_path=ledger,
            )

    def test_bad_fill_date_raises(self, ledger, cert_hash, previous_hash):
        with pytest.raises(StopRule, match="Invalid fill_date"):
            create_encapsulation_receipt(
                facility_id="BOT-01",
                facility_name="Test",
                facility_cert_type="NSF",
                facility_cert_id="X",
                facility_cert_hash=cert_hash,
                lot_number="LOT-TEST",
                fill_date="not-a-date",
                batch_id="BP-TEST",
                capsule_count=90,
                mg_per_capsule=1000.0,
                previous_hash=previous_hash,
                ledger_path=ledger,
            )
