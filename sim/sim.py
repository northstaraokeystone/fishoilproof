"""
Monte Carlo Simulation Runner

Runs configurable scenarios against the FishOilProof pipeline.
Each cycle creates a full receipt chain and validates outcomes.
"""

import os
import sys
import random
import tempfile
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.core import dual_hash, StopRule
from src.catch import create_catch_receipt
from src.processing import create_processing_receipt
from src.testing import create_testing_receipt
from src.encapsulation import create_encapsulation_receipt
from src.distribution import create_distribution_receipt, validate_cold_chain
from src.chain import verify_chain
from src.fraud import run_all_fraud_checks


@dataclass
class SimConfig:
    name: str
    n_cycles: int
    random_seed: int = 42
    # Overrides for injection
    yield_override: float | None = None
    max_temp_override: float | None = None
    actual_potency_override: float | None = None
    tamper_chain: bool = False
    success_criteria: list = field(default_factory=list)


@dataclass
class SimResult:
    name: str
    cycles_run: int
    successes: int
    failures: int
    false_positives: int
    false_negatives: int
    details: list = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.successes / self.cycles_run if self.cycles_run > 0 else 0.0


def _make_fake_hash(label: str) -> str:
    """Generate a deterministic fake dual-hash for simulation."""
    return dual_hash(label.encode())


def run_single_cycle(
    config: SimConfig,
    cycle_num: int,
    ledger_path: str,
) -> dict:
    """Run a single simulation cycle through all 5 stages.

    Returns dict with cycle results including receipts and anomalies.
    """
    rng = random.Random(config.random_seed + cycle_num)

    result = {
        "cycle": cycle_num,
        "receipts": {},
        "anomalies": [],
        "chain_valid": False,
        "errors": [],
    }

    batch_id = f"SIM-{config.name}-{cycle_num:04d}"
    lot_number = f"LOT-SIM-{cycle_num:04d}-{config.name[:2].upper()}"

    try:
        # Stage 1: Catch
        catch = create_catch_receipt(
            species="Engraulis ringens",
            fishery_registry="PRODUCE Peru",
            import_docs_hash=_make_fake_hash(f"import_{batch_id}"),
            fishery_cert_type="MSC",
            fishery_cert_id=f"MSC-SIM-{cycle_num}",
            fishery_cert_hash=_make_fake_hash(f"msc_{batch_id}"),
            ledger_path=ledger_path,
        )
        result["receipts"]["catch"] = catch

        # Stage 2: Processing (with optional yield override)
        yield_input = 1000.0
        if config.yield_override is not None:
            yield_output = yield_input * config.yield_override
        else:
            yield_output = yield_input * rng.uniform(0.13, 0.17)  # normal range

        processing = create_processing_receipt(
            facility_id="SIM-FAC-01",
            facility_name="Simulation Facility",
            gmp_cert_type="NSF",
            gmp_cert_id=f"NSF-SIM-{cycle_num}",
            gmp_cert_hash=_make_fake_hash(f"gmp_{batch_id}"),
            batch_id=batch_id,
            extraction_method="MolecularDistillation",
            extraction_temp_c=240.0,
            yield_input_kg=yield_input,
            yield_output_kg=round(yield_output, 2),
            previous_hash=catch["payload_hash"],
            ledger_path=ledger_path,
        )
        result["receipts"]["processing"] = processing

        # Stage 3: Testing (with optional potency override)
        if config.actual_potency_override is not None:
            epa = config.actual_potency_override * 0.583  # typical EPA/DHA ratio
            dha = config.actual_potency_override * 0.417
        else:
            epa = rng.uniform(380, 450)
            dha = rng.uniform(270, 320)

        testing = create_testing_receipt(
            lab_name="Sim Lab",
            lab_cert_type="ISO17025",
            lab_cert_id=f"ISO-SIM-{cycle_num}",
            lab_cert_hash=_make_fake_hash(f"lab_{batch_id}"),
            batch_id=batch_id,
            mercury_ppm=rng.uniform(0.01, 0.05),
            pcbs_ppm=rng.uniform(0.01, 0.05),
            dioxins_pg_per_g=rng.uniform(0.5, 2.0),
            epa_mg=round(epa, 1),
            dha_mg=round(dha, 1),
            label_claim_mg=700.0,
            peroxide_meq_per_kg=rng.uniform(2.0, 4.5),
            anisidine=rng.uniform(8.0, 15.0),
            previous_hash=processing["payload_hash"],
            ledger_path=ledger_path,
        )
        result["receipts"]["testing"] = testing

        # Stage 4: Encapsulation
        encap = create_encapsulation_receipt(
            facility_id="SIM-BOTTLE-01",
            facility_name="Sim Bottling",
            facility_cert_type="NSF",
            facility_cert_id=f"NSF-SIM-BOT-{cycle_num}",
            facility_cert_hash=_make_fake_hash(f"bottle_{batch_id}"),
            lot_number=lot_number,
            fill_date="2025-01-31T12:00:00Z",
            batch_id=batch_id,
            capsule_count=90,
            mg_per_capsule=1000.0,
            previous_hash=testing["payload_hash"],
            ledger_path=ledger_path,
        )
        result["receipts"]["encapsulation"] = encap

        # Stage 5: Distribution (with optional temp override)
        if config.max_temp_override is not None:
            temps = [rng.uniform(2.0, config.max_temp_override) for _ in range(10)]
            temps.append(config.max_temp_override)  # ensure max is hit
        else:
            temps = [rng.uniform(2.5, 6.0) for _ in range(10)]  # within 2-8°C range

        cold_chain = validate_cold_chain(temps, duration_days=90)

        dist = create_distribution_receipt(
            distributor_id="SIM-DIST-01",
            distributor_name="Sim Distribution",
            warehouse_id="SIM-WH-01",
            warehouse_location="Simulation City",
            lot_number=lot_number,
            cold_chain_data=cold_chain,
            previous_hash=encap["payload_hash"],
            ledger_path=ledger_path,
        )
        result["receipts"]["distribution"] = dist

        # Tamper simulation
        if config.tamper_chain:
            # Modify a receipt in the ledger after emission
            import json
            with open(ledger_path, "r") as f:
                lines = f.readlines()
            if len(lines) >= 3:
                # Tamper with the processing receipt (line index 1)
                tampered = json.loads(lines[1])
                tampered["yield_output_kg"] = 999.0  # obviously wrong
                lines[1] = json.dumps(tampered) + "\n"
                with open(ledger_path, "w") as f:
                    f.writelines(lines)

        # Verify chain
        chain_result = verify_chain(lot_number, ledger_path=ledger_path)
        result["chain_valid"] = chain_result["chain_valid"]

        # Run fraud checks
        chain_receipts = list(chain_result["receipts"].values()) if chain_result["receipts"] else []
        anomalies = run_all_fraud_checks(chain_receipts, ledger_path=ledger_path)
        result["anomalies"] = anomalies

    except StopRule as e:
        result["errors"].append(str(e))
    except Exception as e:
        result["errors"].append(f"Unexpected: {e}")

    return result


