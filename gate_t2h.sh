#!/usr/bin/env bash
# Gate T+2h: SKELETON
# Core functions exist and emit valid receipt
set -euo pipefail

echo "=== GATE T+2h: SKELETON ==="

echo "[1/4] Checking dual_hash..."
python3 -c "from src.core import dual_hash; assert ':' in dual_hash(b'test')" && echo "  PASS" || { echo "  FAIL"; exit 1; }

echo "[2/4] Checking cli.py --test emits receipt..."
python3 cli.py --test 2>&1 | grep -q '"receipt_type"' && echo "  PASS" || { echo "  FAIL"; exit 1; }

echo "[3/4] Checking ledger_schema.json exists..."
test -f ledger_schema.json && echo "  PASS" || { echo "  FAIL"; exit 1; }

echo "[4/4] Checking spec.md exists..."
test -f spec.md && echo "  PASS" || { echo "  FAIL"; exit 1; }

echo ""
echo "=== GATE T+2h: ALL CHECKS PASSED ==="
