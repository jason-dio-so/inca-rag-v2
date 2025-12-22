# INCA-RAG v2

보험 약관 비교 RAG 시스템 v2

---

## v1 Repository 상태

**v1 repository (inca-rag)는 freeze 상태입니다.**

- v1에서는 신규 기능 개발을 하지 않음
- 버그 수정만 허용
- v2는 이 repository에서 완전히 분리되어 개발됨

---

## 헌법 (Constitution) 요약

### 1. 신정원 Canonical 원칙
- **신정원 통일담보명/통일코드만이 유일한 coverage 기준**
- 모든 alias, ingestion, compare, slot은 신정원 코드에 종속
- coverage_standard 테이블에 없는 코드는 무효

### 2. LLM 사용 제한 원칙
- LLM output은 항상 candidate이며, truth가 아님
- LLM은 coverage_code 추론/통일담보명 판단에 사용 불가
- 승인 없는 자동 반영 금지

### 3. Embedding 비권위 원칙
- Embedding은 semantic authority가 아님
- Canonical 의미 고정 이후에만 강화 가능
- 잘못된 embedding은 시스템 판단을 오염시킴

---

## PR 정책

> **이 repository에서 신정원 canonical을 위반하는 PR은 reject 대상입니다.**

위반 사례:
- coverage_standard에 없는 coverage_code 사용
- LLM으로 coverage_code 자동 생성
- Embedding 유사도로 담보 의미 결정

---

## 문서

- [V2 Roadmap](docs/v2/ROADMAP.md)
- [ADR-000: Canonical 신정원](docs/decisions/ADR-000-canonical-shinjeongwon.md)
- [ADR-001: LLM Controlled Usage](docs/decisions/ADR-001-llm-controlled-usage.md)
- [ADR-002: Embedding Non-Authoritative](docs/decisions/ADR-002-embedding-non-authoritative.md)
