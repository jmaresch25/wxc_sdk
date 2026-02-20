# Space_OdT v2.1 — Development Term Specification Sheet
## Próxima evolutiva backend (Webex SDK-first)

**Documento**: DTS-21-WEBEX-TRANSFORMACION  
**Versión**: 1.0  
**Estado**: Draft listo para implementación  
**Ámbito**: Automatización de acciones de Ubicación, Usuarios y Workspaces mediante `wxc_sdk`  
**Ruta objetivo de scripts**: `Space_OdT/v21/transformacion/`  
**Ruta objetivo de logs**: `Space_OdT/v21/transformacion/logs/`

---

## 1) Definición de lo que se construye

### 1.1 Qué es
Evolutiva backend basada en **scripts desacoplados por acción** para ejecutar operaciones de provisión y configuración en Webex Calling usando `wxc_sdk`.

### 1.2 Para quién es
Equipos técnicos de implantación/operación (PRE/PRO), con necesidad de ejecutar tareas repetibles, auditables y con salida rica en datos reales de API.

### 1.3 Problema que resuelve
Centraliza y estandariza acciones hoy dispersas (PSTN, numeraciones, permisos, licencias, forwarding, etc.) con foco en:
- mínimo boilerplate,
- alta mantenibilidad,
- escalabilidad por crecimiento de acciones,
- verbosidad útil en outputs con payload/response reales del SDK.

### 1.4 Cómo funcionará
Cada acción vive en **su propio script** dentro de `v21/transformacion`, con patrón uniforme:
1. leer estado actual (`read/list/details`),
2. aplicar cambio (`configure/update/create/add`),
3. emitir salida técnica detallada,
4. registrar trazas en **archivo de log dedicado por acción**.

### 1.5 Modelo conceptual (distilled)
- **Entidad**: `Location`, `Person`, `Workspace`.
- **Acción**: script unitario idempotente por capacidad SDK.
- **Contrato entrada**: parámetros obligatorios mínimos por acción.
- **Contrato salida**: resultado técnico verboso + resumen ejecutivo corto.
- **Trazabilidad**: 1 acción = 1 log file rotado por ejecución/fecha.

---

## 2) Diseño de experiencia operativa (UX técnica)

### 2.1 Historias de usuario (happy path)
1. Operador ejecuta script de acción con parámetros.
2. El script imprime contexto, request normalizado y respuesta real del SDK.
3. Se guarda log técnico en fichero propio.
4. Operador encadena siguiente script del flujo funcional.

### 2.2 Flujos alternativos
- Ejecución solo lectura para validación previa (sin escritura).
- Re-ejecución con mismos parámetros para contraste de estado (pre/post).
- Diferenciación de comportamiento por tipo de entidad (location/person/workspace).

### 2.3 Principios UX
- salida clara, útil y sin ocultar campos relevantes de API,
- estructura homogénea entre scripts,
- cero acoplamiento innecesario entre acciones.

---

## 3) Necesidades técnicas

## 3.1 Convenciones de implementación (obligatorias)

### Estructura de carpetas

```text
Space_OdT/v21/transformacion/
  ubicacion_configurar_pstn.py
  ubicacion_alta_numeraciones_desactivadas.py
  ubicacion_actualizar_cabecera.py
  ubicacion_configurar_llamadas_internas.py
  ubicacion_configurar_permisos_salientes_defecto.py
  usuarios_alta_people.py
  usuarios_alta_scim.py
  usuarios_modificar_licencias.py
  usuarios_anadir_intercom_legacy.py
  usuarios_configurar_desvio_prefijo53.py
  usuarios_configurar_perfil_saliente_custom.py
  workspaces_alta.py
  workspaces_anadir_intercom_legacy.py
  workspaces_configurar_desvio_prefijo53.py
  workspaces_configurar_perfil_saliente_custom.py
  logs/
```

### Logging por acción
- Cada script debe escribir en su propio fichero:
  - `logs/<nombre_script>.log`
- Formato recomendado:
  - timestamp, action_id, entidad, parámetros de entrada relevantes, request SDK, response SDK.
- No es prioridad en esta fase gestión avanzada de errores/mensajería ejecutiva interna.

