# V3-1 Sample Data

## Required Files

Place the following PDF files in their respective directories:

```
data/v3_1_sample/
├── SAMSUNG/
│   └── 약관/
│       └── 삼성_약관.pdf
├── MERITZ/
│   └── 약관/
│       └── 메리츠_약관.pdf
└── README.md
```

## File Requirements

- **삼성_약관.pdf**: Samsung Fire & Marine Insurance 약관 (terms and conditions)
- **메리츠_약관.pdf**: Meritz Fire & Marine Insurance 약관 (terms and conditions)

## Notes

- doc_type must be "약관" (terms and conditions)
- 쉬운요약서 (easy summary) is NOT used in V3-1
- Files should contain cancer diagnosis benefit (암진단비) information for comparison

## Usage

After placing the PDF files, run:

```bash
tools/run_v3_1_e2e.sh
```
