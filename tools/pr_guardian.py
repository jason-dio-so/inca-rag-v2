#!/usr/bin/env python3
"""
PR Guardian - Constitutional Compliance Scanner
inca-rag-v2

This script scans PR diffs for constitutional violations.
It does NOT make decisions — it only detects violations.

Reference:
- CLAUDE.md (Execution Constitution)
- .github/PR_REVIEW_RULES.md (PR Guardian Rules)
- ADR-000 ~ ADR-003
"""

import re
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ViolationType(str, Enum):
    """Violation categories mapped to ADRs"""
    TERMINOLOGY = "terminology"      # insurer terminology enforcement
    MEANING_IN_CODE = "meaning_in_code"  # hardcoded policies
    # Future: canonical, llm_usage, embedding_usage, etc.


@dataclass
class Violation:
    """A single constitutional violation"""
    type: ViolationType
    file: str
    line: Optional[int]
    message: str
    severity: str  # "error" or "warning"


class PRGuardian:
    """PR Guardian scanner for constitutional violations"""

    # Terminology violations
    FORBIDDEN_TERMS = {
        "carrier": "Use 'insurer' instead of 'carrier'",
    }

    # Patterns that suggest meaning-in-code violations
    MEANING_PATTERNS = [
        (r'coverage_code\s*[=:]\s*["\'][A-Z0-9_]+["\']',
         "Possible hardcoded coverage_code"),
        (r'if\s+.*coverage.*==',
         "Possible coverage logic in code (should be in config)"),
        (r'fallback|best.?guess|default.?value',
         "Possible fallback/guess logic detected"),
    ]

    def __init__(self):
        self.violations: list[Violation] = []

    def scan_diff(self) -> list[Violation]:
        """Scan git diff for violations"""
        try:
            # Get diff against base branch
            result = subprocess.run(
                ["git", "diff", "origin/main", "--unified=0"],
                capture_output=True,
                text=True,
                check=True
            )
            diff_output = result.stdout
        except subprocess.CalledProcessError:
            # Fallback: diff against HEAD~1
            try:
                result = subprocess.run(
                    ["git", "diff", "HEAD~1", "--unified=0"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                diff_output = result.stdout
            except subprocess.CalledProcessError:
                print("Warning: Could not get git diff", file=sys.stderr)
                return []

        self._scan_diff_content(diff_output)
        return self.violations

    def _scan_diff_content(self, diff: str) -> None:
        """Parse diff and scan for violations"""
        current_file = None
        current_line = 0

        for line in diff.split("\n"):
            # Track current file
            if line.startswith("+++ b/"):
                current_file = line[6:]
                continue

            # Track line numbers
            if line.startswith("@@"):
                match = re.search(r"\+(\d+)", line)
                if match:
                    current_line = int(match.group(1))
                continue

            # Only scan added lines (not removed)
            if not line.startswith("+") or line.startswith("+++"):
                continue

            # Skip non-code files
            if current_file and not self._is_scannable_file(current_file):
                continue

            added_content = line[1:]  # Remove leading +
            self._check_line(current_file or "unknown", current_line, added_content)
            current_line += 1

    def _is_scannable_file(self, filepath: str) -> bool:
        """Check if file should be scanned"""
        scannable_extensions = {".py", ".ts", ".js", ".yaml", ".yml", ".json"}
        return any(filepath.endswith(ext) for ext in scannable_extensions)

    def _check_line(self, file: str, line: int, content: str) -> None:
        """Check a single line for violations"""
        content_lower = content.lower()

        # Check forbidden terminology
        for term, message in self.FORBIDDEN_TERMS.items():
            if term in content_lower:
                # Skip if it's in a comment explaining the rule or in FORBIDDEN_TERMS dict
                if "instead of" in content_lower or "금지" in content:
                    continue
                # Skip dictionary keys in FORBIDDEN_TERMS definition
                if "FORBIDDEN_TERMS" in content or f'"{term}"' in content:
                    continue
                self.violations.append(Violation(
                    type=ViolationType.TERMINOLOGY,
                    file=file,
                    line=line,
                    message=f"{message} (found: '{term}')",
                    severity="error"
                ))

        # Check meaning-in-code patterns
        for pattern, message in self.MEANING_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                self.violations.append(Violation(
                    type=ViolationType.MEANING_IN_CODE,
                    file=file,
                    line=line,
                    message=message,
                    severity="warning"
                ))

    def report(self) -> int:
        """Print report and return exit code"""
        errors = [v for v in self.violations if v.severity == "error"]
        warnings = [v for v in self.violations if v.severity == "warning"]

        if not self.violations:
            print("✅ PR Guardian: No violations detected")
            return 0

        print("=" * 60)
        print("PR GUARDIAN SCAN RESULTS")
        print("=" * 60)

        if errors:
            print(f"\n❌ ERRORS ({len(errors)}):\n")
            for v in errors:
                print(f"  [{v.type.value}] {v.file}:{v.line}")
                print(f"    → {v.message}\n")

        if warnings:
            print(f"\n⚠️  WARNINGS ({len(warnings)}):\n")
            for v in warnings:
                print(f"  [{v.type.value}] {v.file}:{v.line}")
                print(f"    → {v.message}\n")

        print("=" * 60)
        print("References:")
        print("  - CLAUDE.md (Execution Constitution)")
        print("  - .github/PR_REVIEW_RULES.md (PR Guardian Rules)")
        print("  - ADR-000 ~ ADR-003")
        print("=" * 60)

        # Return non-zero if there are errors
        return 1 if errors else 0


def main():
    guardian = PRGuardian()
    guardian.scan_diff()
    exit_code = guardian.report()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