### Estilo técnico
- Preferir funciones pequeñas sobre clases.
- Separar creación del cliente SDK del uso del cliente.
- Reutilizar helpers mínimos comunes solo si reducen boilerplate real.
- Evitar sobre-ingeniería y lógica transversal no esencial.

---

## 3.2 Matriz funcional oficial (SDK reference sheet)

| Sección | Acción | Subtareas / paso (visión SDK) | Campos obligatorios (SDK) | Referencia SDK | Documentación SDK | Método SDK |
| --- | --- | --- | --- | --- | --- | --- |
| Ubicación | Configurar PSTN de Ubicación | Leer configuración PSTN actual de la sede | `org_id` (opcional) | PSTN settings (org-level) | https://wxc-sdk.readthedocs.io/en/1.27.1/_modules/wxc_sdk/telephony/pstn.html | `api.telephony.pstn.list()` |
| Ubicación | Configurar PSTN de Ubicación | Aplicar conexión PSTN (`TRUNK`/`ROUTE_GROUP`) a la ubicación | `location_id`, `settings` (`PstnConnection`) | PSTN settings (location connection) | https://wxc-sdk.readthedocs.io/en/1.27.1/_modules/wxc_sdk/telephony/pstn.html | `api.telephony.pstn.configure(location_id=..., settings=...)` |
| Ubicación | Alta numeraciones en ubicación (estado desactivado) | Comprobar numeraciones actuales de la ubicación | `location_id`, `org_id` (opcional) | Location numbers (consulta) | https://wxc-sdk.readthedocs.io/en/1.26.0/_modules/wxc_sdk/telephony/location.html | `api.telephony.location.phone_numbers(location_id=...)` |
| Ubicación | Alta numeraciones en ubicación (estado desactivado) | Añadir bloque de DDIs (normalmente con `state=INACTIVE`) | `location_id`, `numbers` (lista `LocationNumber`) | Location numbers (alta) | https://wxc-sdk.readthedocs.io/en/1.26.0/_modules/wxc_sdk/telephony/location.html | `api.telephony.location.number.add(location_id=..., numbers=[...])` |
| Ubicación | Añadir cabecera de Ubicación | Leer detalle Webex Calling de la ubicación | `location_id`, `org_id` (opcional) | TelephonyLocation details | https://wxc-sdk.readthedocs.io/en/1.26.0/apidoc/wxc_sdk.telephony.location.html | `api.telephony.location.details(location_id=...)` |
| Ubicación | Añadir cabecera de Ubicación | Actualizar `calling_line_id.phone_number` con DDI cabecera | `location_id`, `settings` (`TelephonyLocation`) | TelephonyLocation update | https://wxc-sdk.readthedocs.io/en/1.26.0/apidoc/wxc_sdk.telephony.location.html | `api.telephony.location.update(location_id=..., settings=...)` |
| Ubicación | Configuración llamadas internas | Leer configuración actual de marcación interna | `entity_id=location_id`, `org_id` (opcional) | Location internal dialing (consulta) | https://wxc-sdk.readthedocs.io/en/1.27.1/apidoc/wxc_sdk.telephony.location.internal_dialing.html | `api.telephony.location.internal_dialing.read(entity_id=...)` |
| Ubicación | Configuración llamadas internas | Activar enrutado a `ROUTE_GROUP` para extensiones desconocidas | `entity_id=location_id`, `settings` (`InternalDialing`) | Location internal dialing (configuración) | https://wxc-sdk.readthedocs.io/en/1.27.1/apidoc/wxc_sdk.telephony.location.internal_dialing.html | `api.telephony.location.internal_dialing.configure(entity_id=..., settings=...)` |
| Ubicación | Configurar Permisos de Llamadas Salientes por Defecto | Leer permisos salientes por defecto de sede | `entity_id=location_id`, `org_id` (opcional) | Outgoing permissions (location lectura) | https://wxc-sdk.readthedocs.io/en/1.27.0/apidoc/wxc_sdk.person_settings.permissions_out.html | `api.telephony.location.permissions_out.read(entity_id=...)` |
| Ubicación | Configurar Permisos de Llamadas Salientes por Defecto | Aplicar perfil de permisos salientes “defecto” | `entity_id=location_id`, `settings` (`OutgoingPermissions`) | Outgoing permissions (location escritura) | https://wxc-sdk.readthedocs.io/en/1.27.0/apidoc/wxc_sdk.person_settings.permissions_out.html | `api.telephony.location.permissions_out.configure(entity_id=..., settings=...)` |
| Usuarios | Alta usuario | Crear usuario clásico (People API) con datos básicos | `person` (`emails`, `display_name`, etc.) | People management (alta directa) | https://wxc-sdk.readthedocs.io/en/1.21.1/apidoc/wxc_sdk.people.html | `api.people.create(person=...)` |
| Usuarios | Alta usuario | Crear usuario vía SCIM 2.0 (objetivo futuro recomendado) | `user` SCIM (`user_name`, `emails`, `active`, etc.) | SCIM 2 Users | https://wxc-sdk.readthedocs.io/en/1.26.0/apidoc/wxc_sdk.scim.users.html | `api.scim.users.create(user=...)` |
| Usuarios | Modificación de licencias en usuarios | Consultar licencias asignadas a usuario(s) | `org_id` (opcional), `license_id` (opcional), `user_id` (opcional) | Licenses assigned users | https://wxc-sdk.readthedocs.io/en/1.27.1/_modules/wxc_sdk/licenses.html | `api.licenses.assigned_users(license_id=..., org_id=...)` |
| Usuarios | Modificación de licencias en usuarios | Añadir/eliminar licencias (PATCH masivo GICAR/SOSTIC) | `org_id` (opcional), `request` (`LicenseAssignmentRequest`) | Licenses assign | https://wxc-sdk.readthedocs.io/en/1.27.1/_modules/wxc_sdk/licenses.html | `api.licenses.assign_licenses_to_users(org_id=..., request=...)` |
| Usuarios | Añadir Número de Intercomunicación Legacy (Secundario) | Leer numeraciones actuales del usuario | `entity_id=person_id`, `org_id` (opcional) | Person numbers (lectura) | https://wxc-sdk.readthedocs.io/en/1.27.1/apidoc/wxc_sdk.person_settings.numbers.html | `api.person_settings.numbers.read(entity_id=...)` |
| Usuarios | Añadir Número de Intercomunicación Legacy (Secundario) | Actualizar numeraciones añadiendo DDI secundario (`primary=false`, `action=ADD`) | `entity_id=person_id`, `numbers` (`PersonNumbers`) | Person numbers (actualización) | https://wxc-sdk.readthedocs.io/en/1.27.1/apidoc/wxc_sdk.person_settings.numbers.html | `api.person_settings.numbers.update(entity_id=..., numbers=...)` |
| Usuarios | Configurar Desvío a Plataforma Antigua (Prefijo 53) | Leer configuración actual de desvíos del usuario | `entity_id=person_id`, `org_id` (opcional) | Person forwarding (lectura) | https://wxc-sdk.readthedocs.io/en/1.27.1/apidoc/wxc_sdk.person_settings.forwarding.html | `api.person_settings.forwarding.read(entity_id=...)` |
| Usuarios | Configurar Desvío a Plataforma Antigua (Prefijo 53) | Activar desvío `always` hacia `53 + extensión` | `entity_id=person_id`, `settings` (`Forwarding`) | Person forwarding (configuración) | https://wxc-sdk.readthedocs.io/en/1.27.1/apidoc/wxc_sdk.person_settings.forwarding.html | `api.person_settings.forwarding.configure(entity_id=..., settings=...)` |
| Usuarios | Configurar Perfil de Llamadas Salientes (si difiere del defecto) | Leer permisos salientes efectivos del usuario | `entity_id=person_id`, `org_id` (opcional) | Outgoing permissions (user lectura) | https://wxc-sdk.readthedocs.io/en/1.27.0/apidoc/wxc_sdk.person_settings.permissions_out.html | `api.person_settings.permissions_out.read(entity_id=...)` |
| Usuarios | Configurar Perfil de Llamadas Salientes (si difiere del defecto) | Aplicar perfil custom (`useCustomEnabled`, categorías, etc.) | `entity_id=person_id`, `settings` (`OutgoingPermissions`) | Outgoing permissions (user escritura) | https://wxc-sdk.readthedocs.io/en/1.27.0/apidoc/wxc_sdk.person_settings.permissions_out.html | `api.person_settings.permissions_out.configure(entity_id=..., settings=...)` |
| Workspaces | Alta de Workspace | Crear workspace (`displayName`, `location`, tipo, etc.) | `display_name` (mínimo), opcional `location_id`, `calling` | Workspaces API alta | https://wxc-sdk.readthedocs.io/en/1.26.0/apidoc/wxc_sdk.workspaces.html | `api.workspaces.create(workspace=Workspace.create(display_name=...))` |
| Workspaces | Alta de Workspace | Consultar/buscar workspaces (validación duplicados) | filtros opcionales (`display_name`, `location_id`, etc.) | Workspaces API consulta | https://wxc-sdk.readthedocs.io/en/1.26.0/apidoc/wxc_sdk.workspaces.html | `api.workspaces.list(display_name=..., location_id=...)` |
| Workspaces | Añadir Número de Intercomunicación Legacy (Secundario) | Leer numeraciones actuales del workspace | `entity_id=workspace_id`, `org_id` (opcional) | Workspace numbers (lectura) | https://wxc-sdk.readthedocs.io/en/1.27.1/apidoc/wxc_sdk.workspace_settings.numbers.html | `api.workspace_settings.numbers.read(entity_id=...)` |
| Workspaces | Añadir Número de Intercomunicación Legacy (Secundario) | Actualizar numeraciones añadiendo DDI secundario (`primary=false`, `action=ADD`) | `entity_id=workspace_id`, `numbers` (lista TNs) | Workspace numbers (actualización) | https://wxc-sdk.readthedocs.io/en/1.27.1/apidoc/wxc_sdk.workspace_settings.numbers.html | `api.workspace_settings.numbers.update(entity_id=..., numbers=...)` |
| Workspaces | Configurar Desvío a Plataforma Antigua (Prefijo 53) | Leer configuración de desvíos del workspace | `entity_id=workspace_id`, `org_id` (opcional) | Workspace forwarding (lectura) | https://wxc-sdk.readthedocs.io/en/1.27.1/apidoc/wxc_sdk.workspace_settings.forwarding.html | `api.workspace_settings.forwarding.read(entity_id=...)` |
| Workspaces | Configurar Desvío a Plataforma Antigua (Prefijo 53) | Activar desvío `always` hacia `53 + extensión` | `entity_id=workspace_id`, `settings` (`Forwarding`) | Workspace forwarding (configuración) | https://wxc-sdk.readthedocs.io/en/1.27.1/apidoc/wxc_sdk.workspace_settings.forwarding.html | `api.workspace_settings.forwarding.configure(entity_id=..., settings=...)` |
| Workspaces | Configurar Perfil de Llamadas Salientes (si difiere del defecto) | Leer permisos salientes efectivos del workspace | `entity_id=workspace_id`, `org_id` (opcional) | Outgoing permissions (workspace lectura) | https://wxc-sdk.readthedocs.io/en/1.27.0/apidoc/wxc_sdk.person_settings.permissions_out.html | `api.workspace_settings.permissions_out.read(entity_id=...)` |
| Workspaces | Configurar Perfil de Llamadas Salientes (si difiere del defecto) | Aplicar perfil custom de permisos salientes | `entity_id=workspace_id`, `settings` (`OutgoingPermissions`) | Outgoing permissions (workspace escritura) | https://wxc-sdk.readthedocs.io/en/1.27.0/apidoc/wxc_sdk.person_settings.permissions_out.html | `api.workspace_settings.permissions_out.configure(entity_id=..., settings=...)` |

