"""Tests for Stage 1: Catch Receipt."""

import os
import tempfile
import pytest

from src.core import dual_hash, StopRule
from src.catch import (
    create_catch_receipt,
    validate_species,
    hash_document,
    APPROVED_SPECIES,
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
def sample_hashes():
    return {
        "import_docs": dual_hash(b"test_import_docs.pdf"),
        "fishery_cert": dual_hash(b"test_fishery_cert.pdf"),
    }


class TestValidateSpecies:
    def test_approved_species(self):
        assert validate_species("Engraulis ringens") is True

    def test_all_approved_species(self):
        for species in APPROVED_SPECIES:
            assert validate_species(species) is True

    def test_unapproved_species(self):
        assert validate_species("Homo sapiens") is False

    def test_empty_string(self):
        assert validate_species("") is False


class TestHashDocument:
    def test_hash_existing_file(self, tmp_path):
        f = tmp_path / "test.pdf"
        f.write_bytes(b"test document content")
        result = hash_document(str(f))
        assert "SHA256_" in result
        assert ":BLAKE3_" in result

    def test_hash_nonexistent_file(self):
        with pytest.raises(StopRule, match="Document not found"):
            hash_document("/nonexistent/path.pdf")


class TestCreateCatchReceipt:
    def test_basic_receipt(self, ledger, sample_hashes):
        receipt = create_catch_receipt(
            species="Engraulis ringens",
            fishery_registry="PRODUCE Peru",
            import_docs_hash=sample_hashes["import_docs"],
            ledger_path=ledger,
        )
        assert receipt["receipt_type"] == "catch"
        assert receipt["species"] == "Engraulis ringens"
        assert receipt["species_common"] == "Peruvian Anchoveta"
        assert receipt["fishery_approved"] is True
        assert receipt["fishery_registry"] == "PRODUCE Peru"
        assert "payload_hash" in receipt
        assert "merkle_root" in receipt
        assert "ts" in receipt
        assert "tenant_id" in receipt

    def test_with_msc_cert(self, ledger, sample_hashes):
        receipt = create_catch_receipt(
            species="Engraulis ringens",
            fishery_registry="PRODUCE Peru",
            import_docs_hash=sample_hashes["import_docs"],
            fishery_cert_type="MSC",
            fishery_cert_id="MSC-C-12345",
            fishery_cert_hash=sample_hashes["fishery_cert"],
            ledger_path=ledger,
        )
        assert receipt["fishery_cert_type"] == "MSC"
        assert receipt["fishery_cert_id"] == "MSC-C-12345"
        assert receipt["fishery_cert_hash"] == sample_hashes["fishery_cert"]

    def test_with_fos_cert(self, ledger, sample_hashes):
        receipt = create_catch_receipt(
            species="Sardina pilchardus",
            fishery_registry="EU Registry",
            import_docs_hash=sample_hashes["import_docs"],
            fishery_cert_type="FriendOfSea",
            fishery_cert_id="FOS-123",
            fishery_cert_hash=sample_hashes["fishery_cert"],
            ledger_path=ledger,
        )
        assert receipt["fishery_cert_type"] == "FriendOfSea"

    def test_unapproved_species_raises(self, ledger, sample_hashes):
        with pytest.raises(StopRule, match="not FDA-approved"):
            create_catch_receipt(
                species="Fake Fish",
                fishery_registry="Nowhere",
                import_docs_hash=sample_hashes["import_docs"],
                ledger_path=ledger,
            )

    def test_cert_claimed_no_hash_raises(self, ledger, sample_hashes):
        with pytest.raises(StopRule, match="no cert hash provided"):
            create_catch_receipt(
                species="Engraulis ringens",
                fishery_registry="PRODUCE Peru",
                import_docs_hash=sample_hashes["import_docs"],
                fishery_cert_type="MSC",
                fishery_cert_id="MSC-123",
                fishery_cert_hash=None,
                ledger_path=ledger,
            )

    def test_invalid_cert_type_raises(self, ledger, sample_hashes):
        with pytest.raises(StopRule, match="Invalid fishery cert type"):
            create_catch_receipt(
                species="Engraulis ringens",
                fishery_registry="PRODUCE Peru",
                import_docs_hash=sample_hashes["import_docs"],
                fishery_cert_type="INVALID",
                ledger_path=ledger,
            )

    def test_receipt_written_to_ledger(self, ledger, sample_hashes):
        create_catch_receipt(
            species="Engraulis ringens",
            fishery_registry="PRODUCE Peru",
            import_docs_hash=sample_hashes["import_docs"],
            ledger_path=ledger,
        )
        assert os.path.exists(ledger)
        with open(ledger) as f:
            lines = f.readlines()
        assert len(lines) == 1

    def test_dual_hash_format(self, ledger, sample_hashes):
        receipt = create_catch_receipt(
            species="Engraulis ringens",
            fishery_registry="PRODUCE Peru",
            import_docs_hash=sample_hashes["import_docs"],
            ledger_path=ledger,
        )
        ph = receipt["payload_hash"]
        assert "SHA256_" in ph
        assert ":BLAKE3_" in ph
