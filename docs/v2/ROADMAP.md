# V2 Roadmap

## 단계 구분

### V2-0: Bootstrap (현재)
**목표**: Repository 구조 및 헌법 문서화

**작업 범위**:
- 폴더 구조 생성
- README, ADR 문서 작성
- 헌법 원칙 명문화

**금지사항**:
- 코드 작성 금지
- DB 스키마 정의 금지

---

### V2-1: Ingestion Semantic Fixing
**목표**: 문서 적재 시 coverage_code 태깅 정확도 향상

**작업 범위**:
- coverage_alias 기반 태깅 로직 강화
- 신정원 canonical 검증 적용

**금지사항**:
- LLM으로 coverage_code 추론 금지
- Embedding으로 의미 판단 금지
- 새로운 coverage_code 임의 생성 금지

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
