"""
Compare Engine Tests
STEP V2-2: Canonical-Driven Compare Engine

테스트 시나리오:
1. 정상 비교: 동일 canonical_code, 2개 보험사 모두 evidence 존재
2. Partial Failure: 삼성 성공, 현대 not_covered
3. Hard Fail: canonical_code 자체가 존재하지 않음
"""

import pytest

from compare.engine import CompareEngine, serialize_result
from compare.types import (
    CanonicalNotFoundError,
    CompareInput,
    CompareValue,
    DocType,
    Evidence,
    Insurer,
    InvalidInputError,
    NotCoveredResult,
    ResultStatus,
    SuccessResult,
    UnknownResult,
)


# --- Mock Stores ---

class MockCanonicalStore:
    """테스트용 Canonical Store"""

    def __init__(self, data: dict[str, str]):
        self._data = data  # {coverage_code: coverage_name}

    def exists(self, coverage_code: str) -> bool:
        return coverage_code in self._data

    def get_name(self, coverage_code: str) -> str | None:
        return self._data.get(coverage_code)


class MockEvidenceStore:
    """테스트용 Evidence Store"""

    def __init__(
        self,
        evidence_data: dict[tuple[str, Insurer], tuple[CompareValue, Evidence]],
        coverage_exists_data: dict[tuple[str, Insurer], bool] | None = None
    ):
        self._evidence_data = evidence_data
        self._coverage_exists_data = coverage_exists_data or {}

    def get_evidence(
        self,
        canonical_code: str,
        insurer: Insurer
    ) -> tuple[CompareValue, Evidence] | None:
        return self._evidence_data.get((canonical_code, insurer))

    def coverage_exists_for_insurer(
        self,
        canonical_code: str,
        insurer: Insurer
    ) -> bool:
        key = (canonical_code, insurer)
        if key in self._coverage_exists_data:
            return self._coverage_exists_data[key]
        # evidence가 있으면 coverage도 있는 것
        return key in self._evidence_data


# --- Test Fixtures ---

@pytest.fixture
def canonical_store():
    """기본 canonical store"""
    return MockCanonicalStore({
        "A4200_1": "암진단비(유사암제외)",
        "A4103": "뇌졸중진단비",
        "A5100": "질병수술비",
    })


@pytest.fixture
def evidence_store_full():
    """모든 보험사에 evidence 있는 store"""
    return MockEvidenceStore({
        ("A4200_1", Insurer.SAMSUNG): (
            CompareValue(amount=50_000_000, currency="KRW", max_count=1),
            Evidence(
                doc_type=DocType.YAKGWAN,
                doc_id="SAMSUNG_CANCER_2024",
                page=45,
                excerpt="암 진단 확정시 5천만원 지급"
            )
        ),
        ("A4200_1", Insurer.MERITZ): (
            CompareValue(amount=30_000_000, currency="KRW", max_count=1),
            Evidence(
                doc_type=DocType.YAKGWAN,
                doc_id="MERITZ_CANCER_2024",
                page=32,
                excerpt="암 진단 확정시 3천만원 지급"
            )
        ),
    })


@pytest.fixture
def evidence_store_partial():
    """일부 보험사만 evidence 있는 store"""
    return MockEvidenceStore(
        evidence_data={
            ("A4200_1", Insurer.SAMSUNG): (
                CompareValue(amount=50_000_000, currency="KRW", max_count=1),
                Evidence(
                    doc_type=DocType.YAKGWAN,
                    doc_id="SAMSUNG_CANCER_2024",
                    page=45,
                    excerpt="암 진단 확정시 5천만원 지급"
                )
            ),
        },
        coverage_exists_data={
            ("A4200_1", Insurer.SAMSUNG): True,
            ("A4200_1", Insurer.HYUNDAI): False,  # 담보 미제공
        }
    )


