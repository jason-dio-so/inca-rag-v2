"""
Explain View Mapper - V2-6: Explain View / Boundary UX + Slot Rendering

BindingResult → ExplainViewResponse 매핑.

처리 흐름 (PIPELINE):
1. Compare Engine 결과 수신
2. BindingResult → ExplainView 매핑
3. Decision별 Reason Card 생성
4. Evidence Slot 탭 구성
5. Rule Trace 구성
6. 응답 반환

금지 사항:
- 설명 문장 생성(LLM) ❌
- decision_status 변조 ❌
- evidence 생략 ❌
- "사용자 친화적" 추론 추가 ❌
"""

from compare.decision_types import (
    BindingResult,
    BoundEvidence,
    CompareDecision,
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
from compare.types import Insurer


# --- Decision → Card Mapping (고정 규칙) ---

DECISION_CARD_CONFIG = {
    CompareDecision.DETERMINED: {
        "type": CardType.INFO,
        "title": "결과 확정",
        "message": "약관 근거에서 금액이 확인되었습니다",
    },
    CompareDecision.NO_AMOUNT: {
        "type": CardType.ERROR,
        "title": "금액 근거 부족",
        "message": "약관 및 사업방법서에서 지급 금액이 명시된 근거를 찾지 못했습니다",
    },
    CompareDecision.CONDITION_MISMATCH: {
        "type": CardType.WARNING,
        "title": "조건 충돌",
        "message": "금액은 확인되었으나 적용 조건 간 충돌이 감지되었습니다",
    },
    CompareDecision.DEFINITION_ONLY: {
        "type": CardType.INFO,
        "title": "정의만 존재",
        "message": "용어 정의는 확인되었으나 지급 금액 근거가 없습니다",
    },
    CompareDecision.INSUFFICIENT_EVIDENCE: {
        "type": CardType.ERROR,
        "title": "판단 불가",
        "message": "비교 판단에 필요한 근거가 충분하지 않습니다",
    },
}

DECISION_HEADLINE = {
    CompareDecision.DETERMINED: "비교 결과 확정",
    CompareDecision.NO_AMOUNT: "금액 근거 없음",
    CompareDecision.CONDITION_MISMATCH: "조건 충돌 감지",
    CompareDecision.DEFINITION_ONLY: "정의만 존재",
    CompareDecision.INSUFFICIENT_EVIDENCE: "판단 불가",
}


class ExplainViewMapper:
    """
    BindingResult → ExplainViewResponse 매퍼.

    Boundary UX 원칙:
    - 사실(evidence), 규칙(rule), 결론(decision)을 시각적으로 분리
    - 문서/페이지/발췌(source boundary)를 항상 함께 표시
    - "없음/불가"는 빈칸이 아니라 사유 카드로 표시
    """

    def map(self, binding_result: BindingResult) -> ExplainViewResponse:
        """
        BindingResult → ExplainViewResponse 매핑.

        Args:
            binding_result: V2-5 EvidenceBinder 결과

        Returns:
            ExplainViewResponse
        """
        decision = binding_result.decision

        # Step 1: Headline 생성
        headline = self._create_headline(decision)

        # Step 2: Reason Cards 생성
        reason_cards = self._create_reason_cards(binding_result)

        # Step 3: Evidence Tabs 구성
        evidence_tabs = self._create_evidence_tabs(binding_result)

        # Step 4: Rule Trace 구성
        rule_trace = self._create_rule_trace(binding_result)

        return ExplainViewResponse(
            decision=decision.value,
            headline=headline,
            reason_cards=reason_cards,
            evidence_tabs=evidence_tabs,
            rule_trace=rule_trace,
        )

    def map_multi_insurer(
        self,
        canonical_code: str,
        canonical_name: str,
        insurer_results: dict[Insurer, BindingResult]
    ) -> MultiInsurerExplainView:
        """
        다보험사 비교 매핑.

        보험사별 Explain View 카드 반복.
        동일 decision_status라도 사유/규칙은 다를 수 있음.
        """
        insurer_views = []

        for insurer, binding_result in insurer_results.items():
            explain_view = self.map(binding_result)
            insurer_views.append(InsurerExplainView(
                insurer=insurer.value,
                explain_view=explain_view,
            ))

        return MultiInsurerExplainView(
            canonical_coverage_code=canonical_code,
            canonical_coverage_name=canonical_name,
            insurer_views=tuple(insurer_views),
        )

    def _create_headline(self, decision: CompareDecision) -> str:
        """Headline 생성 (사실 기반)"""
        return DECISION_HEADLINE.get(decision, "결과 확인 필요")

    def _create_reason_cards(
        self,
        binding_result: BindingResult
    ) -> tuple[ReasonCard, ...]:
        """
        Reason Cards 생성.

        Decision별 카드 규칙:
        - DETERMINED: INFO
        - NO_AMOUNT: ERROR
        - CONDITION_MISMATCH: WARNING
        - DEFINITION_ONLY: INFO
        - INSUFFICIENT_EVIDENCE: ERROR
        """
        decision = binding_result.decision
        config = DECISION_CARD_CONFIG.get(decision)

        if not config:
            return ()

        # References 생성
        references = self._create_references(binding_result)

        card = ReasonCard(
            type=config["type"],
            title=config["title"],
            message=config["message"],
            decision=decision.value,
            references=references,
        )

        return (card,)

    def _create_references(
        self,
        binding_result: BindingResult
    ) -> tuple[EvidenceReference, ...]:
        """Evidence References 생성"""
        references = []

        for evidence in binding_result.bound_evidence:
            ref = EvidenceReference(
                doc_type=evidence.doc_type,
                doc_id=evidence.doc_id,
                page=evidence.page,
            )
            references.append(ref)

        return tuple(references)

    def _create_evidence_tabs(
        self,
        binding_result: BindingResult
    ) -> EvidenceTabs:
        """
        Evidence Tabs 구성.

        Slot Rendering 규칙:
        - 슬롯 간 내용 혼합 ❌
        - 금액 슬롯에 정의 문단 표시 ❌
        - 출처 없는 발췌 ❌
        """
        amount_items = []
        condition_items = []
        definition_items = []

        for evidence in binding_result.bound_evidence:
            if evidence.slot_type == "amount":
                item = AmountEvidenceItem(
                    value=binding_result.amount_value or "",
                    source_doc=evidence.doc_type,
                    page=evidence.page or 0,
                    excerpt=evidence.excerpt or "",
                    doc_id=evidence.doc_id,
                )
                amount_items.append(item)

            elif evidence.slot_type == "condition":
                # 조건 충돌 여부 확인
                has_conflict = (
                    binding_result.decision == CompareDecision.CONDITION_MISMATCH
                )
                item = ConditionEvidenceItem(
                    source_doc=evidence.doc_type,
                    excerpt=evidence.excerpt or "",
                    page=evidence.page,
                    doc_id=evidence.doc_id,
                    has_conflict=has_conflict,
                )
                condition_items.append(item)

            elif evidence.slot_type == "definition":
                item = DefinitionEvidenceItem(
                    source_doc=evidence.doc_type,
                    excerpt=evidence.excerpt or "",
                    page=evidence.page,
                    doc_id=evidence.doc_id,
                )
                definition_items.append(item)

        return EvidenceTabs(
            amount=tuple(amount_items),
            condition=tuple(condition_items),
            definition=tuple(definition_items),
        )

    def _create_rule_trace(
        self,
        binding_result: BindingResult
    ) -> RuleTrace:
        """
        Rule Trace 구성.

        규칙은 요약하지 않고 실행된 규칙 이름 그대로 노출.
        """
        # Applied rules
        applied_rules = tuple(
            rule.value for rule in binding_result.explanation.applied_rules
        )

        # Dropped evidence
        dropped_evidence = tuple(
            DroppedEvidenceInfo(id=eid, reason="dropped")
            for eid in binding_result.explanation.dropped_evidence_ids
        )

        return RuleTrace(
            applied_rules=applied_rules,
            dropped_evidence=dropped_evidence,
        )


# --- Convenience Functions ---

def create_explain_view(binding_result: BindingResult) -> ExplainViewResponse:
    """ExplainView 생성 (편의 함수)"""
    mapper = ExplainViewMapper()
    return mapper.map(binding_result)


def create_multi_insurer_explain_view(
    canonical_code: str,
    canonical_name: str,
    insurer_results: dict[Insurer, BindingResult]
) -> MultiInsurerExplainView:
    """다보험사 ExplainView 생성 (편의 함수)"""
    mapper = ExplainViewMapper()
    return mapper.map_multi_insurer(
        canonical_code=canonical_code,
        canonical_name=canonical_name,
        insurer_results=insurer_results,
    )
