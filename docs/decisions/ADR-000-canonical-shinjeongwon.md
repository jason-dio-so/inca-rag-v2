# ADR-000: 신정원 통일담보명/통일코드 Canonical 원칙

## Status
Accepted

## Context
보험 담보 비교 시스템에서 coverage_code의 일관성이 핵심이다.
보험사마다 동일 담보를 다르게 표기하며, LLM/embedding 추론은 오류를 유발한다.
신뢰할 수 있는 단일 기준(canonical source)이 필요하다.

## Decision
**신정원 통일담보명/통일코드를 유일한 canonical coverage 기준으로 채택한다.**

### 세부 규칙

1. **Canonical Truth 선언**
   - coverage_standard 테이블의 coverage_code만 유효
   - 보험사 고유 표기, LLM 추론 결과는 canonical이 아님

2. **Coverage Code 정합성**
   - coverage_standard에 없는 코드는 무효(invalid)
   - 무효 코드는 Compare/Slots/Evidence 계산에서 제외

3. **Alias 사용 제한**
   - coverage_alias는 보험사 표현 → 신정원 코드로 수렴시키는 보조 수단
   - alias 자체가 의미 기준이 될 수 없음
   - alias로 새로운 coverage_code 생성 금지

4. **적용 범위**
   - Backfill: canonical 검증 통과 시에만 태깅
   - Ingestion: 신정원 기준으로만 의미 고정
   - Compare: canonical 확정 chunk만 계산에 사용

5. **LLM 사용 제한**
   - LLM 허용: 담보명 후보 추출, 질의 해석 보조
   - LLM 금지: coverage_code 추론, 통일담보명 판단

6. **충돌 시 우선순위**
   1. 신정원 통일코드 (coverage_standard)
   2. coverage_name_map
   3. coverage_alias
   4. 보험사 문서 텍스트
   5. LLM 추론 결과

## Consequences

### 긍정적
- 담보 비교의 일관성 보장
- 보험사 확장 시에도 동일 원칙 적용
- 오류 발생 시 원인 추적 용이

### 부정적
- 신정원 코드에 없는 신규 담보는 즉시 지원 불가
- coverage_standard 테이블 유지보수 필요

### 메타 규칙
이 원칙은 불변 전제(axiom)이다.
이후 어떤 STEP, 기능, 개선에서도 본 규칙을 재논의하거나 완화하지 않는다.
