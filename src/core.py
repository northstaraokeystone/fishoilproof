"""
FishOilProof Core — CLAUDEME-compliant foundation.

LAW_1 = "No receipt -> not real"
LAW_2 = "No test -> not shipped"
LAW_3 = "No gate -> not alive"
"""

import hashlib
import json
import os
import time
from datetime import datetime, timezone

import blake3

# Ledger path (append-only)
LEDGER_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "receipts.jsonl")

# Default tenant for demo
DEFAULT_TENANT = "fishoilproof-demo"


class StopRule(Exception):
    """Raised when a stoprule triggers. Never catch silently."""
    pass


def dual_hash(data: bytes | str) -> str:
    """Compute dual hash in SHA256:BLAKE3 format.

    Args:
        data: Input bytes or string to hash.

    Returns:
        String in format "SHA256_<hex>:BLAKE3_<hex>"
    """
    if isinstance(data, str):
        data = data.encode("utf-8")

    sha256_hex = hashlib.sha256(data).hexdigest()
    blake3_hex = blake3.blake3(data).hexdigest()

    return f"SHA256_{sha256_hex}:BLAKE3_{blake3_hex}"


def merkle_root(items: list) -> str:
    """Compute BLAKE3 Merkle tree root.

    Args:
        items: List of strings or bytes to build tree from.

    Returns:
        Hex string of Merkle root.
    """
    if not items:
        return blake3.blake3(b"empty").hexdigest()

    # Leaf hashes
    leaves = []
    for item in items:
        if isinstance(item, str):
            item = item.encode("utf-8")
        leaves.append(blake3.blake3(item).digest())

    # Build tree bottom-up
    while len(leaves) > 1:
        next_level = []
        for i in range(0, len(leaves), 2):
            if i + 1 < len(leaves):
                combined = leaves[i] + leaves[i + 1]
            else:
                combined = leaves[i] + leaves[i]  # duplicate odd leaf
            next_level.append(blake3.blake3(combined).digest())
        leaves = next_level

    return leaves[0].hex()


def emit_receipt(receipt_type: str, payload: dict, tenant_id: str | None = None,
                 ledger_path: str | None = None) -> dict:
    """Emit a receipt to the append-only ledger.

    Every receipt gets: ts, tenant_id, payload_hash, receipt_type.
    Appended to receipts.jsonl immediately (not batched).

    Args:
        receipt_type: Type of receipt (catch, processing, testing, etc.)
        payload: Receipt payload dict.
        tenant_id: Tenant identifier. Defaults to demo tenant.
        ledger_path: Override ledger file path.

    Returns:
        Complete receipt dict with metadata.
    """
    ts = datetime.now(timezone.utc).isoformat()
    tenant = tenant_id or DEFAULT_TENANT

    receipt = {
        "receipt_type": receipt_type,
        "ts": ts,
        "tenant_id": tenant,
    }
    receipt.update(payload)

    # Compute payload hash over the full receipt content
    payload_bytes = json.dumps(receipt, sort_keys=True, default=str).encode("utf-8")
    receipt["payload_hash"] = dual_hash(payload_bytes)

    # Compute merkle root over all field values
    field_values = [str(v) for v in receipt.values()]
    receipt["merkle_root"] = merkle_root(field_values)

    # Append to ledger
    target = ledger_path or LEDGER_PATH
    os.makedirs(os.path.dirname(target) if os.path.dirname(target) else ".", exist_ok=True)
    with open(target, "a") as f:
        f.write(json.dumps(receipt, default=str) + "\n")

    return receipt


def load_ledger(ledger_path: str | None = None) -> list[dict]:
    """Load all receipts from the ledger.

    Args:
        ledger_path: Override ledger file path.

    Returns:
        List of receipt dicts.
    """
    target = ledger_path or LEDGER_PATH
    if not os.path.exists(target):
        return []

    receipts = []
    with open(target, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                receipts.append(json.loads(line))
    return receipts


def find_receipt(receipt_type: str, key: str, value: str,
                 ledger_path: str | None = None) -> dict | None:
    """Find a specific receipt in the ledger.

    Args:
        receipt_type: Type to filter by.
        key: Field name to match.
        value: Field value to match.
        ledger_path: Override ledger file path.

    Returns:
        First matching receipt or None.
    """
    for receipt in load_ledger(ledger_path):
        if receipt.get("receipt_type") == receipt_type and receipt.get(key) == value:
            return receipt
    return None


def verify_dual_hash(data: bytes | str, expected_hash: str) -> bool:
    """Verify data matches a dual hash.

    Args:
        data: Original data.
        expected_hash: Expected SHA256:BLAKE3 hash string.

    Returns:
        True if both hashes match.
    """
    computed = dual_hash(data)
    return computed == expected_hash
