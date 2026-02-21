# Space_OdT v2.1 — Estado actual backend (Webex SDK-first)

> Documento actualizado para reflejar la realidad del repositorio en lugar de una propuesta futura.

## 1) Definición de lo construido

El backend de transformaciones v21 ya está implementado como scripts desacoplados por acción en `Space_OdT/v21/transformacion/` y un launcher CSV que invoca acciones según dependencias.

### Para quién es
Equipos de operación técnica que ejecutan cambios masivos sobre Ubicación/Usuarios/Workspaces con trazabilidad por fila.

### Problema que resuelve hoy
- Estandariza ejecución por scripts.
- Permite ejecución por CSV y mapeo de parámetros.
- Devuelve respuestas normalizadas por fila para reporting.

## 2) Arquitectura real

### Componentes vigentes

- `launcher_csv_dependencias.py`
  - carga CSV,
  - valida dependencias,
  - ejecuta handlers,
  - incorpora retry básico con `Retry-After`.
- `generar_csv_candidatos_desde_artifacts.py`
  - define `SCRIPT_DEPENDENCIES` para parámetros requeridos.
- `common.py`
  - carga token/config,
  - configura logger por script en `transformacion/logs`.
- scripts de acción `ubicacion_*`, `usuarios_*`, `workspaces_*`
  - encapsulan llamadas al SDK con resultado normalizado.

### Estado real de handlers en launcher

Activos:
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

Definidos en código pero comentados/no activos en launcher:
- `ubicacion_configurar_pstn`
- `usuarios_alta_people`
- `usuarios_alta_scim`
- `workspaces_alta`
- `workspaces_anadir_intercom_legacy`
- `workspaces_configurar_desvio_prefijo53`
- `workspaces_configurar_desvio_prefijo53_telephony`
- `workspaces_validar_estado_permisos`

## 3) Contratos de entrada/salida (real)

- Entrada principal: CSV con columnas canónicas o mapeadas.
- Validación: dependencias requeridas por acción (`SCRIPT_DEPENDENCIES`).
- Salida: diccionarios por fila con estado (`ok/error`), payload y metadatos útiles de ejecución.

## 4) Testing existente

Hay cobertura específica para:
- utilidades de bulk,
- flujo de UI v211,
- launcher CSV y validaciones de dependencias,
- acciones concretas de transformación.

## 5) Próxima evolutiva recomendada (pendiente real)

1. Descomentar/activar handlers pendientes de forma gradual.
2. Homogeneizar políticas de retry/backoff entre launcher y UI.
3. Resolver divergencias entre tests y estado real de handlers para evitar falsos negativos.
4. Si se requiere asíncrono robusto: persistencia de jobs y reanudación tras reinicio.

