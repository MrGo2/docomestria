# Docomestria — Marco de Extracción Estructural

> Documento maestro. Define el objetivo, la arquitectura lógica, el marco
> estadístico y la estrategia de pruebas para convertir PDFs en JSON
> estructurado fusionando LiteParse v2 + Docling + pdfplumber.
>
> Complementa `structural-extraction-strategy.md` (validación empírica
> sobre 5 PDFs) con el marco teórico y el roadmap v0.7.1 → v0.9.0.

---

## 1. Objetivo

**Fusionar las tres herramientas — LiteParse (geometría exacta de cada
palabra), Docling (qué es tabla, qué es prosa, qué es título) y pdfplumber
(líneas vectoriales y bboxes ajustados) — para convertir tablas y columnas
en key-values y JSON estructurado fiable.**

Métrica de éxito: igualar o superar a Azure Document Intelligence en
precisión sobre los 5 PDFs del benchmark
(`azuredemo__LABORAL`, `__PATRIMONIAL`, `__BBVA3`, `__BBVA4`, `__BBVA5`),
en local, open-source, sin coste por página.

---

## 2. Rol de cada motor

| Motor | Papel | Fortaleza | Debilidad |
|---|---|---|---|
| **LiteParse v2** | el "ojo" | bbox sub-píxel por palabra, `font_name`/`font_size`, stream rápido | sin entendimiento semántico, sin orden de lectura |
| **Docling** | el "cerebro" | `DocItemLabel` (text/list_item/table/section_header), fusión de celdas TableFormer | bbox de región no ajustada, lento |
| **pdfplumber** | la "regla" | `find_tables()` con grid real, `page.lines/rects`, bbox ajustado | divide labels multi-línea, alucina tablas fantasma |

Ninguno es fuente única de verdad. La extracción correcta nace de su fusión.

### 2.1 Lo único de cada motor (qué muere si lo quitas)

| Motor | Capacidad ÚNICA | Sin él, falla en… |
|---|---|---|
| **LiteParse** | bbox sub-píxel por palabra + `font_name`/`font_size` | detección de columnas sin grid; distinción bold/regular; jerarquía por tamaño; cualquier emitter geométrico (L-horizontal, L-twocol-form, L-vertical) |
| **Docling** | etiquetas semánticas (`DocItemLabel`) + fusión TableFormer | supresión de prosa (S6 explota en falsos positivos); fusión de labels multi-línea; sub-secciones; jerarquía JSON |
| **pdfplumber** | acceso directo a gráficos vectoriales (`page.lines`, `page.rects`, `chars.non_stroking_color`) | validación física de grids; detección de checkboxes; subrayados como pista de campo; color/itálica |

### 2.2 Sinergia: 5 casos reales del proyecto

Antes/después por combinación, sobre los PDFs del benchmark.

#### Caso 1 — LABORAL "Respuesta" (label bold multi-línea)

| Motor solo | Resultado |
|---|---|
| LiteParse | 4 items sueltos, sin fusión |
| Docling | 1 celda fusionada ✓, pero bbox de región (ancho) |
| pdfplumber | Parte el label en 2 filas ✗ |
| **Los 3 fusionados** | Docling fusiona + LiteParse confirma geometría + pdfplumber recorta → **1 par correcto con bbox tight** |

#### Caso 2 — BBVA3 row con multi-colon

Celda Docling: `"N.I.F.: 009786573G Tipo Identificación: NIF PERSONA FISICA"`

| Motor solo | Resultado |
|---|---|
| Docling | 1 par incorrecto (fusiona dos KV en uno) |
| LiteParse | 4 palabras, no sabe que es celda |
| pdfplumber | Celda detectada pero texto partido en 2 filas |
| **Los 3 fusionados** | Docling marca celda → trigger E5 → LiteParse re-extrae por X-coord → **2 pares correctos** |

#### Caso 3 — Prosa con "label: value" embebido

Frase narrativa en un párrafo: `"...el plazo aplicable: 30 días naturales..."`.

| Motor solo | Resultado |
|---|---|
| LiteParse | Falso positivo (`plazo aplicable` → `30 días naturales`) |
| Docling | Etiqueta `text` (prosa) ✓ |
| pdfplumber | No aplica (sin tabla) |
| **LiteParse + Docling** | Docling suprime emitters dentro del bbox `text` → **0 falsos positivos** |

