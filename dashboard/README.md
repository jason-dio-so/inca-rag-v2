# INCA RAG V2 - Ops Dashboard

## Overview

Read-only operations dashboard for monitoring INCA RAG V2 system health.

**Purpose**: Enable operators to instantly determine:
- Is the system healthy?
- Where is it degrading?
- Is immediate action required?

## Quick Start

### Local

```bash
# 1. Generate metrics (if not already done)
tools/run_metrics_collect.sh

# 2. Open dashboard
open dashboard/index.html
```

### From CI Artifacts

1. Go to GitHub Actions → Nightly Ops Monitoring
2. Download `ops-metrics-*` artifact
3. Extract and open `dashboard/index.html`

## Dashboard Sections

### 1. Overview (Top)
- Current status: OK / WARNING / ERROR
- Key metrics at a glance
- Partial Failure %
- Golden Drift count

### 2. Decision Distribution
- Pie chart showing 5 decision types
- DETERMINED (green) = success
- Others = partial failures

### 3. Partial Failure by Type
- Bar chart breaking down failure types
- NO_AMOUNT, CONDITION_MISMATCH, etc.

### 4. Evidence Quality
- PASS1 success rate
- PASS2 augmentation rate

### 5. Source Boundary
- Document type distribution
- 약관 vs 사업방법서 vs 상품요약서

### 6. Golden Drift Panel
- Highlighted when drift detected
- Shows regressions (DETERMINED → Failure)
- Decision and rule changes

## Data Source

Dashboard reads ONLY from `metrics/` directory:

```
metrics/
├── ops_summary.json
├── decision_distribution.json
├── partial_failure_rate.json
├── evidence_quality.json
├── source_boundary.json
└── golden_diff.json
```

**Important**: Dashboard does NOT calculate or transform data.
All metrics are pre-computed by V2-8 collectors.

## Status Levels

| Level | Visual | Meaning |
|-------|--------|---------|
| OK | ✅ Green | System healthy |
| WARNING | ⚠️ Yellow | Review recommended |
| ERROR | ❌ Red | Immediate action required |

## Technology

- Static HTML + JavaScript
- Chart.js for visualizations
- No server required
- No external dependencies (CDN for Chart.js)

## Absolute Prohibitions

- ❌ No metric recalculation
- ❌ No engine/golden modification
- ❌ No LLM-based interpretation
- ❌ No "everything is fine" auto-messages

## Files

```
dashboard/
├── index.html      # Main dashboard page
├── dashboard.js    # Visualization logic
└── README.md       # This file
```

## References

- [OPS-V2-8-monitoring.md](../docs/ops/OPS-V2-8-monitoring.md) - Metrics documentation
- [ROADMAP.md](../docs/v2/ROADMAP.md) - V2 Roadmap
- [CLAUDE.md](../CLAUDE.md) - Execution Constitution
