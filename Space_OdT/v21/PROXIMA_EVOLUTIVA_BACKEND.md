# Space_OdT v2.1 — Próxima evolutiva
## Development Term Specification Sheet (SDK + UI)

**Documento**: DTS-21-WEBEX-TRANSFORMACION  
**Versión**: 1.2  
**Estado**: Draft listo para implementación  
**Ámbito**: Automatización de acciones de Ubicación, Usuarios y Workspaces mediante `wxc_sdk`  
**Ruta objetivo de scripts**: `Space_OdT/v21/transformacion/`  
**Ruta objetivo de logs**: `Space_OdT/v21/transformacion/logs/`

---

## 1) Define what we are building

### 1.1 Qué es
Una evolución funcional única (backend + UI operativa) para ejecutar acciones de provisión/configuración en Webex Calling con patrón **1 acción = 1 script** y trazabilidad por log.

### 1.2 Para quién es
Para el equipo responsable de ejecutar y supervisar las transformaciones técnicas de telefonía.

### 1.3 Problema que resuelve
Evita flujos manuales dispersos, reduce inconsistencias entre acciones y permite ejecución repetible con salida técnica detallada de SDK.

### 1.4 Cómo va a funcionar
- Menú UI por secciones (Ubicación, Usuarios, Workspaces).
- Cada acción abre su pantalla dedicada.
- Cada pantalla dispara su script correspondiente en `v21/transformacion`.
- Cada ejecución persiste su log en archivo dedicado en `v21/transformacion/logs`.

### 1.5 Conceptos principales
- **Entidad**: `Location`, `Person`, `Workspace`.
- **Acción**: unidad ejecutable independiente.
- **Submétodo SDK**: lectura, escritura o variación complementaria.
- **Evidencia**: output SDK + log técnico por acción.

---

## 2) Design the user experience

## 2.1 Menú de navegación obligatorio
- **Ubicación**
  - Configurar PSTN de Ubicación
  - Alta numeraciones en ubicación (estado desactivado)
  - Añadir cabecera de Ubicación
  - Configuración llamadas internas
  - Configurar Permisos de Llamadas Salientes por Defecto
- **Usuarios**
  - Alta usuario
  - Modificación de licencias en usuarios
  - Añadir Número de Intercomunicación Legacy (Secundario)
  - Configurar Desvío a Plataforma Antigua (Prefijo 53)
  - Configurar Perfil de Llamadas Salientes (si difiere del defecto)
- **Workspaces**
  - Alta de Workspace
  - Añadir Número de Intercomunicación Legacy (Secundario)
  - Configurar Desvío a Plataforma Antigua (Prefijo 53)
  - Configurar Perfil de Llamadas Salientes (si difiere del defecto)

## 2.2 Layout base de pantalla (común)
1. **Formulario** (obligatorios + opcionales)
2. **Botonera de acción** (leer/validar, aplicar, refrescar salida)
3. **Panel de resultados**
   - Tab 1: Output SDK (JSON técnico)
   - Tab 2: Log técnico de archivo
   - Tab 3: Resumen legible de ejecución

## 2.3 Diseño frontend por acción (diferenciado)
> Requisito explícito: no se reutiliza exactamente la misma UI para todas las acciones.