#### Caso 4 — Formulario 2-col paralelo (BBVA5 TAE Sin/Con)

| Motor solo | Resultado |
|---|---|
| Docling | Fusiona ambas columnas en celdas erróneas |
| pdfplumber | Detecta tabla pero parte mal |
| LiteParse | Palabras sin saber que son 2 columnas |
| **Los 3 fusionados** | Docling marca región → LiteParse X-coords revelan gutter → **2 streams KV paralelos: TAE Sin Seguro + TAE Con Seguro** |

#### Caso 5 — Checkbox booleano (pendiente v0.8.0)

| Motor solo | Resultado |
|---|---|
| pdfplumber | Ve un `rect` pero no sabe si es checkbox o decoración |
| Docling | Sin concepto de checkbox |
| LiteParse | No ve nada dentro del rect |
| **Los 3 fusionados** | Docling dice "región formulario" + pdfplumber rect pequeño + LiteParse sin texto dentro → **booleano detectado: marcado vs vacío** |

### 2.3 La regla de oro

**Cada motor es necesario, ninguno es suficiente.** Quitar cualquiera de los
tres degrada el sistema asimétricamente:

- Sin **LiteParse** → mueren los emitters geométricos (3 de 5 hoy).
- Sin **Docling** → explotan los falsos positivos en prosa (S6 imposible).
- Sin **pdfplumber** → no se validan grids ni se detectan checkboxes/subrayados.

La fusión no es aditiva (1+1+1=3); es **combinatoria** — habilita lógicas
imposibles para cualquier subconjunto de dos motores.

---

## 3. Las 8 capas de lógica

Cada capa se aplica sobre la anterior. Marcas: ✅ implementado, ⏳ pendiente.

### 3.1 Lógica de TABLA (estructura de celdas — Docling)

- ✅ **2-col directo** → `col[0]=label, col[1]=value` (emitter D-2col)
- ✅ **N-col con valor repetido** → colspan disfrazado, colapsar a 1 par
- ✅ **2-col con multi-colon en una celda** → re-extraer desde LiteParse (E5)
- ⏳ **N-col con cabecera de columna** → matriz `label × header → value`
- ⏳ **Tabla con sub-secciones** → agrupar pares por sub-título
- ⏳ **Tabla "lista de cosas"** (filas homogéneas) → array de objetos

### 3.2 Lógica de TEXTO (patrones de separadores)

- ✅ **Inline `Label: Value`** (L-inline-split)
- ⏳ **Multi-colon en un item** → `A: x B: y` → 2 pares
- ⏳ **Dotted leader** → `Total ....... 1.234,56€`
- ⏳ **Tab/espacio ancho** como separador implícito
- ⏳ **Línea bajo el label** → valor rellena el subrayado

### 3.3 Lógica de GEOMETRÍA (posición — LiteParse)

- ✅ **Par horizontal** — bold + regular en misma Y (L-horizontal)
- ✅ **Formulario 2-col** — detectar gutter, dos streams paralelos (L-twocol-form)
- ⏳ **Par vertical** — label arriba, value abajo en mismo X (L-vertical)
- ⏳ **Alineación X implícita** — columna sin grid
- ⏳ **Indent jerárquico** — items con misma X indentada = hijos

### 3.4 Lógica de TIPOGRAFÍA (fuente — LiteParse)

- ✅ **Bold = label, Regular = value**
- ✅ **Tamaño mayor = TITLE/section**
- ⏳ **Cambio de fuente** como frontera de campo
- ⏳ **Itálica = anotación** (no value)
- ✅ **Penalización si value < label en tamaño** (anti-falso-positivo)

### 3.5 Lógica SEMÁNTICA (etiquetas Docling)

- ✅ **`text` / `list_item`** → suprimir emitters (S6 prose)
- ✅ **`section_header`** → cortar sub-secciones
- ✅ **`table`** → ruta a emitters de tabla
- ⏳ **`caption`** → asociar a tabla anterior
- ⏳ **`formula`** → skip explícito

