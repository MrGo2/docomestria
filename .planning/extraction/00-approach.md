# The approach — KIE with CRF + ILP joint inference

## Name and academic context

**Task.** Key Information Extraction (KIE) — a sub-field of Document AI /
Document Understanding. Given a PDF page, emit structured records
(`{label, value, section, confidence, evidence}`) covering the semantic
content of the page.

**Framework.** Heuristic-engineered, log-linear structured KIE with ILP
joint inference, leveraging multi-engine geometric and typographic
features. In academic terms this is a **Conditional Random Field (CRF)
with joint inference**, also known as log-linear structured prediction.

### Foundational references

- Lafferty, J., McCallum, A., & Pereira, F. (2001). *Conditional Random
  Fields: Probabilistic Models for Segmenting and Labeling Sequence
  Data.* In Proceedings of the Eighteenth International Conference on
  Machine Learning (ICML).
- Collins, M. (2002). *Discriminative Training Methods for Hidden Markov
  Models: Theory and Experiments with Perceptron Algorithms* (the
  structured perceptron). In Proceedings of the Conference on Empirical
  Methods in Natural Language Processing (EMNLP).
- Roth, D., & Yih, W. (2004). *A Linear Programming Formulation for
  Global Inference in Natural Language Tasks.* In Proceedings of the
  Conference on Computational Natural Language Learning (CoNLL). — the
  original joint-inference-via-ILP formulation we adopt in
  [`01-model.md` §A.7](./01-model.md#a7-ilp-joint-resolution).

### Modern neural rivals

Where this approach sits versus the neural state of the art (so the
reader knows the trade-off space):

- **LayoutLM v1 / v2 / v3** (Microsoft) — transformer pre-trained on
  text + 2-D layout + image; the dominant academic baseline.
- **Donut** (Naver) — OCR-free encoder-decoder.
- **LiLT** (Tencent) — language-independent layout transformer.
- **LayoutXLM** (Microsoft) — multilingual variant of LayoutLM v2.
- **Google Document AI Form Parser** — managed cloud KIE service.
- **TILT** (Applica) — text-image-layout transformer.

Common training/eval datasets used by those systems: **FUNSD** (forms),
**CORD** (receipts), **DocBank**, **RVL-CDIP**, **SROIE** (scanned
receipts).

## Why CRF + ILP over end-to-end neural (in 2026)

Three reasons drive the choice in our deployment context.

### 1. Interpretability for regulated sectors

Spanish banking, legal and insurance customers require an audit trail
for every extracted field. With this framework every decision factors
as

    score = w₁·f₁ + w₂·f₂ + … + wₙ·fₙ

so any output can be explained as a weighted sum of explicit features
(bold, case, x-distance, Docling label, etc.). LayoutLM is a black box
— there is no comparable per-decision justification.

### 2. Dataset cost

LayoutLM fine-tuning needs on the order of **≥500 annotated PDFs** to
converge on a new document family. The CRF approach calibrates with
**~30 labelled KV pairs** (≈ one day of human work), and adding a new
document family only requires extending the role templates.

### 3. Latency and compute

CRF + ILP runs in **milliseconds per page on CPU**, with no GPU
required. LayoutLM needs a GPU and is on the order of **~1 s per page**
on commodity hardware. For batch ingestion of thousands of contracts,
the CPU/CRF path is one to two orders of magnitude cheaper.

## Future hybrid: LayoutLM embeddings as features

The architecture is extensible. When ≥200 labelled pairs become
available, LayoutLM-style transformer embeddings can be injected as
**additional dimensions in the per-span feature vector** defined in
[`01-model.md` §A.3](./01-model.md#a3-the-data-model-nodes--features--edges)
without replacing the CRF / ILP scaffolding. The result is a hybrid:
neural embeddings provide soft semantics, CRF + ILP provides the
auditable structured assignment. This is the recommended upgrade path
once the dataset volume justifies it.
