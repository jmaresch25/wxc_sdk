# Space_OdT

Deterministic, read-only Webex inventory exporter focused on CSV/JSON outputs.

## V1 behavior

- Uses a fixed method manifest only (no crawling, no SDK introspection).
- Executes retrieval-only methods (`list/details/read/get/members/capabilities/count/status/errors/history/summary/available_numbers.*`).
- Resolves IDs automatically from prior exports (`people`, `groups`, `locations`, `workspaces`, `virtual_lines`, etc.).
- Writes one status record per executed artifact method in `status.csv/json`.

## Usage

```bash
# Option A: pass token directly (highest priority)
python -m Space_OdT.cli inventory_run --token "<WEBEX_ACCESS_TOKEN>" --out-dir .artifacts --open-report

# Option B: place WEBEX_ACCESS_TOKEN in a .env file
# (supported in the current folder, any parent folder, or project root)
python -m Space_OdT.cli inventory_run --out-dir .artifacts --open-report

# Windows/PowerShell alternative (script path invocation)
python Space_OdT\cli.py inventory_run --out-dir .\.artifacts\ --open-report
```

## Output

- `.artifacts/exports/*.csv`
- `.artifacts/exports/*.json`
- `.artifacts/exports/status.csv`
- `.artifacts/cache.json` (optional)
- `.artifacts/report/index.html` (optional)

The static HTML report highlights the new V1 artifacts in a dedicated section so new coverage is visible quickly.

## V2 bulk softphone provisioning (CLI)

V2 adds an async bulk runner for provisioning existing users as softphones using V1 inventory as lookup cache.

### Inputs

- `.artifacts/v1_inventory/*` from V1 inventory export (used for `email -> person_id`, location and queue resolution).
- `.artifacts/v2/input_softphones.csv` with at least: `user_email`, `calling_license_id`, (`location_id` or `location_name`), (`extension` or `phone_number`).
- `.artifacts/v2/static_policy.json` with global defaults for optional calling features.

### Run

```bash
python -m Space_OdT.cli v2_bulk_run --out-dir .artifacts --concurrent-requests 20
```

Optional flags:

- `--only-failures`: re-run records failed in previous `run_state.json`.
- `--debug-har`: writes `.artifacts/v2/http.har` for HTTP-level troubleshooting.
- `--decisions-file`: JSON con decisiones por etapa para ejecución no interactiva (`yes`, `no`, `yesbut <archivo>`).

### Interactive approvals

En modo normal, antes de cada etapa se solicita confirmación:

- `yes`: aplicar etapa completa
- `no`: saltar etapa
- `yesbut <archivo>`: aplicar etapa con override específico por usuario (CSV/JSON con `user_email`)

### Outputs

- `.artifacts/v2/run_state.json`
- `.artifacts/v2/failures.csv`
- `.artifacts/v2/report.html` (estado anterior/actual por acción)
- `.artifacts/v2/changes.log` (detallado técnico en JSON lines)
- `.artifacts/v2/http.har` (only with `--debug-har`)

## V2.1 base (independiente de V2): bulk de sedes + operación UI

Se añadió una base nueva en `Space_OdT/v21/` totalmente independiente de `Space_OdT/v2/`.

### Objetivo de esta base

Cubrir el alta/actualización de sedes en modo bulk con ejecución asíncrona y trazabilidad de resultados.

### Comando

```bash
  python -m Space_OdT.cli v21_softphone_bulk_run --out-dir .artifacts --token "<WEBEX_ACCESS_TOKEN>"
```

Por defecto ejecuta **dry-run** y genera plan en:

- `.artifacts/v21/plan.csv`
- `.artifacts/v21/run_state.json`

Para modo apply:

```bash
python -m Space_OdT.cli v21_softphone_bulk_run --out-dir .artifacts --token "<WEBEX_ACCESS_TOKEN>" --v21-apply
```

### Inputs V2.1 (bootstrap automático)

Si no se pasa `--token`, el CLI carga `.env` (CWD, ancestros y raíz del proyecto, con `override=True`) antes de resolver `WEBEX_ACCESS_TOKEN`.

