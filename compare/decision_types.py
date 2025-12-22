"""
Decision Types for V2-5: Evidence-to-Compare Binding

Evidence 슬롯 → Compare 결과 필드 바인딩을 위한 타입 정의.

핵심 철학:
- Evidence는 사실
- Compare 결과는 규칙의 결과
- Explanation은 규칙의 로그

설명은 "생성"이 아니라 "기록(rendering)"이다.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CompareDecision(str, Enum):
    """
    Compare 결과 상태.

    각 coverage 비교 결과는 반드시 이 중 하나로 귀결된다.
    """
    DETERMINED = "determined"                    # 결과 확정
    NO_AMOUNT = "no_amount"                      # 금액 근거 부재
    CONDITION_MISMATCH = "condition_mismatch"    # 조건 충돌
    DEFINITION_ONLY = "definition_only"          # 정의만 존재
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"  # 판단 불가


class DecisionRule(str, Enum):
    """
    결정 규칙.

    Compare 결과가 어떤 규칙에 의해 결정되었는지 명시.
    """
    # Amount Binding Rules
    RULE_AMOUNT_PRIMARY = "amount_primary"           # Amount 최우선 규칙
    RULE_DOC_PRIORITY = "doc_priority"               # 문서 우선순위 (약관 > 사업방법서)
    RULE_CONDITION_EXPLICIT = "condition_explicit"   # 지급 조건 명시 우선
    RULE_PAGE_ASC = "page_asc"                       # 페이지 시작 위치 오름차순

    # Condition Binding Rules
    RULE_CONDITION_SAME_DOC = "condition_same_doc"   # Amount와 동일 문서 우선
    RULE_CONDITION_CONFLICT = "condition_conflict"   # 조건 충돌 감지

    # Definition Binding Rules
    RULE_DEFINITION_ONLY = "definition_only"         # 정의만 존재
    RULE_DEFINITION_NO_AMOUNT = "definition_no_amount"  # 정의 있으나 금액 없음

    # Failure Rules
    RULE_NO_EVIDENCE = "no_evidence"                 # 증거 없음
    RULE_PASS_1_EMPTY = "pass_1_empty"               # PASS 1 결과 없음


@dataclass
class CompareExplanation:
    """
    Compare 결과 설명.

    금지 사항:
    - 자연어 요약 ❌
    - "~로 보입니다" ❌
    - 해석/추론 문장 ❌

    이 구조는 규칙의 로그이다.
    """
    decision: CompareDecision
    applied_rules: tuple[DecisionRule, ...]
    used_evidence_ids: tuple[str, ...] = ()
    dropped_evidence_ids: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()  # 사실 기반 이유만 (추론 금지)

    def to_dict(self) -> dict:
        """직렬화"""
        return {
            "decision": self.decision.value,
            "applied_rules": [r.value for r in self.applied_rules],
            "used_evidence_ids": list(self.used_evidence_ids),
            "dropped_evidence": list(self.dropped_evidence_ids),
            "reason": list(self.reasons),
        }


@dataclass
class BoundEvidence:
    """
    바인딩된 Evidence.

    어떤 슬롯의 evidence가 최종 결과에 사용되었는지 추적.
    """
    evidence_id: str
    slot_type: str  # "amount", "condition", "definition"
    doc_type: str
    doc_id: str
    page: Optional[int] = None
    excerpt: Optional[str] = None
    binding_rule: Optional[DecisionRule] = None

    def to_dict(self) -> dict:
        """직렬화"""
        result = {
            "evidence_id": self.evidence_id,
            "slot_type": self.slot_type,
            "doc_type": self.doc_type,
            "doc_id": self.doc_id,
        }
        if self.page is not None:
            result["page"] = self.page
        if self.excerpt:
            result["excerpt"] = self.excerpt
        if self.binding_rule:
            result["binding_rule"] = self.binding_rule.value
        return result


@dataclass
class BindingResult:
    """
    Evidence Binding 결과.

    Evidence Slot → Compare Result 변환 결과.
    """
    decision: CompareDecision
    explanation: CompareExplanation
    bound_evidence: tuple[BoundEvidence, ...] = ()
    amount_value: Optional[str] = None  # 확정된 금액 (문자열)
    amount_numeric: Optional[int] = None  # 확정된 금액 (숫자)

    def to_dict(self) -> dict:
        """직렬화"""
        result = {
            "decision": self.decision.value,
            "explanation": self.explanation.to_dict(),
            "bound_evidence": [e.to_dict() for e in self.bound_evidence],
        }
        if self.amount_value:
            result["amount_value"] = self.amount_value
        if self.amount_numeric is not None:
            result["amount_numeric"] = self.amount_numeric
        return result


# --- Partial Failure Status Mapping ---

PARTIAL_FAILURE_DECISIONS = {
    CompareDecision.NO_AMOUNT,
    CompareDecision.CONDITION_MISMATCH,
    CompareDecision.DEFINITION_ONLY,
    CompareDecision.INSUFFICIENT_EVIDENCE,
}


def is_partial_failure(decision: CompareDecision) -> bool:
    """Partial Failure 여부 확인 (ADR-003)"""
    return decision in PARTIAL_FAILURE_DECISIONS


def is_determined(decision: CompareDecision) -> bool:
    """결과 확정 여부"""
    return decision == CompareDecision.DETERMINED
