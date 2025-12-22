"""
Evidence Retriever Tests
STEP V2-4: Evidence Retrieval Refinement

테스트 시나리오:
1. 정상: Amount-bearing evidence 선택
2. PASS 2: Condition/Definition 보완
3. No Amount: Amount evidence 없음 → NoAmountFoundResult
4. DROP: 강제 탈락 규칙
5. Scoring: 정렬 규칙 검증
"""

import pytest

from compare.evidence_retriever import (
    DocumentStore,
    EvidenceRetriever,
    EvidenceScore,
    RawEvidence,
    calculate_evidence_score,
)
from compare.evidence_types import (
    DropReason,
    EvidencePurpose,
    EvidenceSlot,
    EvidenceSlots,
    NoAmountFoundResult,
    RetrievalDebug,
    RetrievalPass,
)
from compare.types import DocType, Insurer


# --- Mock Document Store ---

class MockDocumentStore:
    """테스트용 Document Store"""

    def __init__(self, data: dict[tuple[str, Insurer], list[RawEvidence]]):
        self._data = data

    def get_documents_by_coverage_code(
        self,
        coverage_code: str,
        insurer: Insurer
    ) -> list[RawEvidence]:
        return self._data.get((coverage_code, insurer), [])


# --- Test Fixtures ---

@pytest.fixture
def document_store_with_amount():
    """Amount가 포함된 문서들"""
    return MockDocumentStore({
        ("A4200_1", Insurer.SAMSUNG): [
            RawEvidence(
                doc_type=DocType.YAKGWAN,
                doc_id="SAMSUNG_CANCER_2024",
                page=45,
                text="암 진단 확정시 5천만원 지급",
                coverage_code="A4200_1"
            ),
            RawEvidence(
                doc_type=DocType.YAKGWAN,
                doc_id="SAMSUNG_CANCER_2024",
                page=46,
                text="계약일로부터 90일 이내 진단 시 보장하지 않음",
                coverage_code="A4200_1"
            ),
            RawEvidence(
                doc_type=DocType.YAKGWAN,
                doc_id="SAMSUNG_CANCER_2024",
                page=10,
                text="암이라 함은 한국표준질병사인분류에서 정의하는 악성신생물을 말합니다",
                coverage_code="A4200_1"
            ),
        ],
    })


@pytest.fixture
def document_store_no_amount():
    """Amount가 없는 문서들"""
    return MockDocumentStore({
        ("A4200_1", Insurer.SAMSUNG): [
            RawEvidence(
                doc_type=DocType.YAKGWAN,
                doc_id="SAMSUNG_CANCER_2024",
                page=46,
                text="계약일로부터 90일 이내 진단 시 보장하지 않음",
                coverage_code="A4200_1"
            ),
            RawEvidence(
                doc_type=DocType.YAKGWAN,
                doc_id="SAMSUNG_CANCER_2024",
                page=10,
                text="암이라 함은 한국표준질병사인분류에서 정의하는 악성신생물을 말합니다",
                coverage_code="A4200_1"
            ),
        ],
    })


@pytest.fixture
def document_store_with_drop_candidates():
    """DROP 대상 문서들"""
    return MockDocumentStore({
        ("A4200_1", Insurer.SAMSUNG): [
            RawEvidence(
                doc_type=DocType.YAKGWAN,
                doc_id="SAMSUNG_CANCER_2024",
                page=45,
                text="암 진단 확정시 3천만원 지급",
                coverage_code="A4200_1"
            ),
            RawEvidence(
                doc_type=DocType.YAKGWAN,
                doc_id="SAMSUNG_CANCER_2024",
                page=1,
                text="",  # 빈 텍스트 - DROP
                coverage_code="A4200_1"
            ),
            RawEvidence(
                doc_type=DocType.YAKGWAN,
                doc_id="SAMSUNG_CANCER_2024",
                page=99,
                text="자세한 내용은 약관 참조",  # 참조만 - DROP
                coverage_code="A4200_1"
            ),
        ],
    })


@pytest.fixture
def document_store_multiple_amounts():
    """여러 Amount 문서 (scoring 테스트)"""
    return MockDocumentStore({
        ("A4200_1", Insurer.SAMSUNG): [
            RawEvidence(
                doc_type=DocType.SAEOP,  # 사업방법서 (낮은 우선순위)
                doc_id="SAMSUNG_SAEOP_2024",
                page=100,
                text="암 진단시 5천만원 지급",
                coverage_code="A4200_1"
            ),
            RawEvidence(
                doc_type=DocType.YAKGWAN,  # 약관 (높은 우선순위)
                doc_id="SAMSUNG_CANCER_2024",
                page=45,
                text="암 진단 확정시 5천만원 지급",
                coverage_code="A4200_1"
            ),
        ],
    })


