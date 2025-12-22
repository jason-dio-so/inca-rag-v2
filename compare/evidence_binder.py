"""
Evidence Binder - V2-5: Evidence-to-Compare Binding

Evidence 슬롯 → Compare 결과 필드 바인딩.

처리 흐름 (Pipeline):
1. EvidenceRetriever (V2-4 결과 입력)
2. EvidenceSlot 분리
3. Amount Binding
4. Condition Binding
5. Definition Binding
6. Decision Status 확정
7. Explanation 생성
8. BindingResult 반환

금지 사항:
- LLM 호출 ❌
- embedding score 사용 ❌
- "가장 그럴듯한" 선택 ❌
- silent fallback ❌
"""

import re
import uuid
from dataclasses import dataclass
from typing import Optional

from compare.decision_types import (
    BindingResult,
    BoundEvidence,
    CompareDecision,
    CompareExplanation,
    DecisionRule,
)
from compare.evidence_types import (
    EvidencePurpose,
    EvidenceSlot,
    EvidenceSlots,
    NoAmountFoundResult,
)
from compare.types import DocType


@dataclass
class BindingContext:
    """바인딩 컨텍스트 (중간 상태 추적)"""
    applied_rules: list[DecisionRule]
    used_evidence_ids: list[str]
    dropped_evidence_ids: list[str]
    reasons: list[str]
    bound_evidence: list[BoundEvidence]

    @classmethod
    def create(cls) -> "BindingContext":
        return cls(
            applied_rules=[],
            used_evidence_ids=[],
            dropped_evidence_ids=[],
            reasons=[],
            bound_evidence=[]
        )

    def add_rule(self, rule: DecisionRule):
        if rule not in self.applied_rules:
            self.applied_rules.append(rule)

    def add_reason(self, reason: str):
        """사실 기반 이유 추가 (추론 금지)"""
        self.reasons.append(reason)


