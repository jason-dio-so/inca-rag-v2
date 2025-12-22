"""
Condition Compare Engine Core
STEP V2-3: Condition & Definition Compare Engine

V2-3은 "누가 더 낫다"를 말하는 단계가 아니다.
각 보험사가 '어떻게 정의하고 있는지'를 판단 없이 그대로 드러낸다.
한 줄이라도 해석이 들어가면, 그 구현은 폐기한다.

Definition: 담보가 무엇을 의미하는지에 대한 정의 문구
Condition: 언제, 어떤 경우에, 어떤 제한 하에 지급되는지에 대한 조건 문구

금지 사항:
- "포함된다 / 제외된다" 자동 판단 ❌
- 타 보험사 정의를 기준으로 보정 ❌
- LLM 생성 문구를 사실처럼 사용 ❌
- 정의 없는 상태에서 summary 생성 ❌
"""

from typing import Protocol

from compare.condition_types import (
    CanonicalNotFoundError,
    ComparisonAspect,
    ConditionCompareInput,
    ConditionCompareResponse,
    ConditionEvidence,
    ConditionInsurerResult,
    ConditionNotCoveredResult,
    ConditionSuccessResult,
    ConditionUnknownResult,
    Definitions,
    InvalidConditionInputError,
    UnknownReason,
)
from compare.types import DocType, Insurer


class CanonicalStore(Protocol):
    """Canonical coverage 저장소 인터페이스"""

    def exists(self, coverage_code: str) -> bool:
        """canonical_code 존재 여부 확인"""
        ...

    def get_name(self, coverage_code: str) -> str | None:
        """canonical_code의 공식 담보명 조회"""
        ...


class ConditionDefinitionStore(Protocol):
    """조건/정의 저장소 인터페이스"""

    def get_definitions(
        self,
        canonical_code: str,
        insurer: Insurer,
        aspects: tuple[ComparisonAspect, ...]
    ) -> tuple[Definitions, ConditionEvidence] | None:
        """
        canonical_code와 insurer에 대한 정의/조건 조회.

        Returns:
            (definitions, evidence) tuple if found, None otherwise.

        Note:
            - 약관/사업방법서 기반 authoritative evidence만 반환
            - 문서 원문 그대로 (요약/정규화 최소화)
            - 해석 금지
        """
        ...

    def is_definition_ambiguous(
        self,
        canonical_code: str,
        insurer: Insurer,
        aspects: tuple[ComparisonAspect, ...]
    ) -> bool:
        """정의가 모호하거나 복합 조건인지 여부"""
        ...

    def coverage_exists_for_insurer(
        self,
        canonical_code: str,
        insurer: Insurer
    ) -> bool:
        """해당 보험사가 이 담보를 제공하는지 여부"""
        ...