# --- Test Case 1: Amount-bearing Evidence Selection ---

class TestAmountRetrieval:
    """
    Amount-bearing evidence 선택 테스트

    조건:
    - Amount가 포함된 문서가 PASS 1에서 선택됨
    - PASS 2에서 Condition/Definition 보완
    """

    def test_pass_1_selects_amount(self, document_store_with_amount):
        """PASS 1이 amount를 선택하는지"""
        retriever = EvidenceRetriever(document_store_with_amount)

        result, debug = retriever.retrieve(
            coverage_code="A4200_1",
            insurer=Insurer.SAMSUNG
        )

        # EvidenceSlots 반환 확인
        assert isinstance(result, EvidenceSlots)
        assert result.has_amount()

        # Amount 슬롯 검증
        assert result.amount is not None
        assert result.amount.purpose == EvidencePurpose.AMOUNT
        assert "5천만원" in result.amount.excerpt
        assert result.amount.source_doc == DocType.YAKGWAN
        assert result.amount.retrieval_pass == RetrievalPass.PASS_1

        # Debug 검증
        assert debug.pass_1_count >= 1

    def test_pass_2_adds_context(self, document_store_with_amount):
        """PASS 2가 condition/definition을 보완하는지"""
        retriever = EvidenceRetriever(document_store_with_amount)

        result, debug = retriever.retrieve(
            coverage_code="A4200_1",
            insurer=Insurer.SAMSUNG
        )

        assert isinstance(result, EvidenceSlots)

        # Condition 슬롯 검증
        if result.condition:
            assert result.condition.purpose == EvidencePurpose.CONDITION
            assert result.condition.retrieval_pass == RetrievalPass.PASS_2

        # Definition 슬롯 검증
        if result.definition:
            assert result.definition.purpose == EvidencePurpose.DEFINITION
            assert "말합니다" in result.definition.excerpt


# --- Test Case 2: No Amount Found ---

class TestNoAmountFound:
    """
    Amount 없음 테스트

    조건:
    - Amount가 없는 문서들만 존재
    - NoAmountFoundResult 반환
    - Hallucinated 금액 생성 금지
    """

    def test_returns_no_amount_result(self, document_store_no_amount):
        """Amount 없으면 NoAmountFoundResult 반환"""
        retriever = EvidenceRetriever(document_store_no_amount)

        result, debug = retriever.retrieve(
            coverage_code="A4200_1",
            insurer=Insurer.SAMSUNG
        )

        # NoAmountFoundResult 확인
        assert isinstance(result, NoAmountFoundResult)
        assert result.reason == "no_amount_bearing_evidence"

        # 모든 문서가 dropped
        assert debug.pass_1_count == 0
        assert len(debug.dropped_evidence) >= 1

    def test_no_documents_returns_no_amount(self):
        """문서 없으면 NoAmountFoundResult"""
        empty_store = MockDocumentStore({})
        retriever = EvidenceRetriever(empty_store)

        result, debug = retriever.retrieve(
            coverage_code="A4200_1",
            insurer=Insurer.SAMSUNG
        )

        assert isinstance(result, NoAmountFoundResult)
        assert result.reason == "no_documents_found"


# --- Test Case 3: DROP Rules ---

class TestDropRules:
    """
    강제 탈락 규칙 테스트

    DROP 조건:
    - 빈 텍스트
    - "약관 참조"만 있는 문단
    """

    def test_drops_empty_text(self, document_store_with_drop_candidates):
        """빈 텍스트 DROP"""
        retriever = EvidenceRetriever(document_store_with_drop_candidates)

        result, debug = retriever.retrieve(
            coverage_code="A4200_1",
            insurer=Insurer.SAMSUNG
        )

        # DROP된 evidence 확인
        drop_reasons = [d.reason for d in debug.dropped_evidence]
        assert DropReason.NO_CONTENT in drop_reasons

    def test_drops_reference_only(self, document_store_with_drop_candidates):
        """참조만 있는 문단 DROP"""
        retriever = EvidenceRetriever(document_store_with_drop_candidates)

        result, debug = retriever.retrieve(
            coverage_code="A4200_1",
            insurer=Insurer.SAMSUNG
        )

        # DROP된 evidence 확인
        drop_reasons = [d.reason for d in debug.dropped_evidence]
        assert DropReason.REFERENCE_ONLY in drop_reasons

    def test_successful_with_valid_amount(self, document_store_with_drop_candidates):
        """유효한 amount 문서로 성공"""
        retriever = EvidenceRetriever(document_store_with_drop_candidates)

        result, debug = retriever.retrieve(
            coverage_code="A4200_1",
            insurer=Insurer.SAMSUNG
        )

        # Amount 있는 문서로 성공
        assert isinstance(result, EvidenceSlots)
        assert result.has_amount()
        assert "3천만원" in result.amount.excerpt


