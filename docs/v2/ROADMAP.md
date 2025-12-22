# V2 Roadmap

## 단계 구분

### V2-0: Bootstrap ✅
**목표**: Repository 구조 및 헌법 문서화

**작업 범위**:
- 폴더 구조 생성
- README, ADR 문서 작성
- 헌법 원칙 명문화

**금지사항**:
- 코드 작성 금지
- DB 스키마 정의 금지

---

### V2-1: Canonical Coverage Data Layer ✅
**목표**: 모든 담보 의미의 유일한 출처(Single Source of Truth) 구축

**작업 범위**:
- canonical_coverage 스키마 정의 (신정원 통일코드 기준)
- coverage_alias 스키마 정의 (단방향 해석)
- alias → canonical resolve 경로 명세
- unresolved canonical 시 hard-fail 정책

**산출물**:
- `schema/canonical_coverage.yaml`
- `schema/coverage_alias.yaml`
- `docs/v2/SPEC-canonical-resolve.md`

**금지사항**:
- LLM으로 coverage_code 추론 금지
- Embedding으로 의미 판단 금지
- 새로운 coverage_code 임의 생성 금지
- canonical 미해결 시 추측/유추 금지

---

### V2-2: Canonical-Driven Compare Engine ✅
**목표**: Canonical coverage_code 단위 비교 엔진 구현

**작업 범위**:
- Compare Engine 입력이 canonical_code로만 이루어짐
- 보험사별 결과가 동일 조건에서 나란히 비교됨
- 일부 보험사 실패 시에도 Partial Failure로 비교 유지
- 근거(evidence) 없는 값은 출력되지 않음
- V2-2에서는 정량 비교만 허용 (금액, 횟수, 기간)

**산출물**:
- `schema/compare_input.yaml`
- `schema/compare_result.yaml`
- `compare/types.py`
- `compare/engine.py`
- `tests/test_compare_engine.py`
- `docs/v2/SPEC-compare-engine.md`

**금지사항**:
- LLM으로 조건 요약 금지
- LLM으로 누락값 보완 금지
- Embedding으로 유사 담보 검색 금지
- 조건 해석, subtype 판단, "더 유리함" 판단 금지 (V2-3에서 처리)

**DoD (완료 기준)**:
- Compare input이 canonical_code로 고정
- Partial failure 동작 확인
- Evidence 없는 값 출력 없음

---

### V2-3: Condition & Definition Compare Engine ✅
**목표**: 동일 canonical coverage에 대해 보험사별 정의/조건을 해석 없이 구조적으로 비교

**작업 범위**:
- 정의(Definition): 담보 의미 정의 문구
- 조건(Condition): 지급 조건/제한 문구
- Comparison Aspects: subtype_coverage, method_condition, boundary_condition, definition_scope
- 문서 원문 그대로 출력 (해석/요약 금지)

**산출물**:
- `schema/condition_compare_input.yaml`
- `schema/condition_compare_result.yaml`
- `compare/condition_types.py`
- `compare/condition_engine.py`
- `tests/test_condition_compare_engine.py`
- `docs/v2/SPEC-condition-compare.md`

**금지사항**:
- "포함된다/제외된다" 자동 판단 금지
- "유리/불리" 판단 금지
- 타 보험사 정의를 기준으로 보정 금지
- LLM 생성 문구를 사실처럼 사용 금지
- Embedding 전면 금지 (유사 문단 탐색에도 불가)

**DoD (완료 기준)**:
- definition/condition 비교 엔진 구현
- partial failure 정상 동작
- evidence 없는 정의 미출력
- LLM/embedding 의미 결정 개입 없음

---

### V2-4: Evidence Retrieval Refinement ✅
**목표**: 2-Pass Retrieval 구조로 비교 정확도 개선

**작업 범위**:
- PASS 1: Amount-centric Retrieval (금액/한도/지급률 우선)
- PASS 2: Context Completion Retrieval (조건/정의 보완)
- Evidence 목적 분리: AMOUNT, CONDITION, DEFINITION
- 강제 탈락 규칙 (DROP rules)
- Debug 정보 필수 포함

