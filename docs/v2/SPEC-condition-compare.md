# Condition & Definition Compare Engine Specification

STEP V2-3: Condition & Definition Compare Engine

---

## 1. 개요

V2-3은 "누가 더 낫다"를 말하는 단계가 아니다.
각 보험사가 '어떻게 정의하고 있는지'를 판단 없이 그대로 드러내는 단계다.
한 줄이라도 해석이 들어가면, 그 구현은 폐기한다.

### 1.1 V2-3 vs V2-2

| 구분 | V2-2 | V2-3 |
|------|------|------|
| 비교 대상 | 정량 (금액, 횟수, 기간) | 정의, 조건, 경계 |
| 출력 | 숫자 값 | 원문 텍스트 |
| 판단 | 없음 | 없음 |

### 1.2 핵심 원칙

- 동일한 canonical coverage에 대해
- 보험사별 보장 조건 / 정의 / 경계 규칙을
- **해석 없이 구조적으로 비교 가능하게 한다**

---

## 2. 핵심 개념 정의

### 2.1 Definition vs Condition

| 유형 | 설명 | 예시 |
|------|------|------|
| Definition | 담보가 무엇을 의미하는지 | "유사암은 갑상선암, 기타피부암, 경계성종양, 제자리암을 말합니다" |
| Condition | 언제, 어떤 경우에, 어떤 제한 하에 지급되는지 | "계약일로부터 90일 이내 진단 시 보장하지 않습니다" |

### 2.2 Comparison Aspects

V2-3에서 다루는 비교 측면:

| Aspect | 설명 | 예시 |
|--------|------|------|
| `subtype_coverage` | 유사암/제자리암/경계성종양 보장 여부 | "유사암 제외", "기타피부암, 갑상선암 제외" |
| `method_condition` | 수술방법 포함 여부 | "다빈치 수술 포함", "로봇수술 별도 특약" |
| `boundary_condition` | 감액/지급률/조건부 보장 | "1년 이내 50% 감액", "90일 면책" |
| `definition_scope` | 정의 범위 | "최초 1회", "전이암 포함", "직접치료 목적" |

---

## 3. 입력 규약 (강제)

### 3.1 입력 스키마

```json
{
  "canonical_coverage_code": "A4200_1",
  "comparison_aspects": [
    "subtype_coverage",
    "boundary_condition"
  ],
  "insurers": ["SAMSUNG", "MERITZ"]
}
```

### 3.2 입력 규칙

| 규칙 | 설명 |
|------|------|
| ✅ canonical_coverage_code 필수 | 신정원 통일코드로만 입력 |
| ❌ 자연어 질의 금지 | "삼성이랑 메리츠 비교해줘" 불가 |
| ❌ coverage_name 문자열 금지 | 담보명 직접 입력 불가 |

---

## 4. 출력 규약

### 4.1 Success 결과

```json
{
  "status": "success",
  "definitions": {
    "subtype_coverage": "유사암(갑상선암, 기타피부암, 경계성종양, 제자리암)은 이 담보에서 보장하지 않습니다",
    "boundary_condition": "계약일로부터 90일 이내 암 진단 시 보장하지 않습니다"
  },
  "evidence": {
    "doc_type": "약관",
    "doc_id": "SAMSUNG_CANCER_2024",
    "page": 45,
    "excerpt": "제3조 보장내용..."
  }
}
```

### 4.2 Unknown 결과

```json
{
  "status": "unknown",
  "reason": "no_authoritative_definition"
}
```

또는:

```json
{
  "status": "unknown",
  "reason": "ambiguous_definition"
}
```

### 4.3 Not Covered 결과

```json
{
  "status": "not_covered",
  "reason": "coverage_not_found"
}
```

---

## 5. 처리 흐름 (순서 고정)

```
1. canonical_coverage_code 수신
2. canonical 존재 확인 (없으면 hard fail)
3. insurers loop
4. 보험사별:
   ├─ authoritative 문서(약관/사업방법서) 조회
   ├─ definition / condition 관련 문단 추출
   └─ 모호함 여부 확인
5. 추론 없이 구조화
6. partial failure 병합
7. response 생성
```

---

## 6. Subtype / Boundary 처리 규칙

### 6.1 Subtype (유사암 등)

