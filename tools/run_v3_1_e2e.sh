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

# Check for --demo flag
DEMO_FLAG=""
if [[ "$1" == "--demo" ]]; then
    DEMO_FLAG="--demo"
    echo "(Running in DEMO mode with mock data)"
    echo ""
fi

# --- Step 1: Ingest ---
echo "[1/4] Ingesting 약관 PDFs..."
python tools/ingest_v3_1_sample.py $DEMO_FLAG
echo ""

# --- Step 2: Run Compare Engine ---
echo "[2/4] Running V2 Compare Engine..."
python -c "
import sys
import json
import re
from pathlib import Path
sys.path.insert(0, '.')

from compare.types import Insurer, DocType
from compare.evidence_types import EvidencePurpose, EvidenceSlot, EvidenceSlots, RetrievalPass
from compare.evidence_binder import EvidenceBinder
from compare.decision_types import CompareDecision

# Fixed coverage code for 암진단비
COVERAGE_CODE = 'A4200_1'

# Load chunks from ingestion
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

# Extract amount from text
def extract_amount(text):
    match = re.search(r'(\d+천만원|\d+만원)', text)
    return match.group(1) if match else None

# Process each insurer
binder = EvidenceBinder()
results = {}

for insurer, insurer_chunks in by_insurer.items():
    # Filter chunks with matching coverage_code
    matching = [c for c in insurer_chunks if c.get('coverage_code') == COVERAGE_CODE]

    if not matching:
        print(f'  {insurer}: No matching evidence')
        continue

    # Build EvidenceSlots from chunks
    amount_slot = None
    condition_slot = None
    definition_slot = None

    for chunk in matching:
        text = chunk.get('text', '')
        page = chunk['page_start']
        source = chunk['source_file']

        # Extract amount if present
        amount = extract_amount(text)
        if amount and not amount_slot:
            amount_slot = EvidenceSlot(
                purpose=EvidencePurpose.AMOUNT,
                source_doc=DocType.YAKGWAN,
                excerpt=text[:200],
                value=amount,
                page=page,
                doc_id=chunk['chunk_id'],
                retrieval_pass=RetrievalPass.PASS_1,
            )

        # Check for condition
        if any(kw in text for kw in ['조건', '경과', '이후', '90일']) and not condition_slot:
            condition_slot = EvidenceSlot(
                purpose=EvidencePurpose.CONDITION,
                source_doc=DocType.YAKGWAN,
                excerpt=text[:200],
                page=page,
                doc_id=chunk['chunk_id'],
                retrieval_pass=RetrievalPass.PASS_2,
            )

    # Create slots and bind
    slots = EvidenceSlots(
        amount=amount_slot,
        condition=condition_slot,
        definition=definition_slot,
    )

    result = binder.bind(slots)
    results[insurer] = result
    print(f'  {insurer}: {result.decision.value}')

# Save intermediate result
output_path = Path('artifacts/v3_1_compare_result.json')
output_path.parent.mkdir(parents=True, exist_ok=True)

serializable = {}
for ins, res in results.items():
    # Get bound evidence details
    amount_info = None
    condition_info = None
    for be in res.bound_evidence:
        if be.slot_type == 'amount':
            amount_info = {
                'value': res.amount_value,
                'source_doc': be.doc_id,
                'page': be.page,
                'excerpt': be.excerpt,
            }
        elif be.slot_type == 'condition':
            condition_info = {
                'excerpt': be.excerpt,
                'source_doc': be.doc_id,
            }

    serializable[ins] = {
        'decision': res.decision.value,
        'amount_value': res.amount_value,
        'amount_slot': amount_info,
        'condition_slot': condition_info,
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
import json
from pathlib import Path
sys.path.insert(0, '.')

# Load compare result
compare_result_path = Path('artifacts/v3_1_compare_result.json')
if not compare_result_path.exists():
    print('  ERROR: Compare result not found')
    sys.exit(1)

with open(compare_result_path, 'r', encoding='utf-8') as f:
    compare_data = json.load(f)

# Build simplified ExplainView for each insurer (without using V2 mapper)
insurer_views = []

for insurer, data in compare_data.items():
    decision = data.get('decision', 'unknown')

    # Build evidence tabs from saved data
    amount_tab = []
    if data.get('amount_slot'):
        amount_tab.append({
            'value': data['amount_slot'].get('value') or data.get('amount_value'),
            'source_doc': data['amount_slot'].get('source_doc', '약관'),
            'page': data['amount_slot'].get('page'),
            'excerpt': data['amount_slot'].get('excerpt', ''),
        })

    condition_tab = []
    if data.get('condition_slot'):
        condition_tab.append({
            'source_doc': data['condition_slot'].get('source_doc', '약관'),
            'excerpt': data['condition_slot'].get('excerpt', ''),
        })

    # Determine card type from decision
    card_type = 'info' if decision == 'determined' else 'error'
    title = '비교 완료' if decision == 'determined' else '근거 부족'

    insurer_views.append({
        'insurer': insurer,
        'explain_view': {
            'decision': decision,
            'reason_card': {
                'card_type': card_type,
                'title': title,
            },
            'evidence_tabs': {
                'amount': amount_tab,
                'condition': condition_tab,
                'definition': [],
            },
        }
    })
    print(f'  {insurer}: {decision}')

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