### 3.6 Lógica de RECONCILIACIÓN entre motores

- ✅ **Docling gana en celdas** (TableFormer fusiona multi-línea)
- ✅ **pdfplumber gana en bbox ajustado**
- ✅ **Dedup por contenido (subset), no por forma** (shadow tables)
- ✅ **Dedup por `(page, label_norm, value_norm)`**
- ⏳ **Off-page guard** — descartar `bbox.bottom > page.height`
- ⏳ **Voto cruzado** — 2 de 3 motores confirman → bonus de confianza

### 3.7 Lógica de TIPADO de VALORES (post-extracción)

- ⏳ **Fechas** → ISO 8601 (`29-03-2021` → `2021-03-29`)
- ⏳ **Importes** → `{amount: 1234.56, currency: "EUR"}`
- ⏳ **Porcentajes** → float (`5,25%` → `0.0525`)
- ⏳ **NIF/CIF/NIE** → regex con dígito de control
- ⏳ **Sí/No / casillas vacías** → boolean
- ⏳ **Valores paralelos** (TAE Sin/Con) → `[{variant, value}]`

### 3.8 Lógica de JERARQUÍA (a JSON final)

- ⏳ **Sub-sección → objeto anidado** (`{datos_personales: {...}}`)
- ⏳ **Filas homogéneas → array** (titulares, intervinientes)
- ⏳ **Mismo label en distintas páginas → array** (no sobrescribir)
- ⏳ **Document-type detection** → schema por tipo (LABORAL vs BBVA)
- ⏳ **Schema-aware mapping** — `N.I.F.` → `nif`, `Nº Procedimiento` → `procedimiento_numero`

---

## 4. Pirámide estructural desde LiteParse

LiteParse por sí solo aporta una **jerarquía geométrica** sin Docling:

```
Nivel 6  Documento        ← secuencia de páginas
Nivel 5  Región de página ← bloques + columnas combinados
Nivel 4  Columna          ← distribución bimodal de X (gutter)
Nivel 3  Bloque           ← líneas consecutivas con mismo rango X
Nivel 2  Run tipográfico  ← items consecutivos misma font/size en una línea
Nivel 1  Línea            ← items agrupados por misma Y (±tolerancia)
Nivel 0  TextItem         ← palabra + bbox + font_name + font_size  ← INPUT
```

### Reglas de agregación

| Nivel | Regla | Tolerancia típica |
|---|---|---|
| Línea | mismo `y` ± tol | ±0.2 pt (subpixel), hasta ±3 pt con acentos |
| Run | consecutivos, mismo `font_name + font_size` | exacto |
| Bloque | líneas con `left`/`right` similares | ±5 pt |
| Columna | clustering 1D de X de inicio de línea | gap > 30 pt |
| Región | bloque + gap vertical grande | Δy > 1.5 × line_height |

### Campos útiles de LiteParse (solo 4)

| Campo | Señal derivable |
|---|---|
| `font_name` | bold (`*-Bold`), itálica (`*-Italic`), familia (cambio = frontera) |
| `font_size` | bucket de jerarquía (TITLE > LABEL > BODY) |
| `text` | CAPS, dígitos, puntuación (`:`, `.`, separadores) |
| `confidence` | solo con OCR — descartar palabras dudosas |

LiteParse **no expone color** — para color usar pdfplumber `chars.non_stroking_color`.

### Implementación propuesta

Nuevo módulo `src/docomestria/structural/lite_layout.py`:

```python
def items_to_lines(items: list[LiteItem]) -> list[Line]: ...
def lines_to_runs(line: Line) -> list[Run]: ...
def lines_to_blocks(lines: list[Line]) -> list[Block]: ...
def blocks_to_columns(blocks: list[Block]) -> list[Column]: ...
```

Los emitters trabajan sobre `Line`/`Run`/`Block` en vez de `LiteItem` plano →
elimina la mitad del código geométrico actual de `candidates.py`.

---

## 5. Matriz: Capa × Motor × Feature

