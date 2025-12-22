#!/bin/bash
# Metrics Collection Script
# V2-8: Operations Monitoring & Drift Detection
#
# Purpose: Collect decision distribution, partial failure rate,
#          evidence quality, and source boundary metrics
#
# Usage: tools/run_metrics_collect.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
METRICS_DIR="$PROJECT_ROOT/metrics"

echo "=========================================="
echo "  Metrics Collection (V2-8)"
echo "=========================================="
echo ""

cd "$PROJECT_ROOT"

# Ensure metrics directory exists
mkdir -p "$METRICS_DIR"

# Run the Python metrics collector
python3 "$SCRIPT_DIR/collect_metrics.py"

COLLECT_EXIT_CODE=$?

if [ $COLLECT_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "[PASS] Metrics collection completed"
    echo "  Output: $METRICS_DIR/ops_summary.json"
else
    echo ""
    echo "[FAIL] Metrics collection failed (exit code: $COLLECT_EXIT_CODE)"
    exit $COLLECT_EXIT_CODE
fi

# Display summary
echo ""
echo "=========================================="
echo "  Metrics Summary"
echo "=========================================="
python3 -c "
import json
with open('$METRICS_DIR/ops_summary.json', 'r') as f:
    data = json.load(f)
    print(f\"  Status: {data.get('status', 'UNKNOWN')}\")
    print(f\"  Level: {data.get('level', 'INFO')}\")
    print(f\"  Action Required: {data.get('action_required', False)}\")

    if data.get('warnings'):
        print(f\"  Warnings: {len(data['warnings'])}\")
    if data.get('errors'):
        print(f\"  Errors: {len(data['errors'])}\")
"
echo "=========================================="
