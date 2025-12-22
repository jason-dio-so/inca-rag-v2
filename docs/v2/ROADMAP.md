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

### V2-2: Product / Plan 구조 도입
**목표**: 보험사-상품-플랜 계층 구조 완성

**작업 범위**:
- product, product_plan 테이블 활용
- 플랜별 문서 분리
- 성별/나이 기반 플랜 자동 선택

**금지사항**:
- 기존 canonical 구조 변경 금지
- 플랜을 coverage_code 판단에 사용 금지

---

### V2-3: LLM Controlled Extraction
**목표**: LLM을 활용한 금액/조건 추출 (controlled)

**작업 범위**:
- 약관 텍스트에서 보장금액 추출
- 지급조건/면책사항 추출
- **human-in-the-loop 검증 필수**

**금지사항**:
- LLM으로 coverage_code 결정 금지
- 승인 없는 자동 DB 반영 금지
- LLM 출력을 truth로 취급 금지

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
