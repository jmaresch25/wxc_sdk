# Space_OdT — README unificado por versiones (v1, v11, v2, v21, v211)

> Documento único y extendido para operación y desarrollo. Mantiene por separado cada línea funcional porque **cada versión resuelve problemas distintos y usa launchers distintos**.

---

## 0) Visión global (zoom out)

`Space_OdT` es una suite de herramientas para inventario y operación masiva sobre Webex Calling. El repositorio convive con varias generaciones funcionales:

- **v1**: exportador determinista de inventario (read-only).
- **v11**: UI de inventario por artefacto/módulo con ejecución guiada.
- **v2**: bulk asíncrono para aprovisionamiento de softphone sobre usuarios existentes.
- **v21**: runner base para plan/apply de sedes (locations) con artefactos de trazabilidad.
- **v211**: UI operativa para transformaciones bulk con chunking/paralelismo.

La idea de diseño es mantener MVPs separados por responsabilidad, evitando mezclar flujos incompatibles.

---

## 1) Qué se construye (por línea)

### v1 — Inventario determinista
**Qué es**: pipeline read-only que exporta inventario a CSV/JSON.

**Para quién**: equipos que necesitan baseline confiable del tenant.

**Problema que resuelve**: inventarios repetibles, auditables y sin mutación remota.

**Cómo funciona**:
- usa manifiesto fijo de artefactos;
- resuelve dependencias/IDs desde exportaciones previas;
- genera `status` por artefacto ejecutado.

### v11 — UI de inventario
**Qué es**: interfaz HTTP local para disparar inventario por artefacto.

**Para quién**: operaciones que prefieren flujo visual/iterativo.

**Problema que resuelve**: evita ejecutar todo el inventario cuando solo se necesita una parte.

**Cómo funciona**:
- servidor local;
- selección de artefactos;
- resolución de dependencias y escritura de CSV por módulo.

### v2 — Bulk softphone (usuarios existentes)
**Qué es**: motor asíncrono de cambios por etapas sobre usuarios.

**Para quién**: operaciones masivas sobre softphone y políticas de usuario.

**Problema que resuelve**: ejecución por lotes concurrente con control por etapas y reintentos.

**Cómo funciona**:
- carga inventario v1 como lookup cache;
- procesa `input_softphones.csv`;
- aplica stages con decisiones (`yes/no/yesbut`);
- guarda estado, cambios y fallos para re-ejecución.

### v21 — Runner base de sedes
**Qué es**: base independiente para planificar/ejecutar operaciones de sedes.

**Para quién**: equipos que administran locations con trazabilidad de plan.

**Problema que resuelve**: dry-run/apply auditable con artefactos estables.

**Cómo funciona**:
- bootstrap de plantillas si faltan;
- generación de `plan.csv`;
- persistencia de `run_state.json`.

### v211 — UI operativa bulk para transformaciones
**Qué es**: UI para acciones de transformación sobre `locations/users/numbers`.

**Para quién**: operación funcional diaria (carga CSV, preview, apply).

**Problema que resuelve**: centraliza ejecución de acciones con mapeo de campos y bulk paralelo.

**Cómo funciona**:
- upload datasets;
- mapping de columnas;
- preview;
- apply con `chunk_size` y `max_workers`;
- consolidación de resultados y logs por acción.

---

## 2) Launchers y comandos (zoom in)

> El CLI principal está en `Space_OdT/cli.py`.

### 2.1 Comando v1 (inventario)

```bash
python -m Space_OdT.cli inventory_run --out-dir .artifacts --open-report
```

Opcional token explícito:

```bash
python -m Space_OdT.cli inventory_run --token "<WEBEX_ACCESS_TOKEN>" --out-dir .artifacts
```

Flags habituales:
- `--no-report`
- `--no-cache`
- `--skip-group-members`

### 2.2 Comando v11 (UI de inventario)

```bash
python -m Space_OdT.cli v11_inventory_ui --out-dir .artifacts --v21-ui-host 127.0.0.1 --v21-ui-port 8772 --open-report
```

### 2.3 Comando v2 (bulk softphone)

```bash
python -m Space_OdT.cli v2_bulk_run --out-dir .artifacts --concurrent-requests 20
```

Flags importantes:
- `--only-failures`
- `--debug-har`
- `--decisions-file <archivo.json>`

### 2.4 Comando v21 (runner plan/apply)

Dry-run (por defecto):

```bash
python -m Space_OdT.cli v21_softphone_bulk_run --out-dir .artifacts
```

Apply:

```bash
python -m Space_OdT.cli v21_softphone_bulk_run --out-dir .artifacts --v21-apply
```

### 2.5 Comando v21 UI legacy

```bash
python -m Space_OdT.cli v21_softphone_ui --out-dir .artifacts --v21-ui-host 127.0.0.1 --v21-ui-port 8765
```

### 2.6 Comando v211 UI (actual para bulk transformaciones)

```bash
python -m Space_OdT.cli v211_softphone_ui --v21-ui-host 127.0.0.1 --v21-ui-port 8765
```

---

## 3) UX operativa (historias de usuario)

### Historia A (happy path inventario)
1. Operador ejecuta `inventory_run`.
2. Revisa `.artifacts/exports/*.csv|json` y `status`.
3. Publica inventario como baseline para otros flujos.

Alternativa: si solo necesita un artefacto puntual, usa `v11_inventory_ui`.

### Historia B (happy path v2)
1. Prepara `v1_inventory` + `input_softphones.csv` + `static_policy.json`.
2. Ejecuta `v2_bulk_run`.
3. Decide etapas (`yes/no/yesbut`).
4. Revisa `run_state`, `failures`, `changes.log`, `report.html`.

