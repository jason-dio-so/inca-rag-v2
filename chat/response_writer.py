#!/usr/bin/env python3
"""
Chat Response Writer
V3-1: E2E with Chat Response

Converts ExplainViewResponse to natural language chat responses
suitable for insurance consultants.

RULES:
- Only mention facts present in ExplainView
- Amount/condition/definition must come from Evidence tabs
- Partial failures MUST be explicitly mentioned
- Source boundary (약관) must be stated

PROHIBITED:
- Adding facts not in ExplainView
- LLM-based coverage_code inference
- Hiding partial failures
- "보험료" mentions
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from compare.explain_types import (
    ExplainViewResponse,
    MultiInsurerExplainView,
    InsurerExplainView,
    EvidenceTabs,
    CardType,
)


@dataclass
class ChatResponse:
    """Chat response structure."""
    message: str
    has_partial_failure: bool
    insurers_compared: list[str]
    sources_cited: list[str]


def format_amount(value: str) -> str:
    """Format amount for display."""
    return value if value else "금액 정보 없음"


def format_insurer_name(insurer: str) -> str:
    """Format insurer name for natural language."""
    names = {
        "SAMSUNG": "삼성화재",
        "MERITZ": "메리츠화재",
        "HYUNDAI": "현대해상",
    }
    return names.get(insurer.upper(), insurer)


def write_single_insurer_response(
    insurer: str,
    explain_view: ExplainViewResponse,
) -> tuple[str, bool, list[str]]:
    """
    Write response for single insurer result.

    Returns: (message, has_partial_failure, sources)
    """
    lines = []
    sources = []
    has_partial_failure = False

    insurer_name = format_insurer_name(insurer)
    decision = explain_view.decision

    # Check for partial failure
    if decision in ["no_amount", "condition_mismatch", "definition_only", "insufficient_evidence"]:
        has_partial_failure = True

    # Decision-based response
    if decision == "determined":
        lines.append(f"**{insurer_name}**")

        # Amount from evidence
        if explain_view.evidence_tabs.amount:
            for amt in explain_view.evidence_tabs.amount:
                lines.append(f"- 암진단비: {amt.value}")
                sources.append(f"{amt.source_doc} {amt.page}페이지")
                if amt.excerpt:
                    lines.append(f"  - 근거: \"{amt.excerpt[:100]}...\"" if len(amt.excerpt) > 100 else f"  - 근거: \"{amt.excerpt}\"")

        # Conditions
        if explain_view.evidence_tabs.condition:
            for cond in explain_view.evidence_tabs.condition:
                if cond.excerpt:
                    lines.append(f"- 조건: {cond.excerpt[:80]}..." if len(cond.excerpt) > 80 else f"- 조건: {cond.excerpt}")
                    sources.append(f"{cond.source_doc} {cond.page}페이지" if cond.page else cond.source_doc)

    elif decision == "no_amount":
        lines.append(f"**{insurer_name}**: 금액 근거를 찾지 못했습니다.")
        lines.append("- 약관에서 암진단비 금액이 명시된 부분을 확인하지 못했습니다.")

    elif decision == "condition_mismatch":
        lines.append(f"**{insurer_name}**: 조건 충돌이 감지되었습니다.")
        if explain_view.evidence_tabs.amount:
            amt = explain_view.evidence_tabs.amount[0]
            lines.append(f"- 금액: {amt.value} (확인됨)")
        lines.append("- ⚠️ 적용 조건 간 충돌이 있어 정확한 비교가 어렵습니다.")

    elif decision == "definition_only":
        lines.append(f"**{insurer_name}**: 정의만 존재합니다.")
        lines.append("- 암의 정의는 확인되었으나 지급 금액 근거가 없습니다.")

    elif decision == "insufficient_evidence":
        lines.append(f"**{insurer_name}**: 근거가 부족합니다.")
        lines.append("- 비교 판단에 필요한 충분한 근거를 찾지 못했습니다.")

    return "\n".join(lines), has_partial_failure, sources


def write_multi_insurer_response(multi_view: MultiInsurerExplainView) -> ChatResponse:
    """
    Write chat response for multi-insurer comparison.

    Args:
        multi_view: MultiInsurerExplainView from V2 compare engine

    Returns:
        ChatResponse with natural language message
    """
    lines = []
    all_sources = []
    has_partial_failure = False
    insurers = []

    # Header
    coverage_name = multi_view.canonical_coverage_name or "담보"
    lines.append(f"## {coverage_name} 비교 결과\n")

    # Process each insurer
    for insurer_view in multi_view.insurer_views:
        insurer = insurer_view.insurer
        insurers.append(insurer)

        msg, partial, sources = write_single_insurer_response(
            insurer,
            insurer_view.explain_view,
        )
        lines.append(msg)
        lines.append("")

        if partial:
            has_partial_failure = True
        all_sources.extend(sources)

    # Summary section
    lines.append("---")
    lines.append("\n### 비교 요약\n")

    # Collect amounts for comparison
    amounts = {}
    for insurer_view in multi_view.insurer_views:
        insurer_name = format_insurer_name(insurer_view.insurer)
        if insurer_view.explain_view.evidence_tabs.amount:
            amt = insurer_view.explain_view.evidence_tabs.amount[0]
            amounts[insurer_name] = amt.value
        else:
            amounts[insurer_name] = "확인 불가"

    if amounts:
        lines.append("| 보험사 | 암진단비 |")
        lines.append("|--------|----------|")
        for name, value in amounts.items():
            lines.append(f"| {name} | {value} |")
        lines.append("")

    # Partial failure warning
    if has_partial_failure:
        lines.append("⚠️ **주의**: 일부 보험사의 근거가 부족하거나 조건 충돌이 있어 정확한 비교가 어려울 수 있습니다.\n")

    # Source boundary
    if all_sources:
        unique_sources = list(set(all_sources))
        lines.append(f"📄 **근거 출처**: {', '.join(unique_sources[:5])}")
        if len(unique_sources) > 5:
            lines.append(f"  외 {len(unique_sources) - 5}건")

    lines.append("\n---")
    lines.append("*본 비교는 약관 원문에 기반하며, 실제 보장 내용은 개별 계약 조건에 따라 다를 수 있습니다.*")

    return ChatResponse(
        message="\n".join(lines),
        has_partial_failure=has_partial_failure,
        insurers_compared=insurers,
        sources_cited=all_sources,
    )


def write_response_from_explain_view(explain_view_dict: dict) -> ChatResponse:
    """
    Write chat response from ExplainView dictionary.

    This is the main entry point for the response writer.

    Args:
        explain_view_dict: Dictionary representation of ExplainViewResponse or MultiInsurerExplainView

    Returns:
        ChatResponse with natural language message
    """
    # Check if it's multi-insurer or single
    if "insurer_views" in explain_view_dict:
        # Multi-insurer
        return _write_from_multi_insurer_dict(explain_view_dict)
    else:
        # Single insurer
        return _write_from_single_dict(explain_view_dict)


def _write_from_multi_insurer_dict(data: dict) -> ChatResponse:
    """Write response from multi-insurer dictionary."""
    lines = []
    all_sources = []
    has_partial_failure = False
    insurers = []

    coverage_name = data.get("canonical_coverage_name", "담보")
    lines.append(f"## {coverage_name} 비교 결과\n")

    for iv in data.get("insurer_views", []):
        insurer = iv.get("insurer", "UNKNOWN")
        insurers.append(insurer)
        ev = iv.get("explain_view", {})

        msg, partial, sources = _write_single_from_dict(insurer, ev)
        lines.append(msg)
        lines.append("")

        if partial:
            has_partial_failure = True
        all_sources.extend(sources)

    # Summary
    lines.append("---")
    lines.append("\n### 비교 요약\n")

    amounts = {}
    for iv in data.get("insurer_views", []):
        insurer_name = format_insurer_name(iv.get("insurer", ""))
        ev = iv.get("explain_view", {})
        tabs = ev.get("evidence_tabs", {})
        amt_list = tabs.get("amount", [])
        if amt_list:
            amounts[insurer_name] = amt_list[0].get("value", "확인 불가")
        else:
            amounts[insurer_name] = "확인 불가"

    if amounts:
        lines.append("| 보험사 | 암진단비 |")
        lines.append("|--------|----------|")
        for name, value in amounts.items():
            lines.append(f"| {name} | {value} |")
        lines.append("")

    if has_partial_failure:
        lines.append("⚠️ **주의**: 일부 보험사의 근거가 부족하거나 조건 충돌이 있어 정확한 비교가 어려울 수 있습니다.\n")

    if all_sources:
        unique_sources = list(set(all_sources))
        lines.append(f"📄 **근거 출처**: {', '.join(unique_sources[:5])}")

    lines.append("\n---")
    lines.append("*본 비교는 약관 원문에 기반하며, 실제 보장 내용은 개별 계약 조건에 따라 다를 수 있습니다.*")

    return ChatResponse(
        message="\n".join(lines),
        has_partial_failure=has_partial_failure,
        insurers_compared=insurers,
        sources_cited=all_sources,
    )


def _write_single_from_dict(insurer: str, ev: dict) -> tuple[str, bool, list[str]]:
    """Write response for single insurer from dictionary."""
    lines = []
    sources = []
    has_partial_failure = False

    insurer_name = format_insurer_name(insurer)
    decision = ev.get("decision", "unknown")

    if decision in ["no_amount", "condition_mismatch", "definition_only", "insufficient_evidence"]:
        has_partial_failure = True

    tabs = ev.get("evidence_tabs", {})

    if decision == "determined":
        lines.append(f"**{insurer_name}**")

        for amt in tabs.get("amount", []):
            lines.append(f"- 암진단비: {amt.get('value', '정보 없음')}")
            page = amt.get("page", "")
            src = amt.get("source_doc", "약관")
            if page:
                sources.append(f"{src} {page}페이지")
            excerpt = amt.get("excerpt", "")
            if excerpt:
                display = excerpt[:100] + "..." if len(excerpt) > 100 else excerpt
                lines.append(f"  - 근거: \"{display}\"")

        for cond in tabs.get("condition", []):
            excerpt = cond.get("excerpt", "")
            if excerpt:
                display = excerpt[:80] + "..." if len(excerpt) > 80 else excerpt
                lines.append(f"- 조건: {display}")

    elif decision == "no_amount":
        lines.append(f"**{insurer_name}**: 금액 근거를 찾지 못했습니다.")
        lines.append("- 약관에서 암진단비 금액이 명시된 부분을 확인하지 못했습니다.")

    elif decision == "condition_mismatch":
        lines.append(f"**{insurer_name}**: 조건 충돌이 감지되었습니다.")
        lines.append("- ⚠️ 적용 조건 간 충돌이 있어 정확한 비교가 어렵습니다.")

    elif decision == "definition_only":
        lines.append(f"**{insurer_name}**: 정의만 존재합니다.")
        lines.append("- 암의 정의는 확인되었으나 지급 금액 근거가 없습니다.")

    elif decision == "insufficient_evidence":
        lines.append(f"**{insurer_name}**: 근거가 부족합니다.")
        lines.append("- 비교 판단에 필요한 충분한 근거를 찾지 못했습니다.")

    else:
        lines.append(f"**{insurer_name}**: 결과를 확인할 수 없습니다.")

    return "\n".join(lines), has_partial_failure, sources


def _write_from_single_dict(ev: dict) -> ChatResponse:
    """Write response from single ExplainView dictionary."""
    msg, partial, sources = _write_single_from_dict("UNKNOWN", ev)
    return ChatResponse(
        message=msg,
        has_partial_failure=partial,
        insurers_compared=["UNKNOWN"],
        sources_cited=sources,
    )
