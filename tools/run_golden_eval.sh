#!/bin/bash
# Golden Set Evaluation Runner
# STEP V2-7: Golden Set Regression Core
#
# 목적: 회귀 방지를 위한 Golden Set 평가
# 원칙:
#   - 최소 3건/결정 (determined, no_amount, condition_mismatch, etc.)
#   - partial_failure_ratio >= 50%
#   - 보험사 균형 (round-robin)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "  Golden Set Evaluation Runner (V2-7)"
echo "=========================================="
echo ""

cd "$PROJECT_ROOT"

# Check required files
GOLDEN_SET_FILE="$PROJECT_ROOT/eval/golden_set_v2_7.json"
SMOKE_CASES_FILE="$PROJECT_ROOT/eval/e2e_smoke_cases.yaml"

if [ ! -f "$GOLDEN_SET_FILE" ]; then
    echo "ERROR: Golden Set file not found: $GOLDEN_SET_FILE"
    exit 1
fi

if [ ! -f "$SMOKE_CASES_FILE" ]; then
    echo "ERROR: Smoke Cases file not found: $SMOKE_CASES_FILE"
    exit 1
fi

echo "Golden Set: $GOLDEN_SET_FILE"
echo "Smoke Cases: $SMOKE_CASES_FILE"
echo ""

# Display golden set statistics
echo "[INFO] Golden Set Statistics:"
echo "------------------------------------------"
python3 -c "
import json
with open('$GOLDEN_SET_FILE', 'r') as f:
    data = json.load(f)
    stats = data.get('statistics', {})
    print(f\"  Total Cases: {stats.get('total_cases', 'N/A')}\")
    print(f\"  Determined: {stats.get('determined', 'N/A')}\")
    print(f\"  No Amount: {stats.get('no_amount', 'N/A')}\")
    print(f\"  Condition Mismatch: {stats.get('condition_mismatch', 'N/A')}\")
    print(f\"  Definition Only: {stats.get('definition_only', 'N/A')}\")
    print(f\"  Insufficient Evidence: {stats.get('insufficient_evidence', 'N/A')}\")
    print(f\"  Multi Insurer: {stats.get('multi_insurer', 'N/A')}\")
    print(f\"  Partial Failure: {stats.get('partial_failure', 'N/A')}\")
    print(f\"  Partial Failure Ratio: {stats.get('partial_failure_ratio', 'N/A')}\")
"
echo "------------------------------------------"
echo ""

# Run all golden set tests
echo "[1/2] Running Golden Set Tests..."
echo "------------------------------------------"

python -m pytest tests/test_e2e_smoke.py \
    -v \
    --tb=short \
    -k "GoldenSet" \
    2>&1

GOLDEN_EXIT_CODE=$?

echo ""
echo "------------------------------------------"

if [ $GOLDEN_EXIT_CODE -eq 0 ]; then
    echo "[PASS] Golden Set evaluation passed"
else
    echo "[FAIL] Golden Set evaluation failed (exit code: $GOLDEN_EXIT_CODE)"
fi

# Run multi-insurer tests
echo ""
echo "[2/2] Running Multi-Insurer Tests..."
echo "------------------------------------------"

python -m pytest tests/test_e2e_smoke.py \
    -v \
    --tb=short \
    -k "MultiInsurer" \
    2>&1

MULTI_EXIT_CODE=$?

echo ""
echo "------------------------------------------"

if [ $MULTI_EXIT_CODE -eq 0 ]; then
    echo "[PASS] Multi-Insurer tests passed"
else
    echo "[FAIL] Multi-Insurer tests failed (exit code: $MULTI_EXIT_CODE)"
fi

# Final summary
echo ""
echo "=========================================="
echo "  Evaluation Summary"
echo "=========================================="
echo ""

TOTAL_PASS=0
TOTAL_FAIL=0

if [ $GOLDEN_EXIT_CODE -eq 0 ]; then
    echo "  Golden Set Tests:     PASS"
    ((TOTAL_PASS++))
else
    echo "  Golden Set Tests:     FAIL"
    ((TOTAL_FAIL++))
fi

if [ $MULTI_EXIT_CODE -eq 0 ]; then
    echo "  Multi-Insurer Tests:  PASS"
    ((TOTAL_PASS++))
else
    echo "  Multi-Insurer Tests:  FAIL"
    ((TOTAL_FAIL++))
fi

echo ""
echo "------------------------------------------"
echo "  Total: $TOTAL_PASS PASS, $TOTAL_FAIL FAIL"
echo "=========================================="

if [ $TOTAL_FAIL -gt 0 ]; then
    exit 1
fi

exit 0
