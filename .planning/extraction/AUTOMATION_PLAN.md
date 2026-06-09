# Golden Generation Automation Plan

**Goal**: reduce golden creation from 10-15 min/page (manual) → 3 min/page (assisted) → 30 sec/page (autonomous) without quality loss.

**Quality target**: pipeline-generated goldens match hand-curated goldens within 95% on KV count, label/value text, and engine_agreement distribution.

---

## Architecture

```
PDF + page
   ↓
extract_atoms.py (existing, deterministic)
   ↓
atoms.json
   ↓
[scaffolder agent]      ← Claude (Phase 4)
   ↓
spec.py (draft)
   ↓
build_golden.py         ← deterministic (Phase 0: extended)
   ↓
golden.json
   ↓
[reviewer agent]        ← Claude (Phase 1)
   ↓
findings.json
   ↓
severity HIGH?
 ├── no  → done ✓
 └── yes →
        ↓
   [patcher]            ← deterministic (Phase 2)
        ↓
   spec.py (updated)
        ↓
   loop to build_golden.py  (max 3 iters, Phase 3)
```

### Key design choices

- **Deterministic build between LLM calls**: no drift across iterations
- **Structured I/O between agents**: findings.json schema → patcher applies mechanically
- **Tri-engine evidence stays automatic**: agents don't compute bboxes
- **Versioned specs**: git tracks every patch → rollback safe
- **Human escape hatch**: max_iter or stuck → escalates to viewer

---

## Phase 0 — Foundation (1-2h)

### Deliverables
- `src/docomestria/golden/walker.py`: add three new node types
  - `prose_block`: text-only block (label/no value), produces structure node + 0 KVs
  - `noise`: page footer/watermark/sidebar, separate `noise[]` array in output
  - `signature_placeholder`: empty signature box, produces structure node + 1 empty KV
- `scripts/specs/_patterns.py`: reusable spec helpers
  - `caixabank_person_block(y_base, **data)` → kv_group for 25-field titular/avalista form
  - `representative_table(table_id, y_base, **data)` → 5-row Nombre/NIF/Dirección/Teléfono/E-mail
  - `consent_matrix(consents)` → SI/NO checkbox group
  - `condiciones_economicas_table(rows)` → 2-col label/value
  - `caixabank_footer_noise(page_num, total)` → standard CaixaBank footer
- `scripts/dump_spans.py`: replaces inline Python heredoc
  - Args: `PDF page [--bands]` (group by y-band if `--bands`)
  - Output: aligned table `y x size bold | text` to stdout

### Validation
- Re-build existing IKEA/PRESTAMO goldens with new types → no regressions
- Re-write 2 specs using `_patterns.py` helpers → spec LOC drops 50%+

### Files touched
- `src/docomestria/golden/walker.py`
- `src/docomestria/golden/__init__.py` (export new types)
- `scripts/specs/_patterns.py` (new)
- `scripts/dump_spans.py` (new)

---

## Phase 1 — Reviewer (3-4h, **most critical**)

### Deliverables
- `.claude/agents/golden-reviewer.md`: agent definition
  - Description: "Validates a golden.json against its source PDF page. Emits findings.json."
  - Tools: Read, Bash (for PDF rendering), Glob
  - Model: sonnet (cost/quality tradeoff)
- `scripts/golden_review.py`: CLI wrapper that spawns the agent and validates output
  - Args: `--golden PATH --pdf PATH --page N [--out findings.json]`
  - Output: structured findings + summary stats

### findings.json schema
```json
{
  "golden_path": "...",
  "pdf_path": "...",
  "page": 2,
  "summary": {"high": 0, "medium": 1, "low": 0},
  "findings": [
    {
      "id": "f01",
      "severity": "HIGH|MEDIUM|LOW",
      "type": "missing_kv|swapped_label_value|wrong_value_text|extra_kv|wrong_section|missing_section|misplaced_noise",
      "spec_location": "section.id=titulares, row=2",
      "evidence": {
        "pdf_text_found": "...",
        "golden_text": "...",
        "bbox_in_pdf": {"x":..., "y":...}
      },
      "proposed_fix": {
        "op": "update_y_hint|add_kv|fix_value|move|delete",
        "path": "structure[0].children[1].pairs[3]",
        "params": {"y_hint": 234}
      }
    }
  ]
}
```

### Issue types caught (vs engine_agreement)
| Issue | engine_agreement | reviewer |
|---|---|---|
| KV text not in PDF | ❌ (returns 0_eng) | ✅ |
| Label/value crossed | ✅ (both 3-eng) | ✅ |
| Wrong row picked | ✅ (3-eng for wrong row) | ✅ |
| Missing KV entirely | ❌ (not in output) | ✅ |
| Extra KV (hallucinated) | ❌ (0_eng) | ✅ |
| KV in wrong section/band | ✅ | ✅ |
| Noise classified as KV | ✅ | ✅ |

### Validation
- Run on IKEA p02-p08 (already curated) → expect ≤2 LOW findings/page
- Inject 5 deliberate errors per category → reviewer catches all
- Run on PRESTAMO COMERCIO 2 (just built without review) → see what it finds

### Files touched
- `.claude/agents/golden-reviewer.md` (new)
- `scripts/golden_review.py` (new)
- `.planning/extraction/reviews/` (new dir for findings)

---

## Phase 2 — Patcher (2h, deterministic)

### Deliverables
- `scripts/spec_patcher.py`: applies findings.json patches to spec.py
  - Reads spec as AST (Python `ast` module)
  - Operations (mechanical, no LLM):
    - `update_y_hint(path, new_y)`
    - `add_kv(parent_path, label, value, y_hint)`
    - `fix_value(path, new_value)`
    - `move(from_path, to_path)`
    - `delete(path)`
  - Outputs updated spec + patch_log.json