| Sección | Acción | Qué se muestra | Botones | Espacio de logs/salida |
| --- | --- | --- | --- | --- |
| Ubicación | Configurar PSTN | `location_id`, selector `TRUNK/ROUTE_GROUP`, `premiseRouteId`, estado PSTN actual | `Leer PSTN actual`, `Configurar PSTN`, `Releer estado` | Comparativa pre/post + log de `pstn.list` y `pstn.configure` |
| Ubicación | Alta numeraciones | Cargador de lista DDIs/TNs, tipo número, estado deseado (`INACTIVE`), numeración existente | `Consultar numeraciones`, `Prevalidar bloque`, `Añadir bloque` | Tabla aceptadas/rechazadas por TN + log por número |
| Ubicación | Añadir cabecera | `location_id`, DDI cabecera propuesta, cabecera actual | `Leer detalle ubicación`, `Actualizar cabecera` | Bloque diff `calling_line_id` (antes/después) + log de update |
| Ubicación | Llamadas internas | Política actual de marcación, target route group | `Leer política`, `Aplicar política` | Diff política y log de `internal_dialing.read/configure` |
| Ubicación | Permisos salientes por defecto | Perfil actual y categorías editables | `Leer permisos`, `Aplicar perfil por defecto` | Resumen de categorías cambiadas + log técnico |
| Usuarios | Alta usuario | Formulario personas (email, display_name, etc.), vista modo People vs SCIM | `Crear con People API`, `Crear con SCIM` | Resultado de alta + id creado + log del método elegido |
| Usuarios | Modificar licencias | Usuario objetivo, licencias actuales, selección add/remove | `Leer licencias`, `Aplicar cambios licencias` | Resultado por usuario + log de `assigned_users` y `assign_licenses...` |
| Usuarios | Intercom legacy secundario | Números actuales, input DDI secundario | `Leer números`, `Añadir secundario` | Lista final de números + log `numbers.read/update` |
| Usuarios | Desvío prefijo 53 | Estado forwarding actual, extensión destino | `Leer desvío`, `Activar desvío 53+ext` | Estado always antes/después + log forwarding |
| Usuarios | Perfil saliente custom | Perfil actual, toggles custom y categorías | `Leer perfil`, `Aplicar perfil custom` | Diff por categoría + log permissions |
| Workspaces | Alta workspace | `display_name`, `location_id`, tipo, calling; chequeo duplicados | `Buscar duplicados`, `Crear workspace` | Resultado de creación + id + log |
| Workspaces | Intercom legacy secundario | Números workspace actuales + input DDI secundario | `Leer números`, `Añadir secundario` | Lista final + log `workspace_settings.numbers` |
| Workspaces | Desvío prefijo 53 | Forwarding actual + extensión destino | `Leer desvío`, `Activar desvío 53+ext` | Estado before/after + log forwarding |
| Workspaces | Perfil saliente custom | Permisos actuales + configuración custom | `Leer perfil`, `Aplicar perfil custom` | Cambios aplicados + log permissions |

## 2.4 Wireframe funcional
```text
┌────────────────────────────────────────────────────────────────────┐
│ Menú lateral                                                      │
│  Ubicación / Usuarios / Workspaces                               │
├────────────────────────────────────────────────────────────────────┤
│ Encabezado acción + descripción corta + script asociado          │
├────────────────────────────────────────────────────────────────────┤
│ Formulario específico de acción                                   │
│ [botón leer/validar] [botón aplicar] [botón refrescar]           │
├────────────────────────────────────────────────────────────────────┤
│ Tabs: Output SDK | Log técnico (archivo) | Resumen ejecución      │
└────────────────────────────────────────────────────────────────────┘
```

## 2.5 User stories
### Happy flow
1. Seleccionar sección y acción.
2. Completar obligatorios.
3. Leer estado actual.
4. Aplicar cambio.
5. Validar output + log.

### Alternative flows
- Solo lectura (auditoría/precheck).
- Reintento con otro submétodo SDK cuando existen variantes para la misma acción funcional.

---

## 3) Understand technical needs

## 3.1 Convenciones de implementación
```text
Space_OdT/v21/transformacion/
  <accion>.py
  logs/<accion>.log
```

- Cada acción en su script independiente.
- Cada script escribe en su log dedicado.
- Funciones pequeñas, sin sobre-ingeniería.
- Separar creación del cliente SDK de la ejecución de la acción.

## 3.2 Versatilidad por acciones con mismo nombre
Hay acciones con mismo nombre funcional porque se catalogaron múltiples métodos del SDK que ayudan a completar la tarea (lectura + escritura + variantes). Esto es intencional. La implementación debe seleccionar dinámicamente el método más adecuado según necesidad operativa.

## 3.3 Matriz funcional oficial (SDK reference sheet)

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

### 4.1 Testing
- Unit tests de normalización de entradas por acción.
- Smoke tests de composición read→write (mock SDK).
- Tests UI por acción: formulario correcto, botones correctos, log tab enlazado a archivo correcto.
- E2E básico: sección → acción → ejecutar → visualizar output/log.

### 4.2 Seguridad
- Enmascarado de tokens/secretos en output y logs.
- No persistir credenciales.
- Validación estricta de campos obligatorios.

---

## 5) Plan the work

### 5.1 Estimación
6–8 días hábiles.

### 5.2 Milestones
1. Base común scripts + logging.
2. Menú UI y routing por acción.
3. Frontend diferenciado por cada acción.
4. Integración SDK por acción.
5. QA y documentación final.

### 5.3 DoD
- Menú por secciones + acciones operativo.
- Cada acción con pantalla específica (formulario, botones y logs adaptados).
- Cada acción ejecuta su script y escribe su log dedicado.
- Output SDK verboso disponible para operación.

---

## 6) Identify ripple effects
- Actualizar runbook operativo (acciones, parámetros, orden recomendado).
- Comunicar cambios de navegación UI.
- Actualizar documentación de soporte.

---

## 7) Broader context
- MVP prioriza versatilidad y mantenibilidad.
- Fase posterior: orquestación declarativa multi-acción, idempotencia fuerte y observabilidad consolidada.