| Capa | LiteParse aporta | Docling aporta | pdfplumber aporta |
|---|---|---|---|
| 1. Tabla | palabras dentro del bbox (re-extracción E5) | `table_cells` con row/col/span, `column_header` flag | `find_tables()` bbox ajustado, estrategia `lines`/`text`/`explicit` |
| 2. Texto | `text` por palabra, X-coords para gaps | etiqueta `text` (aplicar split o no) | `chars` x0/x1 char-by-char |
| 3. Geometría | **PRIMARIO** — bbox exacta por palabra | bboxes de prosa (suprimir) | `page.lines`/`page.rects` (subrayados) |
| 4. Tipografía | **PRIMARIO** — `font_name`, `font_size` | mapea fuente → `section_header` | `chars.non_stroking_color` (color/itálica) |
| 5. Semántica | — | **PRIMARIO** — `DocItemLabel`, `iterate_items()` | — |
| 6. Reconciliación | verifica geometría | autoridad en celda | `page.width/height` (off-page guard), `page.lines` (confirma grid) |
| 7. Tipado | strings limpios | — | — |
| 8. Jerarquía JSON | `font_size` confirma `level` | **PRIMARIO** — `iterate_items()`, árbol `section_header` | — |

### Combinaciones aún sin explotar

1. **pdfplumber `page.lines` → confirmar bordes de tabla Docling** (bonus de confianza)
2. **pdfplumber `page.rects` → detectar checkboxes** (Sí/No con rect vacío vs marcado)
3. **LiteParse `font_size` + Docling `level`** → jerarquía JSON ponderada
4. **pdfplumber `chars.non_stroking_color`** → marcar campos editados/manuscritos
5. **LiteParse stream order + Docling reading order** → resolver ambigüedad de orden
6. **pdfplumber `extract_text(layout=True)` como tercer voto** en regiones disputadas

---

## 6. Marco estadístico — el theorem

El sistema actual (rule-based scoring) es una aproximación log-lineal de la
**inferencia bayesiana con fusión Dempster-Shafer**. Formalizar este marco
permite reemplazar tolerancias hardcoded por umbrales aprendidos.

### 6.1 El theorem central

Para cada par candidato `c = (label, value, page, bbox)`:

```
P(c es real | evidencia) ∝ P(c) × ∏ᵢ P(eᵢ | c)
                          ↑          ↑
                          prior      likelihood por motor i
```

- **Prior** `P(c)` — `BASE_SCORE[regla]` actual
- **Likelihood** — cada motor i aporta una señal independiente
- **Posterior** — el score final, banded en HIGH/MEDIUM/LOW

### 6.2 Dempster-Shafer para voto cruzado

Bayes castiga la abstención de un motor como evidencia negativa. Eso es
incorrecto cuando Docling **no opina** sobre una región (no la ve como
tabla, pero tampoco la refuta). Dempster-Shafer modela ignorancia explícita:

```
m(soporta_par)  — Docling dice "es celda 2-col"     → 0.6
m(refuta_par)   — pdfplumber dice "no hay líneas"   → 0.0
m(ignorancia)   — LiteParse no opina semánticamente → 0.4
                                                      ─────
                                                      Σ = 1.0
```

Se combinan las masas de los 3 motores con la regla de Dempster →
belief y plausibility del par. Mejor que Bayes en este caso porque los
motores son **complementarios**, no redundantes.

### 6.3 GMM / KDE para descubrir umbrales

Hoy hardcoded: `HORIZONTAL_Y_TOLERANCE_PT=3.0`, `HORIZONTAL_X_GAP_MAX_PT=300.0`,
`MULTI_LABEL_CELL_MIN_COLONS=2`.

Una **Gaussian Mixture Model** sobre los datos del benchmark da:

- **Buckets de `font_size`** → cluster en K=3 modos → TITLE/LABEL/BODY automático
- **Distribución de Y-gaps** → ajusta tolerancia por documento
- **Distribución de X-gaps en líneas con `:`** → calibra max-gap por familia de PDF

```python
from sklearn.mixture import GaussianMixture
gmm = GaussianMixture(n_components=3).fit(font_sizes.reshape(-1, 1))
title_threshold = gmm.means_.max() - gmm.covariances_.max() ** 0.5
```

### 6.4 DBSCAN para columnas y bloques

Detección de gutter de 2 columnas = clustering 1D en X.