La responsabilidad queda separada así:

- **CLI (`Space_OdT/cli.py`)**: carga de `.env` y preparación del entorno de ejecución.
- **SDK client (`Space_OdT/sdk_client.py`)**: solo resuelve token ya disponible (`--token` o `WEBEX_ACCESS_TOKEN`) y crea API.

- `.artifacts/v21/input_locations.csv`
- `.artifacts/v21/static_policy.json`

Si faltan plantillas, el comando las crea automáticamente y detiene la corrida para que completes los datos.

### Alcance operativo actual

- Focus principal: **Locations**.
- Upsert determinista por nombre/external id (lookup + create/update).
- Ejecución asíncrona por lotes con concurrencia configurable para evitar bloqueo.
- Persistencia de artifacts por job y estado final remoto.

### Fuera de scope (gestionado por carga masiva Control Hub)

- Alta/Modificación/Supresión usuarios
- Asignar permisos de llamadas
- Traslado de usuarios a otro CUV
- Crear Grupos de usuarios
- Añadir/Editar Ubicaciones
- Eliminar Ubicaciones
- Añadir Espacios de trabajo (Workspace)
- Modificar/Eliminar Espacios de trabajo
- Alta/Modificación contactos Webex
- Alta/Modificar los grupos de recepción de llamadas
- Agregar locuciones
- Alta/Modificar el asistente automático
- Alta/modificar las extensiones de detención de llamada
- Alta/modificar los grupos de llamadas en espera
- Alta/Modificación de Grupo de búsqueda
- Alta de Colas
- Modificación de Colas
- Agregar DDIs
- Asignar DDIs

> Nota: en ocasiones la carga masiva en Control Hub resuelve solo una parte y queda una tarea manual para cierre completo.

### V2.1 Transformación backend (SDK-first)

Se añadieron acciones desacopladas en `Space_OdT/v21/transformacion/`:

- `ubicacion_configurar_pstn.py`
- `ubicacion_alta_numeraciones_desactivadas.py`
- `ubicacion_actualizar_cabecera.py`
- `launcher_prueba_real.py` (ejecución secuencial real contra API)
- `ubicacion_configurar_llamadas_internas.py`
- `ubicacion_configurar_permisos_salientes_defecto.py`
- `usuarios_alta_people.py`
- `usuarios_alta_scim.py`
- `usuarios_modificar_licencias.py`
- `usuarios_anadir_intercom_legacy.py`
- `usuarios_configurar_desvio_prefijo53.py`
- `usuarios_configurar_perfil_saliente_custom.py`
- `workspaces_alta.py`
- `workspaces_anadir_intercom_legacy.py`
- `workspaces_configurar_desvio_prefijo53.py`
- `workspaces_configurar_perfil_saliente_custom.py`
- `launcher_tester_api_remota.py` (tester que recibe acciones desde API remota, incluyendo las 3 acciones iniciales de Ubicación + resto de acciones backend)

Todos los scripts hacen `load_dotenv()` al iniciar y escriben log propio en:

- `Space_OdT/v21/transformacion/logs/<nombre_script>.log`

Ejemplo launcher real:

```bash
python -m Space_OdT.v21.transformacion.launcher_prueba_real   --location-id <LOCATION_ID>   --premise-route-id <ROUTE_GROUP_ID>   --phone-number +34910000001   --phone-number +34910000002   --header-phone-number +34910000001
```

Ejemplo launcher tester API remota:

```bash
python -m Space_OdT.v21.transformacion.launcher_tester_api_remota \
  --remote-url http://127.0.0.1:8080/v21/actions
```

### ¿De qué archivos sale la configuración de cada caso en v2.1?

La estructura quedó así para que cada configuración sea simple de modificar:

- `Space_OdT/v21/models.py`
  - Define entidades y etapa principal de location.
- `Space_OdT/v21/io.py`
  - Define contratos de entrada (cabeceras CSV/JSON), campos obligatorios y bootstrap de plantillas.
  - Archivos de entrada:
    - `.artifacts/v21/input_locations.csv`
    - `.artifacts/v21/static_policy.json`