---

## 4) Implement testing and security measures

### 4.1 Testing (objetivo MVP)
- Unit tests para normalización de entrada por script.
- Smoke tests de composición request/response (mock SDK).
- Validación de contrato de salida (estructura y campos verbosos esperados).

### 4.2 Side-effects
- Riesgo de configuraciones inconsistentes si se altera el orden lógico read→write.
- Riesgo funcional por versionado SDK entre 1.26.x y 1.27.x.

### 4.3 Seguridad de salida y logs
- Enmascarar secretos/tokens.
- Guardar solo parámetros funcionales.
- Evitar incluir credenciales en command-line history.

---

## 5) Plan de trabajo

### 5.1 Estimación
- 5–7 días hábiles (MVP técnico).

### 5.2 Milestones
1. **Base común mínima** (0.5–1 día): utilidades de cliente SDK + logger por script.
2. **Ubicación** (1.5–2 días): PSTN, numeraciones, cabecera, internas, permisos.
3. **Usuarios** (1.5–2 días): alta, licencias, números legacy, forwarding, permisos.
4. **Workspaces** (1.5–2 días): alta, números legacy, forwarding, permisos.
5. **Hardening documental** (0.5 día): ejemplos de ejecución y outputs.

### 5.3 Definition of Done
- Cada acción implementada en script independiente bajo `v21/transformacion`.
- Cada script con su log dedicado en `v21/transformacion/logs`.
- Output verboso útil con información real devuelta por SDK.
- Boilerplate minimizado y helpers comunes estrictamente necesarios.

