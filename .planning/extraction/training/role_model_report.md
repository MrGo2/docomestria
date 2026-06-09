# Role Classifier — Report (Job A)

- **Macro-F1 (pooled OOF):** 0.8799
- **vs Docling baseline:** 0.1627 (delta +0.7172, fallback share 0.112)
- Rows: 4668 (dropped 0 dup text/role) | sklearn 1.8.0

## Per-class

| role | precision | recall | f1 | support |
|---|---|---|---|---|
| key | 0.908 | 0.860 | 0.883 | 908 |
| noise | 0.984 | 0.987 | 0.985 | 2296 |
| prose | 0.890 | 0.844 | 0.866 | 173 |
| section_header | 0.827 | 0.715 | 0.767 | 214 |
| signature | 0.938 | 0.968 | 0.952 | 31 |
| table_header | 0.707 | 0.885 | 0.786 | 139 |
| value | 0.898 | 0.940 | 0.919 | 907 |

## Confusion (rows=true, cols=pred)

| | key | noise | prose | section_header | signature | table_header | value |
|---|---|---|---|---|---|---|---|
| **key** | 781 | 24 | 2 | 16 | 0 | 28 | 57 |
| **noise** | 11 | 2266 | 5 | 2 | 0 | 5 | 7 |
| **prose** | 2 | 3 | 146 | 1 | 2 | 0 | 19 |
| **section_header** | 22 | 3 | 5 | 153 | 0 | 18 | 13 |
| **signature** | 0 | 0 | 0 | 0 | 30 | 0 | 1 |
| **table_header** | 4 | 2 | 0 | 10 | 0 | 123 | 0 |
| **value** | 40 | 5 | 6 | 3 | 0 | 0 | 853 |

## Top feature importances

- len_chars: 0.3477
- engine_agreement: 0.2106
- x: 0.1609
- font_size: 0.1209
- h: 0.0819
- w: 0.0742
- colon_present: 0.0740
- y: 0.0333
- compound_span: 0.0305
- digit_ratio: 0.0207
- inside_rect: 0.0130
- docling_label_list_item: 0.0036
- case_lower: 0.0028
- ends_colon: 0.0010
- docling_label_table: 0.0009
- pdfplumber_present: 0.0008
- starts_paren: 0.0007
- docling_content_layer_furniture: 0.0006
- docling_present: 0.0003
- gap_below: 0.0003
- font_ratio_vs_below: 0.0002
- case_title: 0.0000
- case_mixed: 0.0000
- has_date: 0.0000
- has_percent: 0.0000