# --- Test Case 4: Scoring ---

class TestEvidenceScoring:
    """
    Evidence 정렬 규칙 테스트

    우선순위:
    1. amount_presence
    2. confidence_level (약관 > 사업방법서)
    3. page (낮을수록 우선)
    """

    def test_yakgwan_prioritized_over_saeop(self, document_store_multiple_amounts):
        """약관이 사업방법서보다 우선"""
        retriever = EvidenceRetriever(document_store_multiple_amounts)

        result, debug = retriever.retrieve(
            coverage_code="A4200_1",
            insurer=Insurer.SAMSUNG
        )

        assert isinstance(result, EvidenceSlots)
        assert result.amount.source_doc == DocType.YAKGWAN  # 약관 우선
        assert result.amount.page == 45  # 약관 페이지

    def test_score_calculation(self):
        """점수 계산 검증"""
        slot = EvidenceSlot(
            purpose=EvidencePurpose.AMOUNT,
            source_doc=DocType.YAKGWAN,
            excerpt="암 진단시 5천만원 지급",
            page=45,
            retrieval_pass=RetrievalPass.PASS_1
        )

        score = calculate_evidence_score(slot, ["암", "진단", "지급"])

        assert score.amount_presence is True
        assert score.doc_priority == 0  # 약관
        assert score.page == 45


# --- Test Case 5: EvidenceSlots ---

class TestEvidenceSlots:
    """EvidenceSlots 클래스 테스트"""

    def test_has_amount(self):
        """has_amount() 동작"""
        slots = EvidenceSlots()
        assert slots.has_amount() is False

        slots.amount = EvidenceSlot(
            purpose=EvidencePurpose.AMOUNT,
            source_doc=DocType.YAKGWAN,
            excerpt="5천만원",
            retrieval_pass=RetrievalPass.PASS_1
        )
        assert slots.has_amount() is True

    def test_to_dict(self):
        """to_dict() 직렬화"""
        slots = EvidenceSlots(
            amount=EvidenceSlot(
                purpose=EvidencePurpose.AMOUNT,
                source_doc=DocType.YAKGWAN,
                excerpt="5천만원 지급",
                value="5천만원",
                page=45,
                retrieval_pass=RetrievalPass.PASS_1
            ),
            condition=EvidenceSlot(
                purpose=EvidencePurpose.CONDITION,
                source_doc=DocType.YAKGWAN,
                excerpt="90일 면책",
                page=46,
                retrieval_pass=RetrievalPass.PASS_2
            )
        )

        result = slots.to_dict()

        assert "amount" in result
        assert result["amount"]["value"] == "5천만원"
        assert result["amount"]["source_doc"] == "약관"
        assert "condition" in result
        assert "definition" not in result  # None이면 제외


# --- Test Case 6: RetrievalDebug ---

class TestRetrievalDebug:
    """RetrievalDebug 클래스 테스트"""

    def test_add_dropped(self):
        """탈락 evidence 기록"""
        debug = RetrievalDebug()
        debug.add_dropped(DropReason.NO_AMOUNT, "테스트 문장...")

        assert len(debug.dropped_evidence) == 1
        assert debug.dropped_evidence[0].reason == DropReason.NO_AMOUNT

    def test_to_dict(self):
        """to_dict() 직렬화"""
        debug = RetrievalDebug(
            pass_1_count=2,
            pass_2_count=1
        )
        debug.add_dropped(DropReason.NO_AMOUNT)

        result = debug.to_dict()

        assert result["retrieval_pass_1_count"] == 2
        assert result["retrieval_pass_2_count"] == 1
        assert len(result["dropped_evidence"]) == 1
        assert result["dropped_evidence"][0]["reason"] == "no_amount"


# --- Test Amount Patterns ---

class TestAmountPatterns:
    """금액 패턴 매칭 테스트"""

    @pytest.fixture
    def retriever(self):
        return EvidenceRetriever(MockDocumentStore({}))

    def test_extracts_manwon(self, retriever):
        """만원 패턴"""
        result = retriever._extract_amount("보험금 3000만원 지급")
        assert result is not None
        assert "3000만원" in result

    def test_extracts_percent(self, retriever):
        """퍼센트 패턴"""
        result = retriever._extract_amount("지급률 50% 적용")
        assert result is not None
        assert "50%" in result

    def test_extracts_won(self, retriever):
        """원 패턴"""
        result = retriever._extract_amount("일시금 50000000원")
        assert result is not None
        assert "50000000원" in result

    def test_no_amount(self, retriever):
        """금액 없음"""
        result = retriever._extract_amount("암이라 함은 악성신생물을 말합니다")
        assert result is None
