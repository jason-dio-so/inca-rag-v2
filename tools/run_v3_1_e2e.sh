#!/usr/bin/env bash
# V3-1 E2E Execution Script
# STEP V3-1: E2E with 2 약관 PDFs → Chat Response
#
# Pipeline:
# 1. Ingest PDFs → chunks
# 2. Compare Engine (V2)
# 3. Explain View
# 4. Chat Response
#
# Fixed Query: "삼성화재와 메리츠화재의 암진단비를 비교해줘"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=================================================="
echo "  V3-1 E2E Pipeline"
echo "=================================================="
echo ""
echo "Query: 삼성화재와 메리츠화재의 암진단비를 비교해줘"
echo ""

# --- Step 1: Ingest ---
echo "[1/4] Ingesting 약관 PDFs..."
python tools/ingest_v3_1_sample.py
echo ""

# --- Step 2: Run Compare Engine ---
echo "[2/4] Running V2 Compare Engine..."
python -c "
import sys
sys.path.insert(0, '.')

from compare.types import Insurer
from compare.evidence_types import Evidence, EvidencePurpose, EvidenceSlot
from compare.evidence_binder import EvidenceBinder
from compare.decision_types import CompareDecision

# Fixed coverage code for 암진단비
COVERAGE_CODE = 'A4200_1'

# Load chunks from ingestion
import json
from pathlib import Path

chunks_file = Path('artifacts/v3_1_chunks.jsonl')
chunks = []
if chunks_file.exists():
    with open(chunks_file, 'r', encoding='utf-8') as f:
        for line in f:
            chunks.append(json.loads(line))

print(f'  Loaded {len(chunks)} chunks')

# Group by insurer
by_insurer = {}
for chunk in chunks:
    ins = chunk['insurer']
    if ins not in by_insurer:
        by_insurer[ins] = []
    by_insurer[ins].append(chunk)

print(f'  Insurers: {list(by_insurer.keys())}')

# Create evidence from chunks (simulate retrieval)
results = {}
for insurer, insurer_chunks in by_insurer.items():
    evidence_list = []

    for chunk in insurer_chunks:
        # Only use chunks with matching coverage_code
        if chunk.get('coverage_code') != COVERAGE_CODE:
            continue

        # Determine evidence purpose from text
        text = chunk.get('text', '')
        purpose = EvidencePurpose.DEFINITION

        # Simple heuristics for purpose detection
        if any(kw in text for kw in ['만원', '원을', '지급']):
            purpose = EvidencePurpose.AMOUNT
        elif any(kw in text for kw in ['조건', '경과', '이후']):
            purpose = EvidencePurpose.CONDITION

        evidence = Evidence(
            evidence_id=chunk['chunk_id'],
            coverage_code=COVERAGE_CODE,
            insurer=Insurer(insurer),
            source_doc=chunk['source_file'],
            doc_type=chunk['doc_type'],
            page=chunk['page_start'],
            excerpt=text[:500] if len(text) > 500 else text,
            purpose=purpose,
            retrieval_pass=1,
            confidence_score=0.9,
        )
        evidence_list.append(evidence)

    # Bind evidence to result
    binder = EvidenceBinder()
    if evidence_list:
        binding_result = binder.bind(evidence_list, COVERAGE_CODE, Insurer(insurer))
        results[insurer] = binding_result
        print(f'  {insurer}: {binding_result.decision.value}')
    else:
        print(f'  {insurer}: No matching evidence')

# Save intermediate result
import json
output_path = Path('artifacts/v3_1_compare_result.json')
output_path.parent.mkdir(parents=True, exist_ok=True)

# Convert to serializable format
serializable = {}
for ins, res in results.items():
    serializable[ins] = {
        'decision': res.decision.value,
        'coverage_code': res.coverage_code,
        'amount_slot': {
            'value': res.amount_slot.value if res.amount_slot else None,
            'source_doc': res.amount_slot.source_doc if res.amount_slot else None,
            'page': res.amount_slot.page if res.amount_slot else None,
            'excerpt': res.amount_slot.excerpt if res.amount_slot else None,
        } if res.amount_slot else None,
        'condition_slot': {
            'excerpt': res.condition_slot.excerpt if res.condition_slot else None,
            'source_doc': res.condition_slot.source_doc if res.condition_slot else None,
        } if res.condition_slot else None,
    }

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(serializable, f, ensure_ascii=False, indent=2)
print(f'  Saved: {output_path}')
"
echo ""

# --- Step 3: Generate Explain View ---
echo "[3/4] Generating Explain View..."
python -c "
import sys
sys.path.insert(0, '.')

import json
from pathlib import Path
from compare.explain_view_mapper import ExplainViewMapper
from compare.evidence_binder import BindingResult
from compare.decision_types import CompareDecision
from compare.evidence_types import Evidence, EvidenceSlot, EvidencePurpose
from compare.types import Insurer