- 1 cluster → 1 columna
- 2 clusters bien separados → formulario 2-col (dispara L-twocol-form)
- N clusters → matriz N-col

El algoritmo descubre el gutter; no hay que adivinarlo.

### 6.5 CRF / ILP para selección global

Con candidatos puntuados, la selección final es optimización en grafo:

```
Nodos:    cada PairCandidate
Aristas:  restricciones (no dos pares con mismo label/page salvo paralelos;
                          prose-region suprime; sub-section consistente)
Energía:  E = -Σ score(seleccionado) + Σ penalty(restricción violada)
```

Minimizar `E` con un **CRF (Conditional Random Field)** o **ILP** da la
mejor explicación global. Hoy `_pick_winner` resuelve esto localmente por
`dedup_key` — funciona pero ignora interacciones entre pares distintos.

### 6.6 El theorem en una frase

> **Cada par es una hipótesis. Cada motor es una fuente de evidencia con
> incertidumbre. La extracción correcta es el conjunto de pares que
> maximiza la probabilidad conjunta bajo restricciones estructurales
> (no-solape, prose-suppression, sub-section consistency).**

Formalmente: **MAP inference sobre un Markov Random Field con likelihoods
Dempster-Shafer**.

### 6.7 Traducción a código

| Hoy (heurístico) | Mañana (estadístico) |
|---|---|
| `BASE_SCORE = {...}` hardcoded | priors aprendidos del benchmark |
| `if has_colon: score += 0.10` | log-likelihood ratio del colon |
| `Y_TOLERANCE = 3.0pt` | percentil 95 de Y-gaps observados |
| `_pick_winner` dedup local | ILP global por página |
| 3 motores votan implícito | Dempster-Shafer explícito |

---

## 7. Roadmap de implementación

### v0.7.1 — quick wins (1–2 semanas)

1. **Multi-colon item splitter** — desbloquea pares en BBVA3 (capa 3.2)
2. **pdfplumber off-page shadow guard** — `bbox.bottom > page.height` (capa 3.6)
3. **L-vertical emitter** — label arriba, value abajo (capa 3.3)
4. **GMM sobre `font_size`** — reemplaza umbral hardcoded en `classify.py` (sección 6.3)
5. **Unit tests focalizados** sobre los 5 módulos de `structural/`

### v0.7.2 — refactor estructural (2–3 semanas)

6. **Módulo `lite_layout.py`** — pirámide LiteParse (sección 4)
7. **DBSCAN para detección de columnas** — simplifica L-twocol-form (sección 6.4)
8. **N-col con cabecera de columna** — matriz expansion (capa 3.1)
9. **Sub-section grouping en JSON** — capa 3.8

### v0.8.0 — Dempster-Shafer + tipado

10. **Dempster-Shafer en `scoring.py`** — reemplaza suma de bonuses (sección 6.2)
11. **Voto cruzado entre motores** — bonus de confianza (capa 3.6)
12. **Tipado de valores** — fechas, importes, %, NIF, booleanos (capa 3.7)
13. **Schema-aware mapping** — labels canónicos por tipo de doc (capa 3.8)

### v0.9.0 — optimización global

14. **CRF / ILP para selección global** — reemplaza `_pick_winner` local (sección 6.5)
15. **Document-type detection** — schema diferenciado por familia
16. **Broad ParseBench eval** — más allá de los 5 PDFs hand-picked

Cada paso es **independiente** y mejora el sistema sin reescribirlo.

---

## 8. Estrategia de testing

### 8.1 Tres niveles de prueba

| Nivel | Qué prueba | Velocidad | Cuándo correr |
|---|---|---|---|
| **Unit** (`tests/test_structural_*.py`) | función pura, fixtured input | ms | cada save |
| **Gold** (`tests/test_structural_gold.py`) | extracción E2E sobre 1 PDF de referencia | s | pre-commit |
| **Regression** (5 PDFs Azure DI) | precision/recall vs baseline | 10–30s | pre-commit + pre-PR |

### 8.2 Cobertura objetivo por módulo

