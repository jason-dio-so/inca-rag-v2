"""
Condition Compare Engine Tests
STEP V2-3: Condition & Definition Compare Engine

테스트 시나리오:
1. 정상: 삼성/메리츠 모두 정의 문구 존재, 나란히 정의/조건 출력
2. Partial Failure: 삼성 정의 있음, 메리츠 정의 없음
3. Boundary 케이스: 감액/지급률/조건부 키워드 포함, 판단 없이 노출
4. Ambiguous: 모호한 정의
"""

import pytest

from compare.condition_engine import (
    ConditionCompareEngine,
    serialize_condition_result,
)
from compare.condition_types import (
    CanonicalNotFoundError,
    ComparisonAspect,
    ConditionCompareInput,
    ConditionEvidence,
    ConditionNotCoveredResult,
    ConditionResultStatus,
    ConditionSuccessResult,
    ConditionUnknownResult,
    Definitions,
    UnknownReason,
)
from compare.types import DocType, Insurer


# --- Mock Stores ---

class MockCanonicalStore:
    """테스트용 Canonical Store"""

    def __init__(self, data: dict[str, str]):
        self._data = data

    def exists(self, coverage_code: str) -> bool:
        return coverage_code in self._data

    def get_name(self, coverage_code: str) -> str | None:
        return self._data.get(coverage_code)


class MockConditionDefinitionStore:
    """테스트용 Condition Definition Store"""

    def __init__(
        self,
        definitions_data: dict[
            tuple[str, Insurer],
            tuple[Definitions, ConditionEvidence]
        ],
        coverage_exists_data: dict[tuple[str, Insurer], bool] | None = None,
        ambiguous_data: dict[tuple[str, Insurer], bool] | None = None
    ):
        self._definitions_data = definitions_data
        self._coverage_exists_data = coverage_exists_data or {}
        self._ambiguous_data = ambiguous_data or {}

    def get_definitions(
        self,
        canonical_code: str,
        insurer: Insurer,
        aspects: tuple[ComparisonAspect, ...]
    ) -> tuple[Definitions, ConditionEvidence] | None:
        return self._definitions_data.get((canonical_code, insurer))

    def is_definition_ambiguous(
        self,
        canonical_code: str,
        insurer: Insurer,
        aspects: tuple[ComparisonAspect, ...]
    ) -> bool:
        return self._ambiguous_data.get((canonical_code, insurer), False)

    def coverage_exists_for_insurer(
        self,
        canonical_code: str,
        insurer: Insurer
    ) -> bool:
        key = (canonical_code, insurer)
        if key in self._coverage_exists_data:
            return self._coverage_exists_data[key]
        return key in self._definitions_data


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
def definition_store_full():
    """모든 보험사에 정의 있는 store"""
    samsung_defs = Definitions()
    samsung_defs.subtype_coverage = "유사암(갑상선암, 기타피부암, 경계성종양, 제자리암)은 이 담보에서 보장하지 않습니다"
    samsung_defs.boundary_condition = "계약일로부터 90일 이내 암 진단 시 보장하지 않습니다"

    meritz_defs = Definitions()
    meritz_defs.subtype_coverage = "기타피부암, 갑상선암, 제자리암, 경계성종양 제외"
    meritz_defs.boundary_condition = "90일 면책기간 적용"

    return MockConditionDefinitionStore({
        ("A4200_1", Insurer.SAMSUNG): (
            samsung_defs,
            ConditionEvidence(
                doc_type=DocType.YAKGWAN,
                doc_id="SAMSUNG_CANCER_2024",
                page=45,
                excerpt="제3조 보장내용..."
            )
        ),
        ("A4200_1", Insurer.MERITZ): (
            meritz_defs,
            ConditionEvidence(
                doc_type=DocType.YAKGWAN,
                doc_id="MERITZ_CANCER_2024",
                page=32,
                excerpt="제5조 보장범위..."
            )
        ),
    })


