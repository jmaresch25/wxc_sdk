# LLD — Próxima Evolutiva Backend (Webex SDK-first)

**Fuente base:** `Space_OdT/v21/PROXIMA_EVOLUTIVA_BACKEND.md`  
**Ámbito:** `Space_OdT/v21/transformacion/`  
**Objetivo del LLD:** convertir la especificación funcional en un diseño técnico implementable (módulos, contratos, flujos, testing, seguridad y plan).

---

## 1) Definición de lo que se construye

### 1.1 Qué es la aplicación/feature
Se construye una **capa de automatización backend desacoplada por acción**, donde cada capacidad de Webex Calling (ubicación, usuarios, workspaces) se ejecuta mediante un script independiente, homogéneo e idempotente cuando el endpoint lo permita.

### 1.2 Para quién es
- Equipos PRE/PRO y operación técnica.
- Ingeniería de soporte que necesita evidencias técnicas (payload/response) en logs.

### 1.3 Problema que resuelve
- Evita ejecución manual inconsistente en tareas repetitivas.
- Reduce riesgo de errores por copy/paste de operaciones en consola.
- Unifica trazabilidad con logs por acción y ejecución.

### 1.4 Cómo funcionará (zoom out → zoom in)
**Zoom out (MVP):**
1. Cargar token y contexto runtime.
2. Resolver parámetros de entrada (CLI/CSV).
3. Ejecutar flujo read → write → verify (si aplica).
4. Persistir evidencia técnica en log dedicado.
5. Emitir resumen final operable.

**Zoom in (por script):**
- `main()` parsea args.
- `apply_csv_arguments()` completa faltantes desde CSV.
- `create_api()` crea cliente SDK.
- función de dominio (`configurar_*`, `alta_*`, `anadir_*`) aplica cambios.
- `action_logger()` escribe JSONL por evento (`request`, `response`, `summary`, `error`).

### 1.5 Conceptos principales y relaciones
- **Entidad**: `Location`, `Person`, `Workspace`.
- **Action Script**: unidad de negocio ejecutable y versionable.
- **Launcher**: orquesta múltiples scripts a partir de datasets.
- **Contrato de entrada**: parámetros mínimos declarados por script.
- **Contrato de salida**: objeto técnico + resumen ejecutivo.
- **Logger por acción**: persistencia de trazas para auditoría.

> Distilling aplicado: se evita framework complejo; se reutilizan utilidades mínimas (`common.py`, `bulk_runner.py`) y se elimina lógica transversal no crítica.

---

## 2) Diseño de experiencia operativa (UX técnica)

### 2.1 User stories (happy flows)
1. Como operador, ejecuto una acción con parámetros mínimos y obtengo resultado verificable.
2. Como operador, lanzo múltiples acciones desde launcher sobre CSV sin mapear manualmente cada campo.
3. Como operador, reviso logs por acción para validar pre/post y soporte.

### 2.2 User stories (alternative flows)
- Dry-run para validar dependencias sin escritura.
- Reintentos automáticos ante 429 con `Retry-After`.
- Ejecución por lote (`bulk`) para N filas por dominio.
- Precheck en workspaces antes de aplicar cambios sensibles.

### 2.3 Impacto de UI/estructura operativa
Aunque es backend-first, la experiencia esperada en UI/CLI debe exponer:
- selector de acción,
- modo `single`/`bulk`,
- estado por fila/lote,
- acceso al log por acción,
- mensaje explícito de acciones "en desarrollo".

### 2.4 Wireframe textual (operación)
`Cargar CSVs -> Seleccionar acción -> Validar dependencias -> Ejecutar -> Ver progreso -> Exportar resumen`.

---

## 3) Necesidades técnicas

### 3.1 Arquitectura de módulos

```text
Space_OdT/v21/transformacion/
  common.py                       # token, api, csv merge, logger, serializers
  launcher_csv_dependencias.py    # orquestación por script/dependencias
  bulk_runner.py                  # ejecución en lote/chunking (si aplica)
  <accion>.py                     # una acción = un script
  logs/
```

