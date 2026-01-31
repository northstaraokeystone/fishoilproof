#!/usr/bin/env python3
"""
FishOilProof MCP Server — Machine Control Protocol interface.

Exposes supply chain verification tools to Claude Desktop.

Tools:
  - query_receipts: Search receipts by type, lot, batch
  - verify_chain: Verify full 5-receipt chain for a lot
  - get_summary: Get consumer-friendly chain summary
  - generate_qr: Generate QR payload for a lot
  - run_fraud_checks: Run fraud detection on a chain
"""

import argparse
import json
import sys

from src.core import load_ledger
from src.chain import verify_chain, get_chain_summary, generate_qr_payload
from src.fraud import run_all_fraud_checks


def tool_query_receipts(receipt_type: str | None = None,
                        lot_number: str | None = None,
                        batch_id: str | None = None) -> list[dict]:
    """Query receipts from the ledger with optional filters."""
    receipts = load_ledger()

    results = []
    for r in receipts:
        if receipt_type and r.get("receipt_type") != receipt_type:
            continue
        if lot_number and r.get("lot_number") != lot_number:
            continue
        if batch_id and r.get("batch_id") != batch_id:
            continue
        results.append(r)

    return results


def tool_verify_chain(lot_number: str) -> dict:
    """Verify the full receipt chain for a lot number."""
    return verify_chain(lot_number)


def tool_get_summary(lot_number: str) -> dict:
    """Get a consumer-friendly chain summary."""
    return get_chain_summary(lot_number)


def tool_generate_qr(lot_number: str) -> str:
    """Generate QR payload JSON for a lot number."""
    return generate_qr_payload(lot_number)


def tool_run_fraud_checks(lot_number: str) -> list[dict]:
    """Run fraud detection algorithms on a lot's receipt chain."""
    chain_result = verify_chain(lot_number)
    if not chain_result.get("receipts"):
        return [{"error": f"No receipts found for lot {lot_number}"}]

    chain = list(chain_result["receipts"].values())
    return run_all_fraud_checks(chain)


# MCP tool definitions for Claude Desktop
MCP_TOOLS = [
    {
        "name": "query_receipts",
        "description": "Search fish oil supply chain receipts by type, lot number, or batch ID",
        "inputSchema": {
            "type": "object",
            "properties": {
                "receipt_type": {
                    "type": "string",
                    "enum": ["catch", "processing", "testing", "encapsulation", "distribution", "anomaly"],
                    "description": "Filter by receipt type",
                },
                "lot_number": {
                    "type": "string",
                    "description": "Filter by lot number",
                },
                "batch_id": {
                    "type": "string",
                    "description": "Filter by batch ID",
                },
            },
        },
    },
    {
        "name": "verify_chain",
        "description": "Verify the full 5-receipt supply chain for a fish oil lot number. Returns chain validity, all receipts, and any verification errors.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lot_number": {
                    "type": "string",
                    "description": "The lot number to verify",
                },
            },
            "required": ["lot_number"],
        },
    },
    {
        "name": "get_summary",
        "description": "Get a consumer-friendly summary of supply chain verification for a lot number",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lot_number": {
                    "type": "string",
                    "description": "The lot number to summarize",
                },
            },
            "required": ["lot_number"],
        },
    },
    {
        "name": "generate_qr",
        "description": "Generate a QR code payload (JSON) for a fish oil lot number",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lot_number": {
                    "type": "string",
                    "description": "The lot number for QR code",
                },
            },
            "required": ["lot_number"],
        },
    },
    {
        "name": "run_fraud_checks",
        "description": "Run fraud detection algorithms (yield anomaly, label fraud, cold chain degradation) on a lot's receipt chain",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lot_number": {
                    "type": "string",
                    "description": "The lot number to check for fraud",
                },
            },
            "required": ["lot_number"],
        },
    },
]


def handle_mcp_request(request: dict) -> dict:
    """Handle an MCP JSON-RPC request."""
    method = request.get("method", "")

    if method == "tools/list":
        return {"tools": MCP_TOOLS}

    elif method == "tools/call":
        params = request.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        handlers = {
            "query_receipts": tool_query_receipts,
            "verify_chain": tool_verify_chain,
            "get_summary": tool_get_summary,
            "generate_qr": tool_generate_qr,
            "run_fraud_checks": tool_run_fraud_checks,
        }

        if tool_name not in handlers:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            result = handlers[tool_name](**arguments)
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}]}
        except Exception as e:
            return {"error": str(e)}

    return {"error": f"Unknown method: {method}"}


def health_check() -> bool:
    """Run MCP server health check."""
    # Verify all tools are defined
    assert len(MCP_TOOLS) == 5, f"Expected 5 tools, got {len(MCP_TOOLS)}"

    # Verify tool list returns correctly
    result = handle_mcp_request({"method": "tools/list"})
    assert "tools" in result
    assert len(result["tools"]) == 5

    # Verify tool call works (even with no data)
    result = handle_mcp_request({
        "method": "tools/call",
        "params": {"name": "query_receipts", "arguments": {}},
    })
    assert "content" in result or "error" not in result

    print("MCP server health check: PASS")
    return True


def main():
    parser = argparse.ArgumentParser(description="FishOilProof MCP Server")
    parser.add_argument("--health-check", action="store_true", help="Run health check")
    parser.add_argument("--list-tools", action="store_true", help="List available tools")
    parser.add_argument("--stdio", action="store_true", help="Run in stdio mode (MCP protocol)")

    args = parser.parse_args()

    if args.health_check:
        success = health_check()
        sys.exit(0 if success else 1)

    elif args.list_tools:
        print(json.dumps(MCP_TOOLS, indent=2))

    elif args.stdio:
        # Read JSON-RPC requests from stdin
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = handle_mcp_request(request)
                print(json.dumps(response, default=str))
                sys.stdout.flush()
            except json.JSONDecodeError:
                print(json.dumps({"error": "Invalid JSON"}))
                sys.stdout.flush()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
