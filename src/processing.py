"""
Stage 2: Processing Receipt — Fields 4-7, 14

Proves GMP compliance + detects dilution via yield reconciliation.
"""

from .core import dual_hash, emit_receipt, find_receipt, StopRule

EXTRACTION_METHODS = {"MolecularDistillation", "Winterization", "SupercriticalCO2"}
GMP_CERT_TYPES = {"NSF", "USP", "Other"}

# Expected yield range for fish -> oil
YIELD_MIN = 0.12  # 12%
YIELD_MAX = 0.18  # 18%


def validate_yield(input_kg: float, output_kg: float) -> tuple[float, str]:
    """Validate yield ratio and return status.

    Args:
        input_kg: Raw fish input in kg.
        output_kg: Oil output in kg.

    Returns:
        Tuple of (ratio, status) where status is NORMAL, LOW, or HIGH_DILUTION_FLAG.

    Raises:
        StopRule: If input or output is non-positive.
    """
    if input_kg <= 0 or output_kg <= 0:
        raise StopRule(f"Invalid yield values: input={input_kg}, output={output_kg}")

    ratio = output_kg / input_kg

    if ratio < YIELD_MIN:
        return ratio, "LOW"
    elif ratio > YIELD_MAX:
        return ratio, "HIGH_DILUTION_FLAG"
    else:
        return ratio, "NORMAL"


def link_to_catch(batch_id: str, ledger_path: str | None = None) -> dict | None:
    """Find parent catch receipt by batch_id.

    Args:
        batch_id: Batch identifier to search for.
        ledger_path: Override ledger path.

    Returns:
        Catch receipt dict or None.
    """
    return find_receipt("catch", "batch_id", batch_id, ledger_path=ledger_path)


def create_processing_receipt(
    facility_id: str,
    facility_name: str,
    gmp_cert_type: str,
    gmp_cert_id: str,
    gmp_cert_hash: str,
    batch_id: str,
    extraction_method: str,
    extraction_temp_c: float,
    yield_input_kg: float,
    yield_output_kg: float,
    previous_hash: str,
    tenant_id: str | None = None,
    ledger_path: str | None = None,
) -> dict:
    """Create a Stage 2 processing receipt.

    Args:
        facility_id: Processing facility identifier.
        facility_name: Human-readable facility name.
        gmp_cert_type: NSF, USP, or Other.
        gmp_cert_id: GMP certificate ID.
        gmp_cert_hash: Dual-hash of GMP certificate.
        batch_id: Batch identifier linking to catch.
        extraction_method: MolecularDistillation, Winterization, or SupercriticalCO2.
        extraction_temp_c: Extraction temperature in Celsius.
        yield_input_kg: Raw fish input in kg.
        yield_output_kg: Oil output in kg.
        previous_hash: payload_hash of the linked catch_receipt.
        tenant_id: Tenant identifier.
        ledger_path: Override ledger path.

    Returns:
        Processing receipt dict.

    Raises:
        StopRule: On validation failures.
    """
    if gmp_cert_type not in GMP_CERT_TYPES:
        raise StopRule(f"Invalid GMP cert type: {gmp_cert_type}")

    if extraction_method not in EXTRACTION_METHODS:
        raise StopRule(f"Invalid extraction method: {extraction_method}")

    if ":" not in gmp_cert_hash:
        raise StopRule("GMP cert hash must be dual-hash format (SHA256:BLAKE3)")

    yield_ratio, yield_status = validate_yield(yield_input_kg, yield_output_kg)

    payload = {
        "facility_id": facility_id,
        "facility_name": facility_name,
        "gmp_cert_type": gmp_cert_type,
        "gmp_cert_id": gmp_cert_id,
        "gmp_cert_hash": gmp_cert_hash,
        "batch_id": batch_id,
        "extraction_method": extraction_method,
        "extraction_temp_c": extraction_temp_c,
        "yield_input_kg": yield_input_kg,
        "yield_output_kg": yield_output_kg,
        "yield_ratio": round(yield_ratio, 4),
        "yield_expected_min": YIELD_MIN,
        "yield_expected_max": YIELD_MAX,
        "yield_status": yield_status,
        "previous_hash": previous_hash,
    }

    return emit_receipt("processing", payload, tenant_id=tenant_id, ledger_path=ledger_path)
