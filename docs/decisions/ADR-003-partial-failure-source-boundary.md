# ADR-003: Partial Failure & Source Boundary

## Status
Accepted

## Context

보험 비교 시스템에서 가장 위험한 실패는 다음이다:

- 일부 보험사 데이터가 없는데도
- 시스템이 이를 추론·보정·묵살하여
- 사용자가 "모두 비교된 것처럼" 오인하게 만드는 경우

이는 기술 문제가 아니라 **신뢰 붕괴 문제**다.

V2-2에서 Compare Engine은 이미 다음을 구현했다:
- canonical 기반 비교
- 보험사별 partial failure 허용
- evidence 없는 값 미출력

본 ADR은 이 구현된 원칙을 헌법으로 고정한다.

---

## Decision

### 1. Partial Failure Principle

**보험사 단위 비교에서 일부 보험사의 실패는 전체 비교 실패로 승격되지 않는다.**

#### 규칙

A 보험사: `success`
B 보험사: `not_covered` / `unknown`

👉 결과는 반드시 다음 형태를 유지한다:

```json
{
  "canonical_coverage_code": "A4200_1",
  "results": {
    "SAMSUNG": { "status": "success", "value": {...}, "evidence": {...} },
    "MERITZ": { "status": "not_covered", "reason": "coverage_not_found" }
  }
}
```

#### 금지 사항

| 금지 | 이유 |
|------|------|
| ❌ 전체 failure 반환 | 성공한 보험사 정보 손실 |
| ❌ 성공 보험사 결과 삭제 | 사용자 판단 정보 박탈 |
| ❌ 실패 보험사 결과 생략 | 실패를 숨기는 것은 거짓말 |

---

### 2. Source Boundary Principle

**Authoritative source가 없는 정보는 시스템의 지식 경계 밖(out of boundary)이다.**

#### Authoritative Source (권위 있는 출처)

| 문서 유형 | 권위 |
|-----------|------|
| 약관 | ✅ Authoritative |
| 사업방법서 | ✅ Authoritative |

#### Non-Authoritative (참고 전용)

| 문서/출처 | 권위 |
|-----------|------|
| 상품요약서 | ❌ 참고만 |
| 가입설계서 | ❌ 참고만 |
| LLM 요약 | ❌ 참고만 |
| Embedding similarity | ❌ 참고만 |

---

### 3. Boundary Violation 처리 규칙

Authoritative evidence가 없을 경우:

| 금지 행위 | 이유 |
|-----------|------|
| ❌ 추정 | 시스템이 모르는 것을 아는 척 |
| ❌ 평균 | 타 보험사 기준으로 왜곡 |
| ❌ "보통은" | 일반화는 특정 보험사 정보가 아님 |
| ❌ 타 보험사 값 복사 | 다른 보험사 ≠ 해당 보험사 |
| ❌ LLM 보정 | LLM 출력은 truth가 아님 |

#### 허용되는 유일한 응답

```json
{ "status": "unknown", "reason": "canonical_resolved_but_no_authoritative_evidence" }
```

```json
{ "status": "not_covered", "reason": "coverage_not_found" }
```

---

## Rationale

### 왜 Partial Failure를 정상 상태로 정의하는가?

1. **현실 반영**: 모든 보험사가 모든 담보를 제공하지 않음
2. **정보 보존**: 성공한 비교 결과는 그 자체로 가치 있음
3. **투명성**: 실패를 숨기지 않고 명시적으로 표현

### 왜 Source Boundary를 엄격히 적용하는가?

1. **법적 책임**: 보험금 비교는 계약 결정에 영향
2. **추론 위험**: 잘못된 정보는 잘못된 결정으로 이어짐
3. **신뢰 유지**: "모른다"고 말하는 시스템이 더 신뢰할 수 있음

---

## Consequences

### 긍정적

- 사용자가 어떤 정보가 확실하고 불확실한지 명확히 알 수 있음
- 일부 보험사 실패로 전체 비교가 무너지지 않음
- 시스템 신뢰성 장기 유지

### 부정적

- 불완전한 비교 결과가 노출될 수 있음
- "모든 보험사 비교 완료" 메시지를 보낼 수 없는 경우 발생
- UX 상 "unknown" 상태 처리 필요

### 적용 범위

이 ADR은 다음 모든 계층에 상위 규칙으로 적용된다:

| 계층 | 적용 |
|------|------|
| Compare Engine | ✅ 이미 적용됨 |
| API response layer | ✅ 필수 적용 |
| UI 표현 | ✅ 필수 적용 |
| LLM 설명 계층 (future) | ✅ 필수 적용 |

**이 ADR을 위반하는 컴포넌트는 버그가 아니라 헌법 위반이다.**

---

## Examples

### GOOD: Partial Failure 올바른 처리

```json
{
  "canonical_coverage_code": "A4200_1",
  "canonical_coverage_name": "암진단비(유사암제외)",
  "results": {
    "SAMSUNG": {
      "status": "success",
      "value": { "amount": 50000000, "currency": "KRW" },
      "evidence": { "doc_type": "약관", "doc_id": "SAMSUNG_CANCER_2024", "page": 45 }
    },
    "HYUNDAI": {
      "status": "not_covered",
      "reason": "coverage_not_found"
    }
  },
  "summary": {
    "total_insurers": 2,
    "success_count": 1,
    "not_covered_count": 1,
    "unknown_count": 0
  }
}
```

### BAD: 전체 실패로 처리

```json
{
  "status": "error",
  "message": "일부 보험사 비교 실패로 결과를 제공할 수 없습니다"
}
```

❌ 삼성 결과가 있음에도 전체 실패 처리 — **ADR-003 위반**

---

### GOOD: Source Boundary 올바른 처리

```json
{
  "MERITZ": {
    "status": "unknown",
    "reason": "canonical_resolved_but_no_authoritative_evidence"
  }
}
```

### BAD: 추정값 제공

```json
{
  "MERITZ": {
    "status": "success",
    "value": { "amount": 40000000 },
    "evidence": null,
    "note": "삼성 기준으로 추정"
  }
}
```

❌ evidence 없이 값 제공, 추정 사용 — **ADR-003 위반**

---

### BAD: LLM 보정

```json
{
  "MERITZ": {
    "status": "success",
    "value": { "amount": 35000000 },
    "evidence": { "source": "LLM 추론", "confidence": 0.85 }
  }
}
```

❌ LLM 출력을 authoritative evidence로 사용 — **ADR-003 위반**

---

## Meta Rule

> 이 ADR은 "기능 설명"이 아니다.
> 시스템이 절대 넘지 말아야 할 신뢰의 경계선이다.

이후 어떤 STEP, 기능, UX 개선에서도:
- Partial Failure를 전체 실패로 승격 금지
- Source Boundary 외부 정보를 truth로 취급 금지

위반 시 해당 구현은 즉시 철회되어야 한다.
