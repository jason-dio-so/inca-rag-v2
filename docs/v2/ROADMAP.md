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

### V2-4: Embedding 재도입
**목표**: Canonical 고정 후 embedding 기반 검색 강화

**작업 범위**:
- coverage_code 고정된 chunk에만 embedding 적용
- Vector similarity를 보조 검색으로 사용

**금지사항**:
- Embedding 유사도로 coverage_code 판단 금지
- Canonical 미확정 문서에 embedding 적용 금지

---

## 핵심 원칙

> **Embedding은 V2-4 이전에 의미 결정에 사용하지 않는다.**

- V2-0 ~ V2-3: 의미 결정은 오직 신정원 canonical + coverage_alias
- V2-4: Embedding은 검색 효율화 목적으로만 사용
- Embedding이 canonical과 충돌 시, canonical 우선
