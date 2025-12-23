# V3-1: E2E Minimal Pipeline

## Overview

**목표**: 약관 2개(SAMSUNG, MERITZ)로 E2E 파이프라인을 연결하여 상담용 Chat 응답까지 생성

**Query**: `삼성화재와 메리츠화재의 암진단비를 비교해줘`

## Pipeline

```
PDF 약관 → Ingest → Chunks → V2 Compare Engine → Explain View → Chat Response
```

### 1. Ingestion (`tools/ingest_v3_1_sample.py`)

- PDF text extraction (page-based)
- Page-based chunk generation
- Pattern-based coverage_code detection (LLM 추론 금지)
- Output: `artifacts/v3_1_chunks.jsonl`

**Chunk Metadata**:
```json
{
  "chunk_id": "SAMSUNG_yakgwan_p002_0001",
  "insurer": "SAMSUNG",
  "doc_type": "약관",
  "source_file": "삼성_약관.pdf",
  "page_start": 2,
  "page_end": 2,
  "coverage_code": "A4200_1",
  "text": "...",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 2. V2 Compare Engine

- **EvidenceBinder**: Evidence 슬롯 → Compare 결과 바인딩
- **ExplainViewMapper**: BindingResult → ExplainView 매핑
- V2 엔진 수정 없이 사용

### 3. Chat Response (`chat/response_writer.py`)

- ExplainView → Natural Language 변환
- Partial Failure 명시적 표시
- Source Boundary (약관) 인용

**ChatResponse Structure**:
```python
@dataclass
class ChatResponse:
    message: str              # Natural language response
    has_partial_failure: bool # Partial failure flag
    insurers_compared: list[str]
    sources_cited: list[str]
```

## 실행 방법

```bash
# E2E Pipeline 실행
tools/run_v3_1_e2e.sh

# 테스트 실행
pytest tests/test_v3_1_e2e_minimal.py -v
```

## 산출물

| File | Description |
|------|-------------|
| `artifacts/v3_1_chunks.jsonl` | Ingested chunks with metadata |
| `artifacts/v3_1_compare_result.json` | Compare engine binding results |
| `artifacts/v3_1_explain_view.json` | Explain view for all insurers |
| `artifacts/v3_1_chat_response.json` | Final chat response |

## 핵심 규칙

### 허용

- LLM은 **문장 생성에만** 사용
- Pattern-based coverage_code 탐지 (후보 추출)
- **Canonical 검증 후** coverage_code 주입
- Partial Failure 명시적 표시
- 약관 원문 인용

### 금지

- LLM으로 coverage_code 추론 ❌
- Embedding으로 의미 결정 ❌
- **검증 없는 coverage_code 주입 ❌**
- Partial Failure 은폐 ❌
- "보험료" 언급 ❌
- 사실 아닌 내용 추가 ❌

## Canonical Validation

Pattern matching 결과는 반드시 `CANONICAL_COVERAGE_CODES`에 대해 검증됨:

```python
CANONICAL_COVERAGE_CODES = {
    "A4200_1",  # 암진단비(유사암제외)
    "A4103",    # 뇌졸중진단비
    ...
}

def validate_coverage_code(candidate_code):
    if candidate_code in CANONICAL_COVERAGE_CODES:
        return candidate_code
    return None  # 검증 실패 시 NULL
```

**검증 실패 시**: `coverage_code = None` (절대 검증되지 않은 코드 주입 금지)

## Sample Output

```markdown
## 암진단비 비교 결과

**삼성화재**
- 암진단비: 5천만원
  - 근거: "피보험자가 암으로 진단 확정된 경우 암진단비 5천만원을 지급합니다."
- 조건: 계약일로부터 90일 이후 진단

**메리츠화재**
- 암진단비: 3천만원
  - 근거: "피보험자가 암으로 진단 확정시 암진단비 3천만원을 지급합니다."
- 조건: 가입 후 90일 경과

---

### 비교 요약

| 보험사 | 암진단비 |
|--------|----------|
| 삼성화재 | 5천만원 |
| 메리츠화재 | 3천만원 |

📄 **근거 출처**: 삼성_약관.pdf 2페이지, 메리츠_약관.pdf 2페이지

---
*본 비교는 약관 원문에 기반하며, 실제 보장 내용은 개별 계약 조건에 따라 다를 수 있습니다.*
```

## DoD (완료 기준)

- [x] PDF → chunk 변환 구현
- [x] Pattern-based coverage_code 탐지
- [x] **Canonical 검증 후 coverage_code 주입**
- [x] V2 Compare Engine 연동
- [x] Chat Response 생성
- [x] Partial Failure 표시
- [x] Source Boundary 인용
- [x] 31 tests 통과 (158 total)

## Related Documents

- [ROADMAP](../v2/ROADMAP.md)
- [V2-6: Explain View](../v2/SPEC-explain-view.md)
- [CLAUDE.md](../../CLAUDE.md) - Execution Constitution
