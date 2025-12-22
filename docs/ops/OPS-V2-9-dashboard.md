# V2-9: Operations Dashboard / Visualization

## Overview

V2-9 provides a visual operations dashboard for the INCA RAG V2 system.

**Purpose**: Enable operators to instantly judge system health without deep analysis.

> This is not a "pretty screen" — it's a screen that prevents delayed decisions.

## Architecture

```
V2-8 Metrics → Dashboard → Visual Judgment
     ↓              ↓
JSON/YAML    HTML + Chart.js
```

Dashboard is READ-ONLY. No calculations, no modifications.

## Dashboard Sections

### 1. Overview Banner
- System status: OK / WARNING / ERROR
- Based on `ops_summary.action_required`
- Key numbers at a glance

### 2. Decision Distribution
- Doughnut chart: 5 decision types
- Color coded: green (success), red/yellow (failures)
- Purpose: Detect system judgment tendency changes

### 3. Partial Failure Trend
- Bar chart by failure type
- NO_AMOUNT, CONDITION_MISMATCH, etc.
- Purpose: "Are we getting worse?"

### 4. Evidence Quality
- PASS1 success rate
- PASS2 augmentation rate
- Purpose: Early detection of document/preprocessing issues

### 5. Source Boundary Distribution
- Pie chart: doc_type distribution
- 약관 vs 사업방법서 vs 상품요약서
- Purpose: Detect legal basis weakening

### 6. Golden Drift Panel (Highlighted)
- Changed case count
- Decision change types
- Rule change detection
- 🚨 Red card when drift detected

## Technical Implementation

### Files

```
dashboard/
├── index.html      # Main page (static HTML)
├── dashboard.js    # Chart.js visualizations
└── README.md       # Usage documentation
```

### Technology Stack
- HTML5 + CSS3 (dark theme)
- JavaScript (vanilla)
- Chart.js 4.x (CDN)
- No server required

### Data Flow

```
metrics/ops_summary.json ──────┐
metrics/decision_distribution.json ──┤
metrics/partial_failure_rate.json ───┼──→ dashboard.js ──→ Charts
metrics/evidence_quality.json ───────┤
metrics/source_boundary.json ────────┤
metrics/golden_diff.json ────────────┘
```

## Running the Dashboard

### Local
```bash
# Generate metrics first
tools/run_metrics_collect.sh

# Open in browser
open dashboard/index.html
```

### CI Artifacts
- Nightly workflow uploads dashboard + metrics as artifact
- Download from GitHub Actions UI
- Extract and open `index.html`

## Validation Scenarios

| Scenario | Expected Behavior |
|----------|-------------------|
| Metrics missing | ERROR state displayed |
| Partial Failure spike | Overview → WARNING/ERROR |
| Golden Drift detected | Golden Panel highlighted red |
| All healthy | Overview → OK (green) |

## Absolute Prohibitions

- ❌ Recalculate metrics in dashboard
- ❌ Modify engine/golden directly
- ❌ Auto-generate "no issues" messages
- ❌ Add LLM-based interpretation

## Status Mapping

| Level | Color | Meaning |
|-------|-------|---------|
| INFO | ✅ Green | Normal range |
| WARNING | ⚠️ Yellow | Review recommended |
| ERROR | ❌ Red | Root cause analysis required |

## References

- [OPS-V2-8-monitoring.md](OPS-V2-8-monitoring.md) - Metrics system
- [ROADMAP.md](../v2/ROADMAP.md) - V2 Roadmap
- [CLAUDE.md](../../CLAUDE.md) - Execution Constitution
