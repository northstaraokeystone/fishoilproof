"""
Chain Verification + QR Code Generation

Walks the receipt chain backwards via previous_hash.
Verifies each hash matches recomputed value.
Generates consumer-facing QR payload.
"""

import json
from datetime import datetime, timezone

from .core import dual_hash, load_ledger, StopRule

# Receipt stage order
STAGE_ORDER = ["catch", "processing", "testing", "encapsulation", "distribution"]


def verify_single_receipt(receipt: dict) -> bool:
    """Recompute payload hash and compare to stored value.

    Args:
        receipt: Receipt dict to verify.

    Returns:
        True if hash matches.
    """
    stored_hash = receipt.get("payload_hash")
    if not stored_hash:
        return False

    # Rebuild the receipt without payload_hash and merkle_root for hashing
    check = {}
    for k, v in receipt.items():
        if k not in ("payload_hash", "merkle_root"):
            check[k] = v

    payload_bytes = json.dumps(check, sort_keys=True, default=str).encode("utf-8")
    computed = dual_hash(payload_bytes)

    return computed == stored_hash


def _find_receipt_by_hash(payload_hash: str, receipts: list[dict]) -> dict | None:
    """Find a receipt by its payload_hash."""
    for r in receipts:
        if r.get("payload_hash") == payload_hash:
            return r
    return None


def _find_distribution_by_lot(lot_number: str, receipts: list[dict]) -> dict | None:
    """Find distribution receipt by lot number."""
    for r in receipts:
        if r.get("receipt_type") == "distribution" and r.get("lot_number") == lot_number:
            return r
    return None


def _find_encapsulation_by_lot(lot_number: str, receipts: list[dict]) -> dict | None:
    """Find encapsulation receipt by lot number."""
    for r in receipts:
        if r.get("receipt_type") == "encapsulation" and r.get("lot_number") == lot_number:
            return r
    return None


def verify_chain(lot_number: str, ledger_path: str | None = None) -> dict:
    """Verify the full 5-receipt chain for a given lot number.

    Walks backwards from distribution -> encapsulation -> testing -> processing -> catch.
    Verifies each receipt hash and each previous_hash link.

    Args:
        lot_number: Consumer-facing lot number.
        ledger_path: Override ledger path.

    Returns:
        Dict with chain receipts, verification status, and any errors.
    """
    receipts = load_ledger(ledger_path)

    result = {
        "lot_number": lot_number,
        "chain_length": 0,
        "chain_valid": False,
        "receipts": {},
        "errors": [],
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }

    # Step 1: Find distribution receipt
    dist = _find_distribution_by_lot(lot_number, receipts)
    if not dist:
        result["errors"].append(f"No distribution receipt found for lot {lot_number}")
        return result

    # Step 2: Find encapsulation receipt (by lot_number on dist receipt, walk back)
    encap = _find_encapsulation_by_lot(lot_number, receipts)
    if not encap:
        result["errors"].append(f"No encapsulation receipt found for lot {lot_number}")
        return result

    # Verify dist -> encap link
    if dist.get("previous_hash") != encap.get("payload_hash"):
        result["errors"].append("Distribution previous_hash does not match encapsulation payload_hash")

    # Step 3: Walk backwards from encapsulation via previous_hash
    chain = [dist, encap]
    current = encap
    for expected_type in ["testing", "processing", "catch"]:
        prev_hash = current.get("previous_hash")
        if not prev_hash:
            result["errors"].append(f"Missing previous_hash on {current.get('receipt_type')} receipt")
            break

        prev_receipt = _find_receipt_by_hash(prev_hash, receipts)
        if not prev_receipt:
            result["errors"].append(f"Cannot find receipt with hash {prev_hash[:40]}...")
            break

        if prev_receipt.get("receipt_type") != expected_type:
            result["errors"].append(
                f"Expected {expected_type} receipt but found {prev_receipt.get('receipt_type')}"
            )

        chain.append(prev_receipt)
        current = prev_receipt

    # Verify each receipt hash
    hash_errors = []
    for r in chain:
        if not verify_single_receipt(r):
            hash_errors.append(f"Hash verification failed for {r.get('receipt_type')} receipt")

    result["errors"].extend(hash_errors)

    # Assemble result
    for r in chain:
        result["receipts"][r.get("receipt_type")] = r

    result["chain_length"] = len(chain)
    result["chain_valid"] = len(result["errors"]) == 0 and len(chain) == 5

    return result


def get_chain_summary(lot_number: str, ledger_path: str | None = None) -> dict:
    """Get a consumer-friendly chain summary.

    Args:
        lot_number: Consumer-facing lot number.
        ledger_path: Override ledger path.

    Returns:
        Summary dict with key verification points.
    """
    chain = verify_chain(lot_number, ledger_path=ledger_path)

    if not chain["chain_valid"]:
        return {
            "lot": lot_number,
            "valid": False,
            "errors": chain["errors"],
        }

    catch = chain["receipts"].get("catch", {})
    processing = chain["receipts"].get("processing", {})
    testing = chain["receipts"].get("testing", {})
    distribution = chain["receipts"].get("distribution", {})

    contaminants = testing.get("contaminants", {})
    potency = testing.get("potency", {})
    oxidation = testing.get("oxidation", {})
    cold_chain = distribution.get("cold_chain", {})

    return {
        "lot": lot_number,
        "valid": True,
        "chain_length": chain["chain_length"],
        "species": catch.get("species_common", "Unknown"),
        "species_scientific": catch.get("species", "Unknown"),
        "fishery_certified": catch.get("fishery_cert_type", "None") != "None",
        "fishery_cert": catch.get("fishery_cert_type", "None"),
        "contaminants_pass": contaminants.get("all_pass", False),
        "potency_verified": (
            f"{potency.get('total_omega3_mg', 0):.0f}mg EPA+DHA "
            f"(label: {potency.get('label_claim_mg', 0):.0f}mg)"
        ),
        "potency_pass": potency.get("potency_pass", False),
        "totox": oxidation.get("totox", 0),
        "oxidation_pass": oxidation.get("oxidation_pass", False),
        "yield_status": processing.get("yield_status", "UNKNOWN"),
        "yield_normal": processing.get("yield_status") == "NORMAL",
        "cold_chain_verified": cold_chain.get("cold_chain_pass", False),
        "cold_chain_enabled": cold_chain.get("enabled", False),
    }


def generate_qr_payload(lot_number: str, ledger_path: str | None = None) -> str:
    """Generate JSON payload for QR code.

    Args:
        lot_number: Consumer-facing lot number.
        ledger_path: Override ledger path.

    Returns:
        JSON string for QR code content.
    """
    summary = get_chain_summary(lot_number, ledger_path=ledger_path)

    if not summary.get("valid"):
        return json.dumps({"lot": lot_number, "valid": False, "errors": summary.get("errors", [])})

    qr = {
        "lot": lot_number,
        "chain_length": summary["chain_length"],
        "species": summary["species"],
        "fishery_certified": summary["fishery_certified"],
        "fishery_cert": summary["fishery_cert"],
        "contaminants_pass": summary["contaminants_pass"],
        "potency_verified": summary["potency_verified"],
        "totox": summary["totox"],
        "cold_chain_verified": summary["cold_chain_verified"],
        "yield_normal": summary["yield_normal"],
        "verification_url": f"https://verify.fishoilproof.io/{lot_number}",
    }

    return json.dumps(qr, indent=2)
