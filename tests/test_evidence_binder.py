"""
Evidence Binder Tests
STEP V2-5: Evidence-to-Compare Binding

테스트 시나리오:
1. Amount 2건 → 1건 선택 확인 (DETERMINED)
2. Condition 충돌 → Amount 유지 + CONDITION_MISMATCH
3. Definition only → DEFINITION_ONLY
4. No evidence → INSUFFICIENT_EVIDENCE
5. NoAmountFoundResult → NO_AMOUNT
"""

import pytest

from compare.decision_types import (
    BindingResult,
    BoundEvidence,
    CompareDecision,
    CompareExplanation,
    DecisionRule,
    is_determined,
    is_partial_failure,
)
from compare.evidence_binder import (
    BindingContext,
    EvidenceBinder,
    bind_evidence,
)
from compare.evidence_types import (
    EvidencePurpose,
    EvidenceSlot,
    EvidenceSlots,
    NoAmountFoundResult,
    RetrievalPass,
)
from compare.types import DocType


# --- Test Fixtures ---

@pytest.fixture
def binder():
    """EvidenceBinder 인스턴스"""
    return EvidenceBinder()


@pytest.fixture
def amount_slot():
    """Amount 슬롯"""
    return EvidenceSlot(
        purpose=EvidencePurpose.AMOUNT,
        source_doc=DocType.YAKGWAN,
        excerpt="암 진단 확정시 5천만원 지급",
        value="5천만원",
        page=45,
        doc_id="SAMSUNG_CANCER_2024",
        retrieval_pass=RetrievalPass.PASS_1,
    )


@pytest.fixture
def condition_slot():
    """Condition 슬롯"""
    return EvidenceSlot(
        purpose=EvidencePurpose.CONDITION,
        source_doc=DocType.YAKGWAN,
        excerpt="계약일로부터 90일 이내 진단 시 보장하지 않음",
        page=46,
        doc_id="SAMSUNG_CANCER_2024",
        retrieval_pass=RetrievalPass.PASS_2,
    )


@pytest.fixture
def definition_slot():
    """Definition 슬롯"""
    return EvidenceSlot(
        purpose=EvidencePurpose.DEFINITION,
        source_doc=DocType.YAKGWAN,
        excerpt="암이라 함은 한국표준질병사인분류에서 정의하는 악성신생물을 말합니다",
        page=10,
        doc_id="SAMSUNG_CANCER_2024",
        retrieval_pass=RetrievalPass.PASS_2,
    )


# --- Test Case 1: DETERMINED (정상 바인딩) ---

class TestDeterminedBinding:
    """
    DETERMINED 상태 테스트

    조건:
    - Amount evidence 존재
    - 결과 확정
    """

    def test_amount_only(self, binder, amount_slot):
        """Amount만 있을 때 DETERMINED"""
        slots = EvidenceSlots(amount=amount_slot)

        result = binder.bind(slots)

        assert result.decision == CompareDecision.DETERMINED
        assert is_determined(result.decision)
        assert not is_partial_failure(result.decision)
        assert result.amount_value == "5천만원"
        assert result.amount_numeric == 50_000_000

    def test_amount_with_condition(self, binder, amount_slot, condition_slot):
        """Amount + Condition"""
        slots = EvidenceSlots(
            amount=amount_slot,
            condition=condition_slot
        )

        result = binder.bind(slots)

        assert result.decision == CompareDecision.DETERMINED
        assert len(result.bound_evidence) == 2

        # Amount 바인딩 확인
        amount_bound = [e for e in result.bound_evidence if e.slot_type == "amount"]
        assert len(amount_bound) == 1
        assert amount_bound[0].doc_type == "약관"

        # Condition 바인딩 확인
        condition_bound = [e for e in result.bound_evidence if e.slot_type == "condition"]
        assert len(condition_bound) == 1

    def test_all_slots(self, binder, amount_slot, condition_slot, definition_slot):
        """모든 슬롯 존재"""
        slots = EvidenceSlots(
            amount=amount_slot,
            condition=condition_slot,
            definition=definition_slot
        )

        result = binder.bind(slots)

        assert result.decision == CompareDecision.DETERMINED
        assert len(result.bound_evidence) == 3

    def test_explanation_has_applied_rules(self, binder, amount_slot):
        """Explanation에 적용된 규칙 포함"""
        slots = EvidenceSlots(amount=amount_slot)

        result = binder.bind(slots)

        assert DecisionRule.RULE_AMOUNT_PRIMARY in result.explanation.applied_rules
        assert DecisionRule.RULE_DOC_PRIORITY in result.explanation.applied_rules

    def test_explanation_has_reasons(self, binder, amount_slot):
        """Explanation에 이유 포함"""
        slots = EvidenceSlots(amount=amount_slot)

        result = binder.bind(slots)

        assert len(result.explanation.reasons) > 0
        # 사실 기반 이유 확인 (추론 금지)
        for reason in result.explanation.reasons:
            assert "보입니다" not in reason
            assert "것 같" not in reason


