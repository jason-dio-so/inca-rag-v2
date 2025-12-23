#!/usr/bin/env python3
"""
V3-1 Sample Ingestion Pipeline
STEP V3-1: E2E with 2 약관 PDFs → Chat Response

Ingests Samsung and Meritz 약관 PDFs into chunks for comparison.

Pipeline:
1. PDF text extraction (page-based)
2. Page-based chunk generation
3. Chunk metadata injection
4. Output to artifacts/v3_1_chunks.jsonl

PROHIBITED:
- LLM-based coverage_code generation
- Embedding-based semantic matching
- Modifying canonical definitions
"""

import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Try to import PDF library
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("WARNING: PyPDF2 not installed. Using mock PDF extraction.")

from compare.types import Insurer, DocType


# --- Configuration ---

DATA_DIR = PROJECT_ROOT / "data" / "v3_1_sample"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
OUTPUT_FILE = ARTIFACTS_DIR / "v3_1_chunks.jsonl"

# Sample files
SAMPLE_FILES = {
    Insurer.SAMSUNG: DATA_DIR / "SAMSUNG" / "약관" / "삼성_약관.pdf",
    Insurer.MERITZ: DATA_DIR / "MERITZ" / "약관" / "메리츠_약관.pdf",
}

# Known canonical coverage codes for cancer diagnosis benefit
# Based on 신정원 unified code system
# These codes MUST exist in schema/canonical_coverage.yaml
KNOWN_COVERAGE_PATTERNS = {
    r"암진단비|암\s*진단\s*보험금|암진단급여금": "A4200_1",  # 암진단비
    r"뇌졸중진단비|뇌졸중\s*진단": "A4103",  # 뇌졸중진단비
    r"급성심근경색진단비|급성심근경색": "A4102",  # 급성심근경색진단비
    r"제자리암|유사암": "A4201_1",  # 유사암진단비(제자리암)
}

# Canonical coverage codes from schema/canonical_coverage.yaml
# This is the SINGLE SOURCE OF TRUTH for valid codes
# Pattern matching results MUST be validated against this set
CANONICAL_COVERAGE_CODES = {
    "A4200_1",  # 암진단비(유사암제외)
    "A4103",    # 뇌졸중진단비
    "A4102",    # 급성심근경색진단비
    "A4201_1",  # 유사암진단비(제자리암)
    "A5100",    # 질병수술비
}


def validate_coverage_code(candidate_code: Optional[str]) -> Optional[str]:
    """
    Validate candidate coverage_code against canonical standard.

    Rule: coverage_code MUST exist in CANONICAL_COVERAGE_CODES.
    If validation fails, return None (not the candidate).

    Args:
        candidate_code: Pattern-matched candidate code

    Returns:
        Validated canonical code if exists, else None
    """
    if candidate_code is None:
        return None

    if candidate_code in CANONICAL_COVERAGE_CODES:
        return candidate_code

    # Validation failed - code not in canonical standard
    print(f"WARNING: Coverage code '{candidate_code}' not in canonical standard. Setting to None.")
    return None


@dataclass
class ChunkMeta:
    """Chunk metadata structure."""
    chunk_id: str
    insurer: str
    doc_type: str
    source_file: str
    page_start: int
    page_end: int
    coverage_code: Optional[str]  # Canonical code if detected, else None
    text: str
    created_at: str


# Global flag for demo mode (use mock data instead of real PDFs)
DEMO_MODE = False


def extract_pdf_text(pdf_path: Path) -> list[tuple[int, str]]:
    """
    Extract text from PDF, page by page.

    Returns list of (page_number, text) tuples.
    Page numbers are 1-indexed.
    """
    # Demo mode: use mock data without requiring actual PDFs
    if DEMO_MODE:
        return _mock_pdf_extraction(pdf_path)

    if not pdf_path.exists():
        print(f"WARNING: PDF not found: {pdf_path}")
        return []

    if not PDF_AVAILABLE:
        # Return mock data for testing without PDF library
        return _mock_pdf_extraction(pdf_path)

    pages = []
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append((i + 1, text))
    except Exception as e:
        print(f"ERROR extracting PDF {pdf_path}: {e}")
        return []

    return pages


def _mock_pdf_extraction(pdf_path: Path) -> list[tuple[int, str]]:
    """
    Mock PDF extraction for testing without actual PDFs.
    Returns sample content based on filename.
    """
    filename = pdf_path.name.lower()

    if "삼성" in filename or "samsung" in filename.lower():
        return [
            (1, "삼성화재 암보험 약관\n제1조 목적\n이 약관은 암 진단 시 보험금 지급에 관한 사항을 규정합니다."),
            (2, "제2조 암진단비\n피보험자가 암으로 진단 확정된 경우 암진단비 5천만원을 지급합니다.\n지급 조건: 계약일로부터 90일 이후 진단"),
            (3, "제3조 보장 범위\n암의 정의는 한국표준질병사인분류에 따릅니다.\n제자리암, 경계성종양은 별도 기준 적용"),
        ]
    elif "메리츠" in filename or "meritz" in filename.lower():
        return [
            (1, "메리츠화재 암보험 약관\n제1조 목적\n본 약관은 암 진단 보험금에 관한 내용을 정합니다."),
            (2, "제2조 암진단비\n피보험자가 암으로 진단 확정시 암진단비 3천만원을 지급합니다.\n지급 조건: 가입 후 90일 경과"),
            (3, "제3조 암의 정의\n암이라 함은 악성신생물(C00-C97)을 말합니다.\n갑상선암은 50% 감액 지급"),
        ]

    return [(1, "샘플 약관 내용")]


