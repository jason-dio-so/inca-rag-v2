"""
Explain View Tests
STEP V2-6: Explain View / Boundary UX + Slot Rendering

테스트 시나리오:
1. DETERMINED → INFO 카드 + Amount 탭 필수
2. NO_AMOUNT → ERROR 카드 필수
3. CONDITION_MISMATCH → WARNING 카드 + 조건 탭 표시
4. DEFINITION_ONLY → Definition 탭만 표시
5. 다보험사 비교 레이아웃
6. Serialization 검증
"""

import pytest

from compare.decision_types import (
    BindingResult,
    BoundEvidence,
    CompareDecision,
    CompareExplanation,
    DecisionRule,
)
from compare.explain_types import (
    AmountEvidenceItem,
    CardType,
    ConditionEvidenceItem,
    DefinitionEvidenceItem,
    DroppedEvidenceInfo,
    EvidenceReference,
    EvidenceTabs,
    ExplainViewResponse,
    InsurerExplainView,
    MultiInsurerExplainView,
    ReasonCard,
    RuleTrace,
)
from compare.explain_view_mapper import (
    ExplainViewMapper,
    create_explain_view,
    create_multi_insurer_explain_view,
)
from compare.types import Insurer


# --- Test Fixtures ---

@pytest.fixture
def mapper():
    """ExplainViewMapper 인스턴스"""
    return ExplainViewMapper()


@pytest.fixture
def determined_binding_result():
    """DETERMINED 상태 BindingResult"""
    return BindingResult(
        decision=CompareDecision.DETERMINED,
        explanation=CompareExplanation(
            decision=CompareDecision.DETERMINED,
            applied_rules=(
                DecisionRule.RULE_AMOUNT_PRIMARY,
                DecisionRule.RULE_DOC_PRIORITY,
            ),
            used_evidence_ids=("EVID-001", "EVID-002"),
            reasons=("금액 증거: 약관에서 발견", "금액 확정: 5천만원"),
        ),
        bound_evidence=(
            BoundEvidence(
                evidence_id="EVID-001",
                slot_type="amount",
                doc_type="약관",
                doc_id="SAMSUNG_CANCER_2024",
                page=45,
                excerpt="암 진단 확정시 5천만원 지급",
                binding_rule=DecisionRule.RULE_AMOUNT_PRIMARY,
            ),
            BoundEvidence(
                evidence_id="EVID-002",
                slot_type="condition",
                doc_type="약관",
                doc_id="SAMSUNG_CANCER_2024",
                page=46,
                excerpt="계약일로부터 90일 이내 진단 시 보장하지 않음",
            ),
        ),
        amount_value="5천만원",
        amount_numeric=50_000_000,
    )


@pytest.fixture
def no_amount_binding_result():
    """NO_AMOUNT 상태 BindingResult"""
    return BindingResult(
        decision=CompareDecision.NO_AMOUNT,
        explanation=CompareExplanation(
            decision=CompareDecision.NO_AMOUNT,
            applied_rules=(DecisionRule.RULE_PASS_1_EMPTY,),
            reasons=("PASS 1 결과 없음: no_amount_bearing_evidence",),
        ),
    )


@pytest.fixture
def condition_mismatch_binding_result():
    """CONDITION_MISMATCH 상태 BindingResult"""
    return BindingResult(
        decision=CompareDecision.CONDITION_MISMATCH,
        explanation=CompareExplanation(
            decision=CompareDecision.CONDITION_MISMATCH,
            applied_rules=(
                DecisionRule.RULE_AMOUNT_PRIMARY,
                DecisionRule.RULE_CONDITION_CONFLICT,
            ),
            used_evidence_ids=("EVID-001",),
            reasons=("금액 증거: 약관에서 발견", "조건 충돌 감지됨"),
        ),
        bound_evidence=(
            BoundEvidence(
                evidence_id="EVID-001",
                slot_type="amount",
                doc_type="약관",
                doc_id="SAMSUNG_CANCER_2024",
                page=45,
                excerpt="암 진단 확정시 3천만원 지급",
            ),
            BoundEvidence(
                evidence_id="EVID-002",
                slot_type="condition",
                doc_type="약관",
                doc_id="SAMSUNG_CANCER_2024",
                page=47,
                excerpt="해당 조건 적용 시 보장 제외",
            ),
        ),
        amount_value="3천만원",
        amount_numeric=30_000_000,
    )


