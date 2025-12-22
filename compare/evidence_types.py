"""
Evidence Types for V2-4: Evidence Retrieval Refinement

Evidence 목적 분리 원칙:
- AMOUNT: 금액, 한도, 지급률
- CONDITION: 지급 조건, 예외, 면책
- DEFINITION: 용어 정의, 질병/수술 범위

목적 없는 evidence는 비교 결과에 사용 금지.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from compare.types import DocType


class EvidencePurpose(str, Enum):
    """Evidence 목적 (3가지만 허용)"""
    AMOUNT = "amount"          # 금액, 한도, 지급률
    CONDITION = "condition"    # 지급 조건, 예외, 면책
    DEFINITION = "definition"  # 용어 정의, 질병/수술 범위


class RetrievalPass(str, Enum):
    """Retrieval 단계"""
    PASS_1 = "pass_1"  # Amount-centric
    PASS_2 = "pass_2"  # Context completion


class DropReason(str, Enum):
    """Evidence 탈락 사유"""
    NO_AMOUNT = "no_amount"
    NO_CONTENT = "no_content"
    DUPLICATE_TEXT = "duplicate_text"
    REFERENCE_ONLY = "reference_only"
    AMOUNT_IGNORED = "amount_ignored"


@dataclass(frozen=True)
class EvidenceSlot:
    """
    단일 목적의 Evidence 슬롯.

    필수:
    - purpose: 목적
    - source_doc: 출처 문서 유형
    - excerpt: 원문 발췌

    선택:
    - value: 추출된 값 (amount 슬롯의 경우)
    - page: 페이지 번호
    - doc_id: 문서 식별자
    """
    purpose: EvidencePurpose
    source_doc: DocType
    excerpt: str
    value: Optional[str] = None
    page: Optional[int] = None
    doc_id: Optional[str] = None
    retrieval_pass: RetrievalPass = RetrievalPass.PASS_1


@dataclass
class EvidenceSlots:
    """
    비교 결과에 사용되는 Evidence 슬롯 집합.

    규칙:
    - amount 슬롯 없이 비교 결과 생성 금지
    - condition/definition은 amount를 보조
    - 모든 슬롯은 출처 명시 필수
    """
    amount: Optional[EvidenceSlot] = None
    condition: Optional[EvidenceSlot] = None
    definition: Optional[EvidenceSlot] = None

    def has_amount(self) -> bool:
        """Amount 슬롯 존재 여부"""
        return self.amount is not None

    def to_dict(self) -> dict:
        """직렬화"""
        result = {}
        if self.amount:
            result["amount"] = {
                "value": self.amount.value,
                "source_doc": self.amount.source_doc.value,
                "excerpt": self.amount.excerpt,
                "page": self.amount.page,
            }
        if self.condition:
            result["condition"] = {
                "source_doc": self.condition.source_doc.value,
                "excerpt": self.condition.excerpt,
                "page": self.condition.page,
            }
        if self.definition:
            result["definition"] = {
                "source_doc": self.definition.source_doc.value,
                "excerpt": self.definition.excerpt,
                "page": self.definition.page,
            }
        return result


@dataclass(frozen=True)
class DroppedEvidence:
    """탈락된 Evidence 기록"""
    reason: DropReason
    excerpt: Optional[str] = None
    doc_id: Optional[str] = None


@dataclass
class RetrievalDebug:
    """
    Retrieval 디버그 정보.

    V2-4 필수 요구사항: debug 정보 반드시 포함.
    """
    pass_1_count: int = 0
    pass_2_count: int = 0
    dropped_evidence: list[DroppedEvidence] = field(default_factory=list)

    def add_dropped(self, reason: DropReason, excerpt: Optional[str] = None):
        """탈락 evidence 기록"""
        self.dropped_evidence.append(DroppedEvidence(
            reason=reason,
            excerpt=excerpt[:100] if excerpt else None
        ))

    def to_dict(self) -> dict:
        """직렬화"""
        return {
            "retrieval_pass_1_count": self.pass_1_count,
            "retrieval_pass_2_count": self.pass_2_count,
            "dropped_evidence": [
                {"reason": d.reason.value, "excerpt": d.excerpt}
                for d in self.dropped_evidence
            ]
        }


# --- Extended Result Types ---

class NoAmountFoundStatus(str, Enum):
    """Amount 없음 상태"""
    NO_AMOUNT_FOUND = "no_amount_found"


@dataclass(frozen=True)
class NoAmountFoundResult:
    """
    Amount evidence 없음 결과.

    V2-4 규칙: amount_evidence가 없으면 이 결과 반환.
    Hallucinated 금액 생성 금지.
    """
    status: NoAmountFoundStatus = NoAmountFoundStatus.NO_AMOUNT_FOUND
    reason: str = "no_amount_bearing_evidence"
    available_slots: tuple[EvidencePurpose, ...] = ()
