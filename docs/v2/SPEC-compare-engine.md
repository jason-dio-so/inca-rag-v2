# Compare Engine Specification

STEP V2-2: Canonical-Driven Compare Engine

---

## 1. 개요

Compare Engine은 "답을 만드는 기계"가 아니다.
있는 것을 그대로 보여주고, 없는 것은 없다고 말하는 기계다.

### 1.1 핵심 원칙

- Canonical coverage_code 단위 비교만 수행
- 보험사별 문서 차이를 흡수하지 않고, 차이가 드러나도록 설계
- 근거(evidence) 없는 값은 절대 출력하지 않음
- 일부 보험사 실패 시에도 Partial Failure로 비교 유지

---

## 2. 입력 규약 (강제)

### 2.1 입력 스키마

```json
{
  "canonical_coverage_code": "A4200_1",
  "insurers": ["SAMSUNG", "MERITZ"],
  "query_context": {
    "optional_slots": {}
  }
}
```

### 2.2 입력 규칙

| 규칙 | 설명 |
|------|------|
| ✅ canonical_code 필수 | 입력은 반드시 canonical_coverage_code로만 이루어진다 |
| ❌ coverage_name 문자열 입력 금지 | 담보명 문자열 직접 입력 불가 |
| ❌ alias 직접 입력 금지 | alias 텍스트를 입력으로 사용 불가 |

---

## 3. Compare 대상 범위

### 3.1 허용되는 데이터

- 약관 / 사업방법서 기반 authoritative evidence
- canonical_code로 resolve된 데이터만 허용

### 3.2 제외되는 데이터

| 제외 대상 | 이유 |
|-----------|------|
| canonical 미해결 데이터 | 의미 불확정 |
| 요약서 단독 근거 | non-authoritative |
| LLM 요약 결과 | truth 아님 |

---

## 4. 처리 흐름 (순서 고정)

```
1. canonical_coverage_code 수신
2. canonical 존재 확인 (없으면 hard fail)
3. insurers loop
4. 각 insurer별:
   ├─ canonical_code 기반 evidence 조회
   └─ evidence 존재 여부 판단
5. 결과 정렬 및 병합
6. partial failure 처리
7. 최종 response 생성
```

---

## 5. 보험사별 결과 상태

보험사 단위 결과는 **반드시 다음 중 하나**다:

### 5.1 Success

```json
{
  "status": "success",
  "value": {
    "amount": 50000000,
    "currency": "KRW",
    "max_count": 1
  },
  "evidence": {
    "doc_type": "약관",
    "doc_id": "SAMSUNG_CANCER_2024",
    "page": 45,
    "excerpt": "암 진단 확정시 5천만원 지급"
  }
}
```

### 5.2 Not Covered

```json
{
  "status": "not_covered",
  "reason": "coverage_not_found"
}
```

### 5.3 Unknown

```json
{
  "status": "unknown",
  "reason": "canonical_resolved_but_no_authoritative_evidence"
}
```

### 5.4 불변 규칙

- ❌ status 누락 금지
- ❌ 빈 객체 반환 금지

---

## 6. Partial Failure 원칙

### 6.1 동작

- A 보험사 성공, B 보험사 실패 시:
  - 전체 compare 실패 ❌
  - 부분 성공 유지 ✅

### 6.2 예시

```json
{
  "canonical_coverage_code": "A4200_1",
  "results": {
    "SAMSUNG": { "status": "success", ... },
    "MERITZ": { "status": "not_covered", ... }
  }
}
```

---

## 7. Source Boundary 원칙

근거 문서가 없는 값은:

- ❌ 추정
- ❌ 보정
- ❌ 평균

반드시 `unknown` 또는 `not_covered`로 표현한다.

---

## 8. V2-2 비교 항목 범위

### 8.1 허용 (정량 비교만)

| 항목 | 타입 | 설명 |
|------|------|------|
| amount | number | 보험금 금액 |
| max_count | integer | 지급 횟수 |
| duration_years | integer | 기간 (년) |
| duration_count | integer | 기간 (회) |

### 8.2 금지

| 항목 | 설명 | 처리 시점 |
|------|------|----------|
| 조건 해석 | 지급 조건 의미 해석 | V2-3 |
| subtype 판단 | 세부 유형 분류 | V2-3 |
| "더 유리함" 판단 | 비교 우위 판단 | 금지 |

---

## 9. LLM / Embedding 사용 금지

| 금지 행위 | 이유 |
|-----------|------|
| ❌ LLM으로 조건 요약 | ADR-001 위반 |
| ❌ LLM으로 누락값 보완 | Source Boundary 위반 |
| ❌ embedding으로 유사 담보 검색 | ADR-002 위반 |

**Compare Engine은 결정 트리 + 데이터 조회만으로 동작해야 한다.**

---

## 10. 테스트 시나리오

### 10.1 정상 비교

- 동일 canonical_code
- 2개 보험사 모두 evidence 존재
- 결과 나란히 출력

### 10.2 Partial Failure

- 삼성: canonical + evidence 있음
- 현대: canonical 있으나 evidence 없음
- 👉 삼성 출력 + 현대 not_covered

### 10.3 Hard Fail

- canonical_code 자체가 존재하지 않음
- 👉 compare 시작 ❌
- 👉 명시적 실패 반환 (CanonicalNotFoundError)

---

## 11. 코드 구조

```
compare/
├── __init__.py
├── types.py      # 입출력 타입 정의
└── engine.py     # CompareEngine 구현

tests/
└── test_compare_engine.py  # 테스트 시나리오

schema/
├── compare_input.yaml   # 입력 규약
└── compare_result.yaml  # 출력 규약
```

---

## 12. 사용 예시

```python
from compare.engine import CompareEngine
from compare.types import CompareInput, Insurer

# 엔진 초기화
engine = CompareEngine(
    canonical_store=canonical_store,
    evidence_store=evidence_store
)

# 입력 생성 (canonical_code 필수)
input = CompareInput(
    canonical_coverage_code="A4200_1",
    insurers=(Insurer.SAMSUNG, Insurer.MERITZ)
)

# 비교 수행
response = engine.compare(input)

# 결과 확인
for insurer, result in response.results.items():
    print(f"{insurer}: {result.status}")
```

---

## 13. 에러 처리

### 13.1 CanonicalNotFoundError

canonical_code 자체가 존재하지 않을 때 발생. Compare 시작 불가.

```python
try:
    response = engine.compare(input)
except CanonicalNotFoundError as e:
    # canonical_code가 존재하지 않음
    # 명시적 실패 처리
    pass
```

### 13.2 InvalidInputError

잘못된 입력 시 발생.

```python
try:
    input = CompareInput(
        canonical_coverage_code="",  # 빈 값
        insurers=()
    )
except ValueError:
    # 입력 검증 실패
    pass
```