@pytest.fixture
def evidence_store_unknown():
    """evidence 없지만 coverage는 존재하는 store"""
    return MockEvidenceStore(
        evidence_data={
            ("A4200_1", Insurer.SAMSUNG): (
                CompareValue(amount=50_000_000, currency="KRW", max_count=1),
                Evidence(
                    doc_type=DocType.YAKGWAN,
                    doc_id="SAMSUNG_CANCER_2024",
                    page=45,
                    excerpt="암 진단 확정시 5천만원 지급"
                )
            ),
        },
        coverage_exists_data={
            ("A4200_1", Insurer.SAMSUNG): True,
            ("A4200_1", Insurer.MERITZ): True,  # coverage 있지만 evidence 없음
        }
    )


# --- Test Case 1: 정상 비교 ---

class TestNormalCompare:
    """
    정상 비교 테스트

    조건:
    - 동일 canonical_code
    - 2개 보험사 모두 evidence 존재
    - 결과 나란히 출력
    """

    def test_both_insurers_have_evidence(
        self,
        canonical_store,
        evidence_store_full
    ):
        """두 보험사 모두 evidence 있을 때"""
        engine = CompareEngine(
            canonical_store=canonical_store,
            evidence_store=evidence_store_full
        )

        input = CompareInput(
            canonical_coverage_code="A4200_1",
            insurers=(Insurer.SAMSUNG, Insurer.MERITZ)
        )

        response = engine.compare(input)

        # 기본 검증
        assert response.canonical_coverage_code == "A4200_1"
        assert response.canonical_coverage_name == "암진단비(유사암제외)"

        # 삼성 결과 검증
        samsung_result = response.results[Insurer.SAMSUNG]
        assert isinstance(samsung_result, SuccessResult)
        assert samsung_result.status == ResultStatus.SUCCESS
        assert samsung_result.value.amount == 50_000_000
        assert samsung_result.evidence.doc_type == DocType.YAKGWAN

        # 메리츠 결과 검증
        meritz_result = response.results[Insurer.MERITZ]
        assert isinstance(meritz_result, SuccessResult)
        assert meritz_result.status == ResultStatus.SUCCESS
        assert meritz_result.value.amount == 30_000_000

        # 요약 검증
        assert response.summary.total_insurers == 2
        assert response.summary.success_count == 2
        assert response.summary.not_covered_count == 0
        assert response.summary.unknown_count == 0

    def test_serialization(
        self,
        canonical_store,
        evidence_store_full
    ):
        """직렬화 테스트"""
        engine = CompareEngine(
            canonical_store=canonical_store,
            evidence_store=evidence_store_full
        )

        input = CompareInput(
            canonical_coverage_code="A4200_1",
            insurers=(Insurer.SAMSUNG, Insurer.MERITZ)
        )

        response = engine.compare(input)
        serialized = serialize_result(response)

        assert serialized["canonical_coverage_code"] == "A4200_1"
        assert "SAMSUNG" in serialized["results"]
        assert serialized["results"]["SAMSUNG"]["status"] == "success"
        assert serialized["results"]["SAMSUNG"]["value"]["amount"] == 50_000_000


# --- Test Case 2: Partial Failure ---

