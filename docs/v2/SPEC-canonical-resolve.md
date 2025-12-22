# Canonical Resolve Path Specification

STEP V2-1: alias → canonical 해석 경로 명세

---

## 1. 개요

모든 담보 표현은 canonical_coverage.coverage_code로 해석되어야 한다.
해석 실패 시, 시스템은 **침묵하거나 추측하지 않고 명시적으로 실패**한다.

---

## 2. Resolve 함수 명세

### 2.1 함수 시그니처

```python
def resolve_canonical(
    alias_text: str,
    insurer: str | None = None,
) -> ResolveResult:
    """
    alias 텍스트를 canonical coverage_code로 해석한다.

    Args:
        alias_text: 문서/질의에서 추출된 담보 표현
        insurer: 보험사 코드 (선택, 있으면 우선 매칭)

    Returns:
        ResolveResult: 해석 결과

    Raises:
        CanonicalNotFoundError: canonical 해석 불가 시
    """
```

### 2.2 ResolveResult 구조

```python
@dataclass
class ResolveResult:
    canonical_code: str          # 신정원 통일코드
    canonical_name: str          # 신정원 공식 담보명
    matched_alias: str           # 매칭된 alias 원문
    confidence: Literal["high", "medium", "low"]
    source: Literal["exact", "normalized", "insurer_specific"]
```

### 2.3 CanonicalNotFoundError

```python
class CanonicalNotFoundError(Exception):
    """canonical 해석 불가 시 발생하는 예외"""

    def __init__(self, alias_text: str, reason: str):
        self.alias_text = alias_text
        self.reason = reason
        super().__init__(f"Cannot resolve '{alias_text}': {reason}")
```

---

## 3. Resolve 알고리즘

### 3.1 처리 순서 (순서 변경 금지)

```
1. 입력 정규화
   └─ alias_text → normalized (소문자, 공백 정리)

2. Exact Match (approved=true만)
   └─ coverage_alias WHERE alias_text_normalized = ? AND approved = true
   └─ 매칭 시 → canonical_code 반환

3. Insurer-Specific Match (insurer 파라미터 있을 때)
   └─ coverage_alias WHERE alias_text_normalized = ? AND insurer = ? AND approved = true
   └─ 매칭 시 → canonical_code 반환

4. 실패 처리
   └─ CanonicalNotFoundError 발생
   └─ 절대로 추측/유추/fallback 하지 않음
```

### 3.2 의사 코드

```python
def resolve_canonical(alias_text: str, insurer: str | None = None) -> ResolveResult:
    normalized = normalize_alias(alias_text)

    # Step 1: Exact match
    result = db.query("""
        SELECT ca.canonical_code, ca.confidence, cc.coverage_name_ko
        FROM coverage_alias ca
        JOIN canonical_coverage cc ON ca.canonical_code = cc.coverage_code
        WHERE ca.alias_text_normalized = %s
          AND ca.approved = true
        ORDER BY ca.confidence DESC
        LIMIT 1
    """, [normalized])

    if result:
        return ResolveResult(
            canonical_code=result.canonical_code,
            canonical_name=result.coverage_name_ko,
            matched_alias=alias_text,
            confidence=result.confidence,
            source="exact"
        )

    # Step 2: Insurer-specific match
    if insurer:
        result = db.query("""
            SELECT ca.canonical_code, ca.confidence, cc.coverage_name_ko
            FROM coverage_alias ca
            JOIN canonical_coverage cc ON ca.canonical_code = cc.coverage_code
            WHERE ca.alias_text_normalized = %s
              AND ca.insurer = %s
              AND ca.approved = true
            LIMIT 1
        """, [normalized, insurer])

        if result:
            return ResolveResult(
                canonical_code=result.canonical_code,
                canonical_name=result.coverage_name_ko,
                matched_alias=alias_text,
                confidence=result.confidence,
                source="insurer_specific"
            )

    # Step 3: Hard fail - 추측/유추/fallback 금지
    raise CanonicalNotFoundError(
        alias_text=alias_text,
        reason="No approved alias mapping found"
    )
```