### 3.2 Contratos de datos

#### Entrada base por script
- `token` (directo o vía `WEBEX_ACCESS_TOKEN`).
- parámetros de dominio (`location_id`, `person_id`, `workspace_id`, etc.).
- opcionales: `org_id`, flags de dry-run/bulk.

#### Salida base por script
```json
{
  "script_name": "...",
  "status": "executed|dry_run|skipped|rejected|error",
  "invocation": {...},
  "result": {...},
  "summary": {...}
}
```

#### Logging JSONL
Campos mínimos:
- `ts`
- `action_id`
- `event`
- `payload`

### 3.3 Diseño de componentes (funciones clave)
- `load_runtime_env()`: localiza `.env` en cwd/padres.
- `get_token()`: valida disponibilidad de token.
- `create_api()`: desacopla construcción de SDK client.
- `apply_csv_arguments()`: merge CLI/CSV con validación requerida.
- `_invoke_with_retry_after()`: reintento controlado ante rate limit.
- `_params_for_script()`: coerción de tipos y dependencias por acción.

### 3.4 Decisiones de diseño
- **Funciones sobre clases** por simplicidad y testabilidad.
- Inyección de dependencias por argumentos (`token`, `params`, `handler`).
- Helpers comunes solo cuando eliminan duplicación real.
- Tipado defensivo (`dict[str, Any]`) y normalización centralizada.

### 3.5 Dependencias externas
- `wxc_sdk` (1.26.x–1.27.x; validar compatibilidad por endpoint).
- `python-dotenv` para entorno.
- APIs Webex Calling usadas por `telephony`, `people`, `workspaces`, `workspace_settings`.

### 3.6 Edge cases documentados
- 429 con `Retry-After` numérico o fecha HTTP.
- timeouts/fallos de red transitorios.
- CSV vacío, columnas ausentes o valores inválidos.
- diferencias semánticas entre versiones de SDK.
- operaciones parcialmente exitosas en bulk.

---

## 4) Testing y medidas de seguridad

### 4.1 Objetivo de cobertura (MVP)
- 70%+ en utilidades comunes (`common`, `launcher`, `bulk_runner`).
- Cobertura funcional mínima por acción crítica (ubicación/usuarios/workspaces prioritarios).

### 4.2 Tipos de tests
- **Unit**
  - parsing/coerción de parámetros,
  - validación de requeridos,
  - cálculo de `Retry-After`,
  - formateo de payload/log.
- **Integración (mock SDK)**
  - read→write por acción,
  - reintentos en 429,
  - consolidación de resultados bulk.
- **Regresión**
  - scripts en estado "en desarrollo" no ejecutables,
  - contrato de salida estable para consumidores.

### 4.3 Seguridad para ship
- enmascarar token/secretos en logs (`***`).
- no persistir credenciales en argumentos visibles.
- sanitizar payloads antes de serializar.
- límites de reintentos/backoff para evitar tormenta de requests.
- validación explícita de IDs y listas para reducir estados inválidos.

### 4.4 Side-effects y auditoría
- Cambios en permisos/perfiles pueden afectar llamadas en producción.
- Requiere trazabilidad por acción para rollback operativo.
- Recomendado: precheck + confirmación en acciones de alto impacto.

---

## 5) Plan de trabajo

### 5.1 Estimación total
**5–7 días hábiles** para MVP técnico robusto.

### 5.2 Plan por pasos
1. **Base común y contratos** (0.5–1 día)
   - endurecer `common.py`, formato de salida, logger homogéneo.
2. **Dominio Ubicación** (1.5–2 días)
   - PSTN, numeraciones, cabecera, internas, permisos.
3. **Dominio Usuarios** (1.5–2 días)
   - altas/licencias/intercom/forwarding/permisos.
4. **Dominio Workspaces** (1.5–2 días)
   - alta/intercom/forwarding/permisos.
