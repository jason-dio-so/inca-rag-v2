#!/bin/bash
# Golden Drift Detection Script
# V2-8: Operations Monitoring & Drift Detection
#
# Purpose: Compare current golden set results with baseline
#          to detect regressions and decision changes
#
# Usage: tools/run_golden_drift.sh [--baseline <file>]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
METRICS_DIR="$PROJECT_ROOT/metrics"
BASELINE_FILE="${1:-$METRICS_DIR/golden_baseline.json}"

echo "=========================================="
echo "  Golden Drift Detection (V2-8)"
echo "=========================================="
echo ""

cd "$PROJECT_ROOT"

# Ensure metrics directory exists
mkdir -p "$METRICS_DIR"

# Run the Python drift detector
python3 "$SCRIPT_DIR/detect_golden_drift.py" --baseline "$BASELINE_FILE"

DRIFT_EXIT_CODE=$?

echo ""
echo "=========================================="

if [ $DRIFT_EXIT_CODE -eq 0 ]; then
    echo "  Status: NO DRIFT DETECTED"
    echo "=========================================="
elif [ $DRIFT_EXIT_CODE -eq 1 ]; then
    echo "  Status: WARNING - Minor drift detected"
    echo "=========================================="
elif [ $DRIFT_EXIT_CODE -eq 2 ]; then
    echo "  Status: ERROR - Significant drift detected"
    echo "=========================================="
    exit 2
else
    echo "  Status: UNKNOWN (exit code: $DRIFT_EXIT_CODE)"
    echo "=========================================="
    exit $DRIFT_EXIT_CODE
fi
