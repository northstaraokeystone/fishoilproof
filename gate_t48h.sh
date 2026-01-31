#!/usr/bin/env bash
# Gate T+48h: HARDENED
# Monte Carlo passes, 100% coverage, MCP health
set -euo pipefail

echo "=== GATE T+48h: HARDENED ==="

echo "[1/3] Running all 5 Monte Carlo scenarios..."
python3 -c "from sim.scenarios import run_all; assert run_all()" && echo "  PASS" || { echo "  FAIL"; exit 1; }

echo "[2/3] Running tests with 100% coverage..."
python3 -m pytest tests/ -v --cov=src --cov-fail-under=100 && echo "  PASS" || { echo "  FAIL"; exit 1; }

echo "[3/3] MCP server health check..."
python3 mcp_server.py --health-check && echo "  PASS" || { echo "  FAIL"; exit 1; }

echo ""
echo "=== GATE T+48h: ALL CHECKS PASSED ==="