@pytest.fixture
def definition_only_binding_result():
    """DEFINITION_ONLY 상태 BindingResult"""
    return BindingResult(
        decision=CompareDecision.DEFINITION_ONLY,
        explanation=CompareExplanation(
            decision=CompareDecision.DEFINITION_ONLY,
            applied_rules=(
                DecisionRule.RULE_DEFINITION_ONLY,
                DecisionRule.RULE_DEFINITION_NO_AMOUNT,
            ),
            used_evidence_ids=("EVID-001",),
            reasons=("정의 증거만 존재, 금액 증거 없음",),
        ),
        bound_evidence=(
            BoundEvidence(
                evidence_id="EVID-001",
                slot_type="definition",
                doc_type="약관",
                doc_id="SAMSUNG_CANCER_2024",
                page=10,
                excerpt="암이라 함은 한국표준질병사인분류에서 정의하는 악성신생물을 말합니다",
            ),
        ),
    )


@pytest.fixture
def insufficient_evidence_binding_result():
    """INSUFFICIENT_EVIDENCE 상태 BindingResult"""
    return BindingResult(
        decision=CompareDecision.INSUFFICIENT_EVIDENCE,
        explanation=CompareExplanation(
            decision=CompareDecision.INSUFFICIENT_EVIDENCE,
            applied_rules=(DecisionRule.RULE_NO_EVIDENCE,),
            reasons=("판단 가능한 증거 없음",),
        ),
    )


# --- Test Case 1: DETERMINED ---

class TestDeterminedExplainView:
    """
    DETERMINED 상태 테스트

    조건:
    - INFO 카드 필수
    - Amount 탭 필수
    """

    def test_decision_is_determined(self, mapper, determined_binding_result):
        """decision이 DETERMINED인지"""
        result = mapper.map(determined_binding_result)

        assert result.decision == "determined"

    def test_has_info_card(self, mapper, determined_binding_result):
        """INFO 카드 존재"""
        result = mapper.map(determined_binding_result)

        assert len(result.reason_cards) == 1
        assert result.reason_cards[0].type == CardType.INFO
        assert result.reason_cards[0].title == "결과 확정"

    def test_has_amount_tab(self, mapper, determined_binding_result):
        """Amount 탭 필수"""
        result = mapper.map(determined_binding_result)

        assert result.evidence_tabs.has_amount()
        assert len(result.evidence_tabs.amount) == 1
        assert result.evidence_tabs.amount[0].value == "5천만원"

    def test_has_condition_tab(self, mapper, determined_binding_result):
        """Condition 탭 존재"""
        result = mapper.map(determined_binding_result)

        assert result.evidence_tabs.has_condition()
        assert len(result.evidence_tabs.condition) == 1

    def test_rule_trace_contains_applied_rules(self, mapper, determined_binding_result):
        """Rule trace에 적용된 규칙 포함"""
        result = mapper.map(determined_binding_result)

        assert "amount_primary" in result.rule_trace.applied_rules
        assert "doc_priority" in result.rule_trace.applied_rules


# --- Test Case 2: NO_AMOUNT ---

class TestNoAmountExplainView:
    """
    NO_AMOUNT 상태 테스트

    조건:
    - ERROR 카드 필수
    """

    def test_decision_is_no_amount(self, mapper, no_amount_binding_result):
        """decision이 NO_AMOUNT인지"""
        result = mapper.map(no_amount_binding_result)

        assert result.decision == "no_amount"

    def test_has_error_card(self, mapper, no_amount_binding_result):
        """ERROR 카드 필수"""
        result = mapper.map(no_amount_binding_result)

        assert len(result.reason_cards) == 1
        assert result.reason_cards[0].type == CardType.ERROR
        assert result.reason_cards[0].title == "금액 근거 부족"

    def test_no_amount_tab(self, mapper, no_amount_binding_result):
        """Amount 탭 없음"""
        result = mapper.map(no_amount_binding_result)

        assert not result.evidence_tabs.has_amount()

    def test_headline_indicates_no_amount(self, mapper, no_amount_binding_result):
        """Headline이 금액 없음을 표시"""
        result = mapper.map(no_amount_binding_result)

        assert "금액" in result.headline


# --- Test Case 3: CONDITION_MISMATCH ---