**산출물**:
- `compare/evidence_types.py`
- `compare/evidence_retriever.py`
- `schema/evidence_retrieval.yaml`
- `tests/test_evidence_retriever.py` (17 tests)

**금지사항**:
- amount 없이 비교 결과 생성 금지
- evidence 목적 미표기 금지
- PASS 2 단독 evidence 사용 금지
- 문서 출처 없는 요약 금지
- coverage_code 무시 금지
- hallucinated 금액 생성 금지

**DoD (완료 기준)**:
- PASS 1 / PASS 2 구조 구현 ✅
- amount-bearing evidence 우선 적용 ✅
- evidence 목적 슬롯 분리 ✅
- debug.retrieval 정보 노출 ✅
- 38 tests 통과 ✅

---

### V2-5: Evidence-to-Compare Binding ✅
**목표**: Evidence 슬롯 → Compare 결과 바인딩 규칙 고정

**작업 범위**:
- Evidence 슬롯 → Compare 결과 필드 바인딩
- 결정 규칙 명문화 (tie-breaker 포함)
- Explanation 구조 정의
- Partial Failure 사유 표준화

**산출물**:
- `compare/decision_types.py` - CompareDecision, DecisionRule, CompareExplanation
- `compare/evidence_binder.py` - EvidenceBinder with binding rules
- `schema/binding_result.yaml` - Binding 결과 스키마
- `tests/test_evidence_binder.py` (22 tests)

**핵심 구현**:
- CompareDecision: DETERMINED, NO_AMOUNT, CONDITION_MISMATCH, DEFINITION_ONLY, INSUFFICIENT_EVIDENCE
- Amount Binding: 최우선 (약관 > 사업방법서, page ASC)
- Condition Binding: amount 확정 후, 동일 문서 우선
- Definition Binding: 금액 변경 불가

**금지사항**:
- LLM 호출 금지
- embedding score 사용 금지
- "가장 그럴듯한" 선택 금지
- silent fallback 금지

**DoD (완료 기준)**:
- Evidence → Compare 결과가 규칙으로 고정됨 ✅
- 모든 BindingResult에 explanation 존재 ✅
- Partial Failure 상태 명확히 구분됨 ✅
- LLM/embedding 개입 없음 ✅
- 60 tests 통과 ✅

---

### V2-6: Explain View / Boundary UX + Slot Rendering ✅
**목표**: 비교 결과를 오해 없이, 경계(boundary)를 유지한 채, 일관된 구조로 노출

**작업 범위**:
- API 응답 스키마 확정
- Explain View 전용 응답 모델
- Evidence Slot 렌더링 규칙
- Partial Failure 카드 표준화
- 단일/다보험사 공통 레이아웃

**산출물**:
- `schema/explain_view.yaml` - Explain View 스키마
- `compare/explain_types.py` - ExplainViewResponse, ReasonCard, EvidenceTabs 등
- `compare/explain_view_mapper.py` - BindingResult → ExplainView 매퍼
- `tests/test_explain_view.py` (31 tests)

**핵심 구현**:
- Decision별 Reason Card: DETERMINED→INFO, NO_AMOUNT→ERROR, CONDITION_MISMATCH→WARNING
- Evidence Tabs: Amount, Condition, Definition 분리
- Rule Trace: 적용된 규칙 이름 그대로 노출
- Boundary UX: 사실/규칙/결론 시각적 분리

**금지사항**:
- 설명 문장 생성(LLM) 금지
- decision_status 변조 금지
- evidence 생략 금지
- "사용자 친화적" 추론 추가 금지

**DoD (완료 기준)**:
- Explain View 스키마 정의 ✅
- decision_status → Reason Card 매핑 ✅
- Evidence Slot 탭 렌더링 규칙 고정 ✅
- Rule Trace 노출 ✅
- Partial Failure 명확 표시 ✅
- 91 tests 통과 ✅

---

### V2-7: E2E Smoke & Golden Set ✅
**목표**: E2E 파이프라인 검증 및 회귀 방지 Golden Set 구축

**작업 범위**:
- E2E Smoke Test Cases (6 시나리오)
- Golden Set Regression Core (18 케이스)
- 다보험사 비교 검증
- Partial Failure 검증

