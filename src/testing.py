"""
Stage 3: Testing Receipt — Fields 8-11

Proves safety, potency, and freshness.
Lab cert, contaminants, potency, oxidation markers.
"""

from .core import emit_receipt, StopRule

LAB_CERT_TYPES = {"ISO17025", "Other"}

# GOED/FDA limits
LIMITS = {
    "mercury_ppm": 0.1,
    "pcbs_ppm": 0.09,
    "dioxins_pg_per_g": 3.0,
    "peroxide_meq_per_kg": 5.0,
    "anisidine": 20.0,
    "totox": 26.0,
}

# Potency must be >= 95% of label claim
POTENCY_THRESHOLD = 0.95

# TOTOX freshness warning threshold
TOTOX_WARNING = 19.0


def validate_contaminants(mercury: float, pcbs: float, dioxins: float) -> dict:
    """Validate contaminant levels against FDA/GOED limits.

    Args:
        mercury: Mercury in ppm.
        pcbs: PCBs in ppm.
        dioxins: Dioxins in pg/g.

    Returns:
        Dict with per-contaminant results and overall pass.
    """
    mercury_pass = mercury <= LIMITS["mercury_ppm"]
    pcbs_pass = pcbs <= LIMITS["pcbs_ppm"]
    dioxins_pass = dioxins <= LIMITS["dioxins_pg_per_g"]

    return {
        "mercury_ppm": mercury,
        "mercury_pass": mercury_pass,
        "pcbs_ppm": pcbs,
        "pcbs_pass": pcbs_pass,
        "dioxins_pg_per_g": dioxins,
        "dioxins_pass": dioxins_pass,
        "all_pass": mercury_pass and pcbs_pass and dioxins_pass,
    }


def validate_potency(epa_mg: float, dha_mg: float, label_claim_mg: float) -> dict:
    """Validate potency against label claim.

    Args:
        epa_mg: EPA content in mg.
        dha_mg: DHA content in mg.
        label_claim_mg: Claimed total omega-3 on label in mg.

    Returns:
        Dict with potency data and pass/fail.
    """
    total = epa_mg + dha_mg
    potency_pass = total >= label_claim_mg * POTENCY_THRESHOLD

    return {
        "epa_mg": epa_mg,
        "dha_mg": dha_mg,
        "total_omega3_mg": total,
        "label_claim_mg": label_claim_mg,
        "potency_pass": potency_pass,
    }


def validate_oxidation(peroxide: float, anisidine: float) -> dict:
    """Validate oxidation markers.

    TOTOX = 2 * peroxide + anisidine

    Args:
        peroxide: Peroxide value in meq/kg.
        anisidine: p-Anisidine value.

    Returns:
        Dict with oxidation data, TOTOX, and pass/fail.
    """
    totox = 2 * peroxide + anisidine
    oxidation_pass = (
        peroxide <= LIMITS["peroxide_meq_per_kg"]
        and anisidine <= LIMITS["anisidine"]
        and totox <= LIMITS["totox"]
    )

    return {
        "peroxide_meq_per_kg": peroxide,
        "anisidine": anisidine,
        "totox": round(totox, 2),
        "oxidation_pass": oxidation_pass,
    }