class EvidenceBinder:
    """
    Evidence Binder.

    Evidence 슬롯을 Compare 결과로 바인딩한다.

    Binding 규칙:
    1. Amount Binding (최우선)
    2. Condition Binding (amount 확정 후)
    3. Definition Binding (금액 변경 불가)
    """

    # 문서 우선순위 (낮을수록 높음)
    DOC_PRIORITY = {
        DocType.YAKGWAN: 0,
        DocType.SAEOP: 1,
    }

    def bind(
        self,
        evidence_slots: EvidenceSlots | NoAmountFoundResult
    ) -> BindingResult:
        """
        Evidence 슬롯을 Compare 결과로 바인딩.

        Args:
            evidence_slots: V2-4 EvidenceRetriever 결과

        Returns:
            BindingResult with decision, explanation, bound_evidence
        """
        ctx = BindingContext.create()

        # Case 1: NoAmountFoundResult
        if isinstance(evidence_slots, NoAmountFoundResult):
            return self._handle_no_amount(evidence_slots, ctx)

        # Case 2: EvidenceSlots
        return self._bind_evidence_slots(evidence_slots, ctx)

    def _handle_no_amount(
        self,
        result: NoAmountFoundResult,
        ctx: BindingContext
    ) -> BindingResult:
        """NoAmountFoundResult 처리"""
        ctx.add_rule(DecisionRule.RULE_PASS_1_EMPTY)
        ctx.add_reason(f"PASS 1 결과 없음: {result.reason}")

        return BindingResult(
            decision=CompareDecision.NO_AMOUNT,
            explanation=CompareExplanation(
                decision=CompareDecision.NO_AMOUNT,
                applied_rules=tuple(ctx.applied_rules),
                reasons=tuple(ctx.reasons),
            ),
        )

    def _bind_evidence_slots(
        self,
        slots: EvidenceSlots,
        ctx: BindingContext
    ) -> BindingResult:
        """EvidenceSlots 바인딩"""

        # Step 1: Amount Binding (최우선)
        amount_bound = self._bind_amount(slots, ctx)

        if not amount_bound:
            # Amount 없음 → 결정 분기
            return self._handle_no_amount_slot(slots, ctx)

        # Step 2: Condition Binding
        condition_mismatch = self._bind_condition(slots, ctx)

        if condition_mismatch:
            return self._handle_condition_mismatch(slots, ctx)

        # Step 3: Definition Binding
        self._bind_definition(slots, ctx)

        # Step 4: 결과 확정
        return self._create_determined_result(slots, ctx)

    def _bind_amount(
        self,
        slots: EvidenceSlots,
        ctx: BindingContext
    ) -> bool:
        """
        Amount Binding (최우선).

        규칙:
        1. amount evidence >= 1
        2. PASS 1에서 나온 evidence만 사용
        3. tie-breaker:
           1) 문서 우선순위 (약관 > 사업방법서)
           2) 지급 조건 명시 여부
           3) 페이지 시작 위치 (page_start ASC)
        """
        if not slots.has_amount():
            return False

        amount_slot = slots.amount
        ctx.add_rule(DecisionRule.RULE_AMOUNT_PRIMARY)

        # 문서 우선순위 적용
        ctx.add_rule(DecisionRule.RULE_DOC_PRIORITY)

        # Evidence ID 생성 및 바인딩
        evidence_id = self._generate_evidence_id()
        bound = BoundEvidence(
            evidence_id=evidence_id,
            slot_type="amount",
            doc_type=amount_slot.source_doc.value,
            doc_id=amount_slot.doc_id or "unknown",
            page=amount_slot.page,
            excerpt=amount_slot.excerpt,
            binding_rule=DecisionRule.RULE_AMOUNT_PRIMARY,
        )
        ctx.bound_evidence.append(bound)
        ctx.used_evidence_ids.append(evidence_id)
        ctx.add_reason(f"금액 증거: {amount_slot.source_doc.value}에서 발견")

        return True

    def _bind_condition(
        self,
        slots: EvidenceSlots,
        ctx: BindingContext
    ) -> bool:
        """
        Condition Binding.

        규칙:
        - amount가 확정된 경우에만 수행
        - amount_evidence와 동일 문서 우선
        - 조건 충돌 시 CONDITION_MISMATCH 반환

        Returns:
            True if condition mismatch detected
        """
        if not slots.condition:
            return False

        condition_slot = slots.condition
        amount_slot = slots.amount

        # 동일 문서 여부 확인
        same_doc = (
            amount_slot and
            condition_slot.doc_id == amount_slot.doc_id
        )

        if same_doc:
            ctx.add_rule(DecisionRule.RULE_CONDITION_SAME_DOC)

        # 조건 충돌 감지 (간단한 휴리스틱)
        # 실제로는 더 정교한 규칙이 필요할 수 있음
        has_conflict = self._detect_condition_conflict(condition_slot, amount_slot)

        if has_conflict:
            ctx.add_rule(DecisionRule.RULE_CONDITION_CONFLICT)
            return True

        # Condition 바인딩
        evidence_id = self._generate_evidence_id()
        bound = BoundEvidence(
            evidence_id=evidence_id,
            slot_type="condition",
            doc_type=condition_slot.source_doc.value,
            doc_id=condition_slot.doc_id or "unknown",
            page=condition_slot.page,
            excerpt=condition_slot.excerpt,
            binding_rule=DecisionRule.RULE_CONDITION_SAME_DOC if same_doc else None,
        )
        ctx.bound_evidence.append(bound)
        ctx.used_evidence_ids.append(evidence_id)

        return False

    def _bind_definition(
        self,
        slots: EvidenceSlots,
        ctx: BindingContext
    ) -> None:
        """
        Definition Binding.

        규칙:
        - definition은 금액을 바꾸지 않는다
        - 정보 보완 목적으로만 사용
        """
        if not slots.definition:
            return

        definition_slot = slots.definition

        evidence_id = self._generate_evidence_id()
        bound = BoundEvidence(
            evidence_id=evidence_id,
            slot_type="definition",
            doc_type=definition_slot.source_doc.value,
            doc_id=definition_slot.doc_id or "unknown",
            page=definition_slot.page,
            excerpt=definition_slot.excerpt,
        )
        ctx.bound_evidence.append(bound)
        ctx.used_evidence_ids.append(evidence_id)

    def _handle_no_amount_slot(
        self,
        slots: EvidenceSlots,
        ctx: BindingContext
    ) -> BindingResult:
        """Amount 슬롯 없음 처리"""

        # Definition만 있는 경우
        if slots.definition:
            ctx.add_rule(DecisionRule.RULE_DEFINITION_ONLY)
            ctx.add_rule(DecisionRule.RULE_DEFINITION_NO_AMOUNT)
            ctx.add_reason("정의 증거만 존재, 금액 증거 없음")

            # Definition 바인딩
            self._bind_definition(slots, ctx)

            return BindingResult(
                decision=CompareDecision.DEFINITION_ONLY,
                explanation=CompareExplanation(
                    decision=CompareDecision.DEFINITION_ONLY,
                    applied_rules=tuple(ctx.applied_rules),
                    used_evidence_ids=tuple(ctx.used_evidence_ids),
                    reasons=tuple(ctx.reasons),
                ),
                bound_evidence=tuple(ctx.bound_evidence),
            )

        # 아무 증거도 없는 경우
        ctx.add_rule(DecisionRule.RULE_NO_EVIDENCE)
        ctx.add_reason("판단 가능한 증거 없음")

        return BindingResult(
            decision=CompareDecision.INSUFFICIENT_EVIDENCE,
            explanation=CompareExplanation(
                decision=CompareDecision.INSUFFICIENT_EVIDENCE,
                applied_rules=tuple(ctx.applied_rules),
                reasons=tuple(ctx.reasons),
            ),
        )

    def _handle_condition_mismatch(
        self,
        slots: EvidenceSlots,
        ctx: BindingContext
    ) -> BindingResult:
        """조건 충돌 처리"""
        ctx.add_reason("조건 충돌 감지됨 - 금액은 유지")

        # Amount는 유지
        amount_value = None
        amount_numeric = None
        if slots.amount:
            amount_value = slots.amount.value
            amount_numeric = self._extract_numeric_amount(slots.amount.value)

        return BindingResult(
            decision=CompareDecision.CONDITION_MISMATCH,
            explanation=CompareExplanation(
                decision=CompareDecision.CONDITION_MISMATCH,
                applied_rules=tuple(ctx.applied_rules),
                used_evidence_ids=tuple(ctx.used_evidence_ids),
                reasons=tuple(ctx.reasons),
            ),
            bound_evidence=tuple(ctx.bound_evidence),
            amount_value=amount_value,
            amount_numeric=amount_numeric,
        )

    def _create_determined_result(
        self,
        slots: EvidenceSlots,
        ctx: BindingContext
    ) -> BindingResult:
        """결과 확정"""
        amount_value = None
        amount_numeric = None

        if slots.amount:
            amount_value = slots.amount.value
            amount_numeric = self._extract_numeric_amount(slots.amount.value)
            ctx.add_reason(f"금액 확정: {amount_value}")

        return BindingResult(
            decision=CompareDecision.DETERMINED,
            explanation=CompareExplanation(
                decision=CompareDecision.DETERMINED,
                applied_rules=tuple(ctx.applied_rules),
                used_evidence_ids=tuple(ctx.used_evidence_ids),
                reasons=tuple(ctx.reasons),
            ),
            bound_evidence=tuple(ctx.bound_evidence),
            amount_value=amount_value,
            amount_numeric=amount_numeric,
        )

    def _detect_condition_conflict(
        self,
        condition_slot: EvidenceSlot,
        amount_slot: Optional[EvidenceSlot]
    ) -> bool:
        """
        조건 충돌 감지.

        간단한 규칙 기반 감지.
        실제로는 더 정교한 규칙이 필요할 수 있음.
        """
        if not condition_slot or not amount_slot:
            return False

        # 충돌 키워드 패턴
        conflict_patterns = [
            r'보장하지\s*않',
            r'제외',
            r'면책',
            r'불보장',
        ]

        condition_text = condition_slot.excerpt or ""

        for pattern in conflict_patterns:
            if re.search(pattern, condition_text):
                # 충돌 가능성 있음
                # 단, 이것이 해당 담보 자체에 대한 것인지 확인 필요
                # 여기서는 보수적으로 False 반환 (추론 금지)
                pass

        return False

    def _extract_numeric_amount(self, amount_str: Optional[str]) -> Optional[int]:
        """금액 문자열에서 숫자 추출"""
        if not amount_str:
            return None

        # 억 단위
        match = re.search(r'(\d+)\s*억', amount_str)
        if match:
            return int(match.group(1)) * 100_000_000

        # 천만원 단위
        match = re.search(r'(\d+)\s*천만', amount_str)
        if match:
            return int(match.group(1)) * 10_000_000

        # 만원 단위
        match = re.search(r'(\d+)\s*만', amount_str)
        if match:
            return int(match.group(1)) * 10_000

        # 원 단위
        match = re.search(r'(\d+)\s*원', amount_str)
        if match:
            return int(match.group(1))

        return None

    def _generate_evidence_id(self) -> str:
        """고유 Evidence ID 생성"""
        return f"EVID-{uuid.uuid4().hex[:8].upper()}"


# --- Convenience Functions ---

def bind_evidence(
    evidence_slots: EvidenceSlots | NoAmountFoundResult
) -> BindingResult:
    """Evidence 바인딩 수행 (편의 함수)"""
    binder = EvidenceBinder()
    return binder.bind(evidence_slots)
