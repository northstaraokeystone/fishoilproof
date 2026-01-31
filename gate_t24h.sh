#!/usr/bin/env bash
# Gate T+24h: MVP
# All modules importable, demo runs, 80% test coverage
set -euo pipefail

echo "=== GATE T+24h: MVP ==="

echo "[1/3] Checking all modules importable..."
python3 -c "from src import catch, processing, testing, encapsulation, distribution, chain, fraud" && echo "  PASS" || { echo "  FAIL"; exit 1; }

echo "[2/3] Running terminal demo..."
python3 demo/terminal_demo.py 2>&1 | grep -q "VERIFICATION COMPLETE" && echo "  PASS" || { echo "  FAIL"; exit 1; }

echo "[3/3] Running tests with 80% coverage..."
python3 -m pytest tests/ -v --cov=src --cov-fail-under=80 && echo "  PASS" || { echo "  FAIL"; exit 1; }

echo ""
echo "=== GATE T+24h: ALL CHECKS PASSED ==="