Alternativas:
- re-ejecutar solo errores con `--only-failures`;
- usar `--decisions-file` para operación no interactiva.

### Historia C (happy path v211)
1. Levanta UI `v211_softphone_ui`.
2. Sube datasets (`locations/users/numbers`).
3. Define mapping.
4. Preview.
5. Apply en bulk con parámetros de chunking/concurrencia.
6. Audita resultados por fila y logs.

Alternativa: acción marcada `en desarrollo` => visible pero bloqueada.

---

## 4) Necesidades técnicas clave

### Gestión de token
- Prioridad: `--token` explícito.
- Si no existe, se resuelve por `WEBEX_ACCESS_TOKEN` (con carga previa de `.env`).

### Diseño técnico principal
- Funciones y módulos pequeños por acción (`transformacion/*.py`).
- Separación de orquestación (CLI/UI/launcher) vs ejecución por script.
- Contratos de entrada/salida por fila para trazabilidad y pruebas.

### Dependencias relevantes
- `wxc_sdk` para operaciones Webex.
- `dotenv` para bootstrap de entorno.
- `asyncio`/thread pools para concurrencia según línea.

### Edge cases documentados
- rate-limit/429 (retry básico con `Retry-After` en launcher v211 y backoff en flujos async);
- CSV incompleto o mapeo inválido;
- acciones no habilitadas (bloqueadas por catálogo `en desarrollo`).

---

## 5) Estado funcional por versión

### 5.1 v1
- Exportador determinista read-only.
- Artefactos CSV/JSON + `status`.
- Base de lookup para v2.

### 5.2 v11
- UI de inventario por artefacto/módulo.
- Resolución de dependencias y ejecución parcial.

### 5.3 v2
- Runner asíncrono por etapas.
- Persistencia de estado de corrida.
- Reporte de cambios y fallos.

### 5.4 v21
- Runner independiente de plan/apply para locations.
- Crea plantillas cuando faltan.
- Genera `plan.csv` y `run_state.json`.

### 5.5 v211
- UI con modo bulk real en memoria (chunking + `ThreadPoolExecutor`).
- Consolidación determinista (`orders`/`results`).
- Log técnico por acción en `Space_OdT/v21/transformacion/logs/`.

#### Acciones habilitadas hoy (launcher/UI)
- `ubicacion_alta_numeraciones_desactivadas`
- `ubicacion_actualizar_cabecera`
- `ubicacion_configurar_llamadas_internas`
- `ubicacion_configurar_permisos_salientes_defecto`
- `usuarios_anadir_intercom_legacy`
- `usuarios_asignar_location_desde_csv`
- `usuarios_configurar_desvio_prefijo53`
- `usuarios_configurar_perfil_saliente_custom`
- `usuarios_modificar_licencias`
- `workspaces_configurar_perfil_saliente_custom`

#### En desarrollo (presentes pero no activas para apply)
- `ubicacion_configurar_pstn`
- `usuarios_alta_people`
- `usuarios_alta_scim`
- `workspaces_alta`
- `workspaces_anadir_intercom_legacy`
- `workspaces_configurar_desvio_prefijo53`
- `workspaces_configurar_desvio_prefijo53_telephony`
- `workspaces_validar_estado_permisos`

---

## 6) Testing y seguridad para ship

### Tests recomendados
```bash
pytest -q tests/test_space_odt_v21_bulk_runner.py
pytest -q tests/test_space_odt_v21_ui_v211.py
pytest -q tests/test_space_odt_v21_launcher_csv_dependencias.py
```

### Cobertura esperada (pragmática)
- unit tests de normalización/mapeo;
- integración local de launcher + acciones críticas;
- regresión de chunking/merge y rutas de error.

### Seguridad operativa
- no hardcode de token;
- validación temprana de inputs;
- trazabilidad por logs y artefactos;
- ejecución controlada por acciones habilitadas.

---

## 7) Plan de trabajo y evolución

### Requerido (DoD mínimo)
1. Mantener comandos/launchers actualizados en este README.
2. Sincronizar catálogo de handlers activos entre UI, launcher y tests.
3. Asegurar plantillas de entrada y ejemplos por flujo.

### Opcional (alto impacto)
4. Job queue persistente (reanudación tras reinicio).
5. Observabilidad consolidada (métricas + dashboard).
6. Contratos tipados más estrictos para parámetros de acciones.

### Riesgos y alternativas
- Riesgo mayor: APIs externas/rate limits.
- Alternativa operativa: reducir `max_workers`, aumentar chunking conservador, reintentar solo fallos.

---

## 8) Ripple effects

- Formación/comunicación a operación por versión (v1 != v2 != v211).
- Actualizar plantillas CSV cuando cambie cualquier dependencia de acción.
- Mantener guías internas alineadas con launchers reales del CLI.

---

## 9) Contexto amplio

### Limitaciones actuales
- no hay backend de jobs persistente transversal para todos los flujos;
- coexistencia de varias generaciones implica coste documental.

### Moonshots
- unificar telemetría y estado de ejecuciones en un panel único;
- diseñador de pipelines (encadenar v1 -> v2/v211 con validaciones automáticas).

---

## 10) Estructura de artefactos (referencia rápida)

- `.artifacts/exports/*` → inventario v1.
- `.artifacts/v2/*` → estado/reportes bulk v2.
- `.artifacts/v21/plan.csv` y `.artifacts/v21/run_state.json` → runner v21.
- `Space_OdT/v21/transformacion/logs/*.log` → logs técnicos de acciones v211.

