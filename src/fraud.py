"""
Fraud Detection Algorithms

Yield anomaly, label fraud, cold chain degradation, contaminant exceedance.
Each detector returns an anomaly_receipt if fraud is detected.
"""

from .core import emit_receipt


def detect_yield_anomaly(processing_receipt: dict, ledger_path: str | None = None) -> dict | None:
    """Detect yield anomalies in processing receipt.

    Args:
        processing_receipt: A processing receipt dict.
        ledger_path: Override ledger path.

    Returns:
        Anomaly receipt if flagged, None otherwise.
    """
    yield_status = processing_receipt.get("yield_status")
    yield_ratio = processing_receipt.get("yield_ratio", 0)

    if yield_status == "HIGH_DILUTION_FLAG":
        return emit_receipt("anomaly", {
            "anomaly_type": "YIELD_HIGH",
            "severity": "FLAG",
            "source_receipt_hash": processing_receipt.get("payload_hash", ""),
            "details": {
                "yield_ratio": yield_ratio,
                "yield_input_kg": processing_receipt.get("yield_input_kg"),
                "yield_output_kg": processing_receipt.get("yield_output_kg"),
                "expected_max": processing_receipt.get("yield_expected_max", 0.18),
                "message": f"Yield {yield_ratio:.1%} exceeds expected max 18%. Possible dilution with cheaper oils.",
            },
        }, tenant_id=processing_receipt.get("tenant_id"), ledger_path=ledger_path)

    if yield_status == "LOW":
        return emit_receipt("anomaly", {
            "anomaly_type": "YIELD_LOW",
            "severity": "WARNING",
            "source_receipt_hash": processing_receipt.get("payload_hash", ""),
            "details": {
                "yield_ratio": yield_ratio,
                "yield_input_kg": processing_receipt.get("yield_input_kg"),
                "yield_output_kg": processing_receipt.get("yield_output_kg"),
                "expected_min": processing_receipt.get("yield_expected_min", 0.12),
                "message": f"Yield {yield_ratio:.1%} below expected min 12%. Possible extraction issue.",
            },
        }, tenant_id=processing_receipt.get("tenant_id"), ledger_path=ledger_path)

    return None


def detect_label_fraud(testing_receipt: dict, ledger_path: str | None = None) -> dict | None:
    """Detect label fraud in testing receipt.

    Args:
        testing_receipt: A testing receipt dict.
        ledger_path: Override ledger path.

    Returns:
        Anomaly receipt if flagged, None otherwise.
    """
    potency = testing_receipt.get("potency", {})
    if not potency.get("potency_pass", True):
        total = potency.get("total_omega3_mg", 0)
        claim = potency.get("label_claim_mg", 0)
        pct = (total / claim * 100) if claim > 0 else 0

        return emit_receipt("anomaly", {
            "anomaly_type": "LABEL_FRAUD",
            "severity": "FLAG",
            "source_receipt_hash": testing_receipt.get("payload_hash", ""),
            "details": {
                "actual_mg": total,
                "label_claim_mg": claim,
                "percentage_of_claim": round(pct, 1),
                "threshold": "95%",
                "message": f"Actual potency {total:.0f}mg is {pct:.1f}% of label claim {claim:.0f}mg (below 95% threshold).",
            },
        }, tenant_id=testing_receipt.get("tenant_id"), ledger_path=ledger_path)

    return None


def detect_contaminant_exceed(testing_receipt: dict, ledger_path: str | None = None) -> dict | None:
    """Detect contaminant exceedances in testing receipt.

    Args:
        testing_receipt: A testing receipt dict.
        ledger_path: Override ledger path.

    Returns:
        Anomaly receipt if flagged, None otherwise.
    """
    contaminants = testing_receipt.get("contaminants", {})
    if not contaminants.get("all_pass", True):
        failed = {}
        if not contaminants.get("mercury_pass", True):
            failed["mercury_ppm"] = contaminants.get("mercury_ppm")
        if not contaminants.get("pcbs_pass", True):
            failed["pcbs_ppm"] = contaminants.get("pcbs_ppm")
        if not contaminants.get("dioxins_pass", True):
            failed["dioxins_pg_per_g"] = contaminants.get("dioxins_pg_per_g")

        return emit_receipt("anomaly", {
            "anomaly_type": "CONTAMINANT_EXCEED",
            "severity": "REJECT",
            "source_receipt_hash": testing_receipt.get("payload_hash", ""),
            "details": {
                "failed_contaminants": failed,
                "message": "One or more contaminants exceed FDA/GOED limits. Product cannot ship.",
            },
        }, tenant_id=testing_receipt.get("tenant_id"), ledger_path=ledger_path)

    return None


def detect_cold_chain_degradation(distribution_receipt: dict, ledger_path: str | None = None) -> dict | None:
    """Detect cold chain degradation in distribution receipt.

    Args:
        distribution_receipt: A distribution receipt dict.
        ledger_path: Override ledger path.

    Returns:
        Anomaly receipt if flagged, None otherwise.
    """
    cold_chain = distribution_receipt.get("cold_chain", {})

    if not cold_chain.get("enabled", False):
        return None  # Cold chain not tracked, not a fail

    max_temp = cold_chain.get("max_temp_c")
    deviations = cold_chain.get("deviations_count", 0)

    if max_temp is not None and max_temp > 8.0:
        return emit_receipt("anomaly", {
            "anomaly_type": "COLD_CHAIN_DEGRADATION",
            "severity": "FLAG",
            "source_receipt_hash": distribution_receipt.get("payload_hash", ""),
            "details": {
                "max_temp_c": max_temp,
                "avg_temp_c": cold_chain.get("avg_temp_c"),
                "deviations_count": deviations,
                "threshold_max_c": 8.0,
                "message": f"Max temperature {max_temp}°C exceeds 8°C threshold. Oxidation risk.",
            },
        }, tenant_id=distribution_receipt.get("tenant_id"), ledger_path=ledger_path)

    if deviations > 3:
        return emit_receipt("anomaly", {
            "anomaly_type": "COLD_CHAIN_DEGRADATION",
            "severity": "WARNING",
            "source_receipt_hash": distribution_receipt.get("payload_hash", ""),
            "details": {
                "max_temp_c": max_temp,
                "deviations_count": deviations,
                "threshold_deviations": 3,
                "message": f"{deviations} temperature deviations exceed threshold of 3.",
            },
        }, tenant_id=distribution_receipt.get("tenant_id"), ledger_path=ledger_path)

    return None


def run_all_fraud_checks(chain: list[dict], ledger_path: str | None = None) -> list[dict]:
    """Run all fraud detection algorithms on a receipt chain.

    Args:
        chain: List of receipt dicts (any order).
        ledger_path: Override ledger path.

    Returns:
        List of anomaly receipts detected.
    """
    anomalies = []

    for receipt in chain:
        rtype = receipt.get("receipt_type")

        if rtype == "processing":
            result = detect_yield_anomaly(receipt, ledger_path=ledger_path)
            if result:
                anomalies.append(result)

        elif rtype == "testing":
            label_result = detect_label_fraud(receipt, ledger_path=ledger_path)
            if label_result:
                anomalies.append(label_result)

            contaminant_result = detect_contaminant_exceed(receipt, ledger_path=ledger_path)
            if contaminant_result:
                anomalies.append(contaminant_result)

        elif rtype == "distribution":
            cold_result = detect_cold_chain_degradation(receipt, ledger_path=ledger_path)
            if cold_result:
                anomalies.append(cold_result)

    return anomalies