---

## 6) Ripple effects

- Actualizar documentación operativa de ejecución por lotes.
- Alinear naming y orden de ejecución con equipos PRE/PRO.
- Publicar catálogo de scripts y parámetros obligatorios en runbook.

---

## 7) Contexto amplio y evolución

### 7.1 Limitaciones actuales
- Sin capa de orquestación global unificada (intencional en MVP).
- Sin framework avanzado de recuperación/errores en primera fase.

### 7.2 Evoluciones recomendadas
- Motor de pipeline declarativo (YAML/JSON) que encadene scripts.
- Idempotencia fuerte por hash de entrada y estado remoto.
- Report consolidado multi-acción por entidad.

### 7.3 Moonshot
- Control plane de transformaciones con scheduling, dry-run integral y diff automático pre/post sobre estado Webex.


---

## 8) Diseño detallado launcher multi-CSV + bulk + resiliencia 24h

### 8.1 Definición de lo que se construye
- Se implementa una evolución de `launcher_csv_dependencias.py` para cargar parámetros desde **4 CSV fijos** en una única raíz (`--input_dir`):
  - `global.csv` (parámetros transversales)
  - `ubicaciones.csv`
  - `usuarios.csv`
  - `workspaces.csv` (opcional en MVP actual)
- Problema que resuelve:
  1. Evitar mezclar columnas de dominios distintos en un único CSV.
  2. Permitir ejecución por lote real (múltiples filas) en usuarios y ubicaciones (y opcionalmente workspaces).
  3. Mantener el proceso estable hasta 24h frente a 429 y fallos de red.
