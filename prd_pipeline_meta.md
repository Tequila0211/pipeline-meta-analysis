# PRD — Pipeline local para extracción de datos y metaanálisis (PDFs digitales) con verificación humana

## 0. Resumen ejecutivo
Se requiere un **pipeline reproducible, local y de rápida implementación**, capaz de procesar ~300 PDFs **digitales** (texto seleccionable) ya descargados (que se alamcenaran en la carpeta pdfs despues de la construccion del pipeline) y un **manifest en Excel** (se incluira el archivo valido una vez construido el pipeline)de resultados de búsqueda.

El objetivo es:
- **Triage** (identificar estudios “extractables”).
- **Extracción estructurada** (JSON) de variables para metaanálisis con **evidencia por campo** (página + cita/recorte).
- **Validación automática** (schema + reglas) y **revisión humana** en UI (Streamlit).
- Exportación a **datasets meta-ready** para análisis en R (metafor) y matrices de evidencia.

Restricciones:
- **Costo cero / free tier**.
- Minimizar alucinaciones: política **no-guessing** (si no hay evidencia → `null`).
- PDFs ya descargados con nombres heterogéneos (autores+año). No se renombrarán forzosamente.

---

## 1. Objetivos y no-objetivos

### 1.1 Objetivos (Must)
1) Importar `manifest.xlsx` y guiar al usuario para filtrar por `DT` (p.ej. ARTICLE/REVIEW/PROCEEDINGS/etc.), generando un `references_filtered.csv` y un `run_config.yaml` reproducible.
2) Indexar PDFs locales en `pdfs/` sin depender del nombre del archivo, asignando un `doc_id` estable.
3) Extraer texto por página y persistirlo (`pages_text/`) para reanudar sin recomputar.
4) Implementar triage (sin IA y con IA para casos dudosos) para priorizar extracción.
5) Ejecutar extracción con IA (Gemini) usando RAG por páginas y producir `extractions_raw/` + `extractions_valid/`.
6) Validación automática con reportes y reintentos controlados (máx. 1 reintento por error).
7) Fallback selectivo a imágenes (tablas/figuras/páginas densas) con persistencia en `pages_img/`.
8) UI Streamlit para revisión, edición, aprobación y auditoría de cambios.
9) Exportación a `exports/` de datasets listos para R + script `09_meta.R`.
10) Orquestación por scripts con ejecución por pasos y modo **worker** para procesamiento en paralelo con la revisión humana.

### 1.2 No-objetivos (Won’t para MVP)
- Conectores a bases (Scopus/WoS/etc.) o búsquedas dentro de la app.
- OCR para escaneados (no aplica: PDFs digitales).
- Frontend web completo (Next.js) o multiusuario robusto (se asume 1 usuario o colaboración mínima).
- Digitización automática precisa de curvas complejas (si hace falta, se hará manual con QA).

---

## 2. Contexto científico (para el agente)
Tema: estrategias de retrofit pasivo/pasivo-híbrido para resiliencia térmica y desempeño bajo calor extremo/overheating en edificios existentes.

Datos clave a extraer:
- Comparación baseline vs retrofit (mismo activo/modelo preferido).
- Outcomes primarios alternativos:
  - **A:** overheating/discomfort hours / degree-hours.
  - **B:** temperatura interior/operativa (ΔT).
- Moderadores esenciales:
  - Tipo de comparador (fuerte/débil) + nivel de coincidencia de condiciones de contorno.
  - Tipo de edificio, clima, HVAC/mixed-mode.
  - Envolvente y operación: **U-values baseline y retrofit**, g-value/SHGC, ventilación (ACH), etc.

Política acordada:
- **Análisis principal**: solo comparadores “fuertes” (same-asset controlado) con `boundary_match_level` high/medium.
- Comparadores “débiles”: se almacenan para sensibilidad/evidence-matrix.

---

## 3. Arquitectura del sistema (MVP)

### 3.1 Estructura de repo / carpetas
```
project/
  manifest.xlsx
  references_filtered.csv
  run_config.yaml
  run_log.md
  pdfs/
  pdf_index.csv
  state.sqlite
  pages_text/
    {doc_id}/
      page_000.txt
      page_001.txt
      pages_meta.json
  pages_img/
    {doc_id}/
      page_012.png
      page_012.meta.json
  snippets/
    {doc_id}/
      retrieval_{timestamp}.json
  extractions_raw/
    {doc_id}.json
  extractions_valid/
    {doc_id}.json
  extractions_approved/
    {doc_id}.json
  validation_reports/
    {doc_id}.json
  audit/
    audit_log.jsonl
  exports/
    unified_outcomes.csv
    envelope_components.csv
    operation_profiles.csv
    comparisons.csv
    references.csv
  scripts/
    01_manifest_wizard.py
    02_index_pdfs.py
    03_pages_text.py
    04_triage.py
    05_extract.py
    06_validate.py
    07_worker.py
    08_export.py
  app_streamlit.py
  09_meta.R
```

### 3.2 Componentes
- **CLI/Wizard**: selección interactiva de filtros y configuración.
- **Indexer**: hashing + extracción de DOI/título (si posible) + matching con manifest.
- **Pager**: extracción de texto por página (cache persistente).
- **Retriever**: selección de páginas candidatas (queries + BM25 simple).
- **Triage**: heurístico y IA (lite) para casos dudosos.
- **Extractor**: IA (Flash) con salida JSON schema-valid y evidencia por campo.
- **Validator**: schema + evidencia + plausibilidad + reintento controlado.
- **Image fallback**: render de páginas específicas a PNG y re-extracción multimodal.
- **State/Worker**: motor batch asíncrono local (loop) que avanza estados.
- **Streamlit Review UI**: edición/aprobación con auditoría.
- **Export & R**: generación de CSVs y ejecución de R.

---

## 4. Requerimientos funcionales (RF)

### RF-01 Wizard de manifest y filtros reproducibles
**Entrada**: `manifest.xlsx`.

**Comportamiento**:
1) Detectar columna `DT` y listar valores únicos + conteos.
2) Pedir al usuario:
   - cuáles `DT` incluir
   - cuáles excluir
3) Generar:
   - `references_filtered.csv`
   - `run_config.yaml` (decisiones + rutas + fecha)
   - `run_log.md` (tabla de conteos + selección)

**Criterio de aceptación**:
- El wizard no requiere editar código.
- El `run_config.yaml` permite re-ejecutar el mismo filtro de forma determinista.

---

### RF-02 Indexado de PDFs y asignación `doc_id`
**Entrada**: carpeta `pdfs/`.

**Comportamiento**:
- Calcular `doc_id = sha256(bytes)`.
- Crear/actualizar `pdf_index.csv` con:
  - `doc_id`, `pdf_path`, `file_size`, `sha256`, `n_pages` (si disponible), `extracted_doi`, `extracted_title`, `matched_reference_id`, `match_confidence`, `needs_manual_match`.

**Criterio de aceptación**:
- El pipeline no depende del nombre del PDF.
- Si un PDF no cambia, su `doc_id` permanece igual.

---

### RF-03 Texto por página (cache)
**Entrada**: `pdfs/{any}.pdf`.

