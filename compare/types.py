"""
Compare Engine Types
STEP V2-2: Canonical-Driven Compare Engine

Compare Engine의 입출력 타입 정의.
모든 입력은 canonical_coverage_code로만 이루어진다.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional


class Insurer(str, Enum):
    """보험사 코드"""
    SAMSUNG = "SAMSUNG"
    MERITZ = "MERITZ"
    LOTTE = "LOTTE"
    KB = "KB"
    DB = "DB"
    HANWHA = "HANWHA"
    HEUNGKUK = "HEUNGKUK"
    HYUNDAI = "HYUNDAI"


class ResultStatus(str, Enum):
    """보험사별 결과 상태 (V2-4: 4가지 허용)"""
    SUCCESS = "success"
    NOT_COVERED = "not_covered"
    UNKNOWN = "unknown"
    NO_AMOUNT_FOUND = "no_amount_found"  # V2-4: Amount evidence 없음


class DocType(str, Enum):
    """근거 문서 유형 (authoritative만 허용)"""
    YAKGWAN = "약관"
    SAEOP = "사업방법서"


# --- Input Types ---

@dataclass(frozen=True)
class CompareInput:
    """
    Compare Engine 입력 규약.

    절대 규칙:
    - canonical_coverage_code 필수
    - coverage_name 문자열 입력 금지
    - alias 직접 입력 금지
    """
    canonical_coverage_code: str
    insurers: tuple[Insurer, ...]
    optional_slots: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.canonical_coverage_code:
            raise ValueError("canonical_coverage_code is required")
        if not self.insurers:
            raise ValueError("At least one insurer is required")


# --- Evidence Types ---

@dataclass(frozen=True)
class Evidence:
    """
    근거 문서 정보.
    authoritative evidence만 허용 (약관, 사업방법서).
    """
    doc_type: DocType
    doc_id: str
    page: Optional[int] = None
    excerpt: Optional[str] = None


# --- Value Types (V2-2: 정량 비교만 허용) ---

@dataclass(frozen=True)
class CompareValue:
    """
    비교 값.
    V2-2에서는 정량 비교만 허용:
    - 보험금 금액
    - 지급 횟수
    - 기간 (n년, n회)

    금지:
    - 조건 해석
    - subtype 판단
    - "더 유리함" 판단
    """
    amount: Optional[int] = None
    currency: str = "KRW"
    max_count: Optional[int] = None
    duration_years: Optional[int] = None
    duration_count: Optional[int] = None


# --- Result Types ---

@dataclass(frozen=True)
class SuccessResult:
    """성공 결과: canonical_code에 대한 authoritative evidence 존재"""
    status: Literal[ResultStatus.SUCCESS] = ResultStatus.SUCCESS
    value: CompareValue = field(default_factory=CompareValue)
    evidence: Evidence = None

    def __post_init__(self):
        if self.evidence is None:
            raise ValueError("Evidence is required for success result")


@dataclass(frozen=True)
class NotCoveredResult:
    """미제공 결과: 해당 보험사에서 이 담보를 제공하지 않음"""
    status: Literal[ResultStatus.NOT_COVERED] = ResultStatus.NOT_COVERED
    reason: str = "coverage_not_found"


@dataclass(frozen=True)
class UnknownResult:
    """미확인 결과: canonical은 해석되었으나 authoritative evidence 없음"""
    status: Literal[ResultStatus.UNKNOWN] = ResultStatus.UNKNOWN
    reason: str = "canonical_resolved_but_no_authoritative_evidence"


# --- V2-4: No Amount Found Result ---

@dataclass(frozen=True)
class NoAmountResult:
    """
    Amount evidence 없음 결과 (V2-4).

    규칙:
    - amount_evidence가 없으면 이 결과 반환
    - hallucinated 금액 생성 금지
    """
    status: Literal[ResultStatus.NO_AMOUNT_FOUND] = ResultStatus.NO_AMOUNT_FOUND
    reason: str = "no_amount_bearing_evidence"


# Union type for insurer results (V2-4: NoAmountResult 추가)
InsurerResult = SuccessResult | NotCoveredResult | UnknownResult | NoAmountResult


# --- Compare Response ---

@dataclass(frozen=True)
class CompareSummary:
    """비교 요약 (V2-4: no_amount_count 추가)"""
    total_insurers: int
    success_count: int
    not_covered_count: int
    unknown_count: int
    no_amount_count: int = 0  # V2-4


@dataclass
class CompareResponse:
    """
    Compare Engine 전체 응답.

    Partial Failure 원칙:
    - A 보험사 성공, B 보험사 실패 시에도 전체 compare는 실패하지 않음
    - 부분 성공 유지
    """
    canonical_coverage_code: str
    canonical_coverage_name: str
    results: dict[Insurer, InsurerResult]
    summary: CompareSummary

    @classmethod
    def from_results(
        cls,
        canonical_coverage_code: str,
        canonical_coverage_name: str,
        results: dict[Insurer, InsurerResult]
    ) -> "CompareResponse":
        """결과로부터 응답 생성 (summary 자동 계산)"""
        success_count = sum(
            1 for r in results.values()
            if isinstance(r, SuccessResult)
        )
        not_covered_count = sum(
            1 for r in results.values()
            if isinstance(r, NotCoveredResult)
        )
        unknown_count = sum(
            1 for r in results.values()
            if isinstance(r, UnknownResult)
        )
        no_amount_count = sum(
            1 for r in results.values()
            if isinstance(r, NoAmountResult)
        )

        return cls(
            canonical_coverage_code=canonical_coverage_code,
            canonical_coverage_name=canonical_coverage_name,
            results=results,
            summary=CompareSummary(
                total_insurers=len(results),
                success_count=success_count,
                not_covered_count=not_covered_count,
                unknown_count=unknown_count,
                no_amount_count=no_amount_count,
            )
        )


# --- Error Types ---

class CanonicalNotFoundError(Exception):
    """canonical 해석 불가 시 발생하는 예외 - Hard Fail"""

    def __init__(self, canonical_code: str, reason: str):
        self.canonical_code = canonical_code
        self.reason = reason
        super().__init__(f"Cannot compare '{canonical_code}': {reason}")


class InvalidInputError(Exception):
    """잘못된 입력 시 발생하는 예외"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
