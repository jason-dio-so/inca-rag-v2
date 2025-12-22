"""
Compare Engine Core
STEP V2-2: Canonical-Driven Compare Engine

Compare Engine은 "답을 만드는 기계"가 아니다.
있는 것을 그대로 보여주고, 없는 것은 없다고 말하는 기계다.

금지 사항:
- LLM으로 조건 요약 ❌
- LLM으로 누락값 보완 ❌
- Embedding으로 유사 담보 검색 ❌

Compare Engine은 결정 트리 + 데이터 조회만으로 동작한다.
"""

from typing import Protocol

from compare.types import (
    CanonicalNotFoundError,
    CompareInput,
    CompareResponse,
    CompareValue,
    DocType,
    Evidence,
    Insurer,
    InsurerResult,
    InvalidInputError,
    NotCoveredResult,
    SuccessResult,
    UnknownResult,
)


class CanonicalStore(Protocol):
    """Canonical coverage 저장소 인터페이스"""

    def exists(self, coverage_code: str) -> bool:
        """canonical_code 존재 여부 확인"""
        ...

    def get_name(self, coverage_code: str) -> str | None:
        """canonical_code의 공식 담보명 조회"""
        ...


class EvidenceStore(Protocol):
    """Evidence 저장소 인터페이스"""

    def get_evidence(
        self,
        canonical_code: str,
        insurer: Insurer
    ) -> tuple[CompareValue, Evidence] | None:
        """
        canonical_code와 insurer에 대한 authoritative evidence 조회.

        Returns:
            (value, evidence) tuple if found, None otherwise.

        Note:
            - 약관/사업방법서 기반 authoritative evidence만 반환
            - 요약서 단독 근거 ❌
            - LLM 요약 결과 ❌
        """
        ...

    def coverage_exists_for_insurer(
        self,
        canonical_code: str,
        insurer: Insurer
    ) -> bool:
        """해당 보험사가 이 담보를 제공하는지 여부 (evidence 없이도)"""
        ...


class CompareEngine:
    """
    Canonical-Driven Compare Engine

    처리 흐름 (순서 고정):
    1. canonical_coverage_code 수신
    2. canonical 존재 확인 (없으면 hard fail)
    3. insurers loop
    4. 각 insurer별:
       - canonical_code 기반 evidence 조회
       - evidence 존재 여부 판단
    5. 결과 정렬 및 병합
    6. partial failure 처리
    7. 최종 response 생성
    """

    def __init__(
        self,
        canonical_store: CanonicalStore,
        evidence_store: EvidenceStore
    ):
        self._canonical_store = canonical_store
        self._evidence_store = evidence_store

    def compare(self, input: CompareInput) -> CompareResponse:
        """
        담보 비교 수행.

        Args:
            input: CompareInput (canonical_coverage_code 필수)

        Returns:
            CompareResponse with partial failure support

        Raises:
            CanonicalNotFoundError: canonical_code 자체가 존재하지 않음 (hard fail)
            InvalidInputError: 잘못된 입력

        Note:
            - 부분 성공 유지: A 보험사 성공, B 보험사 실패해도 전체 실패 아님
            - evidence 없는 값은 절대 출력하지 않음
        """
        # Step 1: 입력 검증
        self._validate_input(input)

        # Step 2: canonical 존재 확인 (hard fail)
        canonical_name = self._canonical_store.get_name(
            input.canonical_coverage_code
        )
        if canonical_name is None:
            # Hard Fail: canonical_code 자체가 존재하지 않음
            # Compare 시작 불가
            raise CanonicalNotFoundError(
                canonical_code=input.canonical_coverage_code,
                reason="canonical_code_not_exists"
            )

        # Step 3-5: insurers loop & 결과 수집
        results: dict[Insurer, InsurerResult] = {}

        for insurer in input.insurers:
            result = self._process_insurer(
                canonical_code=input.canonical_coverage_code,
                insurer=insurer
            )
            results[insurer] = result

        # Step 6-7: Partial failure 처리 & 응답 생성
        return CompareResponse.from_results(
            canonical_coverage_code=input.canonical_coverage_code,
            canonical_coverage_name=canonical_name,
            results=results
        )

    def _validate_input(self, input: CompareInput) -> None:
        """입력 검증"""
        if not input.canonical_coverage_code:
            raise InvalidInputError("canonical_coverage_code is required")

        if not input.insurers:
            raise InvalidInputError("At least one insurer is required")

        # canonical_coverage_code 형식 검증 (선택적)
        # 실제로는 canonical_store.exists()로 검증

    def _process_insurer(
        self,
        canonical_code: str,
        insurer: Insurer
    ) -> InsurerResult:
        """
        보험사별 처리.

        Returns:
            - SuccessResult: canonical + evidence 있음
            - NotCoveredResult: 해당 보험사에서 담보 미제공
            - UnknownResult: canonical 있으나 authoritative evidence 없음
        """
        # Step 1: Evidence 조회
        evidence_result = self._evidence_store.get_evidence(
            canonical_code=canonical_code,
            insurer=insurer
        )

        if evidence_result is not None:
            value, evidence = evidence_result
            # Success: evidence 존재
            return SuccessResult(
                value=value,
                evidence=evidence
            )

        # Step 2: Coverage 존재 여부 확인 (evidence 없이)
        coverage_exists = self._evidence_store.coverage_exists_for_insurer(
            canonical_code=canonical_code,
            insurer=insurer
        )

        if not coverage_exists:
            # Not Covered: 담보 자체가 없음
            return NotCoveredResult()

        # Unknown: canonical은 해석되었으나 authoritative evidence 없음
        # ❌ 추정 금지
        # ❌ 보정 금지
        # ❌ 평균 금지
        return UnknownResult()


# --- Serialization ---

def serialize_result(response: CompareResponse) -> dict:
    """CompareResponse를 dict로 직렬화"""
    results_dict = {}

    for insurer, result in response.results.items():
        if isinstance(result, SuccessResult):
            results_dict[insurer.value] = {
                "status": result.status.value,
                "value": {
                    "amount": result.value.amount,
                    "currency": result.value.currency,
                    "max_count": result.value.max_count,
                    "duration_years": result.value.duration_years,
                    "duration_count": result.value.duration_count,
                },
                "evidence": {
                    "doc_type": result.evidence.doc_type.value,
                    "doc_id": result.evidence.doc_id,
                    "page": result.evidence.page,
                    "excerpt": result.evidence.excerpt,
                }
            }
        elif isinstance(result, NotCoveredResult):
            results_dict[insurer.value] = {
                "status": result.status.value,
                "reason": result.reason,
            }
        elif isinstance(result, UnknownResult):
            results_dict[insurer.value] = {
                "status": result.status.value,
                "reason": result.reason,
            }

    return {
        "canonical_coverage_code": response.canonical_coverage_code,
        "canonical_coverage_name": response.canonical_coverage_name,
        "results": results_dict,
        "summary": {
            "total_insurers": response.summary.total_insurers,
            "success_count": response.summary.success_count,
            "not_covered_count": response.summary.not_covered_count,
            "unknown_count": response.summary.unknown_count,
        }
    }
