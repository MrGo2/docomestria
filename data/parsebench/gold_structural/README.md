# Structural Gold Annotations

This folder contains the first gold corpus for `docomestria.structural`.

The files are intentionally lightweight JSON annotations for the five Spanish
PDFs used during the v0.7.0 structural-extraction work:

- `azuredemo__LABORAL`
- `azuredemo__PATRIMONIAL`
- `azuredemo__BBVA3`
- `azuredemo__BBVA4`
- `azuredemo__BBVA5`

Each JSON file has:

- `expected_pairs`: pairs the extractor should emit.
- `expected_tables`: tables the extractor should expose structurally.
- `forbidden_pairs`: pairs the extractor must not emit.
- `forbidden_pages`: page ranges where the extractor must emit no pairs.
- `known_gaps`: desired assertions that are not enforced yet because the
  current extractor is known not to satisfy them.

Value matching rules used by `tests/test_structural_gold.py`:

- Plain strings are exact matches after trimming.
- `contains:<text>` means substring match.
- `<empty>` means the extracted value must be blank.

The five `azuredemo__*.json` cached engine outputs under
`data/parsebench/outputs/{docling,liteparse,pdfplumber}/` are tracked as test
fixtures so the gold suite runs in a clean checkout. Raw PDFs, ground truth
downloads, and generated visual views remain ignored.
