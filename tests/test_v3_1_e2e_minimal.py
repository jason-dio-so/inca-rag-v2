#!/usr/bin/env python3
"""
V3-1 E2E Minimal Tests
STEP V3-1: E2E with 2 약관 PDFs → Chat Response

Tests:
1. Ingestion produces chunks with correct metadata
2. Compare engine produces binding results
3. Explain view has correct structure
4. Chat response contains required elements
5. Partial failures are NOT hidden

PROHIBITED:
- LLM-based coverage_code inference in tests
- Non-deterministic assertions
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from compare.types import Insurer, DocType
from compare.decision_types import CompareDecision, DecisionRule
from compare.evidence_types import (
    EvidencePurpose,
    EvidenceSlot,
    EvidenceSlots,
    NoAmountFoundResult,
    RetrievalPass,
)
from compare.evidence_binder import EvidenceBinder
from compare.explain_types import CardType
from compare.explain_view_mapper import ExplainViewMapper
from chat.response_writer import (
    ChatResponse,
    write_response_from_explain_view,
    format_insurer_name,
    _write_single_from_dict,
)
from tools.ingest_v3_1_sample import (
    ChunkMeta,
    create_chunk,
    detect_coverage_code,
    validate_coverage_code,
    CANONICAL_COVERAGE_CODES,
    _mock_pdf_extraction,
)


# --- Test Fixtures ---

@pytest.fixture
def binder():
    """EvidenceBinder instance."""
    return EvidenceBinder()


@pytest.fixture
def mapper():
    """ExplainViewMapper instance."""
    return ExplainViewMapper()


@pytest.fixture
def sample_samsung_chunks():
    """Samsung sample chunks from mock PDF extraction."""
    pages = _mock_pdf_extraction(Path("삼성_약관.pdf"))
    chunks = []
    for i, (page_num, text) in enumerate(pages):
        chunk = create_chunk(
            insurer=Insurer.SAMSUNG,
            source_file=Path("삼성_약관.pdf"),
            page_num=page_num,
            text=text,
            chunk_index=i,
        )
        chunks.append(chunk)
    return chunks


@pytest.fixture
def sample_meritz_chunks():
    """Meritz sample chunks from mock PDF extraction."""
    pages = _mock_pdf_extraction(Path("메리츠_약관.pdf"))
    chunks = []
    for i, (page_num, text) in enumerate(pages):
        chunk = create_chunk(
            insurer=Insurer.MERITZ,
            source_file=Path("메리츠_약관.pdf"),
            page_num=page_num,
            text=text,
            chunk_index=100 + i,
        )
        chunks.append(chunk)
    return chunks


def create_evidence_slot(
    purpose: EvidencePurpose,
    value: str = None,
    excerpt: str = "",
    page: int = 1,
    doc_type: DocType = DocType.YAKGWAN,
) -> EvidenceSlot:
    """Create an evidence slot for testing."""
    return EvidenceSlot(
        purpose=purpose,
        source_doc=doc_type,
        excerpt=excerpt,
        value=value,
        page=page,
        doc_id=f"TEST_{purpose.value}",
        retrieval_pass=RetrievalPass.PASS_1,
    )


# --- Test: Ingestion ---

class TestIngestion:
    """Test PDF ingestion pipeline."""

    def test_mock_pdf_returns_pages(self):
        """Mock PDF extraction returns pages."""
        pages = _mock_pdf_extraction(Path("삼성_약관.pdf"))
        assert len(pages) > 0
        assert all(isinstance(p[0], int) for p in pages)
        assert all(isinstance(p[1], str) for p in pages)

    def test_create_chunk_has_required_fields(self, sample_samsung_chunks):
        """Chunks have all required metadata fields."""
        for chunk in sample_samsung_chunks:
            assert chunk.chunk_id is not None
            assert chunk.insurer == "SAMSUNG"
            assert chunk.doc_type == "약관"
            assert chunk.source_file is not None
            assert chunk.page_start > 0
            assert chunk.text is not None
            assert chunk.created_at is not None

    def test_chunk_id_format(self, sample_samsung_chunks):
        """Chunk ID follows expected format."""
        for chunk in sample_samsung_chunks:
            # Format: {INSURER}_yakgwan_p{PAGE:03d}_{INDEX:04d}
            assert chunk.chunk_id.startswith("SAMSUNG_yakgwan_p")
            parts = chunk.chunk_id.split("_")
            assert len(parts) >= 3

    def test_coverage_code_detection_cancer(self):
        """Detect cancer diagnosis coverage code."""
        text = "제2조 암진단비 피보험자가 암으로 진단된 경우"
        code = detect_coverage_code(text)
        assert code == "A4200_1"

    def test_coverage_code_detection_stroke(self):
        """Detect stroke coverage code."""
        text = "뇌졸중진단비를 지급합니다"
        code = detect_coverage_code(text)
        assert code == "A4103"

    def test_coverage_code_none_for_unmatched(self):
        """No coverage code for unmatched text."""
        text = "제1조 목적 이 약관은 보험계약에 관한 사항을 규정합니다."
        code = detect_coverage_code(text)
        assert code is None

    def test_chunks_detect_coverage_code(self, sample_samsung_chunks):
        """Some chunks should have detected coverage codes."""
        codes = [c.coverage_code for c in sample_samsung_chunks if c.coverage_code]
        assert len(codes) > 0
        assert "A4200_1" in codes

    def test_validate_coverage_code_valid(self):
        """Valid canonical codes pass validation."""
        assert validate_coverage_code("A4200_1") == "A4200_1"
        assert validate_coverage_code("A4103") == "A4103"

    def test_validate_coverage_code_invalid(self):
        """Invalid codes return None (not the candidate)."""
        assert validate_coverage_code("INVALID_CODE") is None
        assert validate_coverage_code("A9999") is None

    def test_validate_coverage_code_none(self):
        """None input returns None."""
        assert validate_coverage_code(None) is None

    def test_canonical_codes_match_schema(self):
        """CANONICAL_COVERAGE_CODES contains expected codes from schema."""
        # These must exist in schema/canonical_coverage.yaml
        assert "A4200_1" in CANONICAL_COVERAGE_CODES
        assert "A4103" in CANONICAL_COVERAGE_CODES


# --- Test: Compare Engine ---

class TestCompareEngine:
    """Test V2 compare engine integration."""

    def test_binder_creates_result_with_amount(self, binder):
        """Evidence binder creates binding result with amount."""
        slots = EvidenceSlots(
            amount=create_evidence_slot(
                purpose=EvidencePurpose.AMOUNT,
                value="5천만원",
                excerpt="암진단비 5천만원을 지급합니다.",
                page=2,
            )
        )
        result = binder.bind(slots)
        assert result is not None
        assert result.decision == CompareDecision.DETERMINED

    def test_binder_no_amount_without_amount_evidence(self, binder):
        """Binding without amount evidence yields NO_AMOUNT or DEFINITION_ONLY."""
        slots = EvidenceSlots(
            definition=create_evidence_slot(
                purpose=EvidencePurpose.DEFINITION,
                excerpt="암의 정의는 악성신생물을 말합니다.",
            )
        )
        result = binder.bind(slots)
        # Should be DEFINITION_ONLY when only definition exists
        assert result.decision == CompareDecision.DEFINITION_ONLY

    def test_binder_insufficient_evidence_empty(self, binder):
        """Empty slots yield INSUFFICIENT_EVIDENCE."""
        slots = EvidenceSlots()
        result = binder.bind(slots)
        assert result.decision == CompareDecision.INSUFFICIENT_EVIDENCE

    def test_binder_handles_no_amount_found_result(self, binder):
        """NoAmountFoundResult yields NO_AMOUNT."""
        result = binder.bind(NoAmountFoundResult(reason="no_amount_bearing_evidence"))
        assert result.decision == CompareDecision.NO_AMOUNT


# --- Test: Explain View ---

class TestExplainView:
    """Test Explain View generation."""

    def test_mapper_creates_explain_view(self, binder, mapper):
        """Mapper creates ExplainView from BindingResult."""
        slots = EvidenceSlots(
            amount=create_evidence_slot(
                purpose=EvidencePurpose.AMOUNT,
                value="5천만원",
                excerpt="암진단비 5천만원을 지급합니다.",
            )
        )
        binding_result = binder.bind(slots)
        view = mapper.map(binding_result)

        assert view is not None
        assert view.decision == "determined"
        assert len(view.reason_cards) > 0
        assert view.evidence_tabs is not None

    def test_determined_has_info_card(self, binder, mapper):
        """DETERMINED decision produces INFO card."""
        slots = EvidenceSlots(
            amount=create_evidence_slot(
                purpose=EvidencePurpose.AMOUNT,
                value="5천만원",
            )
        )
        binding_result = binder.bind(slots)
        view = mapper.map(binding_result)

        assert view.reason_cards[0].type == CardType.INFO

    def test_no_amount_has_error_card(self, binder, mapper):
        """NO_AMOUNT decision produces ERROR card."""
        result = binder.bind(NoAmountFoundResult(reason="test"))
        view = mapper.map(result)

        assert view.reason_cards[0].type == CardType.ERROR

    def test_evidence_tabs_populated(self, binder, mapper):
        """Evidence tabs are populated from slots."""
        slots = EvidenceSlots(
            amount=create_evidence_slot(
                purpose=EvidencePurpose.AMOUNT,
                value="5천만원",
                excerpt="암진단비 5천만원",
            )
        )
        binding_result = binder.bind(slots)
        view = mapper.map(binding_result)

        assert len(view.evidence_tabs.amount) > 0

    def test_rule_trace_included(self, binder, mapper):
        """Rule trace is included in view."""
        slots = EvidenceSlots(
            amount=create_evidence_slot(
                purpose=EvidencePurpose.AMOUNT,
                value="5천만원",
            )
        )
        binding_result = binder.bind(slots)
        view = mapper.map(binding_result)

        assert view.rule_trace is not None
        assert "amount_primary" in view.rule_trace.applied_rules


# --- Test: Chat Response ---

class TestChatResponse:
    """Test chat response generation."""

    def test_format_insurer_name_samsung(self):
        """Format Samsung insurer name."""
        assert format_insurer_name("SAMSUNG") == "삼성화재"

    def test_format_insurer_name_meritz(self):
        """Format Meritz insurer name."""
        assert format_insurer_name("MERITZ") == "메리츠화재"

    def test_single_determined_response(self):
        """Single insurer determined response."""
        ev = {
            "decision": "determined",
            "evidence_tabs": {
                "amount": [
                    {"value": "5천만원", "source_doc": "삼성_약관.pdf", "page": 2, "excerpt": "암진단비 5천만원"}
                ],
                "condition": [],
                "definition": [],
            },
        }
        msg, partial, sources = _write_single_from_dict("SAMSUNG", ev)

        assert "삼성화재" in msg
        assert "5천만원" in msg
        assert not partial
        assert len(sources) > 0

    def test_single_no_amount_response(self):
        """Single insurer no_amount response shows failure."""
        ev = {
            "decision": "no_amount",
            "evidence_tabs": {"amount": [], "condition": [], "definition": []},
        }
        msg, partial, sources = _write_single_from_dict("MERITZ", ev)

        assert "메리츠화재" in msg
        assert "금액 근거를 찾지 못했습니다" in msg
        assert partial  # Must indicate partial failure

    def test_multi_insurer_response(self):
        """Multi-insurer comparison response."""
        data = {
            "canonical_coverage_name": "암진단비",
            "insurer_views": [
                {
                    "insurer": "SAMSUNG",
                    "explain_view": {
                        "decision": "determined",
                        "evidence_tabs": {
                            "amount": [{"value": "5천만원", "source_doc": "삼성_약관.pdf", "page": 2}],
                            "condition": [],
                            "definition": [],
                        },
                    },
                },
                {
                    "insurer": "MERITZ",
                    "explain_view": {
                        "decision": "determined",
                        "evidence_tabs": {
                            "amount": [{"value": "3천만원", "source_doc": "메리츠_약관.pdf", "page": 2}],
                            "condition": [],
                            "definition": [],
                        },
                    },
                },
            ],
        }
        response = write_response_from_explain_view(data)

        assert "암진단비 비교 결과" in response.message
        assert "삼성화재" in response.message
        assert "메리츠화재" in response.message
        assert "5천만원" in response.message
        assert "3천만원" in response.message
        assert len(response.insurers_compared) == 2

    def test_partial_failure_not_hidden(self):
        """Partial failure is NOT hidden in response."""
        data = {
            "canonical_coverage_name": "암진단비",
            "insurer_views": [
                {
                    "insurer": "SAMSUNG",
                    "explain_view": {
                        "decision": "determined",
                        "evidence_tabs": {
                            "amount": [{"value": "5천만원", "source_doc": "삼성_약관.pdf", "page": 2}],
                            "condition": [],
                            "definition": [],
                        },
                    },
                },
                {
                    "insurer": "MERITZ",
                    "explain_view": {
                        "decision": "no_amount",
                        "evidence_tabs": {"amount": [], "condition": [], "definition": []},
                    },
                },
            ],
        }
        response = write_response_from_explain_view(data)

        # Partial failure MUST be visible
        assert response.has_partial_failure
        assert "주의" in response.message or "⚠️" in response.message
        # Meritz failure message must be present
        assert "금액 근거를 찾지 못했습니다" in response.message

    def test_source_boundary_cited(self):
        """Source boundary (약관) is cited."""
        data = {
            "canonical_coverage_name": "암진단비",
            "insurer_views": [
                {
                    "insurer": "SAMSUNG",
                    "explain_view": {
                        "decision": "determined",
                        "evidence_tabs": {
                            "amount": [
                                {
                                    "value": "5천만원",
                                    "source_doc": "삼성_약관.pdf",
                                    "page": 2,
                                    "excerpt": "암진단비 5천만원",
                                }
                            ],
                            "condition": [],
                            "definition": [],
                        },
                    },
                },
            ],
        }
        response = write_response_from_explain_view(data)

        # Source must be cited
        assert len(response.sources_cited) > 0
        assert "약관" in response.message.lower() or "페이지" in response.message

    def test_comparison_summary_table(self):
        """Comparison summary includes table."""
        data = {
            "canonical_coverage_name": "암진단비",
            "insurer_views": [
                {
                    "insurer": "SAMSUNG",
                    "explain_view": {
                        "decision": "determined",
                        "evidence_tabs": {
                            "amount": [{"value": "5천만원", "source_doc": "삼성_약관.pdf", "page": 2}],
                            "condition": [],
                            "definition": [],
                        },
                    },
                },
                {
                    "insurer": "MERITZ",
                    "explain_view": {
                        "decision": "determined",
                        "evidence_tabs": {
                            "amount": [{"value": "3천만원", "source_doc": "메리츠_약관.pdf", "page": 2}],
                            "condition": [],
                            "definition": [],
                        },
                    },
                },
            ],
        }
        response = write_response_from_explain_view(data)

        # Summary table markers
        assert "비교 요약" in response.message
        assert "|" in response.message  # Markdown table

    def test_disclaimer_present(self):
        """Disclaimer about 약관 원문 basis is present."""
        data = {
            "canonical_coverage_name": "암진단비",
            "insurer_views": [
                {
                    "insurer": "SAMSUNG",
                    "explain_view": {
                        "decision": "determined",
                        "evidence_tabs": {
                            "amount": [{"value": "5천만원"}],
                            "condition": [],
                            "definition": [],
                        },
                    },
                },
            ],
        }
        response = write_response_from_explain_view(data)

        # Disclaimer
        assert "약관 원문" in response.message


# --- Test: E2E Integration ---

class TestE2EIntegration:
    """End-to-end integration tests."""

    def test_full_pipeline_mock_data(
        self, sample_samsung_chunks, sample_meritz_chunks, binder, mapper
    ):
        """Full pipeline with mock data."""
        # 1. Chunks created from ingestion
        all_chunks = sample_samsung_chunks + sample_meritz_chunks
        assert len(all_chunks) > 0

        # 2. Filter chunks with coverage_code
        cancer_chunks = [c for c in all_chunks if c.coverage_code == "A4200_1"]
        assert len(cancer_chunks) > 0

        # 3. Create evidence slots per insurer
        samsung_chunks = [c for c in cancer_chunks if c.insurer == "SAMSUNG"]
        meritz_chunks = [c for c in cancer_chunks if c.insurer == "MERITZ"]

        # 4. Build slots and bind for each insurer
        results = {}
        for insurer, chunks in [("SAMSUNG", samsung_chunks), ("MERITZ", meritz_chunks)]:
            if chunks:
                chunk = chunks[0]  # Use first matching chunk
                slots = EvidenceSlots(
                    amount=EvidenceSlot(
                        purpose=EvidencePurpose.AMOUNT,
                        source_doc=DocType.YAKGWAN,
                        excerpt=chunk.text[:200],
                        value="5천만원" if insurer == "SAMSUNG" else "3천만원",
                        page=chunk.page_start,
                        doc_id=chunk.chunk_id,
                        retrieval_pass=RetrievalPass.PASS_1,
                    )
                )
                results[insurer] = binder.bind(slots)

        # 5. Create explain views
        views = []
        for insurer, result in results.items():
            view = mapper.map(result)
            views.append({
                "insurer": insurer,
                "explain_view": {
                    "decision": view.decision,
                    "evidence_tabs": {
                        "amount": [
                            {"value": e.value, "source_doc": str(e.source_doc)}
                            for e in view.evidence_tabs.amount
                        ],
                        "condition": [],
                        "definition": [],
                    },
                },
            })

        # 6. Generate chat response
        multi_view = {
            "canonical_coverage_name": "암진단비",
            "insurer_views": views,
        }
        response = write_response_from_explain_view(multi_view)

        # Assertions
        assert len(response.insurers_compared) >= 1
        assert "암진단비" in response.message

    def test_partial_failure_preserved_in_pipeline(self, binder, mapper):
        """Partial failure is preserved through the pipeline."""
        # Samsung: DETERMINED
        samsung_slots = EvidenceSlots(
            amount=create_evidence_slot(
                purpose=EvidencePurpose.AMOUNT,
                value="5천만원",
            )
        )
        samsung_result = binder.bind(samsung_slots)

        # Meritz: NO_AMOUNT
        meritz_result = binder.bind(NoAmountFoundResult(reason="no_amount"))

        # Map to explain views
        samsung_view = mapper.map(samsung_result)
        meritz_view = mapper.map(meritz_result)

        # Build multi-insurer view
        data = {
            "canonical_coverage_name": "암진단비",
            "insurer_views": [
                {
                    "insurer": "SAMSUNG",
                    "explain_view": {
                        "decision": samsung_view.decision,
                        "evidence_tabs": {
                            "amount": [{"value": "5천만원", "source_doc": "삼성_약관.pdf", "page": 2}],
                            "condition": [],
                            "definition": [],
                        },
                    },
                },
                {
                    "insurer": "MERITZ",
                    "explain_view": {
                        "decision": meritz_view.decision,
                        "evidence_tabs": {"amount": [], "condition": [], "definition": []},
                    },
                },
            ],
        }
        response = write_response_from_explain_view(data)

        # Both insurers preserved
        assert len(response.insurers_compared) == 2
        assert "SAMSUNG" in response.insurers_compared
        assert "MERITZ" in response.insurers_compared
        # Partial failure visible
        assert response.has_partial_failure


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
