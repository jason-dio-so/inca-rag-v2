"""
Condition Compare Engine Types
STEP V2-3: Condition & Definition Compare Engine

V2-3은 "누가 더 낫다"를 말하는 단계가 아니다.
각 보험사가 '어떻게 정의하고 있는지'를 판단 없이 그대로 드러낸다.

Definition: 담보가 무엇을 의미하는지에 대한 정의 문구
Condition: 언제, 어떤 경우에, 어떤 제한 하에 지급되는지에 대한 조건 문구
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional

from compare.types import DocType, Insurer


class ComparisonAspect(str, Enum):
    """비교 측면 (V2-3에서 다루는 대상)"""
    SUBTYPE_COVERAGE = "subtype_coverage"      # 유사암/제자리암/경계성종양
    METHOD_CONDITION = "method_condition"      # 다빈치/로봇/복강경 등
    BOUNDARY_CONDITION = "boundary_condition"  # 감액/지급률/조건부 보장
    DEFINITION_SCOPE = "definition_scope"      # 직접치료, 최초, 전이 등


class ConditionResultStatus(str, Enum):
    """조건 비교 결과 상태 (3가지만 허용)"""
    SUCCESS = "success"
    UNKNOWN = "unknown"
    NOT_COVERED = "not_covered"


class UnknownReason(str, Enum):
    """Unknown 상태의 이유"""
    NO_AUTHORITATIVE_DEFINITION = "no_authoritative_definition"
    AMBIGUOUS_DEFINITION = "ambiguous_definition"


# --- Input Types ---

@dataclass(frozen=True)
class ConditionCompareInput:
    """
    Condition Compare Engine 입력 규약.

    절대 규칙:
    - canonical_coverage_code 필수
    - 자연어 질의 입력 금지
    - coverage_name 문자열 입력 금지
    """
    canonical_coverage_code: str
    comparison_aspects: tuple[ComparisonAspect, ...]
    insurers: tuple[Insurer, ...]

    def __post_init__(self):
        if not self.canonical_coverage_code:
            raise ValueError("canonical_coverage_code is required")
        if not self.comparison_aspects:
            raise ValueError("At least one comparison_aspect is required")
        if not self.insurers:
            raise ValueError("At least one insurer is required")


# --- Evidence Types ---

@dataclass(frozen=True)
class ConditionEvidence:
    """
    조건/정의 근거 문서 정보.
    authoritative evidence만 허용 (약관, 사업방법서).
    """
    doc_type: DocType
    doc_id: str
    page: Optional[int] = None
    excerpt: Optional[str] = None


# --- Definition Types ---

@dataclass(frozen=True)
class AspectDefinition:
    """
    특정 측면에 대한 정의/조건 문구.

    원문 유지 원칙:
    - 문서에 있는 그대로
    - 요약/정규화 최소화
    - 해석 금지
    """
    aspect: ComparisonAspect
    text: str  # 원문 그대로


@dataclass
class Definitions:
    """보험사별 정의/조건 모음"""
    subtype_coverage: Optional[str] = None
    method_condition: Optional[str] = None
    boundary_condition: Optional[str] = None
    definition_scope: Optional[str] = None

    def get(self, aspect: ComparisonAspect) -> Optional[str]:
        """aspect에 해당하는 정의 반환"""
        mapping = {
            ComparisonAspect.SUBTYPE_COVERAGE: self.subtype_coverage,
            ComparisonAspect.METHOD_CONDITION: self.method_condition,
            ComparisonAspect.BOUNDARY_CONDITION: self.boundary_condition,
            ComparisonAspect.DEFINITION_SCOPE: self.definition_scope,
        }
        return mapping.get(aspect)

    def set(self, aspect: ComparisonAspect, text: str) -> None:
        """aspect에 해당하는 정의 설정"""
        if aspect == ComparisonAspect.SUBTYPE_COVERAGE:
            self.subtype_coverage = text
        elif aspect == ComparisonAspect.METHOD_CONDITION:
            self.method_condition = text
        elif aspect == ComparisonAspect.BOUNDARY_CONDITION:
            self.boundary_condition = text
        elif aspect == ComparisonAspect.DEFINITION_SCOPE:
            self.definition_scope = text

    def to_dict(self) -> dict[str, str]:
        """non-None 정의만 dict로 반환"""
        result = {}
        if self.subtype_coverage:
            result["subtype_coverage"] = self.subtype_coverage
        if self.method_condition:
            result["method_condition"] = self.method_condition
        if self.boundary_condition:
            result["boundary_condition"] = self.boundary_condition
        if self.definition_scope:
            result["definition_scope"] = self.definition_scope
        return result


# --- Result Types ---

@dataclass(frozen=True)
class ConditionSuccessResult:
    """
    성공 결과: 정의/조건 문구가 authoritative evidence에 존재.

    판단 금지:
    - "보장함/안함" 판단 ❌
    - "유리/불리" 판단 ❌
    """
    status: Literal[ConditionResultStatus.SUCCESS] = ConditionResultStatus.SUCCESS
    definitions: Definitions = field(default_factory=Definitions)
    evidence: ConditionEvidence = None

    def __post_init__(self):
        if self.evidence is None:
            raise ValueError("Evidence is required for success result")


@dataclass(frozen=True)
class ConditionUnknownResult:
    """
    미확인 결과: canonical은 해석되었으나 정의/조건 문구 없음.

    allowed reasons:
    - no_authoritative_definition
    - ambiguous_definition
    """
    status: Literal[ConditionResultStatus.UNKNOWN] = ConditionResultStatus.UNKNOWN
    reason: UnknownReason = UnknownReason.NO_AUTHORITATIVE_DEFINITION


@dataclass(frozen=True)
class ConditionNotCoveredResult:
    """미제공 결과: 해당 담보 자체가 존재하지 않음"""
    status: Literal[ConditionResultStatus.NOT_COVERED] = ConditionResultStatus.NOT_COVERED
    reason: str = "coverage_not_found"


# Union type for condition results
ConditionInsurerResult = (
    ConditionSuccessResult | ConditionUnknownResult | ConditionNotCoveredResult
)


# --- Compare Response ---

@dataclass(frozen=True)
class ConditionCompareSummary:
    """비교 요약"""
    total_insurers: int
    success_count: int
    unknown_count: int
    not_covered_count: int


@dataclass
class ConditionCompareResponse:
    """
    Condition Compare Engine 전체 응답.

    Partial Failure 원칙 (ADR-003):
    - 일부 보험사 실패해도 전체 실패 아님
    - 성공한 보험사 결과는 그대로 유지
    """
    canonical_coverage_code: str
    canonical_coverage_name: str
    comparison_aspects: tuple[ComparisonAspect, ...]
    results: dict[Insurer, ConditionInsurerResult]
    summary: ConditionCompareSummary

    @classmethod
    def from_results(
        cls,
        canonical_coverage_code: str,
        canonical_coverage_name: str,
        comparison_aspects: tuple[ComparisonAspect, ...],
        results: dict[Insurer, ConditionInsurerResult]
    ) -> "ConditionCompareResponse":
        """결과로부터 응답 생성 (summary 자동 계산)"""
        success_count = sum(
            1 for r in results.values()
            if isinstance(r, ConditionSuccessResult)
        )
        unknown_count = sum(
            1 for r in results.values()
            if isinstance(r, ConditionUnknownResult)
        )
        not_covered_count = sum(
            1 for r in results.values()
            if isinstance(r, ConditionNotCoveredResult)
        )

        return cls(
            canonical_coverage_code=canonical_coverage_code,
            canonical_coverage_name=canonical_coverage_name,
            comparison_aspects=comparison_aspects,
            results=results,
            summary=ConditionCompareSummary(
                total_insurers=len(results),
                success_count=success_count,
                unknown_count=unknown_count,
                not_covered_count=not_covered_count,
            )
        )


# --- Error Types ---

class CanonicalNotFoundError(Exception):
    """canonical 해석 불가 시 발생 - Hard Fail"""

    def __init__(self, canonical_code: str, reason: str):
        self.canonical_code = canonical_code
        self.reason = reason
        super().__init__(f"Cannot compare '{canonical_code}': {reason}")


class InvalidConditionInputError(Exception):
    """잘못된 입력 시 발생"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