def create_testing_receipt(
    lab_name: str,
    lab_cert_type: str,
    lab_cert_id: str,
    lab_cert_hash: str,
    batch_id: str,
    mercury_ppm: float,
    pcbs_ppm: float,
    dioxins_pg_per_g: float,
    epa_mg: float,
    dha_mg: float,
    label_claim_mg: float,
    peroxide_meq_per_kg: float,
    anisidine: float,
    previous_hash: str,
    tenant_id: str | None = None,
    ledger_path: str | None = None,
) -> dict:
    """Create a Stage 3 testing receipt.

    Args:
        lab_name: Laboratory name.
        lab_cert_type: ISO17025 or Other.
        lab_cert_id: Lab certificate ID.
        lab_cert_hash: Dual-hash of lab certificate.
        batch_id: Batch identifier linking to processing.
        mercury_ppm: Mercury level in ppm.
        pcbs_ppm: PCBs level in ppm.
        dioxins_pg_per_g: Dioxins level in pg/g.
        epa_mg: EPA content in mg.
        dha_mg: DHA content in mg.
        label_claim_mg: Label claim for total omega-3 in mg.
        peroxide_meq_per_kg: Peroxide value.
        anisidine: p-Anisidine value.
        previous_hash: payload_hash of the linked processing_receipt.
        tenant_id: Tenant identifier.
        ledger_path: Override ledger path.

    Returns:
        Testing receipt dict.

    Raises:
        StopRule: On validation failures.
    """
    if lab_cert_type not in LAB_CERT_TYPES:
        raise StopRule(f"Invalid lab cert type: {lab_cert_type}")

    if ":" not in lab_cert_hash:
        raise StopRule("Lab cert hash must be dual-hash format (SHA256:BLAKE3)")

    contaminants = validate_contaminants(mercury_ppm, pcbs_ppm, dioxins_pg_per_g)
    potency = validate_potency(epa_mg, dha_mg, label_claim_mg)
    oxidation = validate_oxidation(peroxide_meq_per_kg, anisidine)

    overall_pass = (
        contaminants["all_pass"] and potency["potency_pass"] and oxidation["oxidation_pass"]
    )

    # StopRule on contaminant exceed — cannot ship
    if not contaminants["all_pass"]:
        failed = []
        if not contaminants["mercury_pass"]:
            failed.append(f"mercury={mercury_ppm}ppm (limit {LIMITS['mercury_ppm']})")
        if not contaminants["pcbs_pass"]:
            failed.append(f"pcbs={pcbs_ppm}ppm (limit {LIMITS['pcbs_ppm']})")
        if not contaminants["dioxins_pass"]:
            failed.append(f"dioxins={dioxins_pg_per_g}pg/g (limit {LIMITS['dioxins_pg_per_g']})")
        # Still emit the receipt (for audit trail) then raise
        receipt = _emit_testing(
            lab_name, lab_cert_type, lab_cert_id, lab_cert_hash, batch_id,
            contaminants, potency, oxidation, overall_pass, previous_hash,
            tenant_id, ledger_path,
        )
        raise StopRule(f"CONTAMINANT_EXCEED: {', '.join(failed)}. Receipt emitted: {receipt['payload_hash']}")

    # StopRule on rancid product
    if oxidation["totox"] > LIMITS["totox"]:
        receipt = _emit_testing(
            lab_name, lab_cert_type, lab_cert_id, lab_cert_hash, batch_id,
            contaminants, potency, oxidation, overall_pass, previous_hash,
            tenant_id, ledger_path,
        )
        raise StopRule(f"TOTOX_EXCEED: {oxidation['totox']} > {LIMITS['totox']}. Receipt emitted: {receipt['payload_hash']}")

    return _emit_testing(
        lab_name, lab_cert_type, lab_cert_id, lab_cert_hash, batch_id,
        contaminants, potency, oxidation, overall_pass, previous_hash,
        tenant_id, ledger_path,
    )


def _emit_testing(
    lab_name, lab_cert_type, lab_cert_id, lab_cert_hash, batch_id,
    contaminants, potency, oxidation, overall_pass, previous_hash,
    tenant_id, ledger_path,
) -> dict:
    """Internal: emit the testing receipt."""
    payload = {
        "lab_name": lab_name,
        "lab_cert_type": lab_cert_type,
        "lab_cert_id": lab_cert_id,
        "lab_cert_hash": lab_cert_hash,
        "batch_id": batch_id,
        "contaminants": contaminants,
        "potency": potency,
        "oxidation": oxidation,
        "overall_pass": overall_pass,
        "previous_hash": previous_hash,
    }

    return emit_receipt("testing", payload, tenant_id=tenant_id, ledger_path=ledger_path)
