#!/usr/bin/env python3
"""
Ops Report Renderer
V2-8: Operations Monitoring & Drift Detection

Renders collected metrics (JSON/YAML) into a Markdown report.

Output: docs/ops/OPS-REPORT-YYYYMMDD.md

This script does NOT:
- Modify engine logic
- Auto-fix issues
- Generate LLM summaries
"""

import json
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
METRICS_DIR = PROJECT_ROOT / "metrics"
OPS_DIR = PROJECT_ROOT / "docs" / "ops"


def load_json(path: Path) -> dict:
    """Load JSON file."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_level_emoji(level: str) -> str:
    """Get emoji for level."""
    return {
        "INFO": "✅",
        "WARNING": "⚠️",
        "ERROR": "❌",
    }.get(level, "❓")


def render_decision_distribution(data: dict) -> str:
    """Render decision distribution section."""
    lines = [
        "## Decision Distribution",
        "",
    ]

    metrics = data.get("metrics", {})
    total = data.get("total_cases", 0)

    lines.append("| Decision | Count | Percentage |")
    lines.append("|----------|-------|------------|")

    for decision in ["determined", "no_amount", "condition_mismatch", "definition_only", "insufficient_evidence"]:
        info = metrics.get(decision, {})
        count = info.get("count", 0)
        pct = info.get("percentage", 0.0)
        lines.append(f"| {decision} | {count} | {pct:.1f}% |")

    lines.append("")
    lines.append(f"**Total cases:** {total}")
    lines.append("")

    return "\n".join(lines)


def render_partial_failure(data: dict) -> str:
    """Render partial failure rate section."""
    lines = [
        "## Partial Failure Rate",
        "",
    ]

    metrics = data.get("metrics", {})
    level = data.get("level", "INFO")
    emoji = get_level_emoji(level)

    pf_rate = metrics.get("partial_failure_rate", 0.0)
    pf_count = metrics.get("partial_failure_count", 0)
    total = metrics.get("total_cases", 0)

    lines.append(f"**Status:** {emoji} {level}")
    lines.append("")
    lines.append(f"- Partial Failure Rate: **{pf_rate:.1%}** ({pf_count}/{total})")
    lines.append("")

    by_decision = metrics.get("by_decision", {})
    if by_decision:
        lines.append("### By Decision Type")
        lines.append("")
        lines.append("| Decision | Count | Rate |")
        lines.append("|----------|-------|------|")
        for decision, info in by_decision.items():
            count = info.get("count", 0)
            rate = info.get("rate", 0.0)
            lines.append(f"| {decision} | {count} | {rate:.1%} |")
        lines.append("")

    return "\n".join(lines)


def render_evidence_quality(data: dict) -> str:
    """Render evidence quality section."""
    lines = [
        "## Evidence Quality",
        "",
    ]

    metrics = data.get("metrics", {})
    level = data.get("level", "INFO")
    emoji = get_level_emoji(level)

    lines.append(f"**Status:** {emoji} {level}")
    lines.append("")

    pass1 = metrics.get("pass1_success_rate", {})
    pass2 = metrics.get("pass2_augmentation_rate", {})
    dropped = metrics.get("dropped_evidence", {})

    lines.append(f"- PASS1 Success Rate: **{pass1.get('rate', 0.0):.1%}**")
    lines.append(f"- PASS2 Augmentation Rate: **{pass2.get('rate', 0.0):.1%}**")
    lines.append(f"- Total Dropped Evidence: **{dropped.get('total_dropped', 0)}**")
    lines.append("")

    by_reason = dropped.get("by_reason", {})
    if any(by_reason.values()):
        lines.append("### Dropped Evidence by Reason")
        lines.append("")
        lines.append("| Reason | Count |")
        lines.append("|--------|-------|")
        for reason, count in by_reason.items():
            if count > 0:
                lines.append(f"| {reason} | {count} |")
        lines.append("")

    return "\n".join(lines)


def render_source_boundary(data: dict) -> str:
    """Render source boundary section."""
    lines = [
        "## Source Boundary",
        "",
    ]

    metrics = data.get("metrics", {})
    level = data.get("level", "INFO")
    emoji = get_level_emoji(level)

    lines.append(f"**Status:** {emoji} {level}")
    lines.append("")

    auth_ratio = metrics.get("authoritative_ratio", {})
    lines.append(f"- Authoritative Ratio: **{auth_ratio.get('ratio', 0.0):.1%}**")
    lines.append("")

    by_doc = metrics.get("by_doc_type", {})
    if by_doc:
        lines.append("### By Document Type")
        lines.append("")
        lines.append("| Doc Type | Count | Percentage |")
        lines.append("|----------|-------|------------|")
        for doc_type, info in by_doc.items():
            desc = info.get("description", doc_type)
            count = info.get("count", 0)
            pct = info.get("percentage", 0.0)
            lines.append(f"| {desc} | {count} | {pct:.1f}% |")
        lines.append("")

    return "\n".join(lines)


def render_golden_drift(data: dict) -> str:
    """Render golden drift section."""
    lines = [
        "## Golden Set Drift",
        "",
    ]

    status = data.get("status", "UNKNOWN")
    level = data.get("level", "INFO")
    emoji = get_level_emoji(level)

    lines.append(f"**Status:** {emoji} {status}")
    lines.append("")

    diff = data.get("diff", {})
    change_rate = diff.get("change_rate", 0.0)
    total_changed = diff.get("total_changed", 0)
    total_cases = diff.get("total_cases", 0)
    regressions = diff.get("regressions", [])

    lines.append(f"- Decision Changes: **{total_changed}/{total_cases}** ({change_rate:.1%})")
    lines.append(f"- Regressions: **{len(regressions)}**")
    lines.append("")

    if regressions:
        lines.append("### Regressions (DETERMINED → Partial Failure)")
        lines.append("")
        lines.append("| Case ID | From | To |")
        lines.append("|---------|------|-----|")
        for reg in regressions:
            lines.append(f"| {reg['case_id']} | {reg['from']} | {reg['to']} |")
        lines.append("")

    decision_changes = diff.get("decision_changes", [])
    if decision_changes and not regressions:
        lines.append("### Decision Changes")
        lines.append("")
        lines.append("| Case ID | Baseline | Current |")
        lines.append("|---------|----------|---------|")
        for change in decision_changes[:10]:
            lines.append(f"| {change['case_id']} | {change['baseline']} | {change['current']} |")
        if len(decision_changes) > 10:
            lines.append(f"| ... | ({len(decision_changes) - 10} more) | |")
        lines.append("")

    return "\n".join(lines)


def render_ops_report(
    ops_summary: dict,
    decision_dist: dict,
    partial_failure: dict,
    evidence_quality: dict,
    source_boundary: dict,
    golden_drift: dict,
) -> str:
    """Render full ops report."""
    now = datetime.utcnow()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")

    status = ops_summary.get("status", "UNKNOWN")
    level = ops_summary.get("level", "INFO")
    action_required = ops_summary.get("action_required", False)
    emoji = get_level_emoji(level)

    lines = [
        f"# Ops Report - {date_str}",
        "",
        f"**Generated:** {time_str}",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"**Overall Status:** {emoji} {status}",
        f"**Level:** {level}",
        f"**Action Required:** {'YES' if action_required else 'NO'}",
        "",
    ]

    # Warnings and Errors
    warnings = ops_summary.get("warnings", [])
    errors = ops_summary.get("errors", [])

    if errors:
        lines.append("### ❌ Errors")
        lines.append("")
        for err in errors:
            lines.append(f"- {err}")
        lines.append("")

    if warnings:
        lines.append("### ⚠️ Warnings")
        lines.append("")
        for warn in warnings:
            lines.append(f"- {warn}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Detailed sections
    lines.append(render_decision_distribution(decision_dist))
    lines.append("---")
    lines.append("")

    lines.append(render_partial_failure(partial_failure))
    lines.append("---")
    lines.append("")

    lines.append(render_evidence_quality(evidence_quality))
    lines.append("---")
    lines.append("")

    lines.append(render_source_boundary(source_boundary))
    lines.append("---")
    lines.append("")

    lines.append(render_golden_drift(golden_drift))
    lines.append("---")
    lines.append("")

    lines.append("## References")
    lines.append("")
    lines.append("- [CLAUDE.md](../../CLAUDE.md) — Execution Constitution")
    lines.append("- [ROADMAP.md](../../docs/v2/ROADMAP.md) — V2 Roadmap")
    lines.append("- [Golden Set](../../eval/golden_set_v2_7.json) — Regression Core")
    lines.append("")

    return "\n".join(lines)


def main():
    """Main entry point for ops report rendering."""
    print("Loading metrics...")

    ops_summary = load_json(METRICS_DIR / "ops_summary.json")
    decision_dist = load_json(METRICS_DIR / "decision_distribution.json")
    partial_failure = load_json(METRICS_DIR / "partial_failure_rate.json")
    evidence_quality = load_json(METRICS_DIR / "evidence_quality.json")
    source_boundary = load_json(METRICS_DIR / "source_boundary.json")
    golden_drift = load_json(METRICS_DIR / "golden_diff.json")

    print("Rendering report...")
    report = render_ops_report(
        ops_summary,
        decision_dist,
        partial_failure,
        evidence_quality,
        source_boundary,
        golden_drift,
    )

    # Ensure output directory exists
    OPS_DIR.mkdir(parents=True, exist_ok=True)

    # Save report
    date_str = datetime.utcnow().strftime("%Y%m%d")
    report_path = OPS_DIR / f"OPS-REPORT-{date_str}.md"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Report saved to {report_path}")

    # Also save as latest
    latest_path = OPS_DIR / "OPS-REPORT-LATEST.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Latest report: {latest_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
