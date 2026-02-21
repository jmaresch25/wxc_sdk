# Estado real v2.1.1: ejecución bulk en UI 211

> Este documento reemplaza el plan original y describe **lo que existe hoy** en el repositorio.

## 1) Qué está construido

La UI `v2.1.1` ya permite ejecutar acciones en modo normal o en modo bulk con chunking y paralelismo en memoria.

- Backend UI: `Space_OdT/v21/ui_v211.py`
- Runner bulk: `Space_OdT/v21/transformacion/bulk_runner.py`
- Handlers disponibles: `Space_OdT/v21/transformacion/launcher_csv_dependencias.py`

### Funcionamiento actual del bulk

1. Se cargan datasets (`locations`, `users`, `numbers`) en memoria.
2. Se elige acción y mapeo (opcional).
3. Si bulk está activo, las filas se dividen en chunks.
4. Cada chunk se procesa en paralelo con `ThreadPoolExecutor`.
5. Se consolida resultado por orden (`orders`) y por fila (`results`).
6. Se escribe log en `Space_OdT/v21/transformacion/logs/<action_id>.log`.

## 2) UX real de la UI 211

La UI sí incluye:
- check de “Modo bulk”,
- `chunk_size`,
- `max_workers`,
- resumen de ejecución con `orders_total`.

También marca acciones fuera de alcance con etiqueta `en desarrollo` y bloquea su ejecución.

## 3) Estado de acciones (real)

### Acciones ejecutables hoy (registradas en `HANDLERS`)

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

### Acciones visibles pero marcadas `en desarrollo`

- `ubicacion_configurar_pstn`
- `usuarios_alta_people`
- `usuarios_alta_scim`
- `workspaces_alta`
- `workspaces_anadir_intercom_legacy`
- `workspaces_configurar_desvio_prefijo53`
- `workspaces_configurar_perfil_saliente_custom`

> Nota: aunque `workspaces_configurar_perfil_saliente_custom` existe en `HANDLERS`, la UI la mantiene marcada como `en desarrollo` y no se puede aplicar desde la UI.

## 4) Diferencias respecto al plan original

No existe actualmente un sistema de jobs persistentes ni polling contra órdenes asíncronas remotas del SDK.

Lo que sí existe:
- paralelización local por threads,
- consolidación determinista de resultados,
- tests unitarios para chunking/merge y flujo bulk de UI.

Lo pendiente para un “bulk asíncrono full”:
- cola persistente (Redis/RQ/Celery o similar),
- reanudación tras reinicio,
- estado duradero de órdenes,
- retries/backoff transversales por lote en UI.

## 5) Validación recomendada

- `pytest -q tests/test_space_odt_v21_bulk_runner.py`
- `pytest -q tests/test_space_odt_v21_ui_v211.py`