| Módulo | Cobertura mínima | Estado actual |
|---|---|---|
| `structural/models.py` | implícita | ✅ |
| `structural/classify.py` | 85% línea | ❌ ninguno focalizado |
| `structural/structure.py` | 85% línea | ❌ ninguno focalizado |
| `structural/candidates.py` | 85% línea | ❌ ninguno focalizado |
| `structural/scoring.py` | 90% línea | ❌ ninguno focalizado |
| `structural/extractor.py` | 70% línea | parcial vía gold |

### 8.3 Patrón de fixtures (sin PDF I/O)

```python
def make_lite(text, x, y, w=80, h=10, page=1, font="Helvetica", size=10.0):
    return LiteItem(
        text=text,
        bbox=BBox(x=x, y=y, w=w, h=h),
        font_name=font, font_size=size, page=page,
    )

def make_classified(text, x, y, kind=ItemKind.LABEL, **kw):
    return ClassifiedItem(item=make_lite(text, x, y, **kw), kind=kind)

def make_table(page=1, top=100, bottom=200, left=50, right=400, cells=None):
    return Table(
        page=page,
        bbox=BBox(x=left, y=top, w=right-left, h=bottom-top),
        cells=cells or [],
        subsections=(),
    )
```

Helpers en `tests/conftest.py`. Nunca duplicar entre tests.

### 8.4 Qué probar por módulo

**`scoring.py`** (máxima prioridad — lógica pura)
- `score_one`: base × bonus × penalty con scores esperados
- `confidence_for`: valores frontera (justo bajo/sobre umbrales)
- `_dedup_key`: collapse de whitespace + lowercase
- `_pick_winner`: empate y precedencia entre reglas
- `resolve_pairs`: dedup + scoring E2E sobre lista hand-built

**`candidates.py`** (cada emitter)
- Caso positivo mínimo → 1 PairCandidate esperado
- Caso de supresión (prose region o tabla) → 0 candidatos
- Caso frontera (tolerancia justa vs justo fuera)
- Multi-page (regiones de página 1 no afectan página 2)
- `_is_multi_label_form`: ≥2 colons en una fila dispara, 0 no

**`structure.py`**
- Shadow-table dedup por contenido subset (no por forma)
- Off-page guard cuando se implemente
- Sub-section split: header + body bbox → `SubSection` correcto
- Prose-region collection: `text`/`list_item` contribuyen, `caption`/`formula` no

**`classify.py`**
- Umbral de `font_size` → TITLE
- Bold-font + `:` → LABEL
- Items en tabla → kind apropiado

**`extractor.py`** (focalizado, no E2E)
- Orquestación: monkeypatch motores, verificar emitters invocados
- Resultado determinista con fake stream

### 8.5 Test de regresión — los 5 PDFs

Baseline cacheada en `.regression/baseline.json` con pares HIGH por PDF.

```bash
# Setup baseline (solo una vez por release):
python3 scripts/build_regression_baseline.py

# Antes de cada commit:
for stem in azuredemo__LABORAL azuredemo__PATRIMONIAL azuredemo__BBVA3 \
            azuredemo__BBVA4 azuredemo__BBVA5; do
    python3 scripts/validate_extract.py "$stem" --json > /tmp/regnow_${stem}.json
done

python3 scripts/diff_vs_baseline.py /tmp/regnow_*.json
```

Output esperado:

```
azuredemo__LABORAL        ✅  15 HIGH (baseline 15)
azuredemo__PATRIMONIAL    ✅  36 HIGH (baseline 36)
azuredemo__BBVA3          ✅  21 HIGH (baseline 21)
azuredemo__BBVA4          ❌  31 HIGH (baseline 34)  — lost: TAE, Comisión apertura, Cuota Sin Seguro
azuredemo__BBVA5          ✅  25 HIGH (baseline 25)

VERDICT: BLOCK COMMIT — 3 HIGH-confidence pairs lost on BBVA4
```

### 8.6 Mapping síntoma → área de código

| Pérdida observada | Causa probable |
|---|---|
| HIGH → ausente (era D-2col) | Docling no detecta tabla — `structure.py` table fusion |
| HIGH → ausente (era L-twocol-form) | Heurística de columna — `candidates.py` E5 |
| HIGH → MEDIUM, score cae ~0.05–0.15 | Cambio de bonus/penalty — `scoring.py` |
| Múltiples labels perdidos en todos los PDFs | Dedup sobre-colapsa — `scoring._dedup_key` |
| Pérdida solo en PDF multi-página | Bug de page-blind suppression |
| Pérdida en regiones prose-heavy | S6 supresión sobre-celosa |