---

## 4. Ingestion Flow에서의 사용

```python
def ingest_coverage_chunk(chunk: DocumentChunk) -> IngestResult:
    """문서 청크에서 담보 정보 추출 및 저장"""

    # 1. 담보명 추출 (string level only)
    coverage_text = extract_coverage_name(chunk.content)

    if not coverage_text:
        return IngestResult(status="skipped", reason="no coverage name found")

    # 2. Canonical resolve (hard fail on error)
    try:
        resolved = resolve_canonical(
            alias_text=coverage_text,
            insurer=chunk.insurer
        )
    except CanonicalNotFoundError as e:
        # ❌ 저장 금지
        # ❌ 임시 코드 생성 금지
        # ✅ 실패로 기록
        return IngestResult(
            status="failed",
            reason=f"canonical_not_found: {e.reason}",
            unresolved_alias=coverage_text
        )

    # 3. Canonical 확정된 경우만 저장
    save_chunk_with_coverage(chunk, resolved.canonical_code)
    return IngestResult(status="success", canonical_code=resolved.canonical_code)
```

---

## 5. Query/Compare Flow에서의 사용

```python
def compare_coverages(query: str, insurers: list[str]) -> CompareResult:
    """담보 비교 요청 처리"""

    # 1. 질의에서 담보 키워드 추출
    coverage_keywords = extract_coverage_keywords(query)

    if not coverage_keywords:
        return CompareResult(status="error", message="담보명을 찾을 수 없습니다")

    # 2. 각 키워드를 canonical로 해석
    canonical_codes = []
    for keyword in coverage_keywords:
        try:
            resolved = resolve_canonical(keyword)
            canonical_codes.append(resolved.canonical_code)
        except CanonicalNotFoundError:
            # ❌ 추측 금지
            # ❌ 유사 담보 제안 금지
            # ✅ 명시적 실패
            return CompareResult(
                status="error",
                message=f"'{keyword}'에 대한 담보를 찾을 수 없습니다. 정확한 담보명을 입력해주세요."
            )

    # 3. Canonical 확정된 경우만 비교 진행
    return execute_comparison(canonical_codes, insurers)
```

---

## 6. 금지 사항 (Hard Rules)

| 금지 행위 | 이유 |
|-----------|------|
| ❌ LLM으로 canonical_code 추론 | ADR-001 위반 |
| ❌ Embedding 유사도로 fallback | ADR-002 위반 |
| ❌ approved=false alias 사용 | 미검증 데이터 |
| ❌ 임시 코드 생성 | canonical 오염 |
| ❌ "가장 유사한" 담보 추천 | 추측 금지 |

---

## 7. 에러 처리 정책

### 7.1 Ingestion 실패 시
- 해당 청크는 저장하지 않음
- `unresolved_alias` 로그에 기록
- 수동 검토 대기열에 추가

### 7.2 Query 실패 시
- 사용자에게 명확한 에러 메시지 반환
- "비교 불가" 상태로 응답
- 어떤 결과도 반환하지 않음

### 7.3 로그 형식

```json
{
  "event": "canonical_resolve_failed",
  "alias_text": "암진단특약",
  "insurer": "MERITZ",
  "reason": "No approved alias mapping found",
  "timestamp": "2025-12-22T12:00:00Z",
  "context": "ingestion"
}
```

---

## 8. 검증 시나리오

### 8.1 정상 케이스
```
Input:  alias_text="암진단비(유사암 제외)", insurer="SAMSUNG"
Output: ResolveResult(canonical_code="A4200_1", ...)
```

### 8.2 실패 케이스
```
Input:  alias_text="가상의담보명", insurer="SAMSUNG"
Output: CanonicalNotFoundError("No approved alias mapping found")
```

### 8.3 미승인 alias 케이스
```
# DB에 alias 존재하나 approved=false
Input:  alias_text="암진단특약", insurer="MERITZ"
Output: CanonicalNotFoundError("No approved alias mapping found")
```