# Load compare result
compare_result_path = Path('artifacts/v3_1_compare_result.json')
if not compare_result_path.exists():
    print('  ERROR: Compare result not found')
    sys.exit(1)

with open(compare_result_path, 'r', encoding='utf-8') as f:
    compare_data = json.load(f)

# Build ExplainView for each insurer
mapper = ExplainViewMapper()
insurer_views = []

for insurer, data in compare_data.items():
    # Reconstruct BindingResult
    amount_slot = None
    if data.get('amount_slot') and data['amount_slot'].get('value'):
        amount_slot = EvidenceSlot(
            slot_type=EvidencePurpose.AMOUNT,
            value=data['amount_slot']['value'],
            source_doc=data['amount_slot'].get('source_doc', ''),
            page=data['amount_slot'].get('page'),
            excerpt=data['amount_slot'].get('excerpt', ''),
        )

    condition_slot = None
    if data.get('condition_slot') and data['condition_slot'].get('excerpt'):
        condition_slot = EvidenceSlot(
            slot_type=EvidencePurpose.CONDITION,
            value=None,
            source_doc=data['condition_slot'].get('source_doc', ''),
            page=None,
            excerpt=data['condition_slot'].get('excerpt', ''),
        )

    binding_result = BindingResult(
        coverage_code=data['coverage_code'],
        insurer=Insurer(insurer),
        decision=CompareDecision(data['decision']),
        amount_slot=amount_slot,
        condition_slot=condition_slot,
        definition_slot=None,
        applied_rules=[],
        explanation=None,
    )

    # Map to ExplainView
    explain_view = mapper.map(binding_result)
    insurer_views.append({
        'insurer': insurer,
        'explain_view': {
            'decision': explain_view.decision,
            'reason_card': {
                'card_type': explain_view.reason_card.card_type.value,
                'title': explain_view.reason_card.title,
                'description': explain_view.reason_card.description,
            },
            'evidence_tabs': {
                'amount': [
                    {
                        'value': e.value,
                        'source_doc': e.source_doc,
                        'page': e.page,
                        'excerpt': e.excerpt,
                    }
                    for e in explain_view.evidence_tabs.amount
                ],
                'condition': [
                    {
                        'source_doc': e.source_doc,
                        'page': e.page,
                        'excerpt': e.excerpt,
                    }
                    for e in explain_view.evidence_tabs.condition
                ],
                'definition': [
                    {
                        'source_doc': e.source_doc,
                        'excerpt': e.excerpt,
                    }
                    for e in explain_view.evidence_tabs.definition
                ],
            },
            'rule_trace': explain_view.rule_trace,
        }
    })
    print(f'  {insurer}: {explain_view.reason_card.card_type.value} - {explain_view.reason_card.title}')

# Build multi-insurer view
multi_view = {
    'canonical_coverage_name': '암진단비',
    'canonical_coverage_code': 'A4200_1',
    'query': '삼성화재와 메리츠화재의 암진단비를 비교해줘',
    'insurer_views': insurer_views,
}

# Save explain view
output_path = Path('artifacts/v3_1_explain_view.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(multi_view, f, ensure_ascii=False, indent=2)
print(f'  Saved: {output_path}')
"
echo ""

# --- Step 4: Generate Chat Response ---
echo "[4/4] Generating Chat Response..."
python -c "
import sys
sys.path.insert(0, '.')

import json
from pathlib import Path
from chat.response_writer import write_response_from_explain_view

# Load explain view
explain_view_path = Path('artifacts/v3_1_explain_view.json')
if not explain_view_path.exists():
    print('  ERROR: Explain view not found')
    sys.exit(1)

with open(explain_view_path, 'r', encoding='utf-8') as f:
    explain_view = json.load(f)

# Generate chat response
response = write_response_from_explain_view(explain_view)

print('=' * 50)
print('  Chat Response')
print('=' * 50)
print()
print(response.message)
print()
print('=' * 50)
print(f'  Partial Failure: {response.has_partial_failure}')
print(f'  Insurers: {response.insurers_compared}')
print(f'  Sources: {len(response.sources_cited)} cited')
print('=' * 50)

# Save chat response
output_path = Path('artifacts/v3_1_chat_response.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump({
        'message': response.message,
        'has_partial_failure': response.has_partial_failure,
        'insurers_compared': response.insurers_compared,
        'sources_cited': response.sources_cited,
    }, f, ensure_ascii=False, indent=2)
print(f'Saved: {output_path}')
"

echo ""
echo "=================================================="
echo "  V3-1 E2E Complete"
echo "=================================================="
echo ""
echo "Artifacts:"
echo "  - artifacts/v3_1_chunks.jsonl"
echo "  - artifacts/v3_1_compare_result.json"
echo "  - artifacts/v3_1_explain_view.json"
echo "  - artifacts/v3_1_chat_response.json"
echo ""