### 8.7 Métricas de calidad

Por PDF y por tipo de extracción:

```
Precision = pairs_correctos / pairs_emitidos
Recall    = pairs_correctos / pairs_en_ground_truth
F1        = 2 × P × R / (P + R)
```

Banded por confidence:
- **HIGH**: precision objetivo ≥ 95%
- **MEDIUM**: precision objetivo ≥ 80%
- **LOW**: precision objetivo ≥ 50% (solo para debugging)

Ground truth en `data/parsebench/ground_truth/<stem>.json`.

---

## 9. Agentes Claude Code disponibles

7 agentes en `.claude/agents/` cubriendo el ciclo completo:

### Especialistas de motor
- **`docling-expert`** — DocumentConverter, TableFormer, `iterate_items`, prov/bbox
- **`liteparse-expert`** — `ParseResult`/`ParsedPage`/`TextItem` schema, geometría
- **`pdfplumber-expert`** — `find_tables`, estrategias, `crop`/`within_bbox`

### Workflow
- **`regression-runner`** — diff vs baseline en los 5 PDFs, verdict OK/BLOCK
- **`bbox-geometry-debugger`** — page-blind suppression, shadow guards, drift
- **`emitter-designer`** — nuevos emitters en `candidates.py`
- **`extraction-test-writer`** — unit tests focalizados por módulo

Invocar via `Agent(subagent_type=<nombre>)`.

---

## 10. Memoria persistente (Claude)

Entries en `~/.claude/projects/-Users-carlos-Edelwyss-Projects-docomestria/memory/`:

- `[[project_state]]` — repo y rama
- `[[docling_cell_fusion]]` — TableFormer fusiona multi-línea bien
- `[[per_page_bbox_suppression]]` — siempre scoped por página
- `[[dedup_by_text]]` — dedup por contenido normalizado, no bbox
- `[[docling_prose_regions]]` — `text`/`list_item` bboxes ready-made
- `[[shadow_tables]]` — match por subset, no por forma
- `[[azure_di_benchmark]]` — los 5 PDFs como contrato de regresión

---

## 11. Referencias cruzadas

- **Validación empírica:** `.planning/structural-extraction-strategy.md`
- **Handoff de release:** `.planning/structural-extraction-handoff.md` y `.remember/remember.md`
- **Código:** `src/docomestria/structural/{models,classify,structure,candidates,scoring,extractor}.py`
- **Scripts:** `scripts/validate_extract.py`, `scripts/run_engines_on_sample.py`, `scripts/build_comparison_view.py`
- **Datos:** `data/parsebench/` (gitignored)
- **Tests:** `tests/test_structural_*.py` (la mayoría pendientes)

---

## 12. Glosario

| Término | Significado |
|---|---|
| **TableFormer** | Modelo de Docling para estructura de tablas |
| **`DocItemLabel`** | Enum de Docling: text, list_item, section_header, table, picture, caption, formula |
| **`BBox`** | Bounding box top-left: `(x, y, w, h)` |
| **`LiteItem`** | Palabra de LiteParse con bbox + font_name + font_size + page |
| **`PairCandidate`** | Par candidato pre-scoring con `rule` (qué emitter) y `evidence` |
| **`Pair`** | Par final post-scoring con `confidence` (HIGH/MEDIUM/LOW) |
| **Shadow table** | Tabla pdfplumber que duplica o fragmenta una tabla Docling |
| **S6 / S7** | Etapas históricas: S6 = prose suppression, S7 = two-col form emitter |
| **MAP** | Maximum a Posteriori — hipótesis más probable |
| **MRF / CRF** | Markov / Conditional Random Field — grafo probabilístico |
| **GMM** | Gaussian Mixture Model — clustering con k modos gaussianos |
| **DBSCAN** | Density-Based Spatial Clustering — clustering sin k pre-fijado |
| **Dempster-Shafer** | Teoría de evidencia que maneja ignorancia explícita |