- Modelo simplificado (distilled):
  - **Dataset global (1 fila)** + **dataset de dominio (N filas)**
  - **Script** consume sólo las claves que declare.
  - **Bulk mode** = iteración fila a fila con reintentos y reporte acumulado (`ok/error logs`).

### 8.2 UX operativa (cómo se usará)

#### Story principal
1. El operador lanza el launcher con `--input_dir .artifacts/...`.
2. El launcher carga `global.csv` al inicio y, por cada script, detecta su dominio (`ubicacion_`, `usuarios_`, `workspaces_`).
3. Antes de ejecutar cada script, pregunta: **¿ejecución bulk para este script?**
4. Si respuesta = sí, procesa todas las filas del CSV de dominio; si no, usa la primera fila o la fila filtrada.
5. Genera un informe final con éxitos/errores por fila.

#### Logging operativo para >4000 filas (detalle requerido)
- Para volumen alto se separa en dos salidas append-only por script/ejecución:
  - `*_ok.csv`: una línea por operación aplicada correctamente (mínimo `row_index`, `script_name`, `entity_id/person_id/workspace_id`, `timestamp`, `payload_hash`).
  - `*_error.jsonl`: una línea JSON por fallo con error completo (`traceback`, respuesta remota completa, parámetros de entrada normalizados).
