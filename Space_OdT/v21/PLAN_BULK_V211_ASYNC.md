# Plan de evolución v2.1.1: ejecución batch/asíncrona por bulk order

## 1) Definición de lo que se construye

### Qué es
Una ampliación de los scripts de `Space_OdT/v21/transformacion` para soportar **modo batch** mediante modificador `--bulk`, sin romper su comportamiento actual fila a fila.

### Para quién es
Operación técnica que ejecuta cargas masivas desde la UI 211 con CSVs potencialmente >4.000 registros para Ubicaciones y Usuarios.

### Problema que resuelve
Hoy la ejecución secuencial por fila no escala bien para volúmenes altos y no ofrece control robusto de trabajos asíncronos por lote (bulk order).

### Cómo funcionará
- Se mantienen los scripts actuales (compatibilidad completa).
- Se añade un wrapper común de ejecución bulk:
  - ingestión de CSV,
  - chunking configurable,
  - envío asíncrono por lotes,
  - polling de estado,
  - reintentos,
  - consolidación de resultados y logs.

### Conceptos principales
- **Dataset maestro**: `GLOBAL.CSV`, `UBICACIONES.CSV`, `USUARIOS.CSV`.
- **Mapeo canónico**: si no se especifica, se usa el nombre del parámetro como nombre de columna por defecto.
- **Bulk order**: unidad asíncrona de ejecución de N filas por acción.
- **Batch runner**: orquestador para recursividad/chunking y seguimiento.
- **Action adapter**: adaptador por script para traducir fila -> parámetros del método.

---

## 2) Diseño de experiencia de usuario (UI 211)

### Historias de usuario
- Como operador, subo los 3 CSV y lanzo una acción sin definir mapeo manual cuando las cabeceras ya son canónicas.
- Como operador, activo `--bulk` y el sistema procesa automáticamente miles de filas en lotes asíncronos.
- Como operador, veo progreso (creados/en curso/finalizados/error), trazabilidad por lote y resumen final exportable.

### Happy flow
1. Carga de CSVs.
2. Selección de acción.
3. (Opcional) mapeo custom.
4. Activación modo bulk.
5. Ejecución asíncrona por batches.
6. Polling de estados.
7. Resumen final + log por acción/lote.

### Flujos alternativos
- Reintentar solo lotes fallidos.
- Pausar/reanudar ejecución.
- Modo dry-run (solo validación de parámetros sin llamadas write).

### Impacto UI
- Añadir selector “Modo bulk” y tamaño de lote.
- Mostrar tablero de estado por lotes (queued/running/success/error).
- En acciones no soportadas: mostrar explícitamente `... en desarrollo ...`.

---

## 3) Necesidades técnicas

### Entrada CSV (default)
Se usará por defecto la cabecera de CSV como fuente de parámetro cuando no exista mapeo manual.

### Scripts objetivo (soporte bulk prioritario)
- `ubicacion_alta_numeraciones_desactivadas`
- `ubicacion_actualizar_cabecera`
- `ubicacion_configurar_llamadas_internas`
- `ubicacion_configurar_permisos_salientes_defecto`
- `usuarios_anadir_intercom_legacy`
- `usuarios_asignar_location_desde_csv`
- `usuarios_configurar_desvio_prefijo53`
- `usuarios_configurar_perfil_saliente_custom`
- `usuarios_modificar_licencias`

### Scripts fuera de alcance inmediato
Todos los scripts no listados arriba deben mostrarse con estado: `... en desarrollo ...`.

### Diseño técnico propuesto
- Crear componente común `bulk_runner.py` (funciones, no clases salvo dataclass de estado):
  - `iter_rows(dataset)`
  - `build_chunks(rows, chunk_size)`
  - `submit_bulk_order(action_id, chunk)`
  - `poll_bulk_order(order_id)`
  - `merge_bulk_results(orders)`
- Extender cada script objetivo para aceptar `bulk=False` y `chunk_size`.
- Mantener firma actual: `func(token=..., **params)` + nueva vía opcional `--bulk`.
- Logging por lote en `transformacion/logs/<action_id>.log`.

### Dependencias
Aprovechar SDK actual + utilidades existentes de `bulk_config/` cuando reduzcan duplicación real.

### Edge cases críticos
- Timeout de polling.
- Retries con backoff para 429/5xx.
- Registros parcialmente válidos dentro de un lote.
- Idempotencia en reintentos.

---

## 4) Testing y seguridad

### Tests
- Unit:
  - parsing CSV grande,
  - fallback de mapeo por defecto,
  - chunking,
  - merge de resultados.
- Integración (mock SDK):
  - submit/poll asíncrono,
  - recuperación tras fallos transitorios.
- Regresión UI:
  - acciones `en desarrollo` no ejecutables.

### Seguridad
- No loguear tokens.
- Sanitizar payloads en logs.
- Control de rate-limit y protección ante retries excesivos.

---

## 5) Plan de trabajo

### Estimación
6–9 días hábiles (MVP robusto).

### Milestones
1. **Base bulk común** (1.5 días).
2. **Fallback mapeo canónico + UI estados** (1 día).
3. **Adaptación scripts objetivo** (2.5–3 días).
4. **Asíncrono + retries + polling** (1.5 días).
5. **Testing + hardening + docs** (1–2 días).

### Riesgos
- Límites/rate limiting API en cargas simultáneas.
- Divergencias de comportamiento entre endpoints SDK.

### Definition of Done
- Scripts listados soportan `--bulk` sin romper modo actual.
- Procesamiento recursivo de CSV completo.
- Resumen final por bulk order + log por lote.
- UI 211 distingue soportado vs `... en desarrollo ...`.

---

## 6) Ripple effects

- Actualizar runbook operativo de UI 211.
- Comunicar tamaño de lote recomendado (p.ej. 100–300 filas).
- Añadir plantilla de troubleshooting de fallos asíncronos.

---

## 7) Contexto amplio

### Limitaciones actuales
- Scripts muy acoplados a ejecución inmediata por fila.
- Falta de tracking unificado de trabajos largos.

### Extensiones futuras
- Cola de jobs persistente (Redis/RQ/Celery).
- Reanudación tras reinicio.
- Dashboard histórico de ejecuciones.

### Moonshot
- Motor declarativo de transformaciones con DAG de dependencias entre acciones y compensación automática de errores.