class TestConditionMismatchExplainView:
    """
    CONDITION_MISMATCH 상태 테스트

    조건:
    - WARNING 카드 필수
    - 조건 탭 표시
    """

    def test_decision_is_condition_mismatch(self, mapper, condition_mismatch_binding_result):
        """decision이 CONDITION_MISMATCH인지"""
        result = mapper.map(condition_mismatch_binding_result)

        assert result.decision == "condition_mismatch"

    def test_has_warning_card(self, mapper, condition_mismatch_binding_result):
        """WARNING 카드 필수"""
        result = mapper.map(condition_mismatch_binding_result)

        assert len(result.reason_cards) == 1
        assert result.reason_cards[0].type == CardType.WARNING
        assert result.reason_cards[0].title == "조건 충돌"

    def test_has_condition_tab_with_conflict(self, mapper, condition_mismatch_binding_result):
        """조건 탭에 충돌 표시"""
        result = mapper.map(condition_mismatch_binding_result)

        assert result.evidence_tabs.has_condition()
        assert result.evidence_tabs.condition[0].has_conflict is True

    def test_amount_still_shown(self, mapper, condition_mismatch_binding_result):
        """금액은 여전히 표시됨"""
        result = mapper.map(condition_mismatch_binding_result)

        assert result.evidence_tabs.has_amount()
        assert result.evidence_tabs.amount[0].value == "3천만원"


# --- Test Case 4: DEFINITION_ONLY ---

class TestDefinitionOnlyExplainView:
    """
    DEFINITION_ONLY 상태 테스트

    조건:
    - Definition 탭만 표시
    """

    def test_decision_is_definition_only(self, mapper, definition_only_binding_result):
        """decision이 DEFINITION_ONLY인지"""
        result = mapper.map(definition_only_binding_result)

        assert result.decision == "definition_only"

    def test_has_info_card(self, mapper, definition_only_binding_result):
        """INFO 카드 존재"""
        result = mapper.map(definition_only_binding_result)

        assert len(result.reason_cards) == 1
        assert result.reason_cards[0].type == CardType.INFO

    def test_only_definition_tab(self, mapper, definition_only_binding_result):
        """Definition 탭만 존재"""
        result = mapper.map(definition_only_binding_result)

        assert result.evidence_tabs.has_definition()
        assert not result.evidence_tabs.has_amount()
        assert not result.evidence_tabs.has_condition()


# --- Test Case 5: INSUFFICIENT_EVIDENCE ---

class TestInsufficientEvidenceExplainView:
    """
    INSUFFICIENT_EVIDENCE 상태 테스트

    조건:
    - ERROR 카드 필수
    """

    def test_decision_is_insufficient(self, mapper, insufficient_evidence_binding_result):
        """decision이 INSUFFICIENT_EVIDENCE인지"""
        result = mapper.map(insufficient_evidence_binding_result)

        assert result.decision == "insufficient_evidence"

    def test_has_error_card(self, mapper, insufficient_evidence_binding_result):
        """ERROR 카드 필수"""
        result = mapper.map(insufficient_evidence_binding_result)

        assert len(result.reason_cards) == 1
        assert result.reason_cards[0].type == CardType.ERROR
        assert result.reason_cards[0].title == "판단 불가"

    def test_empty_evidence_tabs(self, mapper, insufficient_evidence_binding_result):
        """모든 탭 비어있음"""
        result = mapper.map(insufficient_evidence_binding_result)

        assert not result.evidence_tabs.has_amount()
        assert not result.evidence_tabs.has_condition()
        assert not result.evidence_tabs.has_definition()


# --- Test Case 6: Multi-Insurer ---

class TestMultiInsurerExplainView:
    """
    다보험사 비교 테스트

    조건:
    - 보험사별 Explain View 카드 반복
    - 동일 decision_status라도 사유/규칙은 다를 수 있음
    """

    def test_multi_insurer_view(
        self,
        mapper,
        determined_binding_result,
        no_amount_binding_result
    ):
        """다보험사 비교"""
        result = mapper.map_multi_insurer(
            canonical_code="A4200_1",
            canonical_name="암진단비(유사암제외)",
            insurer_results={
                Insurer.SAMSUNG: determined_binding_result,
                Insurer.MERITZ: no_amount_binding_result,
            }
        )

        assert result.canonical_coverage_code == "A4200_1"
        assert len(result.insurer_views) == 2

        # 삼성: DETERMINED
        samsung_view = next(
            v for v in result.insurer_views if v.insurer == "SAMSUNG"
        )
        assert samsung_view.explain_view.decision == "determined"

        # 메리츠: NO_AMOUNT
        meritz_view = next(
            v for v in result.insurer_views if v.insurer == "MERITZ"
        )
        assert meritz_view.explain_view.decision == "no_amount"

    def test_convenience_function(
        self,
        determined_binding_result,
        no_amount_binding_result
    ):
        """편의 함수 테스트"""
        result = create_multi_insurer_explain_view(
            canonical_code="A4200_1",
            canonical_name="암진단비(유사암제외)",
            insurer_results={
                Insurer.SAMSUNG: determined_binding_result,
            }
        )

        assert len(result.insurer_views) == 1


