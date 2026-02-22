# Space_OdT v2.1 — README unificado

Este documento consolida y actualiza la información operativa de `Space_OdT` enfocada en **v2.1 (UI + backend de transformaciones)**, sustituyendo documentos previos dispersos.

## 1) Qué se construye

### Qué es
Plataforma técnica para ejecutar transformaciones masivas en Webex Calling con trazabilidad por fila, combinando:
- **UI v2.1.1** para operación guiada.
- **Backend SDK-first** con scripts desacoplados por acción.
- **Ejecución bulk local** con chunking y paralelismo.

### Para quién
Equipos de operación técnica/implantación que necesitan cambios repetibles en:
- Ubicaciones.
- Usuarios.
- Workspaces.

### Problema que resuelve
- Evita ejecuciones manuales inconsistentes.
- Normaliza entrada CSV + validación de dependencias.
- Entrega resultados auditables (`orders`, `results`, logs por acción).

### Conceptos principales
- **Acción**: script funcional (`ubicacion_*`, `usuarios_*`, `workspaces_*`).
- **Handler**: acción habilitada en el launcher/UI.
- **Bulk run**: ejecución por lotes (`chunk_size`) y concurrencia (`max_workers`).
- **Dependencias de datos**: columnas requeridas por acción.
- **Trazabilidad**: salida por fila + log técnico por ejecución.

---

## 2) Diseño de experiencia de uso (operador)

### Flujo principal (happy path)
1. Preparar CSV y, si aplica, mapeo de columnas.
2. Seleccionar acción en UI 211.
3. Activar modo bulk y ajustar `chunk_size` / `max_workers`.
4. Ejecutar y revisar resumen (`orders_total`) + resultados por fila.
5. Auditar log en `Space_OdT/v21/transformacion/logs/<action_id>.log`.

### Flujos alternativos
- **Acción en desarrollo**: visible pero bloqueada para ejecución.
- **Errores por dependencia faltante**: falla temprana antes de ejecutar.
- **Rate limit/transitorios**: retry básico respetando `Retry-After` en launcher.

### Impacto UI
La UI actual ya incorpora controles de bulk, resumen de ejecución y bloqueo de acciones no habilitadas. No se requiere navegación adicional compleja para el MVP operativo.

---

## 3) Necesidades técnicas y arquitectura

### Componentes base
- `ui_v211.py`: orquestación desde UI.
- `transformacion/bulk_runner.py`: chunking + paralelismo + merge de resultados.
- `transformacion/launcher_csv_dependencias.py`: lectura CSV, validación de dependencias, ejecución de handlers.
- `transformacion/generar_csv_candidatos_desde_artifacts.py`: dependencias por script.
- `transformacion/common.py`: token/config/logger.

### Contratos de datos
- **Entrada**: CSV con columnas canónicas o mapeadas.
- **Validación**: dependencias requeridas por acción.
- **Salida**: dict por fila con estado (`ok/error`), payload y metadatos.

### Acciones operativas hoy
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

### Acciones pendientes / en desarrollo
- `ubicacion_configurar_pstn`
- `usuarios_alta_people`
- `usuarios_alta_scim`
- `workspaces_alta`
- `workspaces_anadir_intercom_legacy`
- `workspaces_configurar_desvio_prefijo53`
- `workspaces_configurar_desvio_prefijo53_telephony`
- `workspaces_validar_estado_permisos`

---

## 4) Testing y seguridad

### Testing mínimo recomendado
- Bulk runner (chunking, merge, orden determinista).
- UI 211 (flujo bulk y bloqueo de acciones en desarrollo).
- Launcher CSV (dependencias, validaciones, ejecución por handler).
- Tests de scripts críticos de transformación.

### Seguridad/robustez para operar
- Gestión de token por configuración/entorno (sin hardcode).
- Validación temprana de entradas para reducir errores de ejecución.
- Logs por acción para auditoría.
- Manejo de límites de API con retry básico (`Retry-After`).

---

## 5) Plan de evolución (priorizado)

### MVP evolutivo (requerido)
1. Activar gradualmente handlers pendientes con pruebas por acción.
2. Homogeneizar estrategia retry/backoff entre UI y launcher.
3. Eliminar divergencias entre tests y catálogo real de handlers.

### Siguiente nivel (opcional, alto impacto)
4. Persistencia de jobs (cola externa) + reanudación tras reinicio.
5. Estado duradero/polling para asíncrono robusto end-to-end.

### Riesgos clave
- Integraciones externas (límites API y variaciones de payload).
- Calidad de datos CSV de entrada.
- Desalineación entre UI, launcher y pruebas.

---

## 6) Ripple effects (fuera de código)

- Mantener esta documentación sincronizada al activar/desactivar handlers.
- Comunicar a operación qué acciones están habilitadas vs en desarrollo.
- Alinear plantillas CSV y guías internas con las dependencias reales por acción.

---

## 7) Contexto amplio

### Límites actuales
- El bulk actual es paralelo en memoria; no hay cola persistente nativa.
- No existe reanudación automática tras caída del proceso.

### Extensiones futuras
- Modo “job manager” persistente (Redis/RQ/Celery equivalente).
- Observabilidad centralizada de ejecuciones (métricas + dashboard).
- Plantillas y validaciones más estrictas por dominio (usuarios, sedes, workspaces).

---

## Comandos de validación recomendados

```bash
pytest -q tests/test_space_odt_v21_bulk_runner.py
pytest -q tests/test_space_odt_v21_ui_v211.py
```