class ConditionCompareEngine:
    """
    Condition & Definition Compare Engine

    처리 흐름 (순서 고정):
    1. canonical_coverage_code 수신
    2. canonical 존재 확인 (없으면 hard fail)
    3. insurers loop
    4. 보험사별:
       - authoritative 문서(약관/사업방법서) 조회
       - definition / condition 관련 문단 추출
    5. 추론 없이 구조화
    6. partial failure 병합
    7. response 생성

    금지 사항:
    - "보장함/안함" 판단 ❌
    - "유리/불리" 판단 ❌
    - LLM 정의 해석 ❌
    - embedding 유사 문단 탐색 ❌
    """

    def __init__(
        self,
        canonical_store: CanonicalStore,
        definition_store: ConditionDefinitionStore
    ):
        self._canonical_store = canonical_store
        self._definition_store = definition_store

    def compare(self, input: ConditionCompareInput) -> ConditionCompareResponse:
        """
        조건/정의 비교 수행.

        Args:
            input: ConditionCompareInput (canonical_coverage_code 필수)

        Returns:
            ConditionCompareResponse with partial failure support

        Raises:
            CanonicalNotFoundError: canonical_code가 존재하지 않음 (hard fail)
            InvalidConditionInputError: 잘못된 입력
        """
        # Step 1: 입력 검증
        self._validate_input(input)

        # Step 2: canonical 존재 확인 (hard fail)
        canonical_name = self._canonical_store.get_name(
            input.canonical_coverage_code
        )
        if canonical_name is None:
            raise CanonicalNotFoundError(
                canonical_code=input.canonical_coverage_code,
                reason="canonical_code_not_exists"
            )

        # Step 3-5: insurers loop & 결과 수집
        results: dict[Insurer, ConditionInsurerResult] = {}

        for insurer in input.insurers:
            result = self._process_insurer(
                canonical_code=input.canonical_coverage_code,
                insurer=insurer,
                aspects=input.comparison_aspects
            )
            results[insurer] = result

        # Step 6-7: Partial failure 처리 & 응답 생성
        return ConditionCompareResponse.from_results(
            canonical_coverage_code=input.canonical_coverage_code,
            canonical_coverage_name=canonical_name,
            comparison_aspects=input.comparison_aspects,
            results=results
        )

    def _validate_input(self, input: ConditionCompareInput) -> None:
        """입력 검증"""
        if not input.canonical_coverage_code:
            raise InvalidConditionInputError(
                "canonical_coverage_code is required"
            )

        if not input.comparison_aspects:
            raise InvalidConditionInputError(
                "At least one comparison_aspect is required"
            )

        if not input.insurers:
            raise InvalidConditionInputError(
                "At least one insurer is required"
            )

    def _process_insurer(
        self,
        canonical_code: str,
        insurer: Insurer,
        aspects: tuple[ComparisonAspect, ...]
    ) -> ConditionInsurerResult:
        """
        보험사별 조건/정의 처리.

        Returns:
            - ConditionSuccessResult: 정의/조건 문구 있음
            - ConditionNotCoveredResult: 담보 자체가 없음
            - ConditionUnknownResult: 담보는 있으나 정의/조건 없음 또는 모호함

        판단 금지:
        - "보장함/안함" 판단 ❌
        - "유리/불리" 판단 ❌
        """
        # Step 1: 담보 존재 여부 확인
        coverage_exists = self._definition_store.coverage_exists_for_insurer(
            canonical_code=canonical_code,
            insurer=insurer
        )

        if not coverage_exists:
            return ConditionNotCoveredResult()

        # Step 2: 모호한 정의인지 확인
        is_ambiguous = self._definition_store.is_definition_ambiguous(
            canonical_code=canonical_code,
            insurer=insurer,
            aspects=aspects
        )

        if is_ambiguous:
            return ConditionUnknownResult(
                reason=UnknownReason.AMBIGUOUS_DEFINITION
            )

        # Step 3: 정의/조건 조회
        definition_result = self._definition_store.get_definitions(
            canonical_code=canonical_code,
            insurer=insurer,
            aspects=aspects
        )

        if definition_result is None:
            return ConditionUnknownResult(
                reason=UnknownReason.NO_AUTHORITATIVE_DEFINITION
            )

        definitions, evidence = definition_result

        # Step 4: 정의가 비어있으면 unknown
        if not definitions.to_dict():
            return ConditionUnknownResult(
                reason=UnknownReason.NO_AUTHORITATIVE_DEFINITION
            )

        return ConditionSuccessResult(
            definitions=definitions,
            evidence=evidence
        )


# --- Serialization ---

def serialize_condition_result(response: ConditionCompareResponse) -> dict:
    """ConditionCompareResponse를 dict로 직렬화"""
    results_dict = {}

    for insurer, result in response.results.items():
        if isinstance(result, ConditionSuccessResult):
            results_dict[insurer.value] = {
                "status": result.status.value,
                "definitions": result.definitions.to_dict(),
                "evidence": {
                    "doc_type": result.evidence.doc_type.value,
                    "doc_id": result.evidence.doc_id,
                    "page": result.evidence.page,
                    "excerpt": result.evidence.excerpt,
                }
            }
        elif isinstance(result, ConditionUnknownResult):
            results_dict[insurer.value] = {
                "status": result.status.value,
                "reason": result.reason.value,
            }
        elif isinstance(result, ConditionNotCoveredResult):
            results_dict[insurer.value] = {
                "status": result.status.value,
                "reason": result.reason,
            }

    return {
        "canonical_coverage_code": response.canonical_coverage_code,
        "canonical_coverage_name": response.canonical_coverage_name,
        "comparison_aspects": [a.value for a in response.comparison_aspects],
        "results": results_dict,
        "summary": {
            "total_insurers": response.summary.total_insurers,
            "success_count": response.summary.success_count,
            "unknown_count": response.summary.unknown_count,
            "not_covered_count": response.summary.not_covered_count,
        }
    }
