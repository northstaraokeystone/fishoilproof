# FishOilProof v1.0 — Specification

## Mission
15-field supply chain telemetry with receipts-native fraud detection.
Track fish oil from ocean to bottle using cryptographically-chained receipt fields.

## Laws (CLAUDEME)
- LAW_1: No receipt -> not real
- LAW_2: No test -> not shipped
- LAW_3: No gate -> not alive

## Pipeline
```
CATCH -> PROCESSING -> TESTING -> ENCAPSULATION -> DISTRIBUTION
```

## Inputs
- Species identification data
- Fishery certifications (MSC/FoS PDFs)
- Import documents (PDF)
- GMP certificates (PDF)
- Lab test results (contaminants, potency, oxidation)
- IoT temperature logs (cold chain)

## Outputs
- 5 stage receipts (catch, processing, testing, encapsulation, distribution)
- Anomaly receipts (yield, label fraud, cold chain, contaminant)
- QR verification payload (JSON)
- Full chain verification report

## Receipt Types
| Receipt | Stage | Fields Covered |
|---------|-------|----------------|
| catch_receipt | Catch | 1-3, 13 |
| processing_receipt | Processing | 4-7, 14 |
| testing_receipt | Testing | 8-11 |
| encapsulation_receipt | Encapsulation | lot/fill |
| distribution_receipt | Distribution | 12, 15 |
| anomaly_receipt | Any | fraud flags |

## The 15 Fields
### Must-Have (12): FDA/GMP Compliance
1. Species identification
2. Approved fishery link
3. Import docs hash
4. Facility ID
5. GMP cert hash
6. Batch/lot ID
7. Extraction method
8. Lab cert (ISO 17025)
9. Contaminants (Hg, PCBs, dioxins)
10. Potency (EPA/DHA mg)
11. Oxidation (TOTOX)
12. Distribution records

### Strategic (3): Competitive Differentiation
13. Fishery certification (MSC/FoS) — per-batch sustainability proof
14. Yield reconciliation — catches dilution fraud
15. Cold chain monitoring — prevents oxidation during transport

## SLO Thresholds
| Metric | Threshold | Stoprule |
|--------|-----------|----------|
| Receipt emission latency | <100ms | Emit violation |
| Chain verification latency | <3s for 5 receipts | Emit violation |
| QR payload generation | <500ms | Emit violation |
| Fraud detection accuracy | 100% (no false negatives) | HALT |
| Chain integrity check | 100% (detect all tampering) | HALT |
| Memory usage | <1GB for 10k receipts | Emit violation |

## Stoprules
- Any contaminant exceeds FDA limit -> REJECT (cannot ship)
- TOTOX > 26 -> REJECT (rancid product)
- Chain hash verification fails -> HALT
- Fraud detection false negative -> HALT

## Fraud Detection Heuristics
- Yield ratio > 18% -> DILUTION_FLAG
- Yield ratio < 12% -> LOW_YIELD_FLAG
- Potency < 95% of label claim -> LABEL_FRAUD_FLAG
- Cold chain max_temp > 8C -> OXIDATION_RISK_FLAG
- Cold chain deviations > 3 -> STORAGE_WARNING
- Species not in FDA-approved list -> REJECT
- Import docs hash mismatch -> REJECT
- Fishery cert claimed but hash missing -> FLAG

## Cryptographic Strategy
- Dual-hash: SHA256:BLAKE3 on every payload
- Merkle tree: BLAKE3 for root computation
- Chain linking: each receipt.previous_hash = parent receipt.payload_hash
- Append-only ledger: receipts.jsonl (immutable)

## Monte Carlo Scenarios
1. BASELINE (100 cycles) — normal flow
2. DILUTION_FRAUD (50 cycles) — yield 22%
3. COLD_CHAIN_FAILURE (50 cycles) — max_temp 12C
4. LABEL_FRAUD (50 cycles) — 600mg actual vs 700mg label
5. CHAIN_INTEGRITY (50 cycles) — tamper simulation

## Gates
- T+2h: spec.md, ledger_schema.json, cli.py --test emits receipt
- T+24h: all modules importable, demo runs, 80% coverage
- T+48h: Monte Carlo passes, 100% coverage, MCP health