class TestPartialFailure:
    """
    Partial Failure 테스트

    조건:
    - 삼성: canonical + evidence 있음
    - 현대: canonical 있으나 evidence 없음 (담보 미제공)

    결과:
    - 삼성 출력 + 현대 not_covered
    - 전체 compare는 실패하지 않음
    """

    def test_one_success_one_not_covered(
        self,
        canonical_store,
        evidence_store_partial
    ):
        """삼성 성공, 현대 not_covered"""
        engine = CompareEngine(
            canonical_store=canonical_store,
            evidence_store=evidence_store_partial
        )

        input = CompareInput(
            canonical_coverage_code="A4200_1",
            insurers=(Insurer.SAMSUNG, Insurer.HYUNDAI)
        )

        response = engine.compare(input)

        # 전체 실패가 아님
        assert response.canonical_coverage_code == "A4200_1"

        # 삼성 결과 검증 (성공)
        samsung_result = response.results[Insurer.SAMSUNG]
        assert isinstance(samsung_result, SuccessResult)
        assert samsung_result.status == ResultStatus.SUCCESS

        # 현대 결과 검증 (not_covered)
        hyundai_result = response.results[Insurer.HYUNDAI]
        assert isinstance(hyundai_result, NotCoveredResult)
        assert hyundai_result.status == ResultStatus.NOT_COVERED
        assert hyundai_result.reason == "coverage_not_found"

        # 요약 검증
        assert response.summary.total_insurers == 2
        assert response.summary.success_count == 1
        assert response.summary.not_covered_count == 1
        assert response.summary.unknown_count == 0

    def test_one_success_one_unknown(
        self,
        canonical_store,
        evidence_store_unknown
    ):
        """삼성 성공, 메리츠 unknown (coverage 있으나 evidence 없음)"""
        engine = CompareEngine(
            canonical_store=canonical_store,
            evidence_store=evidence_store_unknown
        )

        input = CompareInput(
            canonical_coverage_code="A4200_1",
            insurers=(Insurer.SAMSUNG, Insurer.MERITZ)
        )

        response = engine.compare(input)

        # 삼성 결과 검증 (성공)
        samsung_result = response.results[Insurer.SAMSUNG]
        assert isinstance(samsung_result, SuccessResult)

        # 메리츠 결과 검증 (unknown)
        meritz_result = response.results[Insurer.MERITZ]
        assert isinstance(meritz_result, UnknownResult)
        assert meritz_result.status == ResultStatus.UNKNOWN
        assert meritz_result.reason == "canonical_resolved_but_no_authoritative_evidence"

        # 요약 검증
        assert response.summary.success_count == 1
        assert response.summary.unknown_count == 1


# --- Test Case 3: Hard Fail ---

class TestHardFail:
    """
    Hard Fail 테스트

    조건:
    - canonical_code 자체가 존재하지 않음

    결과:
    - compare 시작 불가
    - 명시적 실패 반환 (CanonicalNotFoundError)
    """

    def test_canonical_not_exists(
        self,
        canonical_store,
        evidence_store_full
    ):
        """존재하지 않는 canonical_code"""
        engine = CompareEngine(
            canonical_store=canonical_store,
            evidence_store=evidence_store_full
        )

        input = CompareInput(
            canonical_coverage_code="INVALID_CODE",
            insurers=(Insurer.SAMSUNG, Insurer.MERITZ)
        )

        with pytest.raises(CanonicalNotFoundError) as exc_info:
            engine.compare(input)

        assert exc_info.value.canonical_code == "INVALID_CODE"
        assert exc_info.value.reason == "canonical_code_not_exists"


# --- Test Input Validation ---

class TestInputValidation:
    """입력 검증 테스트"""

    def test_empty_canonical_code(self):
        """빈 canonical_code"""
        with pytest.raises(ValueError):
            CompareInput(
                canonical_coverage_code="",
                insurers=(Insurer.SAMSUNG,)
            )

    def test_empty_insurers(self):
        """빈 insurers"""
        with pytest.raises(ValueError):
            CompareInput(
                canonical_coverage_code="A4200_1",
                insurers=()
            )


# --- Test Result Types ---

class TestResultTypes:
    """결과 타입 테스트"""

    def test_success_requires_evidence(self):
        """SuccessResult는 evidence 필수"""
        with pytest.raises(ValueError):
            SuccessResult(
                value=CompareValue(amount=50_000_000),
                evidence=None
            )

    def test_not_covered_result(self):
        """NotCoveredResult 생성"""
        result = NotCoveredResult()
        assert result.status == ResultStatus.NOT_COVERED
        assert result.reason == "coverage_not_found"

    def test_unknown_result(self):
        """UnknownResult 생성"""
        result = UnknownResult()
        assert result.status == ResultStatus.UNKNOWN
        assert result.reason == "canonical_resolved_but_no_authoritative_evidence"
