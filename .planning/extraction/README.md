# Structural extraction — KIE framework documentation

> **Elevator pitch.** Heuristic-engineered KIE with multi-engine features
> + CRF + ILP joint inference. Reads Spanish business forms (banking,
> insurance, government) by combining `pdfplumber` (vector geometry),
> `Docling` (semantic ML labels), and `LiteParse v2` (typographic spans),
> scoring role and pair candidates with a log-linear model, and resolving
> the global assignment with an integer linear program.

## Files

| File | Purpose |
|---|---|
| [`00-approach.md`](./00-approach.md) | The approach name, academic context, why CRF + ILP over end-to-end neural in 2026, and the LayoutLM-hybrid upgrade path. |
| [`01-model.md`](./01-model.md) | The mathematical model — feature vectors, edge functions, role-classification templates, column coherence, pair scoring, ILP formulation, worked example, weight calibration. |
| [`02-engines.md`](./02-engines.md) | Capability catalog for `pdfplumber`, `Docling`, `LiteParse v2` — what each emits, what we use today, what we leave on the table, and the cross-engine routing matrix. |
| [`03-pipeline.md`](./03-pipeline.md) | The super-engine spec — Capa 0 → Capa 9 layered pipeline + per-page output JSON schema. |
| [`04-cases.md`](./04-cases.md) | Evidence — eight concrete failure cases from real BBVA contracts that drive the design. |
| [`05-roadmap.md`](./05-roadmap.md) | Implementation roadmap (6 steps) — wrapper lifts → super-engine module → validation set → diff harness. |
| [`06-anti-patterns.md`](./06-anti-patterns.md) | What NOT to do, consolidated from the cases and design discussions. |

## Reading order

For a new collaborator landing here, work through the files in this order:

1. **`00-approach.md`** — understand the framing (KIE, CRF, log-linear, ILP) and why we are not using LayoutLM.
2. **`01-model.md`** — internalise the feature vectors, the role templates, the pair scoring and the ILP formulation. This is the heart of the system.
3. **`02-engines.md`** — learn which features come from which engine and why none of them wins alone.
4. **`04-cases.md`** — read the evidence; every design choice in the model traces back to one of these eight cases.
5. **`03-pipeline.md`** — once the model is clear, see how the layers materialise it end-to-end.
6. **`05-roadmap.md`** — when you are ready to implement, follow the six steps.
7. **`06-anti-patterns.md`** — keep as reference; consult before introducing any new heuristic.

## Test material

- BBVA loan, page 1 — `data/parsebench/pdfs/banking__bbva_loan_1414.pdf` — the source for cases 1–5 (rect-height filter, header projection, text-positioned tables, parent-rect title, title-above parent).
- BBVA mortgage `BBVA_0608` — `/Users/carlos/Edelwyss/Projects/docomestria/Dataset/AZUREDOCUI/5_Example/BBVA_0608-01491495_DOC2_CONTRATO.pdf` — pages 2 and 3 power cases 6, 7, 8 (case-contrast, variable-layout sections, per-cell profile + column coherence).

## Visual debugger

`scripts/view_boxes_p1.py` serves an interactive overlay viewer at
`http://localhost:8770/` showing pdfplumber rects, Docling blocks and
LiteParse spans on top of the rasterized page. Use it to validate every
hypothesis before writing code.

## Related planning documents

- `../structural-extraction-strategy.md` — the v0.9.0 milestone strategy
  (predates this restructure; kept for historical context).
- `../structural-extraction-handoff.md` — current handoff state.
- `../dod-status.md` — Definition of Done tracker for the milestone.
- `../extraction-framework.md` — the framework spec adjacent to this folder.
