# VALIDATION_GUIDE.md
## Guía complementaria de validación (preflight) para extracción JSON

**Propósito:** Este documento es una **guía de complemento** para robustecer el pipeline de extracción y metaanálisis.  
Se solicita al **agente/implementador** que **revise este documento** e **implemente los cambios necesarios** en el extractor IA y/o en el validador (`06_validate.py`) para reducir rechazos, asegurar trazabilidad y mantener consistencia analítica.

> Alcance: **no cambia la lógica** del pipeline; refuerza **controles previos** (preflight) y criterios de consistencia para producir JSON conforme a los schemas y utilizable para metaanálisis.

---

## 1) Principio operativo

Antes de emitir un JSON final, el agente debe ejecutar un **preflight** que verifique:

1. Integridad referencial y estructura mínima (bloqueantes).
2. Coherencia analítica para metaanálisis (bloqueantes prácticos).
3. Consistencia semántica por outcome (calidad, para evitar “basura estadística”).
4. Reglas de salida de errores: si hay bloqueantes, **no** emitir JSON parcial.

---

## 2) Checks BLOQUEANTES (integridad estructural)

### 2.1 Versión de schema
- `schema_version` debe estar dentro de las versiones soportadas por el core schema (p.ej., `"1.0.0"`, `"1.1.0"`).

### 2.2 Unicidad de IDs en el documento
- `units[].unit_id` únicos.
- `scenarios[].scenario_id` únicos.
- `conditions[].condition_id` únicos.
- `comparisons[].comparison_id` únicos.

### 2.3 Integridad referencial (crítico)
Para cada `measurement`:

- `measurements[].comparison_id` **debe existir** en `comparisons[].comparison_id`.

Para cada `comparison`:

- `unit_id` ∈ `units[].unit_id`
- `scenario_id` ∈ `scenarios[].scenario_id`
- `baseline_condition_id` ∈ `conditions[].condition_id`
- `retrofit_condition_id` ∈ `conditions[].condition_id`

### 2.4 Coherencia de roles (baseline vs retrofit)
- `conditions[baseline_condition_id].condition_role` debe ser `"baseline"`.
- `conditions[retrofit_condition_id].condition_role` debe ser `"retrofit"`.

### 2.5 Evidencia obligatoria por medición
Cada `measurement` debe incluir:
- `evidence.page` (entero > 0).

Buenas prácticas:
- Si `numeric_source_quality="figure_digitized"`, el `quote`/nota debe referir la figura (p.ej., “Figura 4”).

### 2.6 Valores numéricos mínimos
- `baseline_value` y `retrofit_value` deben ser numéricos (no rangos tipo “10–20”, no “~”, no texto).
- Si el paper solo provee rango o barras sin números:
  - **No inventar** valores.
  - No emitir la medición (o usar un mecanismo explícito de “not_extractable” solo si existe en el schema).

---

## 3) Checks BLOQUEANTES (forma analítica para metaanálisis)

### 3.1 Comparaciones bien formadas (multi-edificio × multi-paquete × multi-escenario)
Regla: un `comparison` representa una combinación:

- **(unit_id × scenario_id × baseline_condition_id × retrofit_condition_id)**

Implicación:
- Si el paper reporta múltiples edificios y múltiples paquetes, se deben crear los `comparison_id` necesarios para preservar esa estructura (no colapsar).

### 3.2 Mínimo de outcomes primarios utilizables
- Debe existir ≥1 `measurement` con `is_primary=true` para los outcomes objetivo.
- Si el objetivo del proyecto exige **energía + confort como primarios**, entonces deben existir mediciones primarias para ambos (si el paper lo permite).

### 3.3 Coherencia tipo de estudio vs comparador
- `study.study_type` debe ser coherente con `comparisons[].comparator_type`.
  - Simulación: comparadores del tipo “misma herramienta/modelo, baseline vs retrofit”.
  - Empírico: “before-after”, “DiD”, “RCT”, etc. según el PRD.

---

## 4) Checks SEMÁNTICOS por outcome (calidad)

> Estos checks no siempre son bloqueantes; se recomienda tratarlos como `WARN` salvo incompatibilidad grave.

