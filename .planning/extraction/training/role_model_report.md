# Role Classifier — Report (Job A)

- **Macro-F1 (pooled OOF):** 0.6519
- **vs Docling baseline:** 0.1718 (delta +0.4801, fallback share 0.051)
- Rows: 2503 (dropped 2165 dup text/role) | sklearn 1.8.0

## Per-class

| role | precision | recall | f1 | support |
|---|---|---|---|---|
| key | 0.783 | 0.741 | 0.761 | 409 |
| noise | 0.964 | 0.974 | 0.969 | 1366 |
| prose | 0.679 | 0.654 | 0.667 | 81 |
| section_header | 0.739 | 0.649 | 0.691 | 131 |
| signature | 0.000 | 0.000 | 0.000 | 1 |
| table_header | 0.492 | 0.727 | 0.587 | 44 |
| value | 0.883 | 0.894 | 0.888 | 471 |

## Confusion (rows=true, cols=pred)

| | key | noise | prose | section_header | signature | table_header | value |
|---|---|---|---|---|---|---|---|
| **key** | 303 | 27 | 2 | 12 | 0 | 20 | 45 |
| **noise** | 19 | 1331 | 8 | 4 | 0 | 0 | 4 |
| **prose** | 7 | 11 | 53 | 5 | 0 | 0 | 5 |
| **section_header** | 23 | 3 | 7 | 85 | 0 | 12 | 1 |
| **signature** | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| **table_header** | 4 | 0 | 0 | 7 | 0 | 32 | 1 |
| **value** | 30 | 9 | 8 | 2 | 0 | 1 | 421 |

## Top feature importances

- engine_agreement: 0.1829
- x: 0.1706
- inside_rect: 0.1154
- len_chars: 0.1118
- font_size: 0.0908
- w: 0.0574
- digit_ratio: 0.0498
- case_lower: 0.0291
- colon_present: 0.0289
- docling_present: 0.0134
- h: 0.0122
- n_numeric_tokens: 0.0097
- docling_heading_level: 0.0068
- has_currency: 0.0063
- docling_column_header: 0.0054
- compound_span: 0.0041
- gap_below: 0.0040
- is_centered: 0.0034
- docling_label_list_item: 0.0011
- docling_content_layer_furniture: 0.0004
- is_bold: 0.0000
- case_title: 0.0000
- case_mixed: 0.0000
- has_date: 0.0000
- has_percent: 0.0000