def detect_coverage_code(text: str) -> Optional[str]:
    """
    Detect canonical coverage code from text using pattern matching.

    PROHIBITED: LLM-based inference

    Process:
    1. Pattern matching to get candidate code
    2. Validate candidate against CANONICAL_COVERAGE_CODES
    3. Return validated code or None

    Returns: Validated canonical code if pattern matched AND validated, else None.
    """
    text_normalized = text.replace(" ", "").lower()

    for pattern, code in KNOWN_COVERAGE_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            # CRITICAL: Validate against canonical standard before returning
            return validate_coverage_code(code)

    return None


def create_chunk(
    insurer: Insurer,
    source_file: Path,
    page_num: int,
    text: str,
    chunk_index: int,
) -> ChunkMeta:
    """
    Create a chunk with metadata.

    Args:
        insurer: Insurance company
        source_file: Source PDF path
        page_num: Page number (1-indexed)
        text: Page text content
        chunk_index: Global chunk index

    Returns:
        ChunkMeta instance
    """
    # Generate unique chunk ID
    chunk_id = f"{insurer.value}_yakgwan_p{page_num:03d}_{chunk_index:04d}"

    # Detect coverage code from text (pattern-based only)
    coverage_code = detect_coverage_code(text)

    return ChunkMeta(
        chunk_id=chunk_id,
        insurer=insurer.value,
        doc_type=DocType.YAKGWAN.value,
        source_file=str(source_file.name),
        page_start=page_num,
        page_end=page_num,
        coverage_code=coverage_code,
        text=text,
        created_at=datetime.utcnow().isoformat() + "Z",
    )


def ingest_pdf(insurer: Insurer, pdf_path: Path, start_index: int = 0) -> list[ChunkMeta]:
    """
    Ingest a single PDF into chunks.

    Args:
        insurer: Insurance company
        pdf_path: Path to PDF file
        start_index: Starting chunk index

    Returns:
        List of ChunkMeta instances
    """
    print(f"Ingesting {insurer.value}: {pdf_path}")

    pages = extract_pdf_text(pdf_path)

    if not pages:
        print(f"  WARNING: No pages extracted from {pdf_path}")
        return []

    chunks = []
    for i, (page_num, text) in enumerate(pages):
        chunk = create_chunk(
            insurer=insurer,
            source_file=pdf_path,
            page_num=page_num,
            text=text,
            chunk_index=start_index + i,
        )
        chunks.append(chunk)

        if chunk.coverage_code:
            print(f"  Page {page_num}: Detected coverage_code={chunk.coverage_code}")

    print(f"  Created {len(chunks)} chunks")
    return chunks


def save_chunks(chunks: list[ChunkMeta], output_path: Path) -> None:
    """
    Save chunks to JSONL file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        for chunk in chunks:
            f.write(json.dumps(asdict(chunk), ensure_ascii=False) + '\n')

    print(f"Saved {len(chunks)} chunks to {output_path}")


def main():
    """Main ingestion entry point."""
    global DEMO_MODE

    # Check for --demo flag
    if "--demo" in sys.argv:
        DEMO_MODE = True
        print("DEMO MODE: Using mock PDF data")

    print("=" * 50)
    print("  V3-1 Sample Ingestion")
    print("=" * 50)
    print()

    all_chunks = []
    chunk_index = 0

    for insurer, pdf_path in SAMPLE_FILES.items():
        chunks = ingest_pdf(insurer, pdf_path, chunk_index)
        all_chunks.extend(chunks)
        chunk_index += len(chunks)

    if not all_chunks:
        print("\nERROR: No chunks created. Check if PDF files exist.")
        print("TIP: Use --demo flag to run with mock data")
        return 1

    # Save to JSONL
    save_chunks(all_chunks, OUTPUT_FILE)

    # Summary
    print()
    print("=" * 50)
    print("  Ingestion Summary")
    print("=" * 50)
    print(f"  Total chunks: {len(all_chunks)}")

    by_insurer = {}
    by_coverage = {}
    for chunk in all_chunks:
        by_insurer[chunk.insurer] = by_insurer.get(chunk.insurer, 0) + 1
        if chunk.coverage_code:
            by_coverage[chunk.coverage_code] = by_coverage.get(chunk.coverage_code, 0) + 1

    print(f"  By insurer: {by_insurer}")
    print(f"  By coverage_code: {by_coverage}")
    print(f"  Output: {OUTPUT_FILE}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
