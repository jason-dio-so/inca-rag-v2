"""
Evidence Retriever - V2-4: 2-Pass Retrieval Engine

핵심 원칙:
1. Canonical 우선 원칙: 모든 retrieval은 coverage_code 기준
2. Amount-bearing evidence 절대 우선
3. 2-Pass 구조: PASS 1 (Amount) → PASS 2 (Context Completion)

금지 사항:
- ❌ amount 없이 비교 결과 생성
- ❌ evidence 목적 미표기
- ❌ PASS 2 단독 evidence 사용
- ❌ 문서 출처 없는 요약
- ❌ coverage_code 무시
"""

import re
from dataclasses import dataclass
from typing import Optional, Protocol

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


@dataclass(frozen=True)
class RawEvidence:
    """원본 evidence 문서"""
    doc_type: DocType
    doc_id: str
    page: int
    text: str
    coverage_code: str


class DocumentStore(Protocol):
    """문서 저장소 인터페이스"""

    def get_documents_by_coverage_code(
        self,
        coverage_code: str,
        insurer: Insurer
    ) -> list[RawEvidence]:
        """coverage_code 기반 문서 조회"""
        ...


class EvidenceRetriever:
    """
    2-Pass Evidence Retrieval Engine

    PASS 1 — Amount-centric Retrieval:
    - 금액/한도/지급률이 명시된 문단 확보
    - 숫자 패턴 필수
    - coverage_code 일치 필수

    PASS 2 — Context Completion Retrieval:
    - PASS 1 evidence를 해석하는 데 필요한 정의/조건 보완
    - 단독 사용 불가
    """

    # 금액 패턴 (한국어)
    AMOUNT_PATTERNS = [
        r'\d+만원',
        r'\d+천만원',
        r'\d+억',
        r'\d+원',
        r'\d+%',
        r'지급액',
        r'보험금',
        r'한도',
    ]

    # 조건/예외 키워드
    CONDITION_KEYWORDS = [
        '면책',
        '제외',
        '예외',
        '불보장',
        '감액',
        '지급률',
        '조건',
        '이내',
        '이상',
    ]

    # 정의 키워드
    DEFINITION_KEYWORDS = [
        '정의',
        '범위',
        '의미',
        '말합니다',
        '라 함은',
        '이란',
    ]

    # DROP 패턴
    DROP_PATTERNS = [
        r'^[^0-9가-힣]*$',  # 내용 없음
        r'약관\s*참조',
        r'에\s*따른다$',
    ]

    def __init__(self, document_store: DocumentStore):
        self._document_store = document_store

    def retrieve(
        self,
        coverage_code: str,
        insurer: Insurer
    ) -> tuple[EvidenceSlots | NoAmountFoundResult, RetrievalDebug]:
        """
        2-Pass Evidence Retrieval 수행.

        Args:
            coverage_code: canonical coverage code (필수)
            insurer: 대상 보험사

        Returns:
            (EvidenceSlots, RetrievalDebug) if amount found
            (NoAmountFoundResult, RetrievalDebug) if no amount
        """
        debug = RetrievalDebug()

        # Step 1: 문서 조회 (coverage_code 기반)
        raw_evidences = self._document_store.get_documents_by_coverage_code(
            coverage_code=coverage_code,
            insurer=insurer
        )

        if not raw_evidences:
            return NoAmountFoundResult(
                reason="no_documents_found"
            ), debug

        # Step 2: PASS 1 — Amount-centric Retrieval
        amount_candidates = self._pass_1_amount_retrieval(
            raw_evidences, debug
        )

        # Step 3: Amount 없으면 NoAmountFoundResult
        if not amount_candidates:
            return NoAmountFoundResult(
                reason="no_amount_bearing_evidence"
            ), debug

        # Step 4: 최적 amount evidence 선택
        amount_slot = self._select_best_amount(amount_candidates)
        debug.pass_1_count = len(amount_candidates)

        # Step 5: PASS 2 — Context Completion Retrieval
        condition_slot, definition_slot = self._pass_2_context_retrieval(
            raw_evidences, amount_slot, debug
        )

        # Step 6: EvidenceSlots 구성
        slots = EvidenceSlots(
            amount=amount_slot,
            condition=condition_slot,
            definition=definition_slot
        )

        return slots, debug

    def _pass_1_amount_retrieval(
        self,
        raw_evidences: list[RawEvidence],
        debug: RetrievalDebug
    ) -> list[EvidenceSlot]:
        """
        PASS 1: Amount-centric Retrieval

        금액이 명시된 evidence만 선택.
        """
        amount_slots = []

        for raw in raw_evidences:
            # DROP 체크
            if self._should_drop(raw.text, debug):
                continue

            # Amount 패턴 매칭
            amount_value = self._extract_amount(raw.text)
            if amount_value:
                slot = EvidenceSlot(
                    purpose=EvidencePurpose.AMOUNT,
                    source_doc=raw.doc_type,
                    excerpt=raw.text,
                    value=amount_value,
                    page=raw.page,
                    doc_id=raw.doc_id,
                    retrieval_pass=RetrievalPass.PASS_1
                )
                amount_slots.append(slot)
            else:
                # Amount 없음 → DROP
                debug.add_dropped(DropReason.NO_AMOUNT, raw.text)

        return amount_slots

    def _pass_2_context_retrieval(
        self,
        raw_evidences: list[RawEvidence],
        amount_slot: EvidenceSlot,
        debug: RetrievalDebug
    ) -> tuple[Optional[EvidenceSlot], Optional[EvidenceSlot]]:
        """
        PASS 2: Context Completion Retrieval

        PASS 1 evidence를 보조하는 조건/정의 evidence 선택.
        단독 사용 불가 — 반드시 amount와 함께.
        """
        condition_slot = None
        definition_slot = None

        for raw in raw_evidences:
            # 이미 amount로 사용된 문단은 제외
            if raw.text == amount_slot.excerpt:
                continue

            # DROP 체크
            if self._should_drop(raw.text, debug):
                continue

            # Condition 매칭
            if not condition_slot and self._has_condition_keywords(raw.text):
                condition_slot = EvidenceSlot(
                    purpose=EvidencePurpose.CONDITION,
                    source_doc=raw.doc_type,
                    excerpt=raw.text,
                    page=raw.page,
                    doc_id=raw.doc_id,
                    retrieval_pass=RetrievalPass.PASS_2
                )
                debug.pass_2_count += 1

            # Definition 매칭
            if not definition_slot and self._has_definition_keywords(raw.text):
                definition_slot = EvidenceSlot(
                    purpose=EvidencePurpose.DEFINITION,
                    source_doc=raw.doc_type,
                    excerpt=raw.text,
                    page=raw.page,
                    doc_id=raw.doc_id,
                    retrieval_pass=RetrievalPass.PASS_2
                )
                debug.pass_2_count += 1

        return condition_slot, definition_slot

    def _extract_amount(self, text: str) -> Optional[str]:
        """
        텍스트에서 금액 추출.

        Returns:
            추출된 금액 문자열 (e.g., "3000만원", "50%")
            None if no amount found
        """
        for pattern in self.AMOUNT_PATTERNS:
            match = re.search(pattern, text)
            if match:
                # 주변 컨텍스트 포함 추출
                start = max(0, match.start() - 10)
                end = min(len(text), match.end() + 10)
                return text[start:end].strip()
        return None

    def _has_condition_keywords(self, text: str) -> bool:
        """조건/예외 키워드 포함 여부"""
        return any(kw in text for kw in self.CONDITION_KEYWORDS)

    def _has_definition_keywords(self, text: str) -> bool:
        """정의 키워드 포함 여부"""
        return any(kw in text for kw in self.DEFINITION_KEYWORDS)

    def _should_drop(self, text: str, debug: RetrievalDebug) -> bool:
        """
        강제 탈락 규칙 체크.

        DROP 조건:
        - 담보명만 반복되고 내용 없는 문단
        - "~에 따른다", "약관 참조"만 있는 문단
        """
        # 빈 텍스트
        if not text or len(text.strip()) < 10:
            debug.add_dropped(DropReason.NO_CONTENT, text)
            return True

        # DROP 패턴 매칭
        for pattern in self.DROP_PATTERNS:
            if re.search(pattern, text):
                debug.add_dropped(DropReason.REFERENCE_ONLY, text)
                return True

        return False

    def _select_best_amount(
        self,
        candidates: list[EvidenceSlot]
    ) -> EvidenceSlot:
        """
        최적 amount evidence 선택.

        정렬 기준:
        1. confidence_level: 약관 > 사업방법서
        2. page: 낮을수록 우선 (본문 우선)
        """
        def score(slot: EvidenceSlot) -> tuple:
            doc_priority = {
                DocType.YAKGWAN: 0,
                DocType.SAEOP: 1,
            }
            return (
                doc_priority.get(slot.source_doc, 99),
                slot.page or 999
            )

        return min(candidates, key=score)


# --- Scoring Utility ---

@dataclass
class EvidenceScore:
    """Evidence 점수 (정렬용)"""
    amount_presence: bool
    doc_priority: int  # 약관=0, 사업방법서=1
    page: int
    keyword_density: float = 0.0

    def as_tuple(self) -> tuple:
        """정렬용 tuple (낮을수록 우선)"""
        return (
            0 if self.amount_presence else 1,
            self.doc_priority,
            self.page,
            -self.keyword_density  # 높을수록 우선
        )


def calculate_evidence_score(
    slot: EvidenceSlot,
    keywords: list[str]
) -> EvidenceScore:
    """Evidence 점수 계산"""
    doc_priority = {
        DocType.YAKGWAN: 0,
        DocType.SAEOP: 1,
    }

    keyword_count = sum(
        1 for kw in keywords
        if kw in slot.excerpt
    )
    keyword_density = keyword_count / max(len(slot.excerpt.split()), 1)

    return EvidenceScore(
        amount_presence=slot.purpose == EvidencePurpose.AMOUNT,
        doc_priority=doc_priority.get(slot.source_doc, 99),
        page=slot.page or 999,
        keyword_density=keyword_density
    )