### Validation
- Round-trip test: spec → patch → spec → diff is exactly the requested changes
- Idempotency: applying same patch twice = same result
- Failure modes: invalid path raises clear error (not silent skip)

### Files touched
- `scripts/spec_patcher.py` (new)

---

## Phase 3 — Orchestrator loop (1-2h)

### Deliverables
- `scripts/golden_pipeline.py`: end-to-end loop
  - Args: `PDF page [--spec spec.py] [--max-iter 3]`
  - Default: starts from scaffolder if no spec; from existing spec if provided
  - Loop:
    1. (if no spec) scaffold → spec.py
    2. build → golden.json
    3. review → findings.json
    4. if `findings.high == 0`: ✓ done
    5. if `iter >= max_iter`: ⚠ escalate
    6. if `findings == previous_findings`: 🚨 stuck → escalate
    7. patch → spec.py updated → goto 2
  - Output: final spec.py + golden.json + iteration_log.json

### iteration_log.json schema
```json
{
  "pdf": "...",
  "page": 2,
  "iterations": [
    {"iter": 1, "spec_hash": "...", "golden_kvs": 7, "findings_high": 2, "patches": [...]},
    {"iter": 2, "spec_hash": "...", "golden_kvs": 9, "findings_high": 0, "status": "done"}
  ],
  "final_status": "done|escalated|stuck",
  "total_seconds": 45
}
```

### Files touched
- `scripts/golden_pipeline.py` (new)
- `.planning/extraction/iterations/` (new dir)

---

## Phase 4 — Scaffolder agent (3-4h, **highest impact**)

### Deliverables
- `.claude/agents/golden-scaffolder.md`: agent definition
  - Description: "Generates a draft golden spec.py from atoms + PDF image"
  - Tools: Read (PDF + atoms), Write (spec.py), Bash (for image rendering if needed)
  - Model: sonnet
- Scaffolder system prompt includes:
  - Walker types: section / kv_leaf / kv_group / table / array / free_text_list / prose_block / noise
  - Known patterns from `_patterns.py` (must prefer helpers when applicable)
  - y_hint convention (pdfplumber row_y from atoms)
  - Example specs (links to IKEA/BBVA/PRESTAMO existing)
- Validation rules baked into prompt:
  - Every populated value must have a span in atoms (verify by grep)
  - kv_group when 2+ fields share a y-band; kv_leaf otherwise
  - table when 3+ rows with same column structure
  - Always include `_meta.covers_cases` listing patterns demonstrated

### Validation
- Generate spec for IKEA p02 from scratch → match existing hand-written spec within 90%
- Generate spec for PRESTAMO p05 from scratch → match within 90%
- Generate spec for a totally new contract (LABORAL p02?) → reviewer reports ≤3 HIGH findings

### Files touched
- `.claude/agents/golden-scaffolder.md` (new)
- Examples directory referenced from prompt

---

## Phase 5 — Batch mode + viewer integration (2h)

### Deliverables
- `scripts/golden_pipeline_batch.py PDF`: runs pipeline for all pages with triage verdict `extract`
  - Parallelizes per-page pipelines (max 4 concurrent)
  - Skips pages with existing valid golden (`--force` to redo)
  - Summary report at end: N pages OK, M escalated, K stuck
- Viewer (`scripts/view_goldens.py`): new tab "Pipeline history"
  - Shows iteration_log.json contents
  - Per-iteration findings with severity
  - Patches applied diff view

### Files touched
- `scripts/golden_pipeline_batch.py` (new)
- `scripts/view_goldens.py` (extended)

---

## Total estimate
- Phase 0: 1-2h
- Phase 1: 3-4h ← critical path
- Phase 2: 2h
- Phase 3: 1-2h
- Phase 4: 3-4h ← critical path
- Phase 5: 2h

**~12-16h total** → realistic 2-3 working sessions.

After full pipeline: scaling to 50 PDFs × ~8 pages = 400 goldens, expected cost ~$20 in LLM, ~10h human review of escalated cases.

---

## Risk mitigation

| Risk | Mitigation |
|---|---|
| Scaffolder hallucinates labels/values | Reviewer catches it (grep against atoms) |
| Reviewer rubber-stamps bad specs | Test with deliberate-error injection suite |
| Patcher corrupts spec | AST-based, round-trip tested, git versioned |
| Loop never converges | max_iter=3, stuck detection, escalate to human |
| Patterns library drift | Auto-generate from existing curated specs |
| LLM cost runaway | Per-PDF cost tracking, alert if >$1/PDF |

---

## Order of execution

1. **Phase 0** (foundation) — unblocks everything
2. **Phase 1** (reviewer) — gives quality measurement, makes everything else safer
3. **Phase 2** (patcher) — mechanical, no LLM, easy win
4. **Phase 3** (orchestrator) — wires existing pieces, low risk
5. **Phase 4** (scaffolder) — highest leverage but riskiest, do with reviewer already in place
6. **Phase 5** (batch + viewer) — production readiness

---

## Open questions for Carlos

1. **Model choice for agents**: sonnet (cheap, fast) vs opus (better reasoning)? Recommend sonnet for reviewer, opus for scaffolder.
2. **Where to store patterns**: `scripts/specs/_patterns.py` (Python helpers) vs `.claude/contexts/golden_patterns.md` (LLM context)? Recommend both — helpers for build, docs for scaffolder prompt.
3. **Should scaffolder always run or only on new PDFs**? Recommend: scaffolder runs if no spec exists; pipeline starts from existing spec otherwise.
4. **Are we OK adding LLM cost (~$0.05/page)** to the workflow? Recommend yes — cheaper than human time.
