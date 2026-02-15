# LLD — Diseño Detallado para Batch v21 Resiliente

## 1) Modelo operativo detallado

## Entrada
- `input_csv_path`
- `action_type` (operación concreta sobre Webex)
- `batch_size` (p.ej. 100–500, ajustable)
- `max_inflight_batches` (por defecto 1 para control; subir solo con evidencia)
- `retry_profile` (agresivo/normal/conservador)
- `resume_from_checkpoint` (bool)

## Salida
- `run_summary.json`
- `row_errors.csv`
- `checkpoint.json`

## Estados de ejecución
`PENDING -> RUNNING -> COMPLETED | COMPLETED_WITH_ROW_ERRORS | FAILED_SYSTEMIC | ABORTED_BY_POLICY`

---

## 2) Componentes y contratos (sin boilerplate innecesario)

## 2.1 CSV Reader (streaming)
**Responsabilidad**: leer en streaming, validar cabeceras críticas y emitir filas tipadas.

**Contrato**:
- `iter_rows() -> Iterator[RowRecord]`
- Si faltan columnas críticas: error de inicialización (no inicia job).

## 2.2 Batch Iterator
**Responsabilidad**: agrupar filas en lotes.

**Contrato**:
- `iter_batches(rows, batch_size) -> Iterator[Batch]`
- Mantener orden original para trazabilidad.

## 2.3 Action Mapper
**Responsabilidad**: convertir `RowRecord` en request SDK.

**Regla clave**:
- Reutilizar objetos/métodos del SDK existente.
- No duplicar serialización/validación ya provista por SDK.

## 2.4 Resilient Executor
**Responsabilidad**: ejecutar llamada SDK con política de resiliencia.

**Tenacity (requerido)**:
- `wait`: exponential backoff + jitter.
- `retry`: timeout, connection error, HTTP 429/5xx.
- `retry_if_result`: opcional para respuestas semánticamente reintentables.
- `stop`: límite por intento y/o tiempo total.
- **retry-after**: si respuesta incluye cabecera `Retry-After`, priorizar ese valor sobre backoff calculado.

**Circuit Breaker (requerido)**:
- Métrica de fallos sistémicos en ventana deslizante.
- `closed -> open` cuando falla umbral configurado.
- `open -> half-open` tras cooldown.
- `half-open -> closed` si probes exitosos.
- `half-open -> open` si persiste falla.

## 2.5 Error Classifier
**Responsabilidad**: clasificar errores para política `fail-log-continue`.

**Clases**:
1. `ROW_ERROR_NON_RETRYABLE`
   - Validación de negocio, conflicto puntual, recurso inexistente para esa fila.
   - Acción: registrar y continuar.

2. `TRANSIENT_RETRYABLE`
   - 429/5xx/timeout/red.
   - Acción: retry + posible impacto en breaker.

3. `SYSTEMIC_FATAL`
   - Auth inválida persistente, configuración global inválida, breaker abierto sostenido.
   - Acción: abortar corrida con estado sistémico.

## 2.6 State Store
**Responsabilidad**: checkpoint incremental y recuperación.

**Datos mínimos**:
- `run_id`
- último `batch_index` confirmado
- filas procesadas/ok/error
- hash de archivo de entrada (evitar resume con CSV distinto)

## 2.7 Report Writer
**Responsabilidad**: reporte final para operación.

**Campos críticos**:
- totales (`read`, `processed`, `success`, `row_errors`, `systemic_errors`)
- retries ejecutados
- duración total
- estado final

---

## 3) Algoritmo de ejecución (secuencia)

1. Inicializar cliente SDK y validar token.
2. Validar CSV (headers + accesibilidad).
3. Si `resume`: cargar checkpoint y verificar hash CSV.
4. Iterar lotes desde checkpoint.
5. Para cada fila del lote:
   - Mapear fila a llamada SDK.
   - Ejecutar con `Resilient Executor`.
   - Clasificar resultado/error.
   - `ROW_ERROR_NON_RETRYABLE` => guardar error y continuar.
6. Al cerrar lote: persistir checkpoint atómico.
7. Si breaker queda `open` y no recupera según política: finalizar `FAILED_SYSTEMIC`.
8. Escribir reportes finales.

---

## 4) Parámetros recomendados (baseline)

- `batch_size`: 200
- `request_timeout_s`: 30
- `retry_max_attempts`: 5
- `retry_max_delay_s`: 60
- `retry_jitter`: habilitado
- `breaker_failure_threshold`: 50% en ventana de 20 llamadas
- `breaker_open_cooldown_s`: 45
- `half_open_probe_calls`: 3

> Ajustar por telemetría real de entorno; no endurecer sin evidencia.

---

## 5) Testing y validación técnica

## Unit tests críticos
- Clasificador de errores (fila/transitorio/sistémico).
- Lógica de `retry-after`.
- Transiciones de circuito (`closed/open/half-open`).
- Integridad de checkpoint/resume.

## Integration tests críticos
- CSV de muestra con mezcla de éxitos + errores de fila + 429 simulado.
- Reanudación tras interrupción en mitad de lote.
- Corrida de volumen cercana a 21.000 en entorno controlado.

## Criterios de aceptación
- No aborta por errores de fila aislados.
- Reintenta correctamente transitorios.
- Aborta solo por condiciones sistémicas bien definidas.
- Resume sin duplicar procesamiento confirmado.

---

## 6) Seguridad operativa

- Tokens por variable de entorno o vault.
- Nunca persistir token en checkpoint/reportes/logs.
- Logs con redacción de PII sensible cuando aplique.
- Ejecución en entorno controlado sin endpoint de entrada pública.

---

## 7) Plan de trabajo (estimación breve)

1. Definición de contratos y configuración (0.5 d)
2. Implementación resiliencia (Tenacity + breaker + clasificador) (1.0 d)
3. Checkpoint/resume + reportes (0.5 d)
4. Tests unit/integration esenciales (1.0 d)
5. Hardening y ajuste de parámetros (0.5 d)

**Total estimado**: 3.5 días técnicos.

---

## 8) Riesgos y mitigaciones

- **Rate limit variable de API** -> usar `Retry-After` y limitar concurrencia.
- **Errores de calidad de CSV** -> validación temprana de columnas y tipos.
- **Interrupción operativa** -> checkpoint atómico por lote.
- **Cambios de comportamiento API** -> aislar mapping en `Action Mapper` y no dispersar lógica.

---

## 9) Definition of Done (requerido vs opcional)

## Requerido
- Procesamiento de 21.000 registros en batch.
- Política `fail-log-continue` por fila.
- Tenacity con retry-after.
- Circuit breaker activo.
- Resume por checkpoint.
- Reporte final estructurado.

## Opcional (solo si aporta valor claro)
- Perfilado de rendimiento por tipo de acción.
- Ajuste dinámico de batch size basado en rate limit observado.
