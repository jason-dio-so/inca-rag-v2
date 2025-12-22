# CLAUDE.md — Insurance Compare RAG v2 Execution Constitution

This document defines **non-negotiable execution rules** for any LLM
(Claude, Claude Code, Cursor, Copilot, etc.)
working inside this repository.

This is NOT a design document.
This is an **execution constitution**.

If an instruction conflicts with this file,
**this file always wins.**

---

## 0. Absolute Ground Truth (Axiom)

### 0.1 Canonical Coverage Truth

- **Shinjeongwon (신정원) unified coverage code is the ONLY canonical truth.**
- `coverage_code` in this system MUST:
  - Exist in the Shinjeongwon standard table
  - Map 1:1 to a single unified coverage meaning
- Insurer wording, document text, aliases, or LLM outputs
  **can NEVER be canonical truth.**

If canonical validation fails:
- Compare ❌
- Slots ❌
- Subtype 판단 ❌
- Evidence 판단 ❌

---

## 1. Role of the LLM (Strictly Limited)

### 1.1 Allowed

LLM may ONLY:
- Extract candidate keywords from user queries
- Suggest **unapproved** coverage aliases (human review required)
- Reformat / summarize **already-authoritative evidence verbatim**
- Explain results **without adding new facts**

### 1.2 Forbidden (Hard Stop)

LLM must NEVER:
- Decide or generate `coverage_code`
- Modify canonical meaning
- Infer coverage inclusion/exclusion
- Fill missing data
- Normalize conditions
- Compare "which is better"
- Use embedding similarity as truth

If any of the above is required,
**STOP and ask the user.**

---

## 2. Canonical-First System Rule

- Every pipeline stage follows:

```
Canonical → Evidence → Compare → Explain
```

- If canonical is not resolved:
  - Do NOT fallback
  - Do NOT guess
  - Do NOT continue

Silence or explicit failure is the correct behavior.

---

## 3. Partial Failure is NORMAL

- Insurer-level failure ≠ system failure
- Results MUST preserve insurer granularity

Allowed:
```json
{
  "SAMSUNG": { "status": "success" },
  "MERITZ": { "status": "unknown" }
}
```

Forbidden:
- Dropping successful insurers
- Auto-completing missing insurers
- Returning a single merged answer

This rule is defined in ADR-003 and is NOT overridable.

---

## 4. Source Boundary (Non-Negotiable)

### 4.1 Authoritative Sources ONLY

Authoritative:
- 약관
- 사업방법서

Non-authoritative (reference only):
- 상품요약서
- 가입설계서
- Easy summary
- LLM output
- Embeddings

If no authoritative source exists:
- ❌ No inference
- ❌ No compensation
- ✅ Return `unknown` or `not_covered`

---

## 5. No Meaning in Code

- Code implements flow, not meaning
- All meaning/policy MUST live in:
  - Tables
  - YAML / config
- Hardcoded meaning (if/else, dicts, constants) is forbidden

Rule changes must be possible without code changes.

---

## 6. Compare Engine Scope Control

- V2-2: Quantitative comparison ONLY
- V2-3: Definition / condition extraction ONLY
- No "better / worse" judgment
- No normalization unless explicitly instructed (V2-4+)

If tempted to "help the user understand":
**STOP — that is an LLM violation.**

---

## 7. Easy Summary Handling (Fixed Rule)

- Easy summary documents:
  - `doc_type` = 상품요약서
  - `meta.subtype` = easy
- NEVER create a separate doc_type
- Applies to ALL insurers

Violation = system inconsistency.

---

## 8. Git & Reporting Discipline

Every task MUST include:
- Code changes (if applicable)
- Config / table changes (if applicable)
- Documentation updates
- Explicit commit hash
- Clear before/after behavior

Vague completion reports are not acceptable.

---

## 9. Session Start Rule (Critical)

On every new session:
1. Read this file FIRST
2. Assume NOTHING not written here
3. If unsure → ask before acting

---

## Final Rule

If you are about to:
- Infer
- Guess
- Normalize
- Smooth
- Fill gaps
- "Improve UX" by assumption

**STOP.**
That action violates this constitution.

---

## Related Documents

For PR-time enforcement rules, see `.github/PR_REVIEW_RULES.md`.