@pytest.fixture
def definition_store_partial():
    """일부 보험사만 정의 있는 store"""
    samsung_defs = Definitions()
    samsung_defs.subtype_coverage = "유사암 제외"

    return MockConditionDefinitionStore(
        definitions_data={
            ("A4200_1", Insurer.SAMSUNG): (
                samsung_defs,
                ConditionEvidence(
                    doc_type=DocType.YAKGWAN,
                    doc_id="SAMSUNG_CANCER_2024",
                    page=45
                )
            ),
        },
        coverage_exists_data={
            ("A4200_1", Insurer.SAMSUNG): True,
            ("A4200_1", Insurer.HYUNDAI): False,  # 담보 미제공
        }
    )


@pytest.fixture
def definition_store_ambiguous():
    """모호한 정의가 있는 store"""
    samsung_defs = Definitions()
    samsung_defs.subtype_coverage = "유사암 제외"

    return MockConditionDefinitionStore(
        definitions_data={
            ("A4200_1", Insurer.SAMSUNG): (
                samsung_defs,
                ConditionEvidence(
                    doc_type=DocType.YAKGWAN,
                    doc_id="SAMSUNG_CANCER_2024",
                    page=45
                )
            ),
        },
        coverage_exists_data={
            ("A4200_1", Insurer.SAMSUNG): True,
            ("A4200_1", Insurer.MERITZ): True,
        },
        ambiguous_data={
            ("A4200_1", Insurer.MERITZ): True,  # 모호한 정의
        }
    )


@pytest.fixture
def definition_store_boundary():
    """감액/지급률 조건이 있는 store"""
    samsung_defs = Definitions()
    samsung_defs.boundary_condition = "계약일로부터 1년 이내 진단 시 50% 감액 지급"

    meritz_defs = Definitions()
    meritz_defs.boundary_condition = "1년 미만 계약의 경우 보험금의 50% 지급"

    return MockConditionDefinitionStore({
        ("A4200_1", Insurer.SAMSUNG): (
            samsung_defs,
            ConditionEvidence(
                doc_type=DocType.YAKGWAN,
                doc_id="SAMSUNG_CANCER_2024",
                page=47,
                excerpt="제7조 감액지급..."
            )
        ),
        ("A4200_1", Insurer.MERITZ): (
            meritz_defs,
            ConditionEvidence(
                doc_type=DocType.YAKGWAN,
                doc_id="MERITZ_CANCER_2024",
                page=35,
                excerpt="제8조 지급률..."
            )
        ),
    })


# --- Test Case 1: 정상 비교 ---

class TestNormalConditionCompare:
    """
    정상 비교 테스트

    조건:
    - 동일 canonical_code
    - 삼성/메리츠 모두 정의 문구 존재
    - 나란히 정의/조건 출력
    """

    def test_both_insurers_have_definitions(
        self,
        canonical_store,
        definition_store_full
    ):
        """두 보험사 모두 정의 있을 때"""
        engine = ConditionCompareEngine(
            canonical_store=canonical_store,
            definition_store=definition_store_full
        )

        input = ConditionCompareInput(
            canonical_coverage_code="A4200_1",
            comparison_aspects=(
                ComparisonAspect.SUBTYPE_COVERAGE,
                ComparisonAspect.BOUNDARY_CONDITION
            ),
            insurers=(Insurer.SAMSUNG, Insurer.MERITZ)
        )

        response = engine.compare(input)

        # 기본 검증
        assert response.canonical_coverage_code == "A4200_1"
        assert response.canonical_coverage_name == "암진단비(유사암제외)"

        # 삼성 결과 검증
        samsung_result = response.results[Insurer.SAMSUNG]
        assert isinstance(samsung_result, ConditionSuccessResult)
        assert samsung_result.status == ConditionResultStatus.SUCCESS
        assert "유사암" in samsung_result.definitions.subtype_coverage
        assert samsung_result.evidence.doc_type == DocType.YAKGWAN

        # 메리츠 결과 검증
        meritz_result = response.results[Insurer.MERITZ]
        assert isinstance(meritz_result, ConditionSuccessResult)
        assert "경계성종양" in meritz_result.definitions.subtype_coverage

        # 요약 검증
        assert response.summary.total_insurers == 2
        assert response.summary.success_count == 2
        assert response.summary.unknown_count == 0

    def test_serialization(
        self,
        canonical_store,
        definition_store_full
    ):
        """직렬화 테스트"""
        engine = ConditionCompareEngine(
            canonical_store=canonical_store,
            definition_store=definition_store_full
        )

        input = ConditionCompareInput(
            canonical_coverage_code="A4200_1",
            comparison_aspects=(ComparisonAspect.SUBTYPE_COVERAGE,),
            insurers=(Insurer.SAMSUNG, Insurer.MERITZ)
        )

        response = engine.compare(input)
        serialized = serialize_condition_result(response)

        assert serialized["canonical_coverage_code"] == "A4200_1"
        assert "SAMSUNG" in serialized["results"]
        assert serialized["results"]["SAMSUNG"]["status"] == "success"
        assert "subtype_coverage" in serialized["results"]["SAMSUNG"]["definitions"]


