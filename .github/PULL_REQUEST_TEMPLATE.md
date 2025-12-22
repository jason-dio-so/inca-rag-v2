## PR Summary

- **STEP / ADR:**
- **목적 (1문장):**

---

## Changed Scope

- [ ] Code
- [ ] Schema / Config
- [ ] Docs
- [ ] Tests

---

## Constitution Check (MANDATORY)

> All items must be checked before merge. "N/A" is not allowed — mark as checked if no violation.

- [ ] **ADR-000:** Shinjeongwon canonical only (coverage_code 정합)
- [ ] **ADR-001:** LLM not used for meaning/decision
- [ ] **ADR-002:** Embedding not used as semantic authority
- [ ] **ADR-003:** Partial Failure & Source Boundary preserved
- [ ] **Terminology:** `carrier` not used, `insurer` enforced
- [ ] **Easy Summary:** rule preserved (doc_type=상품요약서, subtype only)

---

## Meaning-in-Code Check

- [ ] coverage_code / domain / policy 하드코딩 없음
- [ ] 의미/정책 로직은 설정 또는 테이블에 존재
- [ ] 임시(fallback/best guess) 로직 없음

---

## Evidence & Boundary

- [ ] Authoritative source(약관/사업방법서) 없는 값 출력 없음
- [ ] unknown / not_covered fallback 유지
- [ ] 타 보험사 값 참조 없음

---

## Tests

- [ ] 기존 테스트 전부 통과
- [ ] 신규 테스트 추가 (필요 시)
- [ ] 출력 변화 발생 시 사유 명시:

---

## Reviewer Notes

- **헌법 관련 주의 포인트:**
- **리뷰 시 특별히 봐야 할 부분:**

---

### References

- [CLAUDE.md](../CLAUDE.md) — Execution Constitution
- [.github/PR_REVIEW_RULES.md](./PR_REVIEW_RULES.md) — PR Guardian Rules
- [ADR-000](../docs/decisions/ADR-000-canonical-shinjeongwon.md) — Canonical Shinjeongwon
- [ADR-001](../docs/decisions/ADR-001-llm-controlled-usage.md) — LLM Controlled Usage
- [ADR-002](../docs/decisions/ADR-002-embedding-non-authoritative.md) — Embedding Non-Authoritative
- [ADR-003](../docs/decisions/ADR-003-partial-failure-source-boundary.md) — Partial Failure & Source Boundary