**Comportamiento**:
- Extraer texto por página y guardar en `pages_text/{doc_id}/page_XXX.txt`.
- Guardar `pages_meta.json` (n páginas, tool/version, timestamp).
- Idempotencia: si existe y coincide hash/version, no recomputar.

**Criterio de aceptación**:
- El pipeline puede detenerse y reanudarse sin repetir este paso.

---

### RF-04 Triage sin IA
**Entrada**: `pages_text/`.

**Comportamiento**:
- Detectar señales mínimas (regex/keywords) de:
  - intervención/retrofit
  - outcomes A/B
  - estándares (TM52/ASHRAE/EN)
  - términos de U-value/g-value/SHGC
- Asignar `triage_label`:
  - `extractable` / `maybe` / `no-data`

**Criterio de aceptación**:
- Reduce el número de llamadas IA descartando casos claramente irrelevantes.

---

### RF-05 Triage con IA (solo “maybe”)
**Modelo**: Gemini Flash-Lite (o equivalente barato) configurado.

**Entrada**: páginas top-k candidatas.

**Salida**: JSON mínimo con:
- `has_baseline_retrofit` (bool)
- `has_outcome_A` (bool)
- `has_outcome_B` (bool)
- `comparator_type_guess` (enum)
- `needs_images` (bool)

**Criterio de aceptación**:
- Solo se aplica a “maybe”.
- No produce texto libre; solo JSON.

---

### RF-06 Extracción principal con IA (JSON + evidencia)
**Modelo**: Gemini 2.5 Flash (o equivalente).

**Entrada**:
- `run_config.yaml`
- top-k páginas (RAG por página)
- schema JSON (ver Sección 6)

**Salida**:
- `extractions_raw/{doc_id}.json` (output IA)

**Reglas estrictas**:
- Cada campo numérico debe traer `evidence: {page, quote}` o `bbox` si viene de imagen.
- Si no hay evidencia explícita en la entrada → `null`.
- No inferir unidades; si falta unidad explícita → `null`.

---

### RF-07 Validación automática + reintento controlado
**Entrada**: `extractions_raw/{doc_id}.json`.

**Validaciones**:
A) Schema (JSON válido, tipos, enums, requeridos).
B) Evidencia: cada numérico con `page` y `quote/bbox`.
C) Consistencia/plausibilidad:
- unidades válidas
- baseline y retrofit compatibles
- rangos (U>0, g_value 0–1, etc.)
- coherencia comparador (fuerte vs boundary level)

**Acción si falla**:
- generar `validation_reports/{doc_id}.json`
- ejecutar 1 reintento con prompt “corrige solo estos errores” usando SOLO la evidencia ya aportada.

**Salida**:
- si pasa: `extractions_valid/{doc_id}.json`
- si falla: status `needs_review` o `needs_images`.

---

### RF-08 Fallback a imágenes (selectivo, persistente)
**Criterios para activar**:
- `needs_images=true` por:
  - nulls críticos (baseline/retrofit en outcome primario)
  - señales de tablas/figuras densas (páginas con “Table/Figure”)

**Comportamiento**:
- Renderizar páginas seleccionadas a PNG (300–400 DPI) en `pages_img/{doc_id}/page_XXX.png`.
- Guardar meta `page_XXX.meta.json` (dpi, timestamp).
- Re-llamar a IA en modo multimodal con la imagen + schema (solo para completar campos faltantes o corregir).

**Salida**:
- actualización en `extractions_valid/{doc_id}.json` (nueva versión) manteniendo auditoría.

---

### RF-09 UI de revisión humana (Streamlit)
**Objetivo**: permitir revisión rápida, edición y aprobación con evidencia.

**Layout**:
- Izquierda: visor PDF (o página renderizada) + navegación por páginas + lista de evidencias clicables.
- Derecha: formularios editables (Study/Building/Scenario/Comparison/Conditions/Outcomes) y tabla de mediciones.

**Acciones**:
- Aprobar documento (`approved`).
- Editar campos (agregar/eliminar/ajustar mediciones).
- Marcar “re-extract” (volver a extracción) o “reject”.

**Auditoría**:
- No sobrescribir raw.
- Guardar aprobado en `extractions_approved/{doc_id}.json`.
- Registrar diffs en `audit/audit_log.jsonl`.

---

### RF-10 Exportación a CSV meta-ready
**Entrada**: `extractions_approved/` (preferido) o `extractions_valid/` (fallback).

**Salida**:
- `exports/unified_outcomes.csv`
- `exports/envelope_components.csv`
- `exports/operation_profiles.csv`
- `exports/comparisons.csv`
- `exports/references.csv`

**Criterio**:
- Estructura estable y documentada.

---

### RF-11 Ejecución de R (metaanálisis)
**Archivo**: `09_meta.R` dentro del repo.

**Comportamiento**:
- Leer `exports/unified_outcomes.csv`.
- Filtrar para análisis principal:
  - `eligible_primary==true` y `is_primary==true`.
- Correr modelos (metafor) y exportar:
  - forest/funnel (si aplica)
  - tablas summary

---

## 5. Orquestación, estados y paralelización

### 5.1 Estado (SQLite)
Archivo: `state.sqlite`.

Tabla `docs`:
- `doc_id` TEXT PK
- `pdf_path` TEXT
- `status` TEXT
- `updated_at` DATETIME
- `notes` TEXT
- `matched_reference_id` TEXT NULL
- `triage_label` TEXT NULL
- `needs_images` INTEGER 0/1
- `lock_owner` TEXT NULL
- `lock_ts` DATETIME NULL

Estados recomendados:
- `pending`
- `indexed`
- `paged`
- `triaged_extractable`
- `triaged_maybe`
- `triaged_no_data`
- `extracted_raw`
- `validated_ok`
- `needs_images`
- `validated_with_images`
- `in_review`
- `approved`
- `rejected`

### 5.2 Worker
Script: `scripts/07_worker.py`.

**Loop**:
- busca el siguiente doc con `status in (pending,indexed,paged,triaged_extractable,triaged_maybe,needs_images)`
- ejecuta el siguiente paso necesario
- actualiza estado

**Concurrencia**:
- 1 worker por defecto.
- opcional: multiworker con locks de fila.

### 5.3 Revisión en paralelo
Streamlit lista `status in (validated_ok, validated_with_images, in_review)`.

Al abrir un doc:
- set `status=in_review` + `lock_owner`.

Al aprobar:
- set `status=approved`.

---

## 6. Esquema de datos (JSON) — extracción (A y B) — **robusto multi-unidad/multi-paquete/multi-escenario**

### 6.1 Principios
- Salida única por doc: un JSON con secciones **indexadas por IDs** para evitar ambigüedad.
- Soporta:
  - múltiples **unidades** (edificios/modelos/zonas)
  - múltiples **condiciones** (baseline y varios paquetes retrofit)
  - múltiples **escenarios**
  - múltiples **comparaciones** (unidad × escenario × baseline × retrofit)
  - múltiples **mediciones** (A/B) enlazadas a `comparison_id`
- Cada valor numérico debe tener evidencia.

### 6.2 Entidades y relaciones
#### 6.2.1 `units[]`
Lista de unidades modeladas dentro del estudio.
- `unit_id` (string corto; p.ej. `U1`, `Bldg_A`, `School_2`)
- `unit_type`: `building|zone|model|other`
- `unit_label` (texto)
- `unit_overrides` (opcional; p.ej. building_type específico si difiere)