# --- Test Case 2: Partial Failure ---

class TestPartialFailure:
    """
    Partial Failure 테스트

    조건:
    - 삼성: 정의 있음
    - 현대: 담보 미제공 (not_covered)

    결과:
    - 삼성 출력 + 현대 not_covered
    """

    def test_one_success_one_not_covered(
        self,
        canonical_store,
        definition_store_partial
    ):
        """삼성 성공, 현대 not_covered"""
        engine = ConditionCompareEngine(
            canonical_store=canonical_store,
            definition_store=definition_store_partial
        )

        input = ConditionCompareInput(
            canonical_coverage_code="A4200_1",
            comparison_aspects=(ComparisonAspect.SUBTYPE_COVERAGE,),
            insurers=(Insurer.SAMSUNG, Insurer.HYUNDAI)
        )

        response = engine.compare(input)

        # 삼성 결과 검증 (성공)
        samsung_result = response.results[Insurer.SAMSUNG]
        assert isinstance(samsung_result, ConditionSuccessResult)

        # 현대 결과 검증 (not_covered)
        hyundai_result = response.results[Insurer.HYUNDAI]
        assert isinstance(hyundai_result, ConditionNotCoveredResult)
        assert hyundai_result.status == ConditionResultStatus.NOT_COVERED

        # 요약 검증
        assert response.summary.success_count == 1
        assert response.summary.not_covered_count == 1


# --- Test Case 3: Ambiguous Definition ---

class TestAmbiguousDefinition:
    """
    모호한 정의 테스트

    조건:
    - 삼성: 정의 있음
    - 메리츠: 정의 모호함

    결과:
    - 삼성 success + 메리츠 unknown (ambiguous_definition)
    """

    def test_ambiguous_definition(
        self,
        canonical_store,
        definition_store_ambiguous
    ):
        """모호한 정의"""
        engine = ConditionCompareEngine(
            canonical_store=canonical_store,
            definition_store=definition_store_ambiguous
        )

        input = ConditionCompareInput(
            canonical_coverage_code="A4200_1",
            comparison_aspects=(ComparisonAspect.SUBTYPE_COVERAGE,),
            insurers=(Insurer.SAMSUNG, Insurer.MERITZ)
        )

        response = engine.compare(input)

        # 삼성 결과 검증 (성공)
        samsung_result = response.results[Insurer.SAMSUNG]
        assert isinstance(samsung_result, ConditionSuccessResult)

        # 메리츠 결과 검증 (unknown - ambiguous)
        meritz_result = response.results[Insurer.MERITZ]
        assert isinstance(meritz_result, ConditionUnknownResult)
        assert meritz_result.reason == UnknownReason.AMBIGUOUS_DEFINITION


# --- Test Case 4: Boundary Condition ---