5. **Hardening + documentación** (0.5 día)
   - ejemplos de ejecución, troubleshooting, runbook.

### 5.3 Milestones y orden
- M1: contratos + logging base.
- M2: acciones críticas de Ubicación.
- M3: acciones críticas de Usuarios.
- M4: acciones críticas de Workspaces.
- M5: bulk resiliente + documentación.

### 5.4 Migraciones/scripts auxiliares
- No hay migración de DB en MVP.
- Sí se requieren scripts auxiliares para:
  - generación de CSV candidatos,
  - inspección de parámetros,
  - consolidación de reportes.

### 5.5 Riesgos y rutas alternativas
- **Riesgo:** throttling API. → **Mitigación:** chunking + retry-after + límites.
- **Riesgo:** drift de versión SDK. → **Mitigación:** matriz endpoint-versión y tests smoke por release.
- **Riesgo:** datos de entrada incompletos. → **Mitigación:** validación temprana + report de faltantes.

### 5.6 Definition of Done (requerido vs opcional)
**Requerido**
- scripts por acción implementados y ejecutables,
- logging dedicado por acción,
- salida técnica verbosa consistente,
- validaciones de entrada mínimas.

**Opcional (post-MVP)**
- pipeline declarativo YAML/JSON,
- diff automático pre/post estado remoto,
- panel histórico de ejecuciones.

---

## 6) Ripple effects

### 6.1 Fuera de diseño/implementación
- actualizar runbook operativo (orden recomendado de scripts).
- documentar parámetros obligatorios por acción.
- publicar ejemplos reales de logs y salidas.

### 6.2 Comunicación
- aviso a PRE/PRO sobre cambios de naming y nuevas dependencias CSV.
- guía de transición para scripts legacy.

### 6.3 Sistemas externos afectados
- procesos de soporte/incidencias (consumen logs).
- automatismos de reporting (si parsean `results_manual.csv`/artifacts).

---

## 7) Contexto amplio

### 7.1 Limitaciones actuales
- No existe orquestación global transaccional.
- Recuperación de errores avanzada aún no unificada.
- Dependencia alta de disponibilidad/rate limit de Webex API.

### 7.2 Evolución futura prevista
- motor declarativo de flujos multi-acción.
- idempotencia fuerte basada en hash de entrada + snapshot remoto.
- ejecución distribuida con cola persistente y reanudación tras caída.

### 7.3 Consideraciones de coste/priorización
- Priorizar acciones con mayor volumen operativo y mayor riesgo humano.
- Evitar sobre-ingeniería temprana: primero estabilidad operativa y trazabilidad.

### 7.4 Moonshot ideas
- control plane con scheduling + dry-run integral + diff visual pre/post.
- recomendador de orden de ejecución por dependencias reales detectadas en runtime.

---

## Apéndice A — LLD del launcher multi-CSV y bulk resiliente (24h)

### A.1 Estructura de entrada
Directorio único `--input_dir` con:
- `global.csv` (1 fila)
- `ubicaciones.csv` (N filas)
- `usuarios.csv` (N filas)
- `workspaces.csv` (N filas, opcional MVP)

### A.2 Algoritmo de ejecución
1. Cargar `global.csv`.
2. Seleccionar dataset por acción (ubicación/usuario/workspace).
3. Para cada fila:
   - merge `global + fila`;
   - resolver dependencias;
   - validar y tipar;
   - ejecutar handler con retry/backoff;
   - registrar resultado por fila.
4. Consolidar resumen final `ok/error` y exportar artifacts.

### A.3 Bulk resiliente 24h
- chunk size configurable.
- backoff exponencial con techo.
- timeout global de job y timeout por chunk.
- reintento selectivo de filas fallidas.
- checkpoint periódico para reanudación manual.

### A.4 DoD específico launcher
- Soporta datasets separados por dominio sin mezclar columnas.
- Ejecuta lotes largos sin abortar job completo por errores parciales.
- Entrega resumen final con evidencia por fila/chunk/script.
