# ADR-002: Embedding Non-Authoritative

## Status
Accepted

## Context
Embedding 기반 vector similarity는 "비슷해 보이는" 텍스트를 찾는 데 유용하다.
그러나 embedding은 의미의 정확한 동등성을 보장하지 않는다.
"암진단비"와 "유사암진단비"는 embedding상 유사하지만, 보험 도메인에서는 완전히 다른 담보다.
Embedding을 의미 판단에 사용하면 심각한 비교 오류가 발생한다.

## Decision
**Embedding은 semantic authority가 아니다.**

### 핵심 원칙

1. **의미 결정 권한 없음**
   - Embedding 유사도로 coverage_code 판단 금지
   - Embedding 유사도로 담보 동등성 판단 금지
   - 의미 결정은 오직 coverage_standard + coverage_alias

2. **Canonical 고정 후 사용**
   - coverage_code가 확정된 chunk에만 embedding 적용
   - Canonical 미확정 문서에 embedding 사용 금지
   - V2-4 단계 이전에는 embedding을 의미 결정에 사용하지 않음

3. **보조 역할만 허용**
   - 검색 효율화: 관련 chunk 빠르게 필터링
   - Fallback 검색: exact match 실패 시 보조
   - 결과 정렬: canonical 확정 후 유사도 기반 정렬

4. **충돌 시 처리**
   - Embedding 결과와 canonical이 충돌하면, canonical 우선
   - Embedding은 참고 정보일 뿐, 결정권 없음

## Consequences

### 긍정적
- 담보 의미 오판 방지
- "유사해 보이지만 다른" 담보 혼동 방지
- Canonical 기반 비교의 정확성 보장

### 부정적
- 초기 단계에서 embedding 활용 제한
- Vector search의 장점 일부 포기
- Exact match 기반 검색 의존

### 오염 경고
> 잘못된 embedding은 시스템 판단을 오염시킬 수 있다.

- Embedding 학습 데이터에 오류가 있으면, 유사도 계산 자체가 왜곡됨
- 한 번 오염된 판단은 연쇄적으로 다른 결과에 영향
- 따라서 canonical 고정 없이 embedding 의존은 위험
