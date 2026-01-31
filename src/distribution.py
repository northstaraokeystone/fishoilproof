"""
Stage 5: Distribution Receipt — Fields 12, 15

Proves chain of custody + cold chain integrity.
Distributor data, warehouse data, temperature logs.
"""

from .core import emit_receipt, find_receipt, StopRule

# Cold chain thresholds
COLD_CHAIN_TARGET_MIN = 2.0   # °C
COLD_CHAIN_TARGET_MAX = 8.0   # °C
COLD_CHAIN_MAX_DEVIATIONS = 3


def validate_cold_chain(
    temps: list[float],
    duration_days: int,
    temp_log_hash: str | None = None,
) -> dict:
    """Validate cold chain temperature data.

    Args:
        temps: List of temperature readings in °C.
        duration_days: Duration of storage/transport in days.
        temp_log_hash: Dual-hash of IoT temperature log file.

    Returns:
        Dict with cold chain stats and pass/fail.
    """
    if not temps:
        return {
            "enabled": False,
            "avg_temp_c": None,
            "min_temp_c": None,
            "max_temp_c": None,
            "duration_days": duration_days,
            "deviations_count": 0,
            "temp_log_hash": temp_log_hash,
            "cold_chain_pass": False,
        }

    avg_temp = sum(temps) / len(temps)
    min_temp = min(temps)
    max_temp = max(temps)
    deviations = sum(1 for t in temps if t < COLD_CHAIN_TARGET_MIN or t > COLD_CHAIN_TARGET_MAX)

    cold_chain_pass = max_temp <= COLD_CHAIN_TARGET_MAX and deviations <= COLD_CHAIN_MAX_DEVIATIONS

    return {
        "enabled": True,
        "avg_temp_c": round(avg_temp, 2),
        "min_temp_c": round(min_temp, 2),
        "max_temp_c": round(max_temp, 2),
        "duration_days": duration_days,
        "deviations_count": deviations,
        "temp_log_hash": temp_log_hash,
        "cold_chain_pass": cold_chain_pass,
    }


def link_to_encapsulation(lot_number: str, ledger_path: str | None = None) -> dict | None:
    """Find parent encapsulation receipt by lot_number.

    Args:
        lot_number: Consumer-facing lot number.
        ledger_path: Override ledger path.

    Returns:
        Encapsulation receipt dict or None.
    """
    return find_receipt("encapsulation", "lot_number", lot_number, ledger_path=ledger_path)


def create_distribution_receipt(
    distributor_id: str,
    distributor_name: str,
    warehouse_id: str,
    warehouse_location: str,
    lot_number: str,
    cold_chain_data: dict | None,
    previous_hash: str,
    tenant_id: str | None = None,
    ledger_path: str | None = None,
) -> dict:
    """Create a Stage 5 distribution receipt.

    Args:
        distributor_id: Distributor identifier.
        distributor_name: Human-readable distributor name.
        warehouse_id: Warehouse identifier.
        warehouse_location: Warehouse location string.
        lot_number: Lot number linking to encapsulation.
        cold_chain_data: Cold chain validation result dict, or None if not tracked.
        previous_hash: payload_hash of the linked encapsulation_receipt.
        tenant_id: Tenant identifier.
        ledger_path: Override ledger path.

    Returns:
        Distribution receipt dict.
    """
    if cold_chain_data is None:
        cold_chain_data = {
            "enabled": False,
            "avg_temp_c": None,
            "min_temp_c": None,
            "max_temp_c": None,
            "duration_days": 0,
            "deviations_count": 0,
            "temp_log_hash": None,
            "cold_chain_pass": False,
        }

    payload = {
        "distributor_id": distributor_id,
        "distributor_name": distributor_name,
        "warehouse_id": warehouse_id,
        "warehouse_location": warehouse_location,
        "lot_number": lot_number,
        "cold_chain": cold_chain_data,
        "previous_hash": previous_hash,
    }

    return emit_receipt("distribution", payload, tenant_id=tenant_id, ledger_path=ledger_path)