### 4.1 Confort (Outcome A)
**Compatibilidad métrica ↔ unidad**
- `overheating_hours` / `discomfort_hours` → `unit="h"`.
- `overheating_degree_hours` / `degree_hours` → `unit="K_h"` (o equivalente).

**Estándar y umbral**
- Si `comfort_standard="other"` → `threshold_definition` debe describir el criterio reportado (sin inventar).
- Si TM52/EN16798/ASHRAE55 → `threshold_definition` debe alinearse con lo declarado en el paper (resumen corto).

### 4.2 Temperatura (Outcome B)
**Compatibilidad**
- `unit="C"` para temperatura.
- `statistic` (mean/max/p95/…) solo si está reportado explícitamente.

### 4.3 Energía (Outcome C)
**Compatibilidad métrica ↔ unidad (prácticamente bloqueante)**
- `energy_consumption` → `kWh_yr`, `MWh_yr`, etc.
- `energy_intensity` → `kWh_m2_yr`, `MJ_m2_yr`, etc.
- `peak_demand` → `kW`, `W`, `W_m2`.
- `% cambio` → `unit="%"` (si el schema lo contempla).

**Coherencia end-use y basis**
- `energy_end_use` no se inventa. Si solo hay total, usar `total`.
- `energy_basis` (final/primary/site/source) solo si el paper lo especifica; si no está claro, usar el valor “unknown” solo si el schema lo permite.

**Periodo y resolución**
- Anual: `aggregation_period="annual"`, `time_resolution="annual"`.
- Ventana de ola de calor: `aggregation_period="heatwave_window"`, `time_resolution` coherente (hourly/daily).

---

## 5) Checks de coherencia cruzada (recomendados)

### 5.1 Unidad vs tipo de dato
- Energía a nivel “utility whole-building” no debe asignarse a una `unit` tipo `zone` salvo submetering explícito.

### 5.2 Duplicados silenciosos
- No emitir dos mediciones idénticas (mismo `comparison_id`, mismo outcome/familia, mismo periodo, misma estadística).  
Excepción: estadísticas distintas explícitas (mean vs p95) si están codificadas.

### 5.3 Selección de primarios
Si existen múltiples periodos/métricas:
- Energía: priorizar anual si existe (para `is_primary=true`).
- Confort: priorizar `heatwave_window` o `occupied` si el paper lo enfoca así.
- El resto: `is_primary=false`.

---

## 6) Manejo de errores (salida obligatoria cuando falla el preflight)

Si falla cualquier check **bloqueante**, el agente **no debe emitir** JSON final.  
Debe retornar una lista de errores con el siguiente formato (texto o JSON interno):

- `error_code`
- `severity`: `BLOCKER` | `WARN`
- `location`: ruta tipo `measurements[7].unit`
- `message`: qué falta o qué no cuadra
- `suggested_action`: qué buscar en el PDF (tabla/figura/página)

Ejemplo (texto):
- `BLOCKER | MISSING_COMPARISON_REF | measurements[3].comparison_id | comparison_id no existe en comparisons[] | Buscar el ID correcto o crear la comparación correspondiente.`

---

## 7) Recomendación de implementación (sin cambiar lógica)

El agente/implementador debe:
1. Integrar estos checks en el **extractor IA** como “preflight” antes de emitir el JSON final.
2. Opcionalmente, replicar checks críticos en `06_validate.py` para diagnosticar con mensajes útiles.
3. Mantener la salida de errores estandarizada para facilitar QA humana.

---

## 8) Checklist rápido (para revisión humana)
- [ ] ¿Cada measurement tiene `comparison_id` válido?
- [ ] ¿Cada comparison referencia `unit_id`, `scenario_id`, `condition_id` existentes?
- [ ] ¿Baseline y retrofit roles correctos?
- [ ] ¿Cada measurement trae `evidence.page`?
- [ ] ¿Unidades compatibles con métricas (A/B/C)?
- [ ] ¿Hay al menos un outcome primario para los objetivos del estudio?
- [ ] ¿No hay duplicados obvios?
