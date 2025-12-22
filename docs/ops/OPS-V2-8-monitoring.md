# V2-8: Operations Monitoring & Drift Detection

## Overview

V2-8 provides operational monitoring and drift detection for the Insurance Compare RAG system.

**Purpose**: Detect quality changes early and catch "silent degradation" before it becomes a problem.

> This stage doesn't fix problems — it alerts when problems start.

## Architecture

```
Golden Set → Metrics Collection → Drift Detection → Ops Report
                    ↓                    ↓
              Decision Dist.       Golden Diff
              Partial Failure      Regressions
              Evidence Quality     Rule Changes
              Source Boundary
```

## Metrics Collected

### 1. Decision Distribution
- Tracks distribution of all 5 decision types
- DETERMINED, NO_AMOUNT, CONDITION_MISMATCH, DEFINITION_ONLY, INSUFFICIENT_EVIDENCE
- Output: `metrics/decision_distribution.json`

### 2. Partial Failure Rate
- Measures percentage of non-DETERMINED outcomes
- Thresholds: 50% → WARNING, 70% → ERROR
- Output: `metrics/partial_failure_rate.json`

### 3. Evidence Quality
- PASS1 (Amount-centric) success rate
- PASS2 (Context Completion) augmentation rate
- Dropped evidence distribution by reason
- Output: `metrics/evidence_quality.json`

### 4. Source Boundary
- Doc type distribution (약관, 사업방법서, 상품요약서)
- Authoritative ratio (약관+사업방법서 vs others)
- Drift detection from baseline
- Output: `metrics/source_boundary.json`

### 5. Golden Drift
- Decision changes from baseline
- Regressions (DETERMINED → Partial Failure)
- Rule changes
- Output: `metrics/golden_diff.json`

## Warning Levels

| Level | Condition | Action |
|-------|-----------|--------|
| INFO | Normal range | Record only |
| WARNING | Approaching threshold | Review recommended |
| ERROR | Threshold exceeded | Root cause analysis required |

## Running Metrics Collection

```bash
# Collect all metrics
tools/run_metrics_collect.sh

# Detect golden drift
tools/run_golden_drift.sh

# Generate ops report
python tools/render_ops_report.py
```

## CI Integration

- **PR**: No ops monitoring (avoid overhead)
- **main/nightly**: Automatic execution
- **On failure**: CI fails with ops warning

Workflow: `.github/workflows/nightly-ops.yml`

## Report Output

Reports are generated in `docs/ops/`:
- `OPS-REPORT-YYYYMMDD.md` - Date-specific report
- `OPS-REPORT-LATEST.md` - Latest report

## Absolute Prohibitions

- ❌ Auto-modify rules based on drift detection
- ❌ Auto-update golden set expectations
- ❌ Replace reports with LLM summaries
- ❌ Hide partial failures

## References

- [CLAUDE.md](../../CLAUDE.md) — Execution Constitution
- [ROADMAP.md](../v2/ROADMAP.md) — V2 Roadmap
- [Golden Set](../../eval/golden_set_v2_7.json) — Regression Core
