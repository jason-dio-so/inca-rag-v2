#!/usr/bin/env python3
"""
Metrics Collector
V2-8: Operations Monitoring & Drift Detection

Collects:
- Decision distribution from test results
- Partial failure rate
- Evidence quality metrics
- Source boundary distribution

This script does NOT modify engine logic.
It only observes and records metrics.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from compare.decision_types import CompareDecision, is_partial_failure


METRICS_DIR = PROJECT_ROOT / "metrics"
GOLDEN_SET_FILE = PROJECT_ROOT / "eval" / "golden_set_v2_7.json"


def load_golden_set() -> dict:
    """Load golden set data"""
    with open(GOLDEN_SET_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_decision_distribution(golden_set: dict) -> dict:
    """
    Collect decision distribution from golden set.

    Returns metrics about how decisions are distributed.
    """
    cases = golden_set.get("golden_cases", [])
    total = len(cases)

    distribution = {
        "determined": 0,
        "no_amount": 0,
        "condition_mismatch": 0,
        "definition_only": 0,
        "insufficient_evidence": 0,
    }

    for case in cases:
        expected = case.get("expected", {})
        decision = expected.get("decision", "").lower()
        if decision in distribution:
            distribution[decision] += 1

    # Calculate percentages
    metrics = {}
    for decision, count in distribution.items():
        metrics[decision] = {
            "count": count,
            "percentage": round(count / total * 100, 2) if total > 0 else 0.0,
        }

    return {
        "schema_version": "1.0.0",
        "description": "Decision Distribution Metrics",
        "metrics": metrics,
        "total_cases": total,
        "collected_at": datetime.utcnow().isoformat() + "Z",
    }


def collect_partial_failure_rate(golden_set: dict) -> dict:
    """
    Collect partial failure rate.

    Partial Failure = NO_AMOUNT | CONDITION_MISMATCH | DEFINITION_ONLY | INSUFFICIENT_EVIDENCE
    """
    cases = golden_set.get("golden_cases", [])
    total = len(cases)

    partial_failure_decisions = {
        "no_amount",
        "condition_mismatch",
        "definition_only",
        "insufficient_evidence",
    }

    by_decision = {d: 0 for d in partial_failure_decisions}
    partial_failure_count = 0

    for case in cases:
        expected = case.get("expected", {})
        decision = expected.get("decision", "").lower()
        if decision in partial_failure_decisions:
            partial_failure_count += 1
            by_decision[decision] += 1

    partial_failure_rate = partial_failure_count / total if total > 0 else 0.0

    # Determine level
    level = "INFO"
    if partial_failure_rate >= 0.70:
        level = "ERROR"
    elif partial_failure_rate >= 0.50:
        level = "WARNING"

    return {
        "schema_version": "1.0.0",
        "description": "Partial Failure Rate tracking",
        "metrics": {
            "total_cases": total,
            "partial_failure_count": partial_failure_count,
            "partial_failure_rate": round(partial_failure_rate, 4),
            "by_decision": {
                d: {
                    "count": count,
                    "rate": round(count / total, 4) if total > 0 else 0.0,
                }
                for d, count in by_decision.items()
            },
        },
        "level": level,
        "thresholds": {
            "warning": 0.50,
            "error": 0.70,
        },
        "collected_at": datetime.utcnow().isoformat() + "Z",
    }


def collect_evidence_quality() -> dict:
    """
    Collect evidence quality metrics.

    This is a placeholder that would be populated by actual retrieval runs.
    For now, returns schema with default values.
    """
    return {
        "schema_version": "1.0.0",
        "description": "Evidence Quality Metrics",
        "metrics": {
            "pass1_success_rate": {
                "description": "PASS1 (Amount-centric) success rate",
                "total_attempts": 0,
                "successful": 0,
                "rate": 0.0,
            },
            "pass2_augmentation_rate": {
                "description": "PASS2 (Context Completion) augmentation rate",
                "total_attempts": 0,
                "augmented": 0,
                "rate": 0.0,
            },
            "dropped_evidence": {
                "description": "Dropped evidence by reason",
                "total_dropped": 0,
                "by_reason": {
                    "NO_CONTENT": 0,
                    "REFERENCE_ONLY": 0,
                    "NO_AMOUNT": 0,
                    "OTHER": 0,
                },
            },
        },
        "level": "INFO",
        "thresholds": {
            "pass1_success_warning": 0.70,
            "pass1_success_error": 0.50,
            "dropped_rate_warning": 0.30,
            "dropped_rate_error": 0.50,
        },
        "collected_at": datetime.utcnow().isoformat() + "Z",
    }


def collect_source_boundary() -> dict:
    """
    Collect source boundary (doc_type) distribution.

    This is a placeholder that would be populated by actual retrieval runs.
    For now, returns schema with default values.
    """
    return {
        "schema_version": "1.0.0",
        "description": "Source Boundary distribution",
        "metrics": {
            "total_evidence_items": 0,
            "by_doc_type": {
                "yakgwan": {"description": "약관", "count": 0, "percentage": 0.0},
                "saeop": {"description": "사업방법서", "count": 0, "percentage": 0.0},
                "summary": {"description": "상품요약서", "count": 0, "percentage": 0.0},
                "other": {"description": "기타", "count": 0, "percentage": 0.0},
            },
            "authoritative_ratio": {
                "description": "Authoritative vs Non-authoritative ratio",
                "authoritative_count": 0,
                "non_authoritative_count": 0,
                "ratio": 0.0,
            },
        },
        "drift_detection": {
            "baseline_yakgwan_percentage": None,
            "baseline_saeop_percentage": None,
            "yakgwan_drift": None,
            "saeop_drift": None,
        },
        "level": "INFO",
        "thresholds": {
            "authoritative_ratio_warning": 0.80,
            "authoritative_ratio_error": 0.60,
            "drift_percentage_warning": 10.0,
            "drift_percentage_error": 20.0,
        },
        "collected_at": datetime.utcnow().isoformat() + "Z",
    }


def generate_ops_summary(
    decision_dist: dict,
    partial_failure: dict,
    evidence_quality: dict,
    source_boundary: dict,
) -> dict:
    """
    Generate operations summary from all metrics.
    """
    warnings = []
    errors = []

    # Check partial failure rate
    pf_rate = partial_failure["metrics"]["partial_failure_rate"]
    if pf_rate >= 0.70:
        errors.append(f"Partial failure rate ({pf_rate:.1%}) exceeds error threshold (70%)")
    elif pf_rate >= 0.50:
        warnings.append(f"Partial failure rate ({pf_rate:.1%}) exceeds warning threshold (50%)")

    # Determine overall level
    if errors:
        level = "ERROR"
        status = "DEGRADED"
        action_required = True
    elif warnings:
        level = "WARNING"
        status = "ATTENTION"
        action_required = True
    else:
        level = "INFO"
        status = "HEALTHY"
        action_required = False

    # Calculate determined rate
    total = decision_dist.get("total_cases", 0)
    determined_count = decision_dist.get("metrics", {}).get("determined", {}).get("count", 0)
    determined_rate = determined_count / total if total > 0 else 0.0

    return {
        "schema_version": "1.0.0",
        "description": "Operations Summary",
        "status": status,
        "level": level,
        "action_required": action_required,
        "summary": {
            "decision_distribution": {
                "determined_rate": round(determined_rate, 4),
                "partial_failure_rate": pf_rate,
                "status": partial_failure.get("level", "INFO"),
            },
            "evidence_quality": {
                "pass1_success_rate": evidence_quality["metrics"]["pass1_success_rate"]["rate"],
                "dropped_rate": 0.0,
                "status": evidence_quality.get("level", "INFO"),
            },
            "source_boundary": {
                "authoritative_ratio": source_boundary["metrics"]["authoritative_ratio"]["ratio"],
                "drift_detected": False,
                "status": source_boundary.get("level", "INFO"),
            },
            "golden_drift": {
                "change_rate": 0.0,
                "regressions": 0,
                "status": "INFO",
            },
        },
        "warnings": warnings,
        "errors": errors,
        "collected_at": datetime.utcnow().isoformat() + "Z",
    }


def main():
    """Main entry point for metrics collection."""
    print("Loading golden set...")
    golden_set = load_golden_set()

    print("Collecting decision distribution...")
    decision_dist = collect_decision_distribution(golden_set)

    print("Collecting partial failure rate...")
    partial_failure = collect_partial_failure_rate(golden_set)

    print("Collecting evidence quality...")
    evidence_quality = collect_evidence_quality()

    print("Collecting source boundary...")
    source_boundary = collect_source_boundary()

    print("Generating ops summary...")
    ops_summary = generate_ops_summary(
        decision_dist,
        partial_failure,
        evidence_quality,
        source_boundary,
    )

    # Save metrics
    print("Saving metrics...")

    with open(METRICS_DIR / "decision_distribution.json", "w", encoding="utf-8") as f:
        json.dump(decision_dist, f, indent=2, ensure_ascii=False)

    with open(METRICS_DIR / "partial_failure_rate.json", "w", encoding="utf-8") as f:
        json.dump(partial_failure, f, indent=2, ensure_ascii=False)

    with open(METRICS_DIR / "evidence_quality.json", "w", encoding="utf-8") as f:
        json.dump(evidence_quality, f, indent=2, ensure_ascii=False)

    with open(METRICS_DIR / "source_boundary.json", "w", encoding="utf-8") as f:
        json.dump(source_boundary, f, indent=2, ensure_ascii=False)

    with open(METRICS_DIR / "ops_summary.json", "w", encoding="utf-8") as f:
        json.dump(ops_summary, f, indent=2, ensure_ascii=False)

    print(f"Metrics saved to {METRICS_DIR}")

    # Return exit code based on status
    if ops_summary["level"] == "ERROR":
        return 2
    elif ops_summary["level"] == "WARNING":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