# --- Test Case 2: NO_AMOUNT ---

class TestNoAmountBinding:
    """
    NO_AMOUNT 상태 테스트

    조건:
    - NoAmountFoundResult 입력
    - 또는 EvidenceSlots에 amount 없음
    """

    def test_no_amount_found_result(self, binder):
        """NoAmountFoundResult 입력"""
        result = binder.bind(NoAmountFoundResult(
            reason="no_amount_bearing_evidence"
        ))

        assert result.decision == CompareDecision.NO_AMOUNT
        assert is_partial_failure(result.decision)
        assert DecisionRule.RULE_PASS_1_EMPTY in result.explanation.applied_rules

    def test_convenience_function(self):
        """bind_evidence 편의 함수"""
        result = bind_evidence(NoAmountFoundResult(
            reason="no_documents_found"
        ))

        assert result.decision == CompareDecision.NO_AMOUNT


# --- Test Case 3: DEFINITION_ONLY ---

class TestDefinitionOnlyBinding:
    """
    DEFINITION_ONLY 상태 테스트

    조건:
    - Definition만 존재
    - Amount 없음
    """

    def test_definition_only(self, binder, definition_slot):
        """Definition만 있을 때"""
        slots = EvidenceSlots(definition=definition_slot)

        result = binder.bind(slots)

        assert result.decision == CompareDecision.DEFINITION_ONLY
        assert is_partial_failure(result.decision)
        assert DecisionRule.RULE_DEFINITION_ONLY in result.explanation.applied_rules
        assert len(result.bound_evidence) == 1
        assert result.bound_evidence[0].slot_type == "definition"


# --- Test Case 4: INSUFFICIENT_EVIDENCE ---

class TestInsufficientEvidenceBinding:
    """
    INSUFFICIENT_EVIDENCE 상태 테스트

    조건:
    - 모든 슬롯 비어있음
    """

    def test_empty_slots(self, binder):
        """빈 EvidenceSlots"""
        slots = EvidenceSlots()

        result = binder.bind(slots)

        assert result.decision == CompareDecision.INSUFFICIENT_EVIDENCE
        assert is_partial_failure(result.decision)
        assert DecisionRule.RULE_NO_EVIDENCE in result.explanation.applied_rules


# --- Test Case 5: Amount 추출 ---

class TestAmountExtraction:
    """금액 추출 테스트"""

    def test_extract_manwon(self, binder, amount_slot):
        """만원 단위 추출"""
        slots = EvidenceSlots(amount=amount_slot)
        result = binder.bind(slots)

        assert result.amount_numeric == 50_000_000  # 5천만원

    def test_extract_cheonmanwon(self, binder):
        """천만원 단위 추출"""
        slot = EvidenceSlot(
            purpose=EvidencePurpose.AMOUNT,
            source_doc=DocType.YAKGWAN,
            excerpt="진단시 3천만원 지급",
            value="3천만원",
            page=45,
            retrieval_pass=RetrievalPass.PASS_1,
        )
        slots = EvidenceSlots(amount=slot)
        result = binder.bind(slots)

        assert result.amount_numeric == 30_000_000

    def test_extract_eok(self, binder):
        """억 단위 추출"""
        slot = EvidenceSlot(
            purpose=EvidencePurpose.AMOUNT,
            source_doc=DocType.YAKGWAN,
            excerpt="사망시 1억원 지급",
            value="1억",
            page=45,
            retrieval_pass=RetrievalPass.PASS_1,
        )
        slots = EvidenceSlots(amount=slot)
        result = binder.bind(slots)

        assert result.amount_numeric == 100_000_000