Regla:
- Si el paper no distingue unidades, crear una por defecto `U1`.

#### 6.2.2 `conditions[]`
Lista de condiciones reutilizables.
- `condition_id` (string corto; p.ej. `C0`, `C1`, `C2`)
- `condition_role`: `baseline|retrofit`
- `package_label`
- `strategy_family[]`, `strategy_items[]`, `envelope_components[]`, `operation_profile`

Regla:
- Debe existir al menos una condición `baseline`.
- Puede haber múltiples `retrofit`.

#### 6.2.3 `scenarios[]`
Lista de escenarios.
- `scenario_id` (string corto; `S1`, `S2`…)
- `scenario_label`, `heat_context`, `weather_source`, `year_context`, `time_window`

Regla:
- Si solo hay un escenario, usar `S1`.

#### 6.2.4 `comparisons[]`
Objeto clave para integridad.
- `comparison_id` (string corto; `K1`, `K2`…)
- `unit_id` (FK a `units[].unit_id`)
- `scenario_id` (FK a `scenarios[].scenario_id`)
- `baseline_condition_id` (FK a `conditions[].condition_id`)
- `retrofit_condition_id` (FK a `conditions[].condition_id`)
- `comparator_type`, `boundary_match_level`, `boundary_notes`

Regla:
- Cada comparación debe apuntar a 1 baseline y 1 retrofit.
- `eligible_primary` se deriva a partir del comparador (ver Anexo B).

#### 6.2.5 `measurements[]`
Cada medición se liga a una comparación concreta.
- `comparison_id` (FK a `comparisons[].comparison_id`)
- Luego campos específicos de Outcome A o B.

Regla:
- No se permiten mediciones sin `comparison_id`.

### 6.3 Medidas
Cada medición tiene:
- `comparison_id`
- `outcome_family`: `A` o `B`
- `is_primary`: bool
- `primary_rule_applied`: enum
- `baseline_value`, `retrofit_value`, `unit`
- `variance` opcional
- `evidence`: `{page, quote}` o `{page, bbox}`

### 6.4 Comparador y elegibilidad
Campos en cada `comparison`:
- `comparator_type`
- `boundary_match_level`

`eligible_primary` se deriva en export (Anexo B).

---

## 7. IA: configuración y políticas anti-alucinación

### 7.1 Modelos
- Triage IA: `flash-lite` (si disponible) o `flash` con prompt corto.
- Extracción: `flash`.

### 7.2 Inputs mínimos
- Nunca pasar el PDF completo al modelo.
- Pasar solo top-k páginas (texto) y/o imágenes puntuales.

### 7.3 Reglas
- **No-guessing**: si no está explícito → `null`.
- **Evidencia obligatoria** por cada valor numérico.
- Max 1 reintento de corrección.

---

## 8. Requerimientos no funcionales (RNF)

### RNF-01 Reproducibilidad
- `run_config.yaml` registra filtros y decisiones.
- Idempotencia por cachés (pages_text/pages_img).
- Logs y auditoría.

### RNF-02 Rendimiento
- Procesamiento por lotes.
- Worker no bloquea revisión.

### RNF-03 Seguridad / privacidad
- Clave API de Gemini nunca en repo.
- Uso de `.env` local.
- No subir PDFs a terceros fuera del llamado IA; solo páginas/fragmentos necesarios.

### RNF-04 Calidad
- Validación automática estricta.
- UI para corrección humana.

---

## 9. Criterios de aceptación globales
1) Wizard produce `references_filtered.csv` + `run_config.yaml` sin editar código.
2) Pipeline indexa PDFs sin renombrar y genera `doc_id` estable.
3) Cache por páginas permite reanudar sin recomputar.
4) Worker procesa en batch y Streamlit revisa en paralelo.
5) JSON extraído cumple schema; cada número tiene evidencia.
6) Export genera CSV meta-ready y `09_meta.R` corre al menos un modelo base.


---

## 10. Riesgos y mitigaciones
- **Cuotas/rate limit**: minimizar tokens con RAG; batch nocturno; triage fuerte sin IA.
- **Tablas como imagen**: fallback multimodal; si no fiable, marcar para revisión manual.
- **Heterogeneidad extrema**: garantizar captura de moderadores (U-values, HVAC, comparador).

---

## 11. Entregables del MVP
- Scripts `01`–`08`, `app_streamlit.py`, `09_meta.R`.
- JSON schema(s) de extracción.
- `README.md` con comando por paso y modo worker.
- `run_config.yaml` y logs.

---

## 1. Instrucciones para Antigravity (lo que debe construir)
1) Crear repo con estructura exacta (Sección 3.1).
2) Implementar scripts por RF-01 a RF-11.
3) Implementar `state.sqlite` + worker loop.
4) Implementar Streamlit con layout izquierda PDF / derecha datos + edición + aprobación.
5) Implementar validación estricta + 1 reintento.
6) Exportar CSVs y ejecutar `09_meta.R`.

## ANEXO A — Esquemas JSON (core + outcomes)

### A.0 Ubicación y nombres de archivos
Crear carpeta:
```
project/schemas/
  core_extraction.schema.json
  outcomeA_measurement.schema.json
  outcomeB_measurement.schema.json
```

> Nota: estos esquemas son el contrato principal entre extracción IA, validación y UI.

---