# --- Test Case 7: Serialization ---

class TestSerialization:
    """직렬화 테스트"""

    def test_explain_view_to_dict(self, mapper, determined_binding_result):
        """ExplainViewResponse 직렬화"""
        result = mapper.map(determined_binding_result)
        serialized = result.to_dict()

        assert serialized["decision"] == "determined"
        assert "headline" in serialized
        assert "reason_cards" in serialized
        assert "evidence_tabs" in serialized
        assert "rule_trace" in serialized

    def test_reason_card_to_dict(self, mapper, determined_binding_result):
        """ReasonCard 직렬화"""
        result = mapper.map(determined_binding_result)
        card_dict = result.reason_cards[0].to_dict()

        assert card_dict["type"] == "INFO"
        assert "title" in card_dict
        assert "message" in card_dict
        assert "decision" in card_dict

    def test_evidence_tabs_to_dict(self, mapper, determined_binding_result):
        """EvidenceTabs 직렬화"""
        result = mapper.map(determined_binding_result)
        tabs_dict = result.evidence_tabs.to_dict()

        assert "amount" in tabs_dict
        assert len(tabs_dict["amount"]) == 1
        assert tabs_dict["amount"][0]["value"] == "5천만원"

    def test_rule_trace_to_dict(self, mapper, determined_binding_result):
        """RuleTrace 직렬화"""
        result = mapper.map(determined_binding_result)
        trace_dict = result.rule_trace.to_dict()

        assert "applied_rules" in trace_dict
        assert "amount_primary" in trace_dict["applied_rules"]

    def test_multi_insurer_to_dict(
        self,
        mapper,
        determined_binding_result
    ):
        """MultiInsurerExplainView 직렬화"""
        result = mapper.map_multi_insurer(
            canonical_code="A4200_1",
            canonical_name="암진단비(유사암제외)",
            insurer_results={Insurer.SAMSUNG: determined_binding_result}
        )
        serialized = result.to_dict()

        assert serialized["canonical_coverage_code"] == "A4200_1"
        assert len(serialized["insurer_views"]) == 1


# --- Test Case 8: Convenience Functions ---

class TestConvenienceFunctions:
    """편의 함수 테스트"""

    def test_create_explain_view(self, determined_binding_result):
        """create_explain_view 함수"""
        result = create_explain_view(determined_binding_result)

        assert result.decision == "determined"

    def test_create_multi_insurer_explain_view(self, determined_binding_result):
        """create_multi_insurer_explain_view 함수"""
        result = create_multi_insurer_explain_view(
            canonical_code="A4200_1",
            canonical_name="암진단비",
            insurer_results={Insurer.SAMSUNG: determined_binding_result}
        )

        assert result.canonical_coverage_code == "A4200_1"


# --- Regression Tests ---

class TestRegression:
    """회귀 테스트"""

    def test_v2_5_decision_status_preserved(self, mapper, determined_binding_result):
        """V2-5 decision_status 값 변경 없음"""
        result = mapper.map(determined_binding_result)

        # V2-5 CompareDecision 값과 일치
        assert result.decision == CompareDecision.DETERMINED.value

    def test_applied_rules_not_missing(self, mapper, determined_binding_result):
        """explanation.applied_rules 누락 없음"""
        result = mapper.map(determined_binding_result)

        assert len(result.rule_trace.applied_rules) > 0

    def test_source_boundary_preserved(self, mapper, determined_binding_result):
        """출처 정보 보존"""
        result = mapper.map(determined_binding_result)

        amount_item = result.evidence_tabs.amount[0]
        assert amount_item.source_doc == "약관"
        assert amount_item.page == 45
        assert amount_item.doc_id == "SAMSUNG_CANCER_2024"
