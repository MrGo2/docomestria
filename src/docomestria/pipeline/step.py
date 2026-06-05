"""`PipelineStep` — one observable phase of a `Pipeline.stream()` run.

The stream API surfaces the pipeline's internal phases (extraction, fusion,
LLM call, binding, typing) as immutable steps so UIs (notably
`docomestria-studio`) can render progress and intermediate state, and so
telemetry consumers can attach a `step_callback` without changing call style.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..models import BBox

if TYPE_CHECKING:  # pragma: no cover
    from ..llm.models import BoundValue, ProvenanceIssue
    from ..result import FusionResult
    from ..transform.models import TypedValue


# Canonical step names emitted by `Pipeline.stream()`, in execution order.
# A `cache_hit` step short-circuits the middle phases when the result is
# already cached.
STEP_NAMES: tuple[str, ...] = (
    "start",
    "cache_check",
    "extract_liteparse",
    "extract_docling",
    "extract_pdfplumber",
    "fuse",
    "build_context",
    "llm_call",
    "parse_response",
    "bind_provenance",
    "detect_issues",
    "apply_schema",
    "complete",
)

# Step names for the deterministic (`llm=None`) path. The LLM-specific phases
# are replaced by a single `pair_fields` step.
DETERMINISTIC_STEP_NAMES: tuple[str, ...] = (
    "start",
    "cache_check",
    "extract_liteparse",
    "extract_docling",
    "extract_pdfplumber",
    "fuse",
    "pair_fields",
    "apply_schema",
    "complete",
)

# Total step count used to populate `PipelineStep.total_steps`. We use the
# canonical sequence length so progress is monotonic and predictable even
# when an extract step is skipped (e.g. cache hit replaces 3–12 with a
# single `cache_hit` step but `total_steps` stays the same).
TOTAL_STEPS: int = len(STEP_NAMES)


# Per-step human-readable titles + ES/EN explanations. UIs read these to
# render a friendly description of what the pipeline is currently doing.
STEP_TITLES: dict[str, str] = {
    "start": "Inicio",
    "cache_check": "Comprobando caché",
    "cache_hit": "Caché encontrada",
    "extract_liteparse": "Extracción texto",
    "extract_docling": "Análisis semántico",
    "extract_pdfplumber": "Análisis visual",
    "extract_all": "Extracción paralela",
    "fuse": "Fusión 3 motores",
    "build_context": "Preparando contexto LLM",
    "llm_call": "Consultando modelo",
    "parse_response": "Parseando respuesta",
    "bind_provenance": "Vinculando provenance",
    "detect_issues": "Detectando problemas",
    "apply_schema": "Tipando valores",
    "pair_fields": "Emparejando campos",
    "complete": "Listo",
    "error": "Error",
}

EXPLANATIONS: dict[str, dict[str, str]] = {
    "start": {
        "es": "Recibido el PDF. Preparando pipeline de extracción.",
        "en": "PDF received. Preparing the extraction pipeline.",
    },
    "cache_check": {
        "es": "Buscando si este PDF ya se procesó con este esquema y modelo.",
        "en": "Checking whether this PDF was already processed with this schema and model.",
    },
    "cache_hit": {
        "es": "Resultado encontrado en caché. Reutilizando extracción anterior.",
        "en": "Cache hit — reusing the previous extraction.",
    },
    "extract_liteparse": {
        "es": "LiteParse extrae cada palabra del PDF con su caja, fuente y tamaño.",
        "en": "LiteParse extracts each word from the PDF with its bbox, font, and size.",
    },
    "extract_docling": {
        "es": "Docling identifica títulos, listas, tablas y bloques del documento.",
        "en": "Docling identifies titles, lists, tables, and structural blocks.",
    },
    "extract_pdfplumber": {
        "es": "pdfplumber detecta cajas, líneas y checkboxes dibujados en el PDF.",
        "en": "pdfplumber detects boxes, lines, and checkboxes drawn on the PDF.",
    },
    "extract_all": {
        "es": "Ejecutando los tres motores en paralelo: LiteParse, Docling y pdfplumber.",
        "en": "Running the three engines in parallel: LiteParse, Docling, and pdfplumber.",
    },
    "fuse": {
        "es": "Combinando texto + estructura + cajas visuales en items unificados.",
        "en": "Merging text + structure + visual boxes into unified items.",
    },
    "build_context": {
        "es": "Compactando items relevantes en un contexto JSON para el modelo.",
        "en": "Compacting relevant items into a JSON context for the model.",
    },
    "llm_call": {
        "es": "El LLM extrae los campos definidos en el esquema.",
        "en": "The LLM extracts the fields defined by the schema.",
    },
    "parse_response": {
        "es": "Convirtiendo la respuesta del modelo a JSON estructurado.",
        "en": "Parsing the model's response into structured JSON.",
    },
    "bind_provenance": {
        "es": "Mapeando cada valor extraído de vuelta a su bbox en el PDF.",
        "en": "Mapping each extracted value back to its bbox on the PDF.",
    },
    "detect_issues": {
        "es": "Buscando hallucinaciones y campos sospechosos.",
        "en": "Looking for hallucinations and suspicious fields.",
    },
    "apply_schema": {
        "es": "Convirtiendo strings a tipos (fechas, importes, NIF...) y validando.",
        "en": "Converting strings to typed values (dates, amounts, NIF, ...) and validating.",
    },
    "pair_fields": {
        "es": (
            "Buscando cada campo por su etiqueta (Apellidos:, NIF:, ...) y "
            "emparejándolo con su valor a la derecha o debajo. Sin LLM."
        ),
        "en": (
            "Finding each field by its label (Apellidos:, NIF:, ...) and "
            "pairing it with the value to the right or below. No LLM."
        ),
    },
    "complete": {
        "es": "Extracción completada.",
        "en": "Extraction complete.",
    },
    "error": {
        "es": "Se produjo un error durante la extracción.",
        "en": "An error occurred during extraction.",
    },
}


def explanation_for(step_name: str, lang: str) -> str:
    """Return the explanation for `step_name` in `lang` (falls back to ES)."""
    entry = EXPLANATIONS.get(step_name, {})
    if lang in entry:
        return entry[lang]
    if "es" in entry:
        return entry["es"]
    return ""


def title_for(step_name: str) -> str:
    """Return the short human-readable title for `step_name`."""
    return STEP_TITLES.get(step_name, step_name)


@dataclass(frozen=True)
class PipelineStep:
    """One observable phase of pipeline execution.

    Yielded by `Pipeline.stream()` and (optionally) passed to
    `Pipeline.step_callback`. All fields are immutable; the optional pointers
    to richer state (`fusion`, `bound`, `issues`, `typed_fields`) are `None`
    for early steps and become populated as those artefacts are produced.
    """

    name: str
    title: str
    explanation: str
    engine: str
    step_index: int
    total_steps: int
    elapsed_ms: int
    cumulative_ms: int
    bboxes: tuple[BBox, ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)
    is_terminal: bool = False
    is_error: bool = False
    error_message: str | None = None
    fusion: "FusionResult | None" = None
    bound: "tuple[BoundValue, ...] | None" = None
    issues: "tuple[ProvenanceIssue, ...] | None" = None
    typed_fields: "dict[str, TypedValue] | None" = None

    @property
    def progress(self) -> float:
        """Progress fraction in [0.0, 1.0]."""
        if self.total_steps <= 0:
            return 0.0
        return self.step_index / self.total_steps


__all__ = [
    "DETERMINISTIC_STEP_NAMES",
    "EXPLANATIONS",
    "STEP_NAMES",
    "STEP_TITLES",
    "TOTAL_STEPS",
    "PipelineStep",
    "explanation_for",
    "title_for",
]
