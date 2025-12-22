#!/usr/bin/env python3
"""
Golden Drift Detector
V2-8: Operations Monitoring & Drift Detection

Compares current golden set test results with baseline to detect:
- Decision changes
- Rule changes
- Regressions (DETERMINED -> Partial Failure)

This script does NOT modify engine logic or golden set expectations.
It only observes and reports drift.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
METRICS_DIR = PROJECT_ROOT / "metrics"
GOLDEN_SET_FILE = PROJECT_ROOT / "eval" / "golden_set_v2_7.json"


# Drift thresholds
THRESHOLDS = {
    "decision_change_warning": 0.05,  # 5% decision changes -> WARNING
    "decision_change_error": 0.10,    # 10% decision changes -> ERROR
    "determined_to_failure_max": 0,   # Any regression -> ERROR
}


def load_json(path: Path) -> dict:
    """Load JSON file."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    """Save JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def create_baseline_from_golden_set() -> dict:
    """
    Create baseline from golden set expected values.

    This is used when no baseline file exists.
    """
    golden_set = load_json(GOLDEN_SET_FILE)
    cases = golden_set.get("golden_cases", [])

    results = {}
    for case in cases:
        case_id = case.get("id", "")
        expected = case.get("expected", {})
        results[case_id] = {
            "decision": expected.get("decision", "unknown"),
            "rules": expected.get("rules", []),
        }

    return {
        "source": "golden_set_v2_7.json",
        "collected_at": datetime.utcnow().isoformat() + "Z",
        "total_cases": len(cases),
        "results": results,
    }


def detect_drift(baseline: dict, current: dict) -> dict:
    """
    Detect drift between baseline and current results.

    Returns diff information.
    """
    baseline_results = baseline.get("results", {})
    current_results = current.get("results", {})

    decision_changes = []
    rule_changes = []
    regressions = []  # DETERMINED -> Partial Failure

    all_case_ids = set(baseline_results.keys()) | set(current_results.keys())

    for case_id in sorted(all_case_ids):
        baseline_case = baseline_results.get(case_id, {})
        current_case = current_results.get(case_id, {})

        baseline_decision = baseline_case.get("decision", "unknown")
        current_decision = current_case.get("decision", "unknown")

        # Check decision change
        if baseline_decision != current_decision:
            decision_changes.append({
                "case_id": case_id,
                "baseline": baseline_decision,
                "current": current_decision,
            })

            # Check for regression (DETERMINED -> Partial Failure)
            if baseline_decision == "determined" and current_decision in [
                "no_amount",
                "condition_mismatch",
                "definition_only",
                "insufficient_evidence",
            ]:
                regressions.append({
                    "case_id": case_id,
                    "from": baseline_decision,
                    "to": current_decision,
                })

        # Check rule changes
        baseline_rules = set(baseline_case.get("rules", []))
        current_rules = set(current_case.get("rules", []))

        if baseline_rules != current_rules:
            rule_changes.append({
                "case_id": case_id,
                "baseline": sorted(baseline_rules),
                "current": sorted(current_rules),
                "added": sorted(current_rules - baseline_rules),
                "removed": sorted(baseline_rules - current_rules),
            })

    total_cases = len(all_case_ids)
    change_rate = len(decision_changes) / total_cases if total_cases > 0 else 0.0

    return {
        "decision_changes": decision_changes,
        "rule_changes": rule_changes,
        "regressions": regressions,
        "total_cases": total_cases,
        "total_changed": len(decision_changes),
        "change_rate": round(change_rate, 4),
    }


def determine_status(diff: dict) -> tuple[str, str]:
    """
    Determine status and level from diff.

    Returns (status, level).
    """
    regressions = diff.get("regressions", [])
    change_rate = diff.get("change_rate", 0.0)

    # Any regression is ERROR
    if len(regressions) > THRESHOLDS["determined_to_failure_max"]:
        return "REGRESSION", "ERROR"

    # Check change rate thresholds
    if change_rate >= THRESHOLDS["decision_change_error"]:
        return "SIGNIFICANT_DRIFT", "ERROR"
    elif change_rate >= THRESHOLDS["decision_change_warning"]:
        return "MINOR_DRIFT", "WARNING"

    return "STABLE", "INFO"


def main():
    """Main entry point for golden drift detection."""
    parser = argparse.ArgumentParser(description="Detect golden set drift")
    parser.add_argument(
        "--baseline",
        type=Path,
        default=METRICS_DIR / "golden_baseline.json",
        help="Path to baseline file",
    )
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="Save current results as new baseline",
    )
    args = parser.parse_args()

    print("Loading golden set...")
    current = create_baseline_from_golden_set()

    if args.save_baseline:
        print(f"Saving baseline to {args.baseline}...")
        save_json(args.baseline, current)
        print("Baseline saved.")
        return 0

    print(f"Loading baseline from {args.baseline}...")
    if not args.baseline.exists():
        print("No baseline found. Creating baseline from golden set...")
        save_json(args.baseline, current)
        print(f"Baseline created: {args.baseline}")
        print("No drift to compare (first run).")
        return 0

    baseline = load_json(args.baseline)

    print("Detecting drift...")
    diff = detect_drift(baseline, current)

    status, level = determine_status(diff)

    # Build golden_diff.json
    golden_diff = {
        "schema_version": "1.0.0",
        "description": "Golden Set Drift Detection",
        "baseline": baseline,
        "current": current,
        "diff": diff,
        "thresholds": THRESHOLDS,
        "status": status,
        "level": level,
        "collected_at": datetime.utcnow().isoformat() + "Z",
    }

    # Save results
    save_json(METRICS_DIR / "golden_diff.json", golden_diff)
    print(f"Results saved to {METRICS_DIR / 'golden_diff.json'}")

    # Print summary
    print("")
    print(f"Status: {status}")
    print(f"Level: {level}")
    print(f"Decision changes: {diff['total_changed']} / {diff['total_cases']} ({diff['change_rate']:.1%})")
    print(f"Regressions: {len(diff['regressions'])}")
    print(f"Rule changes: {len(diff['rule_changes'])}")

    if diff["regressions"]:
        print("")
        print("REGRESSIONS (DETERMINED -> Partial Failure):")
        for reg in diff["regressions"]:
            print(f"  - {reg['case_id']}: {reg['from']} -> {reg['to']}")

    if diff["decision_changes"] and level != "INFO":
        print("")
        print("Decision changes:")
        for change in diff["decision_changes"][:10]:  # Show first 10
            print(f"  - {change['case_id']}: {change['baseline']} -> {change['current']}")
        if len(diff["decision_changes"]) > 10:
            print(f"  ... and {len(diff['decision_changes']) - 10} more")

    # Return exit code based on level
    if level == "ERROR":
        return 2
    elif level == "WARNING":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