def run_scenario(config: SimConfig) -> SimResult:
    """Run a full Monte Carlo scenario.

    Args:
        config: Simulation configuration.

    Returns:
        SimResult with aggregated outcomes.
    """
    sim_result = SimResult(
        name=config.name,
        cycles_run=0,
        successes=0,
        failures=0,
        false_positives=0,
        false_negatives=0,
    )

    for i in range(config.n_cycles):
        # Each cycle gets its own ledger to avoid cross-contamination
        ledger_path = tempfile.mktemp(suffix=f"_{config.name}_{i}.jsonl")

        try:
            cycle_result = run_single_cycle(config, i, ledger_path)
            sim_result.cycles_run += 1
            sim_result.details.append(cycle_result)

            # Evaluate success based on scenario type
            if config.name == "BASELINE":
                if cycle_result["chain_valid"] and not cycle_result["anomalies"] and not cycle_result["errors"]:
                    sim_result.successes += 1
                else:
                    sim_result.failures += 1
                    if cycle_result["anomalies"]:
                        sim_result.false_positives += len(cycle_result["anomalies"])

            elif config.name == "DILUTION_FRAUD":
                has_yield_anomaly = any(
                    a.get("anomaly_type") == "YIELD_HIGH" for a in cycle_result["anomalies"]
                )
                if has_yield_anomaly:
                    sim_result.successes += 1
                else:
                    sim_result.failures += 1
                    sim_result.false_negatives += 1

            elif config.name == "COLD_CHAIN_FAILURE":
                has_cold_chain_anomaly = any(
                    a.get("anomaly_type") == "COLD_CHAIN_DEGRADATION" for a in cycle_result["anomalies"]
                )
                if has_cold_chain_anomaly:
                    sim_result.successes += 1
                else:
                    sim_result.failures += 1
                    sim_result.false_negatives += 1

            elif config.name == "LABEL_FRAUD":
                has_label_anomaly = any(
                    a.get("anomaly_type") == "LABEL_FRAUD" for a in cycle_result["anomalies"]
                )
                if has_label_anomaly:
                    sim_result.successes += 1
                else:
                    sim_result.failures += 1
                    sim_result.false_negatives += 1

            elif config.name == "CHAIN_INTEGRITY":
                if not cycle_result["chain_valid"]:
                    sim_result.successes += 1  # correctly detected tamper
                else:
                    sim_result.failures += 1
                    sim_result.false_negatives += 1

        finally:
            try:
                os.unlink(ledger_path)
            except OSError:
                pass

    return sim_result
