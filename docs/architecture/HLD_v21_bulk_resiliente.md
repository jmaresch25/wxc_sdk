# HLD — Operación Batch Resiliente para v21 (Webex SDK)

## 1) Qué se construye (alcance MVP robusto)

**Aplicación/feature**: flujo de ejecución batch para procesar CSV de hasta **21.000 registros** en modo controlado, usando capacidades existentes del SDK y APIs bulk de Webex cuando aplique.

**Para quién**: técnicos de operación en entorno seguro, autenticados por token, sin exposición externa del programa salvo llamadas a API Webex.

**Problema que resuelve**:
- Evitar ejecuciones frágiles y manuales en cargas grandes.
- Mantener continuidad operativa ante errores transitorios de red/API.
- Estandarizar fallos por fila: *fail, log, continue*.

**Cómo funciona (visión macro)**:
1. Carga CSV + validación de formato mínima.
2. Segmentación en lotes configurables.
3. Ejecución de acciones por lote/registro (bulk action por línea según operación).
4. Reintentos automáticos para errores transitorios.
5. Circuit breaker para proteger frente a degradación de API.
6. Persistencia de estado para reanudación.
7. Reporte final de éxito/parcial/fallo.

## 2) Principios de diseño (mínimo boilerplate, máximas prestaciones)

- **SDK-first**: no reimplementar lógica ya disponible en `wxc_sdk` (auth, cliente, serialización, logging básico).
- **Resiliencia por política, no por código duplicado**: Tenacity + Circuit Breaker + timeout + idempotencia.
- **Degradación controlada**: error de fila no detiene job; error sistémico sí puede pausar/abortar.
- **Observabilidad mínima crítica**: métricas y logs operativos, sin sobreingeniería.
- **Simplicidad mantenible**: módulos pequeños, funciones puras cuando sea posible, inyección de dependencias.

## 3) Arquitectura lógica

## Componentes

1. **CLI Orchestrator**
   - Recibe parámetros (`input.csv`, tipo de acción, batch size, retry profile, dry-run opcional).
   - Coordina ciclo completo.

2. **CSV Intake & Validation**
   - Parsing streaming y validación de columnas críticas.
   - Normalización leve (trim, tipos, valores obligatorios).

3. **Batch Planner**
   - Construye lotes para 21k registros sin carga completa en memoria.
   - Define unidades de trabajo y checkpoints.

4. **Action Executor (SDK Adapter)**
   - Traduce fila -> invocación SDK/API.
   - Reutiliza endpoints bulk del SDK cuando existan.
   - Aplica estrategia de error por tipo (fila vs sistémico).

5. **Resilience Layer**
   - **Tenacity**: retry-after, exponential backoff con jitter, stop conditions.
   - **Circuit Breaker**: abre ante ratio/volumen de fallos sistémicos.
   - Timeouts por request y presupuesto temporal por lote.

6. **State Store / Checkpointing**
   - Guarda progreso por lote/fila para reanudación segura.
   - Evita reprocesado no deseado.

7. **Result Writer & Run Report**
   - Output estructurado: procesados, ok, fallidos fila, fallidos sistémicos, reintentos.
   - Artefactos: `run_summary.json` + `row_errors.csv`.

## Flujo de alto nivel

`CSV -> Validación -> Planificación de lotes -> Ejecución resiliente -> Persistencia estado -> Reporte`

## 4) Comportamiento de errores (política operativa)

- **Error de fila (4xx funcional, dato inválido, conflicto puntual)**:
  - Registrar error contextual (row_id, causa).
  - Marcar fila fallida.
  - Continuar con siguiente fila.

- **Error transitorio (429, 5xx, timeout, conexión)**:
  - Reintentar con Tenacity respetando `Retry-After`.
  - Si rebasa umbral, cuenta para Circuit Breaker.

- **Error sistémico sostenido**:
  - Circuit breaker abre y detiene temporalmente nuevas llamadas.
  - Política de recuperación controlada (half-open).
  - Si no recupera, finalizar ejecución con estado `FAILED_SYSTEMIC`.

## 5) UX operativa (sin UI nueva)

No se propone interfaz gráfica. UX de operación en CLI:
- comando único y parámetros explícitos;
- salida de progreso por lotes;
- resumen final accionable;
- códigos de salida consistentes (`0` éxito total/parcial controlado, `!=0` fallo sistémico).

## 6) Seguridad y cumplimiento mínimo

- Token vía entorno/secret manager, nunca en código.
- Sanitización de logs (sin secretos).
- Tráfico únicamente hacia API Webex.
- Artefactos de salida con datos mínimos necesarios.

## 7) SLO/criterios de éxito

- Soportar 21.000 registros en una corrida controlada.
- Tolerar fallos de fila sin abortar el job.
- Reintentos efectivos en errores transitorios con reducción de fallos por red/API.
- Reanudación funcional desde checkpoint ante interrupción.

## 8) Fuera de alcance (para evitar sobreingeniería)

- Nueva UI web.
- Nuevas capas de observabilidad enterprise complejas (tracing distribuido completo, etc.).
- Refactor masivo de SDK.
- Procesamiento paralelo agresivo no justificado por límites de API.
