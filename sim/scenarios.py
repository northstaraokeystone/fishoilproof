"""
5 Mandatory Monte Carlo Scenarios

1. BASELINE — Normal supply chain flow
2. DILUTION_FRAUD — Yield reconciliation catches dilution
3. COLD_CHAIN_FAILURE — Cold chain monitoring catches degradation
4. LABEL_FRAUD — Potency validation catches mislabeling
5. CHAIN_INTEGRITY — Chain verification catches tampering
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sim.sim import SimConfig, SimResult, run_scenario


def scenario_baseline() -> SimConfig:
    return SimConfig(
        name="BASELINE",
        n_cycles=100,
        random_seed=42,
    )


def scenario_dilution_fraud() -> SimConfig:
    return SimConfig(
        name="DILUTION_FRAUD",
        n_cycles=50,
        random_seed=100,
        yield_override=0.22,  # 22% yield = dilution
    )


def scenario_cold_chain_failure() -> SimConfig:
    return SimConfig(
        name="COLD_CHAIN_FAILURE",
        n_cycles=50,
        random_seed=200,
        max_temp_override=12.0,  # 12°C = above 8°C threshold
    )


def scenario_label_fraud() -> SimConfig:
    return SimConfig(
        name="LABEL_FRAUD",
        n_cycles=50,
        random_seed=300,
        actual_potency_override=600.0,  # 600mg actual vs 700mg label = 86%
    )


def scenario_chain_integrity() -> SimConfig:
    return SimConfig(
        name="CHAIN_INTEGRITY",
        n_cycles=50,
        random_seed=400,
        tamper_chain=True,
    )


ALL_SCENARIOS = [
    scenario_baseline,
    scenario_dilution_fraud,
    scenario_cold_chain_failure,
    scenario_label_fraud,
    scenario_chain_integrity,
]


def run_all() -> bool:
    """Run all 5 mandatory scenarios and return True if all pass."""
    all_pass = True

    for scenario_fn in ALL_SCENARIOS:
        config = scenario_fn()
        result = run_scenario(config)

        passed = result.failures == 0 and result.false_negatives == 0
        status = "PASS" if passed else "FAIL"

        print(f"[{status}] {result.name}: {result.successes}/{result.cycles_run} "
              f"(FP={result.false_positives}, FN={result.false_negatives})")

        if not passed:
            all_pass = False

    return all_pass


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
