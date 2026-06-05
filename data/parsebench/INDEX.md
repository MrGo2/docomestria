# ParseBench sample — index

- Total PDFs: **15**
- Total ground-truth records across all PDFs: **2264**
- Engine errors: **0**
- Empty engine outputs (0 items): **1**

Engine cells show `<item count> (<elapsed s>)` from the saved JSON,
`ERROR` if the engine wrote `<stem>.error.txt`, or `—` if no output was produced.

| File | Category | Size (KB) | GT records | Docling | LiteParse | pdfplumber |
|---|---|---:|---:|---|---|---|
| `layout__(Web_version)_E-Government_Survey_2024_1392024_p101.pdf` | layout | 179 | 8 | 61 (28.73s) | 249 (0.33s) | 38 (0.24s) |
| `layout__(Web_version)_E-Government_Survey_2024_1392024_p81.pdf` | layout | 384 | 10 | 29 (1.12s) | 220 (0.04s) | 45 (0.36s) |
| `layout__0000050863-25-000054_p7.pdf` | layout | 589 | 49 | 51 (0.86s) | 70 (0.01s) | 70 (0.04s) |
| `layout__02775267_p3.pdf` | layout | 422 | 59 | 53 (5.45s) | 113 (0.09s) | 34 (0.11s) |
| `layout__076523s007lbl_p2.pdf` | layout | 217 | 198 | 210 (2.57s) | 832 (0.04s) | 64 (0.54s) |
| `table__0000027_page1.pdf` | table | 40 | 1 | 8 (4.91s) | 480 (0.01s) | 192 (0.16s) |
| `table__1 timetable (1)_page2.pdf` | table | 42 | 1 | 2 (8.41s) | 624 (0.01s) | 666 (0.13s) |
| `table__1 timetable (1)_page27.pdf` | table | 32 | 1 | 2 (1.65s) | 76 (0.00s) | 58 (0.02s) |
| `table__1 timetable (1)_page7.pdf` | table | 40 | 1 | 2 (8.69s) | 570 (0.01s) | 564 (0.12s) |
| `table__1653739079_page34.pdf` | table | 58 | 1 | 25 (2.07s) | 228 (0.01s) | 1 (0.07s) |
| `text__text_dense__canara.pdf` | text | 357 | 852 | 11 (1.12s) | 141 (0.01s) | 195 (0.20s) |
| `text__text_dense__cn_article.pdf` | text | 717 | 473 | 55 (1.15s) | 242 (0.01s) | 12 (0.14s) |
| `text__text_dense__de.pdf` | text | 143 | 221 | 18 (0.79s) | 68 (0.01s) | 0 (0.04s) |
| `text__text_misc__012-headline-certificate-fluidpower-group-uk-limited.pdf` | text | 262 | 180 | 25 (0.84s) | 32 (0.00s) | 1 (0.03s) |
| `text__text_misc__6slides.pdf` | text | 21 | 209 | 27 (0.86s) | 62 (0.00s) | 15 (0.03s) |