class TestBoundaryCondition:
    """
    Boundary 케이스 테스트

    조건:
    - "감액", "지급률", "조건부" 키워드 포함
    - 판단 없이 그대로 노출

    판단 금지:
    - "불리/유리" 판단 ❌
    - 요약/정규화 금지 ❌
    """

    def test_boundary_conditions_displayed_as_is(
        self,
        canonical_store,
        definition_store_boundary
    ):
        """감액/지급률 조건이 그대로 노출되는지"""
        engine = ConditionCompareEngine(
            canonical_store=canonical_store,
            definition_store=definition_store_boundary
        )

        input = ConditionCompareInput(
            canonical_coverage_code="A4200_1",
            comparison_aspects=(ComparisonAspect.BOUNDARY_CONDITION,),
            insurers=(Insurer.SAMSUNG, Insurer.MERITZ)
        )

        response = engine.compare(input)

        # 삼성: 원문 그대로
        samsung_result = response.results[Insurer.SAMSUNG]
        assert isinstance(samsung_result, ConditionSuccessResult)
        assert "50% 감액" in samsung_result.definitions.boundary_condition

        # 메리츠: 원문 그대로
        meritz_result = response.results[Insurer.MERITZ]
        assert isinstance(meritz_result, ConditionSuccessResult)
        assert "50% 지급" in meritz_result.definitions.boundary_condition


# --- Test Case 5: Hard Fail ---

class TestHardFail:
    """
    Hard Fail 테스트

    조건:
    - canonical_code 자체가 존재하지 않음

    결과:
    - compare 시작 불가
    - CanonicalNotFoundError
    """

    def test_canonical_not_exists(
        self,
        canonical_store,
        definition_store_full
    ):
        """존재하지 않는 canonical_code"""
        engine = ConditionCompareEngine(
            canonical_store=canonical_store,
            definition_store=definition_store_full
        )

        input = ConditionCompareInput(
            canonical_coverage_code="INVALID_CODE",
            comparison_aspects=(ComparisonAspect.SUBTYPE_COVERAGE,),
            insurers=(Insurer.SAMSUNG, Insurer.MERITZ)
        )

        with pytest.raises(CanonicalNotFoundError) as exc_info:
            engine.compare(input)

        assert exc_info.value.canonical_code == "INVALID_CODE"


# --- Test Input Validation ---

class TestInputValidation:
    """입력 검증 테스트"""

    def test_empty_canonical_code(self):
        """빈 canonical_code"""
        with pytest.raises(ValueError):
            ConditionCompareInput(
                canonical_coverage_code="",
                comparison_aspects=(ComparisonAspect.SUBTYPE_COVERAGE,),
                insurers=(Insurer.SAMSUNG,)
            )

    def test_empty_aspects(self):
        """빈 comparison_aspects"""
        with pytest.raises(ValueError):
            ConditionCompareInput(
                canonical_coverage_code="A4200_1",
                comparison_aspects=(),
                insurers=(Insurer.SAMSUNG,)
            )

    def test_empty_insurers(self):
        """빈 insurers"""
        with pytest.raises(ValueError):
            ConditionCompareInput(
                canonical_coverage_code="A4200_1",
                comparison_aspects=(ComparisonAspect.SUBTYPE_COVERAGE,),
                insurers=()
            )


# --- Test Definitions Class ---

class TestDefinitions:
    """Definitions 클래스 테스트"""

    def test_set_and_get(self):
        """set/get 동작"""
        defs = Definitions()
        defs.set(ComparisonAspect.SUBTYPE_COVERAGE, "유사암 제외")

        assert defs.get(ComparisonAspect.SUBTYPE_COVERAGE) == "유사암 제외"
        assert defs.get(ComparisonAspect.BOUNDARY_CONDITION) is None

    def test_to_dict_excludes_none(self):
        """to_dict는 None 값 제외"""
        defs = Definitions()
        defs.subtype_coverage = "유사암 제외"

        result = defs.to_dict()
        assert "subtype_coverage" in result
        assert "boundary_condition" not in result
