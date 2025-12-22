"""
Explain View Types for V2-6: Explain View / Boundary UX + Slot Rendering

비교 결과를 오해 없이, 경계(boundary)를 유지한 채, 일관된 구조로 노출.

Boundary UX 원칙:
- 사실(evidence), 규칙(rule), 결론(decision)을 시각적으로 분리
- 문서/페이지/발췌(source boundary)를 항상 함께 표시
- "없음/불가"는 빈칸이 아니라 사유 카드로 표시

금지 사항:
- 설명 문장 생성(LLM) ❌
- decision_status 변조 ❌
- evidence 생략 ❌
- "사용자 친화적" 추론 추가 ❌
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CardType(str, Enum):
    """Reason Card 유형"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class HeadlineKey(str, Enum):
    """Headline 키 (사실 기반)"""
    RESULT_DETERMINED = "result_determined"
    NO_AMOUNT_EVIDENCE = "no_amount_evidence"
    CONDITION_CONFLICT = "condition_conflict"
    DEFINITION_ONLY = "definition_only"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


# --- Reference ---

@dataclass(frozen=True)
class EvidenceReference:
    """Evidence 참조 (출처 표시)"""
    doc_type: str
    doc_id: Optional[str] = None
    page: Optional[int] = None


# --- Reason Card ---

@dataclass(frozen=True)
class ReasonCard:
    """
    Reason Card (Partial Failure 포함).

    Boundary UX: "없음/불가"는 빈칸이 아니라 사유 카드로 표시.
    """
    type: CardType
    title: str
    message: str  # 사실 기반 메시지 (추론 금지)
    decision: str
    references: tuple[EvidenceReference, ...] = ()

    def to_dict(self) -> dict:
        result = {
            "type": self.type.value,
            "title": self.title,
            "message": self.message,
            "decision": self.decision,
        }
        if self.references:
            result["references"] = [
                {
                    "doc_type": ref.doc_type,
                    "doc_id": ref.doc_id,
                    "page": ref.page,
                }
                for ref in self.references
            ]
        return result


# --- Evidence Tab Items ---

@dataclass(frozen=True)
class AmountEvidenceItem:
    """
    Amount Evidence 항목.

    필수: value, source_doc, page, excerpt
    """
    value: str
    source_doc: str
    page: int
    excerpt: str
    doc_id: Optional[str] = None

    def to_dict(self) -> dict:
        result = {
            "value": self.value,
            "source_doc": self.source_doc,
            "page": self.page,
            "excerpt": self.excerpt,
        }
        if self.doc_id:
            result["doc_id"] = self.doc_id
        return result


@dataclass(frozen=True)
class ConditionEvidenceItem:
    """
    Condition Evidence 항목.

    필수: source_doc, excerpt
    선택: has_conflict
    """
    source_doc: str
    excerpt: str
    page: Optional[int] = None
    doc_id: Optional[str] = None
    has_conflict: bool = False
    summary: Optional[str] = None

    def to_dict(self) -> dict:
        result = {
            "source_doc": self.source_doc,
            "excerpt": self.excerpt,
            "has_conflict": self.has_conflict,
        }
        if self.page is not None:
            result["page"] = self.page
        if self.doc_id:
            result["doc_id"] = self.doc_id
        if self.summary:
            result["summary"] = self.summary
        return result


@dataclass(frozen=True)
class DefinitionEvidenceItem:
    """
    Definition Evidence 항목.

    필수: source_doc, excerpt
    선택: term, scope
    """
    source_doc: str
    excerpt: str
    page: Optional[int] = None
    doc_id: Optional[str] = None
    term: Optional[str] = None
    scope: Optional[str] = None

    def to_dict(self) -> dict:
        result = {
            "source_doc": self.source_doc,
            "excerpt": self.excerpt,
        }
        if self.page is not None:
            result["page"] = self.page
        if self.doc_id:
            result["doc_id"] = self.doc_id
        if self.term:
            result["term"] = self.term
        if self.scope:
            result["scope"] = self.scope
        return result


# --- Evidence Tabs ---

@dataclass
class EvidenceTabs:
    """
    Evidence 슬롯별 탭.

    Slot Rendering 규칙:
    - 슬롯 간 내용 혼합 ❌
    - 금액 슬롯에 정의 문단 표시 ❌
    - 출처 없는 발췌 ❌
    """
    amount: tuple[AmountEvidenceItem, ...] = ()
    condition: tuple[ConditionEvidenceItem, ...] = ()
    definition: tuple[DefinitionEvidenceItem, ...] = ()

    def to_dict(self) -> dict:
        result = {}
        if self.amount:
            result["amount"] = [item.to_dict() for item in self.amount]
        if self.condition:
            result["condition"] = [item.to_dict() for item in self.condition]
        if self.definition:
            result["definition"] = [item.to_dict() for item in self.definition]
        return result

    def has_amount(self) -> bool:
        return len(self.amount) > 0

    def has_condition(self) -> bool:
        return len(self.condition) > 0

    def has_definition(self) -> bool:
        return len(self.definition) > 0


# --- Rule Trace ---

@dataclass(frozen=True)
class DroppedEvidenceInfo:
    """탈락된 Evidence 정보"""
    id: str
    reason: str

    def to_dict(self) -> dict:
        return {"id": self.id, "reason": self.reason}


@dataclass
class RuleTrace:
    """
    Rule Trace (설명 고정).

    규칙은 요약하지 않고 실행된 규칙 이름 그대로 노출.
    """
    applied_rules: tuple[str, ...]
    dropped_evidence: tuple[DroppedEvidenceInfo, ...] = ()

    def to_dict(self) -> dict:
        result = {
            "applied_rules": list(self.applied_rules),
        }
        if self.dropped_evidence:
            result["dropped_evidence"] = [
                item.to_dict() for item in self.dropped_evidence
            ]
        return result


# --- Explain View Response ---

@dataclass
class ExplainViewResponse:
    """
    Explain View 응답.

    필수 구조:
    - decision: 결정 상태
    - headline: 결과 요약 키
    - reason_cards: 이유 카드 목록
    - evidence_tabs: Evidence 슬롯별 탭
    - rule_trace: 적용된 규칙 로그
    """
    decision: str
    headline: str
    reason_cards: tuple[ReasonCard, ...]
    evidence_tabs: EvidenceTabs
    rule_trace: RuleTrace

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "headline": self.headline,
            "reason_cards": [card.to_dict() for card in self.reason_cards],
            "evidence_tabs": self.evidence_tabs.to_dict(),
            "rule_trace": self.rule_trace.to_dict(),
        }


# --- Multi-Insurer Explain View ---

@dataclass
class InsurerExplainView:
    """보험사별 Explain View"""
    insurer: str
    explain_view: ExplainViewResponse

    def to_dict(self) -> dict:
        return {
            "insurer": self.insurer,
            "explain_view": self.explain_view.to_dict(),
        }


@dataclass
class MultiInsurerExplainView:
    """
    다보험사 비교 Explain View.

    보험사별 Explain View 카드 반복.
    동일 decision_status라도 사유/규칙은 다를 수 있음.
    """
    canonical_coverage_code: str
    canonical_coverage_name: str
    insurer_views: tuple[InsurerExplainView, ...]

    def to_dict(self) -> dict:
        return {
            "canonical_coverage_code": self.canonical_coverage_code,
            "canonical_coverage_name": self.canonical_coverage_name,
            "insurer_views": [view.to_dict() for view in self.insurer_views],
        }