**산출물**:
- `eval/e2e_smoke_cases.yaml` - Smoke 테스트 케이스
- `eval/golden_set_v2_7.json` - Golden Set 데이터
- `tests/test_e2e_smoke.py` - E2E 테스트 (36 tests)
- `tools/run_e2e_smoke.sh` - Smoke 실행 스크립트
- `tools/run_golden_eval.sh` - Golden Set 평가 스크립트

**핵심 구현**:
- Smoke 6 시나리오: 암진단비, 제자리암, 수술비, Query-only, 금액없음, 근거부족
- Golden Set: 18 케이스 (결정 유형별 3건+)
- Partial Failure Ratio: 61%
- 다보험사: 2사/3사 비교 검증

**금지사항**:
- 테스트 데이터에 실제 약관 내용 포함 금지
- LLM 기반 테스트 판정 금지
- 비결정적(non-deterministic) 테스트 금지

**DoD (완료 기준)**:
- Smoke 6+ 시나리오 PASS ✅
- Golden Set 18 케이스 PASS ✅
- 다보험사 비교 검증 ✅
- Partial Failure 검증 ✅
- 127 tests 통과 ✅

---

### V2-8: Ops Monitoring & Drift Detection ✅
**목표**: 운영 중 품질 변화 조기 감지 및 Silent Degradation 포착

**작업 범위**:
- Decision 분포 / Partial Failure 비율 모니터링
- Evidence 품질 / 출처 드리프트 감지
- Golden Set 결과 변화 감지
- CI/Nightly 자동 실행 및 리포트 생성

**산출물**:
- `metrics/decision_distribution.json` - 결정 분포 메트릭
- `metrics/partial_failure_rate.json` - Partial Failure 비율
- `metrics/evidence_quality.json` - Evidence 품질 메트릭
- `metrics/source_boundary.json` - 출처 분포 메트릭
- `metrics/golden_diff.json` - Golden Set 드리프트
- `metrics/ops_summary.json` - 운영 요약
- `tools/collect_metrics.py` - 메트릭 수집기
- `tools/detect_golden_drift.py` - 드리프트 감지기
- `tools/render_ops_report.py` - 리포트 렌더러
- `.github/workflows/nightly-ops.yml` - Nightly CI

**핵심 구현**:
- Decision Distribution: 5개 결정 유형별 분포
- Partial Failure Rate: 임계값 기반 경고 (50% WARNING, 70% ERROR)
- Evidence Quality: PASS1 성공률, dropped evidence 분포
- Source Boundary: 권위 문서 비율, 드리프트 감지
- Golden Drift: 결정 변화, 회귀(regression) 감지

**경고 레벨**:
- INFO: 정상 범위 (기록만)
- WARNING: 드리프트 임계 근접 (리뷰 권장)
- ERROR: 드리프트 임계 초과 (원인 분석 필요)

**금지사항**:
- Drift 감지를 근거로 자동 규칙 변경 ❌
- Golden 기대값 자동 수정 ❌
- LLM 요약으로 리포트 대체 ❌
- Partial Failure 은폐 ❌

**DoD (완료 기준)**:
- Decision/Partial Failure 지표 수집 ✅
- Evidence/Source Drift 감지 ✅
- Golden Diff 자동 비교 ✅
- Nightly CI 연동 ✅
- Ops Report 자동 생성 ✅
- 127 tests 통과 ✅

---

### V2-9: Embedding 재도입 (미착수)
**목표**: Canonical 고정 후 embedding 기반 검색 강화

**작업 범위**:
- coverage_code 고정된 chunk에만 embedding 적용
- Vector similarity를 보조 검색으로 사용

**금지사항**:
- Embedding 유사도로 coverage_code 판단 금지
- Canonical 미확정 문서에 embedding 적용 금지

---

## 핵심 원칙

> **Embedding은 V2-9 이전에 의미 결정에 사용하지 않는다.**

- V2-0 ~ V2-8: 의미 결정은 오직 신정원 canonical + coverage_alias + 규칙 기반 바인딩 + Boundary UX + Ops Monitoring
- V2-9: Embedding은 검색 효율화 목적으로만 사용
- Embedding이 canonical과 충돌 시, canonical 우선
