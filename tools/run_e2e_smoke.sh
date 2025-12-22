#!/bin/bash
# E2E Smoke Test Runner
# STEP V2-7: End-to-End 실상품 다보험사 Smoke
#
# 목적: 엔진·결정·설명 전체 파이프라인 E2E 검증
# 원칙: Smoke는 빠르고 결정적이어야 한다

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "  E2E Smoke Test Runner (V2-7)"
echo "=========================================="
echo ""

cd "$PROJECT_ROOT"

# Check Python environment
if ! command -v python &> /dev/null; then
    echo "ERROR: Python not found"
    exit 1
fi

# Run smoke tests only
echo "[1/3] Running Smoke Tests..."
echo "------------------------------------------"

python -m pytest tests/test_e2e_smoke.py \
    -v \
    --tb=short \
    -k "Smoke" \
    --timeout=30 \
    2>&1 | head -100

SMOKE_EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "------------------------------------------"

if [ $SMOKE_EXIT_CODE -eq 0 ]; then
    echo "[PASS] Smoke tests passed"
else
    echo "[FAIL] Smoke tests failed (exit code: $SMOKE_EXIT_CODE)"
    exit $SMOKE_EXIT_CODE
fi

# Run golden set tests
echo ""
echo "[2/3] Running Golden Set Tests..."
echo "------------------------------------------"

python -m pytest tests/test_e2e_smoke.py \
    -v \
    --tb=short \
    -k "GoldenSet" \
    --timeout=30 \
    2>&1 | head -100

GOLDEN_EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "------------------------------------------"

if [ $GOLDEN_EXIT_CODE -eq 0 ]; then
    echo "[PASS] Golden Set tests passed"
else
    echo "[FAIL] Golden Set tests failed (exit code: $GOLDEN_EXIT_CODE)"
    exit $GOLDEN_EXIT_CODE
fi

# Run regression tests
echo ""
echo "[3/3] Running Regression Tests..."
echo "------------------------------------------"

python -m pytest tests/test_e2e_smoke.py \
    -v \
    --tb=short \
    -k "Regression or Pipeline" \
    --timeout=30 \
    2>&1 | head -100

REGRESSION_EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "------------------------------------------"

if [ $REGRESSION_EXIT_CODE -eq 0 ]; then
    echo "[PASS] Regression tests passed"
else
    echo "[FAIL] Regression tests failed (exit code: $REGRESSION_EXIT_CODE)"
    exit $REGRESSION_EXIT_CODE
fi

echo ""
echo "=========================================="
echo "  All E2E Smoke Tests Passed!"
echo "=========================================="