### A.1 `schemas/core_extraction.schema.json`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "core_extraction.schema.json",
  "title": "Core extraction schema (robust multi-unit/multi-package/multi-scenario)",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "project_id",
    "reference_id",
    "doc_id",
    "study",
    "building",
    "units",
    "scenarios",
    "conditions",
    "comparisons",
    "measurements"
  ],
  "properties": {
    "schema_version": { "type": "string", "const": "1.0.0" },
    "project_id": { "type": "string" },
    "reference_id": { "type": "string" },
    "doc_id": { "type": "string" },

    "study": {
      "type": "object",
      "additionalProperties": false,
      "required": ["study_type", "study_design"],
      "properties": {
        "study_type": { "enum": ["simulation", "empirical", "mixed"] },
        "study_design": { "type": "string" },
        "notes": { "type": "string" }
      }
    },

    "building": {
      "type": "object",
      "additionalProperties": false,
      "required": ["building_type", "location_country", "hvac_status"],
      "properties": {
        "building_type": {
          "enum": ["residential", "school", "educational", "public", "office", "healthcare", "other"]
        },
        "building_subtype": { "type": "string" },
        "location_country": { "type": "string" },
        "location_city": { "type": "string" },
        "climate_class": { "type": "string" },
        "hvac_status": { "enum": ["none", "mixed_mode", "full_mechanical", "unknown"] },
        "zone_definition": { "type": "string" }
      }
    },

    "units": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["unit_id", "unit_type", "unit_label"],
        "properties": {
          "unit_id": { "type": "string" },
          "unit_type": { "enum": ["building", "zone", "model", "other"] },
          "unit_label": { "type": "string" },
          "unit_overrides": { "type": "object" },
          "evidence": { "$ref": "#/definitions/evidence_anchor" }
        }
      }
    },

    "scenarios": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["scenario_id", "scenario_label", "heat_context", "time_window"],
        "properties": {
          "scenario_id": { "type": "string" },
          "scenario_label": { "type": "string" },
          "heat_context": { "enum": ["typical_summer", "heatwave_event", "extreme_heat_scenario", "annual"] },
          "weather_source": { "type": "string" },
          "year_context": { "type": "string" },
          "time_window": {
            "type": "object",
            "additionalProperties": false,
            "required": ["time_window_type", "definition", "occupied_hours_rule"],
            "properties": {
              "time_window_type": { "enum": ["heatwave_window", "seasonal_summer", "annual", "other"] },
              "definition": { "type": "string" },
              "occupied_hours_rule": { "type": "string" }
            }
          },
          "evidence": { "$ref": "#/definitions/evidence_anchor" }
        }
      }
    },

    "conditions": {
      "type": "array",
      "minItems": 2,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["condition_id", "condition_role", "package_label", "strategy_family"],
        "properties": {
          "condition_id": { "type": "string" },
          "condition_role": { "enum": ["baseline", "retrofit"] },
          "package_label": { "type": "string" },
          "strategy_family": {
            "type": "array",
            "minItems": 1,
            "items": {
              "enum": [
                "shading",
                "natural_ventilation",
                "solar_control",
                "cool_roof",
                "thermal_insulation",
                "pcm",
                "green_roof",
                "green_facade",
                "thermal_mass",
                "hybrid",
                "other"
              ]
            }
          },
          "strategy_items": {
            "type": "array",
            "items": { "$ref": "#/definitions/strategy_item" }
          },
          "envelope_components": {
            "type": "array",
            "items": { "$ref": "#/definitions/envelope_component" }
          },
          "operation_profile": { "$ref": "#/definitions/operation_profile" }
        }
      }
    },

    "comparisons": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "comparison_id",
          "unit_id",
          "scenario_id",
          "baseline_condition_id",
          "retrofit_condition_id",
          "comparator_type",
          "boundary_match_level"
        ],
        "properties": {
          "comparison_id": { "type": "string" },
          "unit_id": { "type": "string" },
          "scenario_id": { "type": "string" },
          "baseline_condition_id": { "type": "string" },
          "retrofit_condition_id": { "type": "string" },
          "comparator_type": {
            "enum": [
              "controlled_simulation_same_model",
              "before_after_same_building_controlled",
              "before_after_same_building_uncontrolled",
              "with_without_different_buildings",
              "other"
            ]
          },
          "boundary_match_level": { "enum": ["high", "medium", "low", "unknown"] },
          "boundary_notes": { "type": "string" }
        }
      }
    },

    "measurements": {
      "type": "array",
      "minItems": 1,
      "items": {
        "oneOf": [
          { "$ref": "outcomeA_measurement.schema.json" },
          { "$ref": "outcomeB_measurement.schema.json" }
        ]
      }
    }
  },

  "definitions": {
    "evidence_anchor": {
      "type": "object",
      "additionalProperties": false,
      "required": ["page"],
      "properties": {
        "page": { "type": "integer", "minimum": 0 },
        "quote": { "type": "string" },
        "bbox": {
          "type": "object",
          "additionalProperties": false,
          "required": ["x1", "y1", "x2", "y2"],
          "properties": {
            "x1": { "type": "number", "minimum": 0, "maximum": 1 },
            "y1": { "type": "number", "minimum": 0, "maximum": 1 },
            "x2": { "type": "number", "minimum": 0, "maximum": 1 },
            "y2": { "type": "number", "minimum": 0, "maximum": 1 }
          }
        }
      }
    },

    "variance": {
      "type": "object",
      "additionalProperties": false,
      "required": ["type"],
      "properties": {
        "type": { "enum": ["sd", "se", "ci95", "none"] },
        "value": { "type": "number" },
        "n": { "type": "integer", "minimum": 1 }
      }
    },

    "strategy_item": {
      "type": "object",
      "additionalProperties": false,
      "required": ["family"],
      "properties": {
        "family": {
          "enum": [
            "shading",
            "natural_ventilation",
            "solar_control",
            "cool_roof",
            "thermal_insulation",
            "pcm",
            "green_roof",
            "green_facade",
            "thermal_mass",
            "hybrid",
            "other"
          ]
        },
        "subtype": { "type": "string" },
        "intensity_fields": { "type": "object" },
        "evidence": { "$ref": "#/definitions/evidence_anchor" }
      }
    },

    "envelope_component": {
      "type": "object",
      "additionalProperties": false,
      "required": ["component_type"],
      "properties": {
        "component_type": { "enum": ["roof", "external_wall", "floor", "window", "door", "other"] },
        "u_value_W_m2K": { "type": "number" },
        "shgc_or_g_value": { "type": "number", "minimum": 0, "maximum": 1 },
        "wwr": { "type": "number", "minimum": 0, "maximum": 1 },
        "notes": { "type": "string" },
        "evidence": { "$ref": "#/definitions/evidence_anchor" }
      }
    },

    "operation_profile": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "ventilation_type": { "enum": ["natural", "mechanical", "mixed", "unknown"] },
        "ventilation_rate": { "type": "number" },
        "ventilation_rate_unit": { "type": "string" },
        "infiltration_rate_ach": { "type": "number" },
        "setpoint_cooling_C": { "type": "number" },
        "window_opening_rule": { "type": "string" },
        "internal_gains": { "type": "number" },
        "internal_gains_unit": { "type": "string" },
        "occupancy_profile": { "enum": ["measured", "standard", "assumed", "unknown"] },
        "evidence": { "$ref": "#/definitions/evidence_anchor" }
      }
    }
  }
}
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "core_extraction.schema.json",
  "title": "Core extraction schema (A/B outcomes)",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "project_id",
    "reference_id",
    "doc_id",
    "study",
    "building",
    "scenario",
    "baseline_condition",
    "retrofit_condition",
    "comparison",
    "measurements"
  ],
  "properties": {
    "schema_version": { "type": "string", "const": "1.0.0" },
    "project_id": { "type": "string" },
    "reference_id": { "type": "string" },
    "doc_id": { "type": "string" },

    "study": {
      "type": "object",
      "additionalProperties": false,
      "required": ["study_type", "study_design"],
      "properties": {
        "study_type": { "enum": ["simulation", "empirical", "mixed"] },
        "study_design": { "type": "string" },
        "notes": { "type": "string" }
      }
    },

    "building": {
      "type": "object",
      "additionalProperties": false,
      "required": ["building_type", "location_country", "hvac_status"],
      "properties": {
        "building_type": {
          "enum": ["residential", "school", "educational", "public", "office", "healthcare", "other"]
        },
        "building_subtype": { "type": "string" },
        "location_country": { "type": "string" },
        "location_city": { "type": "string" },
        "climate_class": { "type": "string" },
        "hvac_status": { "enum": ["none", "mixed_mode", "full_mechanical", "unknown"] },
        "zone_definition": { "type": "string" }
      }
    },

    "scenario": {
      "type": "object",
      "additionalProperties": false,
      "required": ["scenario_label", "heat_context", "time_window"],
      "properties": {
        "scenario_label": { "type": "string" },
        "heat_context": { "enum": ["typical_summer", "heatwave_event", "extreme_heat_scenario", "annual"] },
        "weather_source": { "type": "string" },
        "year_context": { "type": "string" },
        "time_window": {
          "type": "object",
          "additionalProperties": false,
          "required": ["time_window_type", "definition", "occupied_hours_rule"],
          "properties": {
            "time_window_type": { "enum": ["heatwave_window", "seasonal_summer", "annual", "other"] },
            "definition": { "type": "string" },
            "occupied_hours_rule": { "type": "string" }
          }
        }
      }
    },

    "baseline_condition": { "$ref": "#/definitions/condition" },
    "retrofit_condition": { "$ref": "#/definitions/condition" },

    "comparison": {
      "type": "object",
      "additionalProperties": false,
      "required": ["comparator_type", "boundary_match_level"],
      "properties": {
        "comparator_type": {
          "enum": [
            "controlled_simulation_same_model",
            "before_after_same_building_controlled",
            "before_after_same_building_uncontrolled",
            "with_without_different_buildings",
            "other"
          ]
        },
        "boundary_match_level": { "enum": ["high", "medium", "low", "unknown"] },
        "boundary_notes": { "type": "string" }
      }
    },

    "measurements": {
      "type": "array",
      "minItems": 1,
      "items": {
        "oneOf": [
          { "$ref": "outcomeA_measurement.schema.json" },
          { "$ref": "outcomeB_measurement.schema.json" }
        ]
      }
    }
  },

  "definitions": {
    "evidence_anchor": {
      "type": "object",
      "additionalProperties": false,
      "required": ["page"],
      "properties": {
        "page": { "type": "integer", "minimum": 0 },
        "quote": { "type": "string" },
        "bbox": {
          "type": "object",
          "additionalProperties": false,
          "required": ["x1", "y1", "x2", "y2"],
          "properties": {
            "x1": { "type": "number", "minimum": 0, "maximum": 1 },
            "y1": { "type": "number", "minimum": 0, "maximum": 1 },
            "x2": { "type": "number", "minimum": 0, "maximum": 1 },
            "y2": { "type": "number", "minimum": 0, "maximum": 1 }
          }
        }
      }
    },

    "variance": {
      "type": "object",
      "additionalProperties": false,
      "required": ["type"],
      "properties": {
        "type": { "enum": ["sd", "se", "ci95", "none"] },
        "value": { "type": "number" },
        "n": { "type": "integer", "minimum": 1 }
      }
    },

    "strategy_item": {
      "type": "object",
      "additionalProperties": false,
      "required": ["family"],
      "properties": {
        "family": {
          "enum": [
            "shading",
            "natural_ventilation",
            "solar_control",
            "cool_roof",
            "thermal_insulation",
            "pcm",
            "green_roof",
            "green_facade",
            "thermal_mass",
            "hybrid",
            "other"
          ]
        },
        "subtype": { "type": "string" },
        "intensity_fields": { "type": "object" },
        "evidence": { "$ref": "#/definitions/evidence_anchor" }
      }
    },

    "envelope_component": {
      "type": "object",
      "additionalProperties": false,
      "required": ["component_type"],
      "properties": {
        "component_type": { "enum": ["roof", "external_wall", "floor", "window", "door", "other"] },
        "u_value_W_m2K": { "type": "number" },
        "shgc_or_g_value": { "type": "number", "minimum": 0, "maximum": 1 },
        "wwr": { "type": "number", "minimum": 0, "maximum": 1 },
        "notes": { "type": "string" },
        "evidence": { "$ref": "#/definitions/evidence_anchor" }
      }
    },

    "operation_profile": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "ventilation_type": { "enum": ["natural", "mechanical", "mixed", "unknown"] },
        "ventilation_rate": { "type": "number" },
        "ventilation_rate_unit": { "type": "string" },
        "infiltration_rate_ach": { "type": "number" },
        "setpoint_cooling_C": { "type": "number" },
        "window_opening_rule": { "type": "string" },
        "internal_gains": { "type": "number" },
        "internal_gains_unit": { "type": "string" },
        "occupancy_profile": { "enum": ["measured", "standard", "assumed", "unknown"] },
        "evidence": { "$ref": "#/definitions/evidence_anchor" }
      }
    },

    "condition": {
      "type": "object",
      "additionalProperties": false,
      "required": ["package_label", "strategy_family"],
      "properties": {
        "package_label": { "type": "string" },
        "strategy_family": {
          "type": "array",
          "minItems": 1,
          "items": {
            "enum": [
              "shading",
              "natural_ventilation",
              "solar_control",
              "cool_roof",
              "thermal_insulation",
              "pcm",
              "green_roof",
              "green_facade",
              "thermal_mass",
              "hybrid",
              "other"
            ]
          }
        },
        "strategy_items": {
          "type": "array",
          "items": { "$ref": "#/definitions/strategy_item" }
        },
        "envelope_components": {
          "type": "array",
          "items": { "$ref": "#/definitions/envelope_component" }
        },
        "operation_profile": { "$ref": "#/definitions/operation_profile" }
      }
    }
  }
}
```

---

### A.2 `schemas/outcomeA_measurement.schema.json`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "outcomeA_measurement.schema.json",
  "title": "Outcome A measurement (overheating/discomfort/degree-hours)",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "comparison_id",
    "outcome_family",
    "metric_A",
    "comfort_standard",
    "threshold_definition",
    "aggregation_period",
    "baseline_value",
    "retrofit_value",
    "unit",
    "numeric_source_quality",
    "is_primary",
    "primary_rule_applied",
    "evidence"
  ],
  "properties": {
    "comparison_id": { "type": "string" },
    "outcome_family": { "const": "A" },
    "metric_A": {
      "enum": [
        "overheating_hours",
        "discomfort_hours",
        "degree_hours",
        "overheating_degree_hours",
        "exceedance_hours"
      ]
    },
    "comfort_standard": { "enum": ["TM52", "ASHRAE55", "EN16798", "ISO7730", "other", "none_reported"] },
    "threshold_definition": { "type": "string" },
    "aggregation_period": { "enum": ["occupied", "day", "night", "24h", "seasonal", "heatwave_window", "annual"] },
    "zone_definition": { "type": "string" },
    "baseline_value": { "type": "number" },
    "retrofit_value": { "type": "number" },
    "unit": { "enum": ["h", "K_h"] },
    "variance": { "$ref": "core_extraction.schema.json#/definitions/variance" },
    "numeric_source_quality": { "enum": ["table", "text", "figure_digitized", "supplement"] },
    "is_primary": { "type": "boolean" },
    "primary_rule_applied": { "enum": ["time_window_priority", "standard_priority", "availability"] },
    "evidence": { "$ref": "core_extraction.schema.json#/definitions/evidence_anchor" }
  }
}
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "outcomeA_measurement.schema.json",
  "title": "Outcome A measurement (overheating/discomfort/degree-hours)",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "outcome_family",
    "metric_A",
    "comfort_standard",
    "threshold_definition",
    "aggregation_period",
    "baseline_value",
    "retrofit_value",
    "unit",
    "numeric_source_quality",
    "is_primary",
    "primary_rule_applied",
    "evidence"
  ],
  "properties": {
    "outcome_family": { "const": "A" },
    "metric_A": {
      "enum": [
        "overheating_hours",
        "discomfort_hours",
        "degree_hours",
        "overheating_degree_hours",
        "exceedance_hours"
      ]
    },
    "comfort_standard": { "enum": ["TM52", "ASHRAE55", "EN16798", "ISO7730", "other", "none_reported"] },
    "threshold_definition": { "type": "string" },
    "aggregation_period": { "enum": ["occupied", "day", "night", "24h", "seasonal", "heatwave_window", "annual"] },
    "zone_definition": { "type": "string" },
    "baseline_value": { "type": "number" },
    "retrofit_value": { "type": "number" },
    "unit": { "enum": ["h", "K_h"] },
    "variance": { "$ref": "core_extraction.schema.json#/definitions/variance" },
    "numeric_source_quality": { "enum": ["table", "text", "figure_digitized", "supplement"] },
    "is_primary": { "type": "boolean" },
    "primary_rule_applied": { "enum": ["time_window_priority", "standard_priority", "availability"] },
    "evidence": { "$ref": "core_extraction.schema.json#/definitions/evidence_anchor" }
  }
}
```