- `Space_OdT/v21/engine.py`
  - Construye plan de acciones (`load_plan_rows`) y procesa jobs asíncronos de locations.
  - Persistencia de estado y resultados:
    - `.artifacts/v21/plan.csv`
    - `.artifacts/v21/run_state.json`
    - `.artifacts/v21/jobs/<job_id>/job.json`
    - `.artifacts/v21/jobs/<job_id>/results.csv`
    - `.artifacts/v21/jobs/<job_id>/pending_rows.csv`
    - `.artifacts/v21/jobs/<job_id>/rejected_rows.csv`
    - `.artifacts/v21/jobs/<job_id>/checkpoint.json`
    - `.artifacts/v21/jobs/<job_id>/final_state.json`

Regla de diseño: **modificas CSV/política, no código**, salvo que quieras introducir una etapa nueva.

### UI HTML5 v2.1 (Space_OdT.cli v21_softphone_ui)

UI ligera para alta de sedes con API local:

```bash
python -m Space_OdT.cli v21_softphone_ui --out-dir .artifacts --token "<WEBEX_ACCESS_TOKEN>"
```

- Abre: `http://127.0.0.1:8765`.
- Endpoints principales:
  - `POST /api/location-jobs` (upload CSV/JSON)
  - `POST /api/location-jobs/<job_id>/start`
  - `GET /api/location-jobs/<job_id>`
  - `GET /api/location-jobs/<job_id>/result`
  - `GET /api/location-state/current`

Incluye:
- preview de carga,
- campos obligatorios para alta,
- ejecución asíncrona sin bloquear UI,
- vista de estado final remoto post-acción.

### UI HTML5 v2.1.1 (Space_OdT.cli v211_softphone_ui)

Nueva versión orientada a operación técnica experta con **planta principal + menú de dos niveles**.

```bash
python -m Space_OdT.cli v211_softphone_ui --v21-ui-port 8771
```

- Abre: `http://127.0.0.1:8771`.
- Planta principal (antes de entrar en menús):
  - carga de 3 CSV maestros exclusivamente vía upload de archivo (`Ubicaciones`, `Usuarios`, `Numeraciones`).
- El mapeo de campos canónicos (`location_id`, `phone_number`, `person_id`, etc.) se configura en el panel operativo de acciones.
- Menú nivel 1: `Carga`, `Ubicación`, `Usuarios`, `Workspaces` (barra lateral fija).
- Menú nivel 2: acciones desacopladas por script (matriz 3.2), visibles dentro de cada sección del nivel 1. En `Carga` se concentra la subida de CSV; en el resto se muestran acciones de ejecución.
  - botón **Preview parámetros**,
  - botón **Aplicar**,
  - box de parámetros preparados,
  - box de respuesta API.
- Reglas de visualización:
  - si hay más de 5 registros se muestra head de 10 filas,
  - en pantalla se muestra resumen de ejecución por fila (`status` + `http_status`),
  - el detalle técnico completo (request/response/error) queda en `Space_OdT/v21/transformacion/logs/<accion>.log`.

Notas operativas:
- esta UI reutiliza los scripts de `Space_OdT/v21/transformacion` como backend real;
- `.artifacts` se mantiene para salidas de run legacy, mientras que la traza de ejecución de acciones UI queda en `transformacion/logs`.

## UI v11 inventario bajo demanda (`v11_inventory_ui`)

Para arrancar la UI v11 de inventario/retrieval on-demand:

```bash
python -m Space_OdT.cli v11_inventory_ui --out-dir .artifacts --v21-ui-port 8772
```

- Abre: `http://127.0.0.1:8772`.
- Si no pasas `--token`, el comando usa `WEBEX_ACCESS_TOKEN` (por variable de entorno o `.env`).
- Desde la UI puedes lanzar el retrieval por secciones y revisar el resultado en `.artifacts/v11/`.


## Resumen rápido de comandos UI

- `v21_softphone_ui`: UI v2.1 de jobs asíncronos de sedes.
- `v211_softphone_ui`: UI v2.1.1 de operación técnica experta por acciones desacopladas.
- `v11_inventory_ui`: UI de inventario/retrieval bajo demanda.