- Razón de diseño: CSV facilita recálculo/reproceso manual de éxitos; JSONL preserva errores completos sin truncado y evita un JSON gigante en memoria.
- Convención MVP: nunca se sobreescriben logs, solo append; cada ejecución crea sufijo de fecha/hora para auditoría.

#### Flujos alternativos
- Si falta `global.csv` o el CSV de dominio: error explícito (`missing_input_csv`).
- Si hay columnas desconocidas: warning + ignorar (modo tolerante), o fail-fast en `--strict-schema`.
- Si proceso se interrumpe: en MVP se reanuda manualmente depurando el CSV (eliminar filas ya exitosas) y relanzando.

#### Confirmación de lectura de parámetros (estado actual)
- CSV detectados para extracción real de parámetros en `Space_OdT/.artifacts/exports` (estos se toman como **campos core** de partida, aunque podrán ampliarse en el tiempo):
  - `locations.csv` → `location_id, name, org_id, timezone, language, address_1, city, state, postal_code, country`
  - `people.csv` → `person_id, email, display_name, status, roles, licenses, location_id, webex_calling_enabled`
  - `workspaces.csv` → `id, workspace_id, name, location_id, extension, phone_number, webex_calling_enabled`
- Decisión de transición:
  1. Mantener compatibilidad temporal para leer desde `Space_OdT/.artifacts/exports`.
  2. Objetivo final: mover contrato a `Space_OdT/input_data/{global,ubicaciones,usuarios,workspaces}.csv`.
  3. Añadir validación estricta de headers en arranque para detectar drift.

### 8.3 Contrato de datos y carga inicial

#### Ubicación de entrada
- A partir de ahora se considera una sola jerarquía de artifacts bajo `Space_OdT/.artifacts`.
- `--input_dir` apunta al directorio que contiene los 4 CSV con nombres fijos indicados arriba.

#### Política de merge
- `params_finales = merge(global_row, domain_row)`
- Regla: **dominio sobreescribe global** cuando coinciden claves.
- El launcher conserva metadatos de origen (`source_map`) para trazabilidad en logs.

#### Campos de referencia
- La clasificación de campos debe alinearse con los CSV ya distribuidos por área en `.artifacts`.
- Si un campo aparece en dos áreas (ej. `extension`), se acepta duplicación intencional: cada script tomará sólo lo que necesite.

### 8.4 Diseño técnico del launcher

#### Resolución dominio por script
- `ubicacion_*` → `ubicaciones.csv`
- `usuarios_*` → `usuarios.csv`
- `workspaces_*` → pendiente (de momento scripts de workspace no activos en launcher; dejar preparado para activación posterior).

#### Pregunta de bulk por script
- Nuevo prompt por script (si no `--auto-confirm`):
  - `¿Ejecutar <script> en modo BULK con todas las filas del CSV de dominio? [y/N]`
- Flags no interactivos:
  - `--bulk-all`: fuerza bulk para todos los scripts seleccionados.
  - `--no-bulk-all`: fuerza modo single para todos.

#### Estrategia de ejecución
- **Single mode**: 1 payload (primera fila o fila filtrada por `--row-index`/`--match key=value`).
- **Bulk mode**: 1 payload por fila válida del CSV de dominio.
- Cada payload pasa por:
  1. validación dependencias del script,
  2. confirmación,
  3. ejecución con política de reintentos,
  4. persistencia de resultado.

#### Reporte y trazabilidad
- Salida JSON final con estructura:
  - `script_name`
  - `bulk_mode`
  - `total_rows`, `executed`, `skipped`, `errors`
  - `results[]` con `row_index`, `params_hash`, `status`, `error_type`, `error`
- Para MVP no se introduce motor de checkpoint automático (evitar boilerplate):
  - se persiste `*_ok.csv` y `*_error.jsonl` por ejecución,
  - la reanudación se hace ajustando manualmente el CSV de entrada según `*_ok.csv`.

### 8.5 Resiliencia 24h (429 + conectividad remota)