---

### A.3 `schemas/outcomeB_measurement.schema.json`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "outcomeB_measurement.schema.json",
  "title": "Outcome B measurement (indoor/operative temperature)",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "comparison_id",
    "outcome_family",
    "temp_metric",
    "statistic",
    "aggregation_period",
    "baseline_value",
    "retrofit_value",
    "unit",
    "numeric_source_quality",
    "is_primary",
    "primary_rule_applied",
    "evidence"
  ],
  "properties": {
    "comparison_id": { "type": "string" },
    "outcome_family": { "const": "B" },
    "temp_metric": { "enum": ["operative_temperature", "indoor_air_temperature", "mean_radiant_temperature"] },
    "statistic": { "enum": ["mean", "max", "min", "p95", "daily_max_mean", "night_mean"] },
    "aggregation_period": { "enum": ["occupied", "day", "night", "24h", "seasonal", "heatwave_window", "annual"] },
    "zone_definition": { "type": "string" },
    "baseline_value": { "type": "number" },
    "retrofit_value": { "type": "number" },
    "unit": { "const": "C" },
    "variance": { "$ref": "core_extraction.schema.json#/definitions/variance" },
    "numeric_source_quality": { "enum": ["table", "text", "figure_digitized", "supplement"] },
    "is_primary": { "type": "boolean" },
    "primary_rule_applied": { "enum": ["time_window_priority", "metric_priority", "availability"] },
    "evidence": { "$ref": "core_extraction.schema.json#/definitions/evidence_anchor" }
  }
}
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "outcomeB_measurement.schema.json",
  "title": "Outcome B measurement (indoor/operative temperature)",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "outcome_family",
    "temp_metric",
    "statistic",
    "aggregation_period",
    "baseline_value",
    "retrofit_value",
    "unit",
    "numeric_source_quality",
    "is_primary",
    "primary_rule_applied",
    "evidence"
  ],
  "properties": {
    "outcome_family": { "const": "B" },
    "temp_metric": { "enum": ["operative_temperature", "indoor_air_temperature", "mean_radiant_temperature"] },
    "statistic": { "enum": ["mean", "max", "min", "p95", "daily_max_mean", "night_mean"] },
    "aggregation_period": { "enum": ["occupied", "day", "night", "24h", "seasonal", "heatwave_window", "annual"] },
    "zone_definition": { "type": "string" },
    "baseline_value": { "type": "number" },
    "retrofit_value": { "type": "number" },
    "unit": { "const": "C" },
    "variance": { "$ref": "core_extraction.schema.json#/definitions/variance" },
    "numeric_source_quality": { "enum": ["table", "text", "figure_digitized", "supplement"] },
    "is_primary": { "type": "boolean" },
    "primary_rule_applied": { "enum": ["time_window_priority", "metric_priority", "availability"] },
    "evidence": { "$ref": "core_extraction.schema.json#/definitions/evidence_anchor" }
  }
}
```

---

### A.4 Validaciones mínimas asociadas al schema (para `scripts/06_validate.py`)
**Schema-level**
- JSON parseable.
- `additionalProperties=false` (rechazar campos inesperados).

**Evidence-level**
- Todo numérico relevante debe incluir `evidence.page` y al menos `evidence.quote` o `evidence.bbox`.

**Plausibility-level (hard flags)**
- `u_value_W_m2K > 0`.
- `shgc_or_g_value`, `wwr` ∈ [0,1].
- `aggregation_period` y `unit` coherentes.

---

## ANEXO B — Contratos de exportación (CSV) + reglas de derivación

### B.0 Principios
- Fuente prioritaria: `extractions_approved/{doc_id}.json`.
- Si un doc no está aprobado, puede exportarse desde `extractions_valid` solo en modo exploratorio.
- Exportar siempre **una fila por medición** (Outcome A/B) en `unified_outcomes.csv`.

### B.1 Reglas de derivación (obligatorias)

#### B.1.1 `eligible_primary`
Derivar en export a partir de `comparison`:
- `eligible_primary = true` si:
  - `comparator_type` ∈ {`controlled_simulation_same_model`, `before_after_same_building_controlled`}
  - y `boundary_match_level` ∈ {`high`, `medium`}
- si no, `false`.

#### B.1.2 Dirección del efecto (convención global)
- `raw_diff = retrofit_value - baseline_value`
- Interpretación: negativo = mejora (menos horas o menor temperatura).

#### B.1.3 Variación (si no existe)
- Si `variance.type` no está o es `none`: exportar `variance_type=none` y `variance_value` vacío.
- Nunca imputar SE/SD.

#### B.1.4 `time_window_priority_rank` (útil para QA)
- heatwave_window=1, seasonal_summer=2, annual=3, other=4.

---

### B.2 `exports/references.csv` (1 fila por referencia)
Columnas:
- `project_id`
- `reference_id`
- `doc_id` (si match)
- `title`
- `year`
- `doi`
- `doc_type`
- `source_db`
- `pdf_path`
- `match_confidence`
- `needs_manual_match`

---

### B.3 `exports/comparisons.csv` (**1 fila por comparison_id**)
En el modelo robusto, la unidad de comparación es `comparison_id` (unidad × escenario × baseline × retrofit).

Columnas:
- `project_id`
- `reference_id`
- `doc_id`
- `comparison_id`
- `unit_id`
- `scenario_id`
- `baseline_condition_id`
- `retrofit_condition_id`

- Study:
  - `study_type`
  - `study_design`

- Building (global; si hay overrides por unidad, exportar columnas `unit_override_*` opcionales):
  - `building_type`
  - `building_subtype`
  - `location_country`
  - `location_city`
  - `climate_class`
  - `hvac_status`

- Scenario (por `scenario_id`):
  - `scenario_label`
  - `heat_context`
  - `weather_source`
  - `year_context`
  - `time_window_type`
  - `time_window_definition`
  - `occupied_hours_rule`

- Comparison:
  - `comparator_type`
  - `boundary_match_level`
  - `boundary_notes`
  - `eligible_primary`

---

### B.4 `exports/envelope_components.csv` (múltiples filas por doc)
Una fila por `condition_id` × `envelope_component`.

Columnas:
- `project_id`
- `reference_id`
- `doc_id`
- `condition_id`
- `condition_role` (baseline/retrofit)
- `package_label`
- `component_type`
- `u_value_W_m2K`
- `shgc_or_g_value`
- `wwr`
- `notes`
- `evidence_page`
- `evidence_quote`
- `evidence_bbox_json`

Columnas derivadas (si existen ambos valores baseline y retrofit para el mismo `component_type` dentro de un par baseline/retrofit):
- `delta_u_W_m2K = u_retrofit - u_baseline`

Regla de matching para `delta_u`:
- Dentro del mismo doc, emparejar por `component_type` **y por pareja baseline/retrofit definida en `comparisons[]`**.
- Si hay múltiples componentes del mismo tipo sin identificador, no calcular `delta_u`.

---

### B.5 `exports/operation_profiles.csv`
Una fila por `condition_id` cuando haya `operation_profile`.

Columnas:
- `project_id`
- `reference_id`
- `doc_id`
- `condition_id`
- `condition_role` (baseline/retrofit)
- `package_label`
- `ventilation_type`
- `ventilation_rate`
- `ventilation_rate_unit`
- `infiltration_rate_ach`
- `setpoint_cooling_C`
- `window_opening_rule`
- `internal_gains`
- `internal_gains_unit`
- `occupancy_profile`
- `evidence_page`
- `evidence_quote`
- `evidence_bbox_json`

---

### B.6 `exports/unified_outcomes.csv` (core del metaanálisis)
Una fila por medición (cada objeto en `measurements[]`).

Columnas (todas):
- Identificadores:
  - `project_id`, `reference_id`, `doc_id`
- **Estructura robusta multi-***:
  - `unit_id` (derivado desde `comparisons[].unit_id` según `measurement.comparison_id`)
  - `scenario_id` (derivado desde `comparisons[].scenario_id`)
  - `baseline_condition_id` (derivado)
  - `retrofit_condition_id` (derivado)
  - `comparison_id` (= `measurement.comparison_id`)
- Study/Building:
  - `study_type`, `study_design`, `building_type`, `building_subtype`, `location_country`, `location_city`, `climate_class`, `hvac_status`, `zone_definition`
- Scenario/Window (derivado por `scenario_id`):
  - `scenario_label`, `heat_context`, `weather_source`, `year_context`, `time_window_type`, `time_window_definition`, `occupied_hours_rule`, `time_window_priority_rank`
- Comparison (derivado por `comparison_id`):
  - `comparator_type`, `boundary_match_level`, `eligible_primary`
- Outcome common:
  - `outcome_family` (A/B)
  - `aggregation_period`
  - `baseline_value`
  - `retrofit_value`
  - `unit`
  - `raw_diff` (= retrofit-baseline)
  - `variance_type`
  - `variance_value`
  - `variance_n`
  - `numeric_source_quality`
  - `is_primary`
  - `primary_rule_applied`
- Outcome A specific (rellenar solo si `A`, si no vacío):
  - `metric_A`
  - `comfort_standard`
  - `threshold_definition`
- Outcome B specific (rellenar solo si `B`, si no vacío):
  - `temp_metric`
  - `statistic`
- Evidencia (por medición):
  - `evidence_page`
  - `evidence_quote`
  - `evidence_bbox_json`

Reglas:
- `raw_diff` siempre se calcula.
- Si `variance` falta: `variance_type=none`.
- No se calcula SE automáticamente.

---

### B.7 QA exports (checks mínimos)
Antes de escribir CSV:
- cada fila debe tener `reference_id`, `doc_id`.
- si `eligible_primary=true` entonces `comparator_type` y `boundary_match_level` deben estar presentes y coherentes.
- `raw_diff` calculable (baseline/retrofit no nulos).

---

## ANEXO C — Prompts, parámetros operativos y configuración (core de ejecución)

> Este anexo fija **textualmente** los prompts (triage/extracción/corrección/multimodal), parámetros de RAG y límites operativos para minimizar alucinación, coste y variabilidad.

---

### C.0 Configuración operacional (`run_config.yaml`)
Ubicación:
```
project/run_config.yaml
```

Estructura mínima (ejemplo):
```yaml
run_id: "2026-02-05T10:30:00+01:00"
manifest_path: "manifest.xlsx"
pdf_dir: "pdfs"
filters:
  dt_include: ["ARTICLE", "ARTICLE; EARLY ACCESS"]
  dt_exclude: ["REVIEW", "BOOK CHAPTER", "ARTICLE; PROCEEDINGS PAPER"]