| 허용 | 금지 |
|------|------|
| 문서에 명시된 정의 문구 추출 | "보장함/안함" 판단 |
| 원문 그대로 반환 | 해석/요약 |

모호하거나 복합 조건일 경우:

```json
{
  "status": "unknown",
  "reason": "ambiguous_definition"
}
```

### 6.2 Boundary (감액/지급률)

| 허용 | 금지 |
|------|------|
| 감액, 지급률, 조건 문구 그대로 노출 | "불리/유리" 판단 |
| 원문 유지 | 요약/정규화 (V2-4에서 처리) |

---

## 7. LLM / Embedding 사용 제한

### 7.1 LLM

| 허용 | 금지 |
|------|------|
| 문단 요약 (verbatim 중심) | 정의 해석 |
| 문장 정리 (의미 변경 금지) | 조건 비교 결과 생성 |
| | 보장 여부 판정 |

### 7.2 Embedding

**전면 금지**
- 유사 문단 탐색에도 사용 불가

---

## 8. 금지 사항 (위반 시 즉시 실패)

| 금지 행위 | 이유 |
|-----------|------|
| ❌ "포함된다 / 제외된다" 자동 판단 | 해석은 V2-3 범위 밖 |
| ❌ 타 보험사 정의를 기준으로 보정 | Source Boundary 위반 (ADR-003) |
| ❌ LLM 생성 문구를 사실처럼 사용 | LLM output ≠ truth (ADR-001) |
| ❌ 정의 없는 상태에서 summary 생성 | evidence 없는 출력 금지 (ADR-003) |

---

## 9. 테스트 시나리오

### 9.1 정상

- 삼성/메리츠 모두 정의 문구 존재
- 나란히 정의/조건 출력

### 9.2 Partial Failure

- 삼성: 정의 있음
- 현대: 담보 미제공
- 👉 삼성 success + 현대 not_covered

### 9.3 Ambiguous

- 삼성: 정의 있음
- 메리츠: 정의 모호함
- 👉 삼성 success + 메리츠 unknown (ambiguous_definition)

### 9.4 Boundary 케이스

- "감액", "지급률", "조건부" 키워드 포함
- 판단 없이 그대로 노출

---

## 10. 코드 구조

```
compare/
├── __init__.py
├── types.py              # V2-2 공통 타입
├── engine.py             # V2-2 정량 비교 엔진
├── condition_types.py    # V2-3 조건 비교 타입
└── condition_engine.py   # V2-3 조건 비교 엔진

tests/
├── test_compare_engine.py           # V2-2 테스트
└── test_condition_compare_engine.py # V2-3 테스트

schema/
├── compare_input.yaml            # V2-2 입력
├── compare_result.yaml           # V2-2 출력
├── condition_compare_input.yaml  # V2-3 입력
└── condition_compare_result.yaml # V2-3 출력
```

---

## 11. 사용 예시

```python
from compare.condition_engine import ConditionCompareEngine
from compare.condition_types import (
    ComparisonAspect,
    ConditionCompareInput,
)
from compare.types import Insurer

# 엔진 초기화
engine = ConditionCompareEngine(
    canonical_store=canonical_store,
    definition_store=definition_store
)

# 입력 생성
input = ConditionCompareInput(
    canonical_coverage_code="A4200_1",
    comparison_aspects=(
        ComparisonAspect.SUBTYPE_COVERAGE,
        ComparisonAspect.BOUNDARY_CONDITION
    ),
    insurers=(Insurer.SAMSUNG, Insurer.MERITZ)
)

# 비교 수행
response = engine.compare(input)

# 결과 확인 (판단 없이 원문 그대로)
for insurer, result in response.results.items():
    if result.status == "success":
        print(f"{insurer}: {result.definitions.subtype_coverage}")
```

---

## 12. 헌법 준수 확인

| ADR | 준수 여부 | 확인 사항 |
|-----|----------|----------|
| ADR-000 | ✅ | canonical_coverage_code로만 입력 |
| ADR-001 | ✅ | LLM으로 정의 해석/판단 금지 |
| ADR-002 | ✅ | Embedding 전면 금지 |
| ADR-003 | ✅ | Partial failure 정상 동작, evidence 없는 출력 없음 |