#### Política de reintentos recomendada
- Priorizar ventajas del SDK (`wxc_sdk`) para reducir boilerplate:
  - encapsular acceso API vía métodos SDK (no HTTP manual salvo gaps puntuales),
  - centralizar retry/backoff en helper común reutilizable por todos los scripts,
  - evaluar `asyncio`/API asíncrona del SDK para bulk I/O-bound con concurrencia limitada y controlada.
- Reintentar en:
  - HTTP `429`, `500`, `502`, `503`, `504`
  - excepciones de red (`ConnectionError`, `Timeout`, DNS/transient socket errors)
- Backoff:
  - Si `Retry-After` existe: respetarlo.
  - Si no existe: `base * 2^attempt + jitter` (cap por espera máxima).
- Límites sugeridos:
  - `max_retries_per_call`: 12
  - `max_sleep_seconds`: 300
  - `max_elapsed_per_row`: 1800s

#### Gestión de salud de ejecución larga
- Heartbeat de progreso cada X minutos (filas procesadas, ETA, tasa error).
- Pausa automática si ratio de error > umbral en ventana móvil.
- Reanudación manual guiada por `*_ok.csv` para no repetir filas ya exitosas.
- Opción `--fail-fast` para entornos donde no conviene continuar tras primer error grave.

#### Idempotencia y seguridad
- No loguear token ni secretos.
- Registrar hash de payload para deduplicar reintentos.
- Marcar explícitamente operaciones potencialmente no idempotentes (`create`) y ofrecer `--dry-run` previo.

### 8.6 Standalone en cada script (`--bulk` + `--input_dir`)

Cada script de `transformacion/` debe soportar:
- `--bulk` (itera filas del CSV de su dominio)
- `--input_dir` (directorio con `global.csv` + CSV de dominio)

#### Contrato runtime standalone
1. Determinar dominio por nombre del propio script.
2. Cargar `global.csv` y `<dominio>.csv`.
3. Construir payload por fila con merge `global <- dominio`.
4. Ejecutar función principal del script con:
   - modo single: fila 0
   - modo bulk: todas las filas válidas
5. Emitir resumen final homogéneo con launcher.

#### Compatibilidad
- Mantener argumentos explícitos actuales (CLI individual) con prioridad superior al CSV.
- Regla de prioridad final:
  - `CLI > dominio.csv > global.csv > default interno`

### 8.7 Testing y quality gates

#### Unit tests mínimos
- resolución de CSV por dominio
- merge de parámetros y precedencia
- parser de bulk/single
- backoff + parser de `Retry-After`
- lectura multi-fila y filtrado de filas inválidas

#### Integration/smoke tests
- dry-run de 1 script por dominio en single y bulk
- simulación de 429 (mock) para validar reintentos + escritura de logs `ok/error`
- test de reanudación manual tras interrupción (filtrado de CSV usando `*_ok.csv`)

#### Criterio DoD
- launcher con soporte 4 CSV y pregunta bulk por script
- scripts standalone compatibles con `--bulk --input_dir`
- reintentos robustos + logs `ok/error` + reporte agregado
- documentación operativa actualizada

### 8.8 Plan de trabajo y riesgos

#### Estimación
- 3–5 días técnicos:
  1. Refactor common I/O + retry policy (1 día)
  2. Launcher multi-CSV + bulk orchestration (1 día)
  3. Adaptación de scripts standalone (1–2 días)
  4. Tests + hardening + docs (1 día)

#### Riesgos clave
- inconsistencias de headers entre CSV por área
- operaciones no idempotentes en bulk
- límite de rate API en ventanas largas

#### Mitigaciones
- validación de schema al arranque
- logs `ok/error` y reintento por fila
- throttle configurable (`--min-interval-ms`)

### 8.9 Ripple effects
- Actualizar runbooks de operación y ejemplos de comando.
- Comunicar cambio de contrato de entrada (4 CSV + input_dir).
- Ajustar generadores para mantener nombres/headers estables en `Space_OdT/.artifacts`.

### 8.10 Contexto amplio
- Limitación actual: el modelo de campos seguirá evolucionando con nuevas acciones.
- Extensión futura: versionado de esquema (`schema_version`) y validador automático previo a ejecución.
- Moonshot: orquestador declarativo de pipelines con diff pre/post por entidad y ventana horaria de ejecución.