matching:
  prefer_doi: true
  fuzzy_title_threshold: 0.88
rag:
  bm25_top_k_pages: 15
  min_pages: 6
  max_pages: 20
  query_templates:
    - "overheating hours"
    - "degree-hours"
    - "discomfort hours"
    - "operative temperature"
    - "TM52"
    - "ASHRAE 55"
    - "EN 16798"
    - "U-value"
    - "transmittance"
    - "SHGC"
    - "g-value"
    - "retrofit"
    - "renovation"
triage:
  enable_ai_for_maybe: true
  model: "gemini-2.5-flash-lite"
  max_input_pages: 8
extraction:
  model: "gemini-2.5-flash"
  max_input_pages: 15
  max_retries_fix: 1
  require_evidence_for_numeric: true
images:
  enable_fallback: true
  dpi: 350
  max_pages_per_doc: 6
  trigger_if_null_critical: true
  trigger_if_table_figure_signal: true
rate_limits:
  max_concurrent_requests: 2
  requests_per_minute_soft: 30
logging:
  write_request_payloads: false
  write_model_responses: true
```

---

### C.1 Variables de entorno (no en repo)
Archivo:
```
project/.env
```
Claves:
- `GEMINI_API_KEY=...`

Política:
- Prohibido commitear `.env`.
- Crear `.env.example` sin claves.

---

### C.2 Parámetros de RAG (deterministas)
Implementación recomendada: BM25 por página (rápido y reproducible).

**Unidad de indexado:** página.
- Documento → lista de páginas `{page_index, text}`.

**Selección de páginas candidatas:**
1) Construir lista de queries a partir de `rag.query_templates`.
2) Para cada query, obtener top-N páginas por BM25 (N=5).
3) Unir páginas y deduplicar.
4) Ordenar por score agregado y recortar a `bm25_top_k_pages`.
5) Garantizar entre `min_pages` y `max_pages`:
   - si hay menos de `min_pages`, completar con páginas iniciales (0..).

**Persistencia:**
- Guardar en `snippets/{doc_id}/retrieval_{timestamp}.json`:
  - queries
  - páginas seleccionadas
  - scores

---

### C.3 Definición de “campos críticos” (para activar imágenes)
Se consideran **críticos** si el doc fue triage `extractable`:
- Al menos 1 medición con:
  - `baseline_value` y `retrofit_value` (A o B)
  - `unit`
  - `evidence.page` y (`quote` o `bbox`)

Si no se logra tras extracción+validación → `needs_images=true`.

---

### C.4 Prompt — Triage sin IA (heurístico) (no aplica prompt)
Criterios (regex/cadenas):
- Intervención: `retrofit|renovat|refurbish|adaptation|passive cooling|shading|cool roof|PCM|green roof|insulation|natural ventilation`
- Outcomes: `overheating|discomfort hours|degree-hours|operative temperature|indoor temperature|TM52|ASHRAE|EN 16798`

Etiqueta:
- `extractable`: intervención + (outcome A o B) presentes.
- `maybe`: intervención presente pero outcome ambiguo.
- `no-data`: intervención ausente o sin outcomes.

---

### C.5 Prompt — Triage IA (solo docs “maybe”)
Archivo sugerido:
```
project/prompts/triage_prompt.txt
```

**Instrucciones (texto exacto):**

> ROLE: You are a strict scientific data triage assistant.
> TASK: Decide whether the provided pages contain enough explicit information to extract baseline vs retrofit outcomes for a meta-analysis.
> IMPORTANT:
> - Papers may include multiple buildings/units, multiple retrofit packages, and multiple scenarios.
> - Your decision must consider whether at least one explicit baseline-vs-retrofit comparison exists for at least one unit.
> Use ONLY the provided text. Do NOT guess.
> OUTPUT: Return ONLY valid JSON.

**JSON requerido:**
```json
{
  "triage_label": "extractable|maybe|no-data",
  "units_detected": ["U1"],
  "packages_detected": ["C0","C1"],
  "scenarios_detected": ["S1"],
  "has_any_valid_comparison": true,
  "has_outcome_A": true,
  "has_outcome_B": false,
  "comparator_type_guess": "controlled_simulation_same_model|before_after_same_building_controlled|before_after_same_building_uncontrolled|with_without_different_buildings|other",
  "boundary_match_level_guess": "high|medium|low|unknown",
  "needs_images": false,
  "signals": {
    "mentions_table_or_figure": true,
    "mentions_u_value": true,
    "mentions_g_value": false
  },
  "notes": "short reason; cite page numbers if mentioned"
}
```

**Entrada al modelo:**
- Texto concatenado de máx. `triage.max_input_pages` páginas, con encabezado `PAGE {n}` antes de cada una.

---

### C.6 Prompt — Extracción principal (texto-only, schema-first; robust multi-*)
Archivo:
```
project/prompts/extract_prompt_text.txt
```

**Instrucciones (texto exacto):**

> ROLE: You are a strict scientific information extraction system.
> CONTEXT: A single paper may report multiple buildings/units, multiple retrofit packages, multiple scenarios.
> You MUST represent them using explicit IDs:
> - units[].unit_id
> - scenarios[].scenario_id
> - conditions[].condition_id (baseline and retrofit packages)
> - comparisons[].comparison_id (unit × scenario × baseline × retrofit)
> Every measurement MUST reference one comparison_id.
>
> CONSTRAINTS:
> 1) Use ONLY the text provided in this prompt. Do NOT use outside knowledge.
> 2) Do NOT guess or infer missing values. If a value is not explicitly stated, output null.
> 3) Every numeric value MUST include evidence with page and either a verbatim quote or a bbox (bbox may be null for text-only). If evidence is missing, set the numeric value to null.
> 4) Output MUST be valid JSON that conforms to the provided JSON schema. Output ONLY JSON.
>
> REQUIRED MINIMUM:
> - At least 1 baseline condition (condition_role=baseline)
> - At least 1 retrofit condition (condition_role=retrofit)
> - At least 1 comparison (comparisons[]) linking unit_id, scenario_id, baseline_condition_id, retrofit_condition_id
> - At least 1 measurement linked to a comparison_id with baseline_value and retrofit_value and evidence.

**Adjuntos lógicos en la llamada:**
- `schemas/core_extraction.schema.json`
- `schemas/outcomeA_measurement.schema.json`
- `schemas/outcomeB_measurement.schema.json`

**Formato de entrada (texto):**
- Bloques:
  1) `SCHEMA_VERSION: 1.0.0`
  2) `DOC_ID`, `REFERENCE_ID`
  3) `PAGES` (PAGE n + contenido)

**Regla adicional:**
- Si el estudio solo reporta valores en una tabla no visible en texto → dejar null y set `study.notes` indicando “table/figure likely; needs_images”.

---

### C.7 Prompt — Extracción multimodal (imágenes de páginas)
Archivo:
```
project/prompts/extract_prompt_multimodal.txt
```

**Instrucciones (texto exacto):**

> ROLE: You are a strict scientific table/figure reader.
> INPUTS: You receive one or more page images from a PDF and optional page text.
> CONSTRAINTS:
> 1) Extract ONLY values that are visibly present in the images/text provided.
> 2) Do NOT guess hidden rows/columns or unreadable numbers. If not clearly readable, output null.
> 3) Every numeric value MUST include evidence with page and bbox. Also include a short quote if legible.
> 4) Output ONLY valid JSON conforming to the schema.

**Uso:**
- Se llama solo para completar campos faltantes (null críticos) o cuando `mentions_table_or_figure=true`.
- Entradas:
  - imágenes `pages_img/{doc_id}/page_XXX.png` (máx `images.max_pages_per_doc`)
  - (opcional) texto de esas páginas.

---

### C.8 Prompt — Corrección por validación (1 reintento máximo)
Archivo:
```
project/prompts/fix_prompt.txt
```

**Instrucciones (texto exacto):**

> ROLE: You are a strict JSON repair assistant.
> TASK: Fix the provided JSON so it conforms to the schema and the validation errors.
> CONSTRAINTS:
> 1) Do NOT add new information beyond what is already present in the provided pages/images.
> 2) If a required numeric value lacks evidence, set it to null.
> 3) Output ONLY valid JSON.

**Entrada:**
- `VALIDATION_ERRORS` (lista)
- `CURRENT_JSON` (el output previo)
- `PAGES_USED` (texto/imágenes usadas originalmente)

**Límite:**
- `extraction.max_retries_fix: 1`

---

### C.9 Parámetros de render de imágenes (PyMuPDF)
- DPI objetivo: `images.dpi` (default 350).
- Render por página seleccionada.
- Guardar PNG y meta JSON:
  - `pages_img/{doc_id}/page_XXX.png`
  - `pages_img/{doc_id}/page_XXX.meta.json` con `{dpi, width, height, created_at}`.

Selección de páginas a render:
- Prioridad:
  1) Páginas con strings: `Table`, `Figure`, `Fig.`, `Results`, `U-value`, `SHGC`, `g-value`.
  2) Páginas donde BM25 score alto para queries de outcomes.
  3) Páginas alrededor (±1) si la tabla se corta.

---

### C.10 Política de batching y paralelización (anti-rate-limit)
- Concurrencia máxima: `rate_limits.max_concurrent_requests` (default 2).
- Backoff exponencial simple en HTTP 429/503.
- Reintento de red: hasta 3 (no confundir con `fix`), sin cambiar prompt.
- Registrar tiempos y fallos en `run_log.md`.

---

### C.11 Formato de logs para auditoría

**`audit/audit_log.jsonl`** (una línea por evento):
- `ts`, `doc_id`, `event_type` (`extract_raw`, `validate_ok`, `fix_applied`, `review_edit`, `approved`, `rejected`)
- `actor` (`worker` / `streamlit_user`)
- `summary`
- `diff` (para `review_edit`: JSON Patch o diff compacto)

---

### C.12 Reglas de UI (Streamlit) para evitar errores
- Mostrar siempre:
  - outcome rows con `baseline_value`, `retrofit_value`, `unit`, `evidence_page`, `evidence_quote`.
- Botón “Approve” solo habilitado si:
  - al menos 1 medición tiene baseline+retrofit+evidencia.
- Botón “Needs images” (manual) para forzar fallback.

---

Fin del PRD.