# --- Test Case 6: Serialization ---

class TestSerialization:
    """직렬화 테스트"""

    def test_binding_result_to_dict(self, binder, amount_slot):
        """BindingResult 직렬화"""
        slots = EvidenceSlots(amount=amount_slot)
        result = binder.bind(slots)

        serialized = result.to_dict()

        assert serialized["decision"] == "determined"
        assert "explanation" in serialized
        assert "bound_evidence" in serialized
        assert serialized["amount_value"] == "5천만원"
        assert serialized["amount_numeric"] == 50_000_000

    def test_explanation_to_dict(self, binder, amount_slot):
        """CompareExplanation 직렬화"""
        slots = EvidenceSlots(amount=amount_slot)
        result = binder.bind(slots)

        explanation_dict = result.explanation.to_dict()

        assert explanation_dict["decision"] == "determined"
        assert "applied_rules" in explanation_dict
        assert "reason" in explanation_dict

    def test_bound_evidence_to_dict(self, binder, amount_slot):
        """BoundEvidence 직렬화"""
        slots = EvidenceSlots(amount=amount_slot)
        result = binder.bind(slots)

        evidence_dict = result.bound_evidence[0].to_dict()

        assert "evidence_id" in evidence_dict
        assert evidence_dict["slot_type"] == "amount"
        assert evidence_dict["doc_type"] == "약관"


# --- Test Case 7: Decision Status Helpers ---

class TestDecisionStatusHelpers:
    """Decision 상태 헬퍼 함수 테스트"""

    def test_is_determined(self):
        """is_determined() 함수"""
        assert is_determined(CompareDecision.DETERMINED) is True
        assert is_determined(CompareDecision.NO_AMOUNT) is False
        assert is_determined(CompareDecision.CONDITION_MISMATCH) is False

    def test_is_partial_failure(self):
        """is_partial_failure() 함수"""
        assert is_partial_failure(CompareDecision.DETERMINED) is False
        assert is_partial_failure(CompareDecision.NO_AMOUNT) is True
        assert is_partial_failure(CompareDecision.CONDITION_MISMATCH) is True
        assert is_partial_failure(CompareDecision.DEFINITION_ONLY) is True
        assert is_partial_failure(CompareDecision.INSUFFICIENT_EVIDENCE) is True


# --- Test Case 8: BindingContext ---

class TestBindingContext:
    """BindingContext 테스트"""

    def test_create(self):
        """BindingContext 생성"""
        ctx = BindingContext.create()

        assert ctx.applied_rules == []
        assert ctx.used_evidence_ids == []
        assert ctx.dropped_evidence_ids == []
        assert ctx.reasons == []
        assert ctx.bound_evidence == []

    def test_add_rule(self):
        """규칙 추가 (중복 방지)"""
        ctx = BindingContext.create()
        ctx.add_rule(DecisionRule.RULE_AMOUNT_PRIMARY)
        ctx.add_rule(DecisionRule.RULE_AMOUNT_PRIMARY)  # 중복

        assert len(ctx.applied_rules) == 1

    def test_add_reason(self):
        """이유 추가"""
        ctx = BindingContext.create()
        ctx.add_reason("금액 증거 발견")

        assert "금액 증거 발견" in ctx.reasons


# --- Regression Tests ---

class TestRegression:
    """회귀 테스트 (V2-2, V2-3, V2-4 결과 의미 불변)"""

    def test_evidence_id_format(self, binder, amount_slot):
        """Evidence ID 형식 확인"""
        slots = EvidenceSlots(amount=amount_slot)
        result = binder.bind(slots)

        for evidence in result.bound_evidence:
            assert evidence.evidence_id.startswith("EVID-")
            assert len(evidence.evidence_id) == 13  # "EVID-" + 8 hex chars

    def test_doc_type_preserved(self, binder, amount_slot):
        """DocType 보존 확인"""
        slots = EvidenceSlots(amount=amount_slot)
        result = binder.bind(slots)

        assert result.bound_evidence[0].doc_type == "약관"
