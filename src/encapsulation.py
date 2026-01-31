"""
Stage 4: Encapsulation Receipt

Proves GMP bottling + lot traceability.
Facility cert, lot number, fill date, capsule specs.
"""

from datetime import datetime, timezone

from .core import emit_receipt, find_receipt, load_ledger, StopRule

FACILITY_CERT_TYPES = {"NSF", "USP", "Other"}


def generate_lot_number(batch_id: str) -> str:
    """Generate a lot number in format LOT-YYYY-MMDD-XX.

    Args:
        batch_id: Batch identifier suffix (last 2 chars used as XX).

    Returns:
        Lot number string.
    """
    now = datetime.now(timezone.utc)
    suffix = batch_id[-2:].upper() if len(batch_id) >= 2 else "XX"
    return f"LOT-{now.year}-{now.month:02d}{now.day:02d}-{suffix}"


def link_to_testing(batch_id: str, ledger_path: str | None = None) -> dict | None:
    """Find parent testing receipt by batch_id.

    Args:
        batch_id: Batch identifier.
        ledger_path: Override ledger path.

    Returns:
        Testing receipt dict or None.
    """
    return find_receipt("testing", "batch_id", batch_id, ledger_path=ledger_path)


def create_encapsulation_receipt(
    facility_id: str,
    facility_name: str,
    facility_cert_type: str,
    facility_cert_id: str,
    facility_cert_hash: str,
    lot_number: str,
    fill_date: str,
    batch_id: str,
    capsule_count: int,
    mg_per_capsule: float,
    previous_hash: str,
    tenant_id: str | None = None,
    ledger_path: str | None = None,
) -> dict:
    """Create a Stage 4 encapsulation receipt.

    Args:
        facility_id: Encapsulation facility identifier.
        facility_name: Human-readable facility name.
        facility_cert_type: NSF, USP, or Other.
        facility_cert_id: Facility certificate ID.
        facility_cert_hash: Dual-hash of facility certificate.
        lot_number: Consumer-facing lot number (must be unique).
        fill_date: ISO8601 fill date.
        batch_id: Batch identifier linking to testing.
        capsule_count: Number of capsules in lot.
        mg_per_capsule: mg of oil per capsule.
        previous_hash: payload_hash of the linked testing_receipt.
        tenant_id: Tenant identifier.
        ledger_path: Override ledger path.

    Returns:
        Encapsulation receipt dict.

    Raises:
        StopRule: On validation failures.
    """
    if facility_cert_type not in FACILITY_CERT_TYPES:
        raise StopRule(f"Invalid facility cert type: {facility_cert_type}")

    if ":" not in facility_cert_hash:
        raise StopRule("Facility cert hash must be dual-hash format (SHA256:BLAKE3)")

    # Validate lot uniqueness
    existing = load_ledger(ledger_path)
    for r in existing:
        if r.get("receipt_type") == "encapsulation" and r.get("lot_number") == lot_number:
            raise StopRule(f"Lot number already exists: {lot_number}")

    # Validate fill_date is ISO8601
    try:
        datetime.fromisoformat(fill_date)
    except ValueError:
        raise StopRule(f"Invalid fill_date format (must be ISO8601): {fill_date}")

    payload = {
        "facility_id": facility_id,
        "facility_name": facility_name,
        "facility_cert_type": facility_cert_type,
        "facility_cert_id": facility_cert_id,
        "facility_cert_hash": facility_cert_hash,
        "lot_number": lot_number,
        "fill_date": fill_date,
        "batch_id": batch_id,
        "capsule_count": capsule_count,
        "mg_per_capsule": mg_per_capsule,
        "previous_hash": previous_hash,
    }

    return emit_receipt("encapsulation", payload, tenant_id=tenant_id, ledger_path=ledger_path)
