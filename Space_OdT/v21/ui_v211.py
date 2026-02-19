from __future__ import annotations

import inspect
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .transformacion.generar_csv_candidatos_desde_artifacts import SCRIPT_DEPENDENCIES
from .transformacion.launcher_csv_dependencias import HANDLERS
from .transformacion.bulk_runner import execute_bulk_orders

CANONICAL_PARAMS = [
    'location_id',
    'phone_number',
    'phone_numbers',
    'enable_unknown_extension_route_policy',
    'premise_route_id',
    'premise_route_type',
    'email',
    'first_name',
    'last_name',
    'licenses',
    'org_id',
    'person_id',
    'legacy_phone_number',
    'extension',
    'destination',
    'add_license_ids',
    'display_name',
    'workspace_id',
]

ACTION_CATALOG = {
    'carga': [],
    'ubicacion': [
        {'id': 'ubicacion_configurar_pstn', 'label': 'Configurar PSTN de Ubicación', 'dataset': 'locations'},
        {'id': 'ubicacion_alta_numeraciones_desactivadas', 'label': 'Alta numeraciones en ubicación (estado desactivado)', 'dataset': 'numbers'},
        {'id': 'ubicacion_actualizar_cabecera', 'label': 'Añadir cabecera de Ubicación', 'dataset': 'locations'},
        {'id': 'ubicacion_configurar_llamadas_internas', 'label': 'Configurar llamadas internas de Ubicación', 'dataset': 'locations'},
        {'id': 'ubicacion_configurar_permisos_salientes_defecto', 'label': 'Configurar permisos salientes por defecto', 'dataset': 'locations'},
    ],
    'usuarios': [
        {'id': 'usuarios_alta_people', 'label': 'Alta de usuario People', 'dataset': 'users'},
        {'id': 'usuarios_alta_scim', 'label': 'Alta de usuario SCIM', 'dataset': 'users'},
        {'id': 'usuarios_modificar_licencias', 'label': 'Modificar licencias', 'dataset': 'users'},
        {'id': 'usuarios_anadir_intercom_legacy', 'label': 'Añadir intercom legacy', 'dataset': 'users'},
        {'id': 'usuarios_configurar_desvio_prefijo53', 'label': 'Configurar desvío prefijo 53', 'dataset': 'users'},
        {'id': 'usuarios_configurar_perfil_saliente_custom', 'label': 'Configurar perfil saliente custom', 'dataset': 'users'},
    ],
    'workspaces': [
        {'id': 'workspaces_alta', 'label': 'Alta de Workspace', 'dataset': 'numbers'},
        {'id': 'workspaces_anadir_intercom_legacy', 'label': 'Añadir intercom legacy', 'dataset': 'numbers'},
        {'id': 'workspaces_configurar_desvio_prefijo53', 'label': 'Configurar desvío prefijo 53', 'dataset': 'numbers'},
        {'id': 'workspaces_configurar_perfil_saliente_custom', 'label': 'Configurar perfil saliente custom', 'dataset': 'numbers'},
    ],
}

EN_DESARROLLO_ACTIONS = {
    'ubicacion_configurar_pstn',
    'usuarios_alta_people',
    'usuarios_alta_scim',
    'workspaces_alta',
    'workspaces_anadir_intercom_legacy',
    'workspaces_configurar_desvio_prefijo53',
    'workspaces_configurar_perfil_saliente_custom',
}

ACTION_DESCRIPTIONS: dict[str, str] = {
    'ubicacion_configurar_pstn': 'Configura la conexión PSTN de la ubicación mediante premise route.',
    'ubicacion_alta_numeraciones_desactivadas': 'Da de alta numeraciones en estado desactivado para la ubicación.',
    'ubicacion_actualizar_cabecera': 'Actualiza la cabecera de llamada de la ubicación.',
    'ubicacion_configurar_llamadas_internas': 'Ajusta política de llamadas internas de la ubicación.',
    'ubicacion_configurar_permisos_salientes_defecto': 'Configura permisos salientes por defecto de ubicación.',
    'usuarios_alta_people': 'Crea usuarios en People API.',
    'usuarios_alta_scim': 'Crea usuarios en SCIM.',
    'usuarios_modificar_licencias': 'Añade o quita licencias sobre usuario.',
    'usuarios_anadir_intercom_legacy': 'Añade número de intercom legacy a usuario.',
    'usuarios_configurar_desvio_prefijo53': 'Configura desvío prefijo 53 para usuario.',
    'usuarios_configurar_perfil_saliente_custom': 'Configura perfil saliente personalizado para usuario.',
    'workspaces_alta': 'Crea workspace en Webex Calling.',
    'workspaces_anadir_intercom_legacy': 'Añade intercom legacy en workspace.',
    'workspaces_configurar_desvio_prefijo53': 'Configura desvío prefijo 53 en workspace.',
    'workspaces_configurar_perfil_saliente_custom': 'Configura perfil saliente personalizado en workspace.',
}

for _section_actions in ACTION_CATALOG.values():
    for _action in _section_actions:
        if _action['id'] in EN_DESARROLLO_ACTIONS:
            _action['label'] = f"{_action['label']} · en desarrollo"

for _action_id in EN_DESARROLLO_ACTIONS:
    ACTION_DESCRIPTIONS[_action_id] = '... en desarrollo ...'

DATASET_NAMES = {
    'locations': 'CSV 1 · Ubicaciones',
    'users': 'CSV 2 · Usuarios',
    'numbers': 'CSV 3 · Numeraciones',
}


def launch_v211_ui(*, token: str, host: str = '127.0.0.1', port: int = 8771) -> None:
    state: dict[str, Any] = {'datasets': {k: [] for k in DATASET_NAMES}, 'mapping': {}}

    class Handler(BaseHTTPRequestHandler):
        def _send(self, payload: dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == '/':
                html = _html_page().encode('utf-8')
                self.send_response(HTTPStatus.OK)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(html)))
                self.end_headers()
                self.wfile.write(html)
                return
            if self.path == '/api/master/state':
                self._send(_master_state(state))
                return
            if self.path == '/api/menu':
                self._send({'sections': ACTION_CATALOG, 'descriptions': ACTION_DESCRIPTIONS})
                return
            self._send({'error': 'not found'}, status=404)

        def do_POST(self) -> None:  # noqa: N802
            try:
                payload = self._read_json()
            except Exception as exc:  # noqa: BLE001
                self._send({'error': f'JSON inválido: {exc}'}, status=400)
                return

            if self.path == '/api/master/upload':
                try:
                    for dataset_key in DATASET_NAMES:
                        rows = payload.get('datasets', {}).get(dataset_key) or []
                        if not isinstance(rows, list):
                            raise ValueError(f'{dataset_key} debe ser una lista de filas')
                        state['datasets'][dataset_key] = rows
                    self._send(_master_state(state))
                except Exception as exc:  # noqa: BLE001
                    self._send({'error': str(exc)}, status=400)
                return

            if self.path == '/api/mapping':
                mapping = payload.get('mapping') or {}
                if not isinstance(mapping, dict):
                    self._send({'error': 'mapping debe ser objeto JSON'}, status=400)
                    return
                state['mapping'] = mapping
                self._send(_master_state(state))
                return

            if self.path == '/api/action/preview':
                action_id = payload.get('action_id')
                try:
                    rows = _rows_for_action(action_id=action_id, state=state)
                    self._send(_preview_action(action_id=action_id, rows=rows, mapping=state['mapping']))
                except Exception as exc:  # noqa: BLE001
                    self._send({'error': str(exc)}, status=400)
                return

            if self.path == '/api/action/apply':
                action_id = payload.get('action_id')
                try:
                    rows = _rows_for_action(action_id=action_id, state=state)
                    bulk_settings = payload.get('bulk') or {}
                    self._send(
                        _apply_action(
                            action_id=action_id,
                            rows=rows,
                            mapping=state['mapping'],
                            token=token,
                            bulk=bool(bulk_settings.get('enabled')),
                            chunk_size=int(bulk_settings.get('chunk_size', 200) or 200),
                            max_workers=int(bulk_settings.get('max_workers', 4) or 4),
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    self._send({'error': str(exc)}, status=400)
                return

            self._send({'error': 'not found'}, status=404)

        def _read_json(self) -> dict[str, Any]:
            content_length = int(self.headers.get('Content-Length', '0'))
            raw = self.rfile.read(content_length)
            return json.loads(raw.decode('utf-8'))

        def log_message(self, format, *args):  # noqa: A003
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f'V2.1.1 UI listening on http://{host}:{port}')
    server.serve_forever()


def _master_state(state: dict[str, Any]) -> dict[str, Any]:
    datasets = {}
    for dataset_key, rows in state['datasets'].items():
        datasets[dataset_key] = {
            'name': DATASET_NAMES[dataset_key],
            'count': len(rows),
            'preview': rows[:10] if len(rows) > 5 else rows,
        }
    return {'datasets': datasets, 'mapping': state['mapping'], 'canonical_params': CANONICAL_PARAMS}


def _rows_for_action(*, action_id: str | None, state: dict[str, Any]) -> list[dict[str, Any]]:
    if not action_id:
        raise ValueError('action_id es obligatorio')
    for section in ACTION_CATALOG.values():
        for action in section:
            if action['id'] == action_id:
                return state['datasets'][action['dataset']]
    raise ValueError(f'Acción no soportada: {action_id}')


def _ensure_action_available(action_id: str) -> None:
    if action_id in EN_DESARROLLO_ACTIONS:
        raise ValueError(f'Acción {action_id} ... en desarrollo ...')


def _extract(row: dict[str, Any], source: str | None) -> Any:
    if not source:
        return None
    if '.' in source:
        _, field = source.split('.', 1)
        return row.get(field)
    return row.get(source)


def _normalize_for_param(param: str, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        raw = value.strip()
        if raw == '':
            return None
        if param in {'phone_numbers', 'licenses', 'add_license_ids'}:
            return [item for item in (part.strip() for part in raw.replace('|', ';').split(';')) if item]
        if raw.lower() == 'true':
            return True
        if raw.lower() == 'false':
            return False
        return raw
    return value


def _build_params(action_id: str, row: dict[str, Any], mapping: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    required = SCRIPT_DEPENDENCIES[action_id]
    accepted = set(inspect.signature(HANDLERS[action_id]).parameters.keys()) - {'token'}

    params: dict[str, Any] = {}
    missing: list[str] = []
    for req in required:
        value = _normalize_for_param(req, _extract(row, mapping.get(req, req)))
        if value in (None, '', []):
            missing.append(req)
        else:
            params[req] = value

    for key in accepted:
        if key in params:
            continue
        value = _normalize_for_param(key, _extract(row, mapping.get(key, key)))
        if value not in (None, '', []):
            params[key] = value

    return params, missing


def _preview_action(action_id: str, rows: list[dict[str, Any]], mapping: dict[str, str]) -> dict[str, Any]:
    _ensure_action_available(action_id)
    detailed_rows = []
    for idx, row in enumerate(rows, start=1):
        params, missing = _build_params(action_id, row, mapping)
        detailed_rows.append({'row_index': idx, 'params': params, 'missing': missing})

    return {
        'action_id': action_id,
        'script_method': HANDLERS[action_id].__name__,
        'required_params': SCRIPT_DEPENDENCIES[action_id],
        'total_rows': len(detailed_rows),
        'rows_preview': detailed_rows[:10] if len(detailed_rows) > 5 else detailed_rows,
    }


def _execute_row(*, action_id: str, row: dict[str, Any], row_index: int, mapping: dict[str, str], token: str) -> dict[str, Any]:
    params, missing = _build_params(action_id, row, mapping)
    if missing:
        return {
            'row_index': row_index,
            'status': 'missing_dependencies',
            'http_status': 'MISSING_PARAMS',
            'missing': missing,
            'params': params,
        }

    try:
        api_response = HANDLERS[action_id](token=token, **params)
        return {
            'row_index': row_index,
            'status': 'ok',
            'http_status': _extract_status_code(api_response),
            'params': params,
            'api_response': api_response,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            'row_index': row_index,
            'status': 'error',
            'http_status': _extract_status_code(exc),
            'params': params,
            'error': str(exc),
        }


def _run_bulk_orders(
    *,
    action_id: str,
    rows: list[dict[str, Any]],
    mapping: dict[str, str],
    token: str,
    chunk_size: int,
    max_workers: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    def _run_order(order_index: int, chunk: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        order_rows = [
            _execute_row(
                action_id=action_id,
                row=row,
                row_index=((order_index - 1) * chunk_size) + offset,
                mapping=mapping,
                token=token,
            )
            for offset, row in enumerate(chunk, start=1)
        ]
        summary = {
            'status': 'completed',
            'rows_total': len(order_rows),
            'rows_ok': sum(1 for item in order_rows if item['status'] == 'ok'),
            'rows_error': sum(1 for item in order_rows if item['status'] == 'error'),
            'rows_missing': sum(1 for item in order_rows if item['status'] == 'missing_dependencies'),
        }
        return order_rows, summary

    return execute_bulk_orders(
        rows=rows,
        chunk_size=chunk_size,
        max_workers=max_workers,
        order_callable=_run_order,
    )


def _apply_action(*, action_id: str, rows: list[dict[str, Any]], mapping: dict[str, str], token: str, bulk: bool = False, chunk_size: int = 200, max_workers: int = 4) -> dict[str, Any]:
    _ensure_action_available(action_id)
    logs_dir = Path(__file__).resolve().parent / 'transformacion' / 'logs'
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f'{action_id}.log'

    if bulk:
        orders, results = _run_bulk_orders(
            action_id=action_id,
            rows=rows,
            mapping=mapping,
            token=token,
            chunk_size=chunk_size,
            max_workers=max_workers,
        )
    else:
        orders = []
        results = [
            _execute_row(action_id=action_id, row=row, row_index=idx, mapping=mapping, token=token)
            for idx, row in enumerate(rows, start=1)
        ]

    with log_path.open('a', encoding='utf-8') as handle:
        for row_result in results:
            handle.write(json.dumps(row_result, ensure_ascii=False) + '\n')

    ui_rows = [
        {
            'row_index': item['row_index'],
            'status': item['status'],
            'http_status': item.get('http_status', 'UNKNOWN'),
            'missing': item.get('missing', []),
        }
        for item in results
    ]
    return {
        'action_id': action_id,
        'script': HANDLERS[action_id].__name__,
        'description': ACTION_DESCRIPTIONS.get(action_id, ''),
        'total_rows': len(ui_rows),
        'rows_preview': ui_rows[:10] if len(ui_rows) > 5 else ui_rows,
        'log_path': str(log_path),
        'bulk': {
            'enabled': bool(bulk),
            'chunk_size': chunk_size if bulk else None,
            'max_workers': max_workers if bulk else None,
            'orders': orders if bulk else [],
            'orders_total': len(orders) if bulk else 0,
        },
    }


def _extract_status_code(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ('status_code', 'http_status', 'status'):
            value = payload.get(key)
            if value is not None and str(value).strip() != '':
                return str(value)
        return 'OK'

    response = getattr(payload, 'response', None)
    if response is not None:
        status_code = getattr(response, 'status_code', None)
        if status_code is not None:
            return str(status_code)
    status_code = getattr(payload, 'status_code', None)
    if status_code is not None:
        return str(status_code)
    return 'ERROR'


def _html_page() -> str:
    return """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <title>Space_OdT.cli v211_softphone_ui</title>
  <style>
    :root { --bg:#0f2332; --panel:#142e44; --line:#2a5575; --text:#ecf6ff; --muted:#aaccdf; --accent:#4ca0d8; }
    * { box-sizing: border-box; }
    body { margin:0; font-family:Inter,Arial,sans-serif; background:var(--bg); color:var(--text); }
    .layout { display:grid; grid-template-columns:320px 1fr; min-height:100vh; }
    .sidebar { background:#091824; border-right:1px solid #1c3c52; padding:16px; }
    .content { padding:18px; }
    .card { border:1px solid var(--line); background:var(--panel); border-radius:10px; padding:14px; margin-bottom:12px; }
    h1,h2,h3 { margin:0 0 10px; }
    .hint { color:var(--muted); font-size:12px; }
    input, textarea, button { font:inherit; }
    input[type=file], textarea { width:100%; background:#0c2030; color:var(--text); border:1px solid #2b5878; border-radius:8px; padding:8px; }
    button { border:1px solid #2d6e96; background:#1c6290; color:#fff; border-radius:8px; padding:8px 10px; cursor:pointer; }
    button.secondary { background:#314f66; }
    .menu-group { margin-bottom:8px; }
    .main-menu { width:100%; text-align:left; margin-bottom:6px; font-weight:700; background:#173a54; }
    .main-menu.active { background:#2f6f9b; }
    .submenu { margin-left:8px; border-left:2px solid #244f6b; padding-left:8px; display:none; }
    .submenu.open { display:block; }
    .submenu button { width:100%; text-align:left; margin:3px 0; font-size:12px; background:#1a4f72; }
    .submenu button.active { background:#2d7dae; }
    pre { background:#0b1b28; border:1px solid #2a5575; border-radius:8px; padding:10px; max-height:320px; overflow:auto; }
    .row { display:flex; gap:8px; flex-wrap:wrap; }
    .bulk-box { margin-top:10px; border:1px solid #356585; border-radius:8px; padding:10px; background:#123149; }
    .bulk-box h3 { margin:0 0 8px; font-size:16px; }
    .bulk-grid { display:grid; grid-template-columns:repeat(3, minmax(140px, 1fr)); gap:8px; align-items:end; }
    .bulk-grid label { display:flex; flex-direction:column; gap:4px; font-size:12px; color:var(--muted); }
    .bulk-grid input[type=number] { width:100%; background:#0c2030; color:var(--text); border:1px solid #2b5878; border-radius:8px; padding:6px 8px; }
    .hidden { display:none; }
  </style>
</head>
<body>
  <div class="layout">
    <aside class="sidebar">
      <h2>Menú v2.1.1</h2>
      <p class="hint">Primer nivel: Carga / Ubicaciones / Usuarios / Workspaces. Segundo nivel: acciones de la sección.</p>
      <div id="menu"></div>
    </aside>

    <main class="content">
      <section class="card" id="master-card">
        <h1>Planta principal</h1>
        <p class="hint">En esta pantalla solo se solicita la carga de 3 CSV mediante upload de archivo.</p>
        <h3>CSV 1 · Ubicaciones</h3>
        <input type="file" id="file-locations" accept=".csv" />
        <h3>CSV 2 · Usuarios</h3>
        <input type="file" id="file-users" accept=".csv" />
        <h3>CSV 3 · Numeraciones</h3>
        <input type="file" id="file-numbers" accept=".csv" />
        <div class="row" style="margin-top:8px;">
          <button onclick="loadMaster()">Cargar CSVs</button>
          <button class="secondary" onclick="refreshState()">Refrescar estado</button>
        </div>
      </section>

      <section class="card hidden" id="mapping-card">
        <h2>Mapeo canónico de campos</h2>
        <p class="hint">Define solo lo necesario para la acción seleccionada. Formato: {"location_id":"Codi Seu", "person_id":"Identificatiu PC"}</p>
        <textarea id="map-json" rows="7">{}</textarea>
        <div class="row" style="margin-top:8px;">
          <button onclick="saveMapping()">Guardar mapeo</button>
          <span class="hint" id="mapping-hint"></span>
        </div>
      </section>

      <section class="card hidden" id="action-card">
        <h2 id="action-title">Selecciona una acción del menú</h2>
        <p class="hint" id="action-info"></p>
        <p class="hint" id="action-description"></p>
        <div class="row">
          <button onclick="previewAction()">Preview parámetros</button>
          <button onclick="applyAction()">Aplicar</button>
        </div>
        <div class="bulk-box">
          <h3>Tema bulk v2.1.1</h3>
          <p class="hint">Activa ejecución asíncrona por lotes según PLAN_BULK_V211_ASYNC.md.</p>
          <div class="bulk-grid">
            <label>
              <span><input type="checkbox" id="bulk-enabled" /> Modo bulk</span>
            </label>
            <label>Tamaño lote
              <input id="bulk-chunk-size" type="number" value="200" min="1" />
            </label>
            <label>Workers
              <input id="bulk-max-workers" type="number" value="4" min="1" />
            </label>
          </div>
          <p class="hint" id="bulk-summary">Bulk desactivado.</p>
        </div>
      </section>

      <section class="card hidden" id="params-card">
        <h3>Box · Parámetros a subir (preview)</h3>
        <pre id="params-box">{}</pre>
      </section>

      <section class="card" id="response-card">
        <h3>Box · Respuesta API / estado (solo resumen)</h3>
        <pre id="response-box">{}</pre>
      </section>
    </main>
  </div>

<script>
let selectedAction = null;
let selectedSection = null;
let actionDescriptions = {};

function showCargaScreen(){
  document.getElementById('master-card').classList.remove('hidden');
  document.getElementById('mapping-card').classList.add('hidden');
  document.getElementById('action-card').classList.add('hidden');
  document.getElementById('params-card').classList.add('hidden');
}

function showActionScreen(){
  document.getElementById('master-card').classList.add('hidden');
  document.getElementById('mapping-card').classList.remove('hidden');
  document.getElementById('action-card').classList.remove('hidden');
  document.getElementById('params-card').classList.remove('hidden');
}

async function api(path, method='GET', body=null){
  const res = await fetch(path, {method, headers:{'Content-Type':'application/json'}, body: body ? JSON.stringify(body) : null});
  return await res.json();
}

async function fileToRows(inputId){
  const input = document.getElementById(inputId);
  const file = input.files && input.files[0];
  if(!file){ return []; }
  const text = await file.text();
  return parseCsv(text);
}

function parseCsv(text){
  const lines = (text || '').replace(/\\r/g, '').split('\\n').filter(Boolean);
  if(lines.length < 2){ return []; }
  const headers = lines[0].split(',').map(v => v.trim());
  const rows = [];
  for(const line of lines.slice(1)){
    const cols = line.split(',');
    const row = {};
    headers.forEach((h, i) => row[h] = (cols[i] || '').trim());
    rows.push(row);
  }
  return rows;
}


function selectAction(actionId, label){
  selectedAction = actionId;
  document.getElementById('action-title').textContent = label;
  showActionScreen();
  document.getElementById('action-info').textContent = 'Script backend: ' + actionId;
  document.getElementById('action-description').textContent = actionDescriptions[actionId] || ''; 
  document.querySelectorAll('.submenu button').forEach(b => b.classList.remove('active'));
  const active = document.querySelector(`.submenu button[data-action="${actionId}"]`);
  if(active){ active.classList.add('active'); }
  updateBulkSummary();
}

function openSection(section){
  selectedSection = section;
  document.querySelectorAll('.main-menu').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.section === section);
  });
  document.querySelectorAll('.submenu').forEach(sub => {
    sub.classList.toggle('open', sub.dataset.section === section);
  });
}

async function buildMenu(){
  const data = await api('/api/menu');
  actionDescriptions = data.descriptions || {};
  const root = document.getElementById('menu');
  root.innerHTML = '';

  let firstSection = null;
  let firstAction = null;

  Object.entries(data.sections).forEach(([section, actions]) => {
    if(!firstSection){ firstSection = section; }

    const group = document.createElement('div');
    group.className = 'menu-group';

    const main = document.createElement('button');
    main.className = 'main-menu';
    main.dataset.section = section;
    main.textContent = section[0].toUpperCase() + section.slice(1);
    main.onclick = () => { openSection(section); if(section === 'carga'){ selectedAction = null; showCargaScreen(); } };

    const sub = document.createElement('div');
    sub.className = 'submenu';
    sub.dataset.section = section;

    if(section === 'carga'){
      const child = document.createElement('button');
      child.dataset.action = 'carga_csv';
      child.textContent = 'Carga CSV maestra';
      child.onclick = () => {
        openSection('carga');
        selectedAction = null;
        showCargaScreen();
        document.querySelectorAll('.submenu button').forEach(b => b.classList.remove('active'));
        child.classList.add('active');
      };
      sub.appendChild(child);
      if(!firstAction){ firstAction = {id:'carga_csv', label:'Carga CSV maestra'}; }
    } else {
      actions.forEach((action, idx) => {
        if(!firstAction){ firstAction = action; }
        const child = document.createElement('button');
        child.dataset.action = action.id;
        child.textContent = action.label;
        child.onclick = () => {
          openSection(section);
          selectAction(action.id, action.label);
        };
        sub.appendChild(child);
        if(section === firstSection && idx === 0){
          child.classList.add('active');
        }
      });
    }

    group.appendChild(main);
    group.appendChild(sub);
    root.appendChild(group);
  });

  if(firstSection){ openSection(firstSection); }
  showCargaScreen();
}

async function loadMaster(){
  const datasets = {
    locations: await fileToRows('file-locations'),
    users: await fileToRows('file-users'),
    numbers: await fileToRows('file-numbers')
  };
  const res = await api('/api/master/upload', 'POST', {datasets});
  document.getElementById('response-box').textContent = JSON.stringify(res, null, 2);
  updateBulkSummary();
}

async function saveMapping(){
  try{
    const mapping = JSON.parse(document.getElementById('map-json').value || '{}');
    const res = await api('/api/mapping', 'POST', {mapping});
    document.getElementById('mapping-hint').textContent = 'Mapeo guardado';
    document.getElementById('response-box').textContent = JSON.stringify(res, null, 2);
  }catch(err){
    document.getElementById('mapping-hint').textContent = 'Error de JSON: ' + err;
  }
}

async function refreshState(){
  const res = await api('/api/master/state');
  document.getElementById('response-box').textContent = JSON.stringify(res, null, 2);
  updateBulkSummary();
}

function readPositiveInt(id, fallbackValue){
  const input = document.getElementById(id);
  const value = Number(input?.value || fallbackValue);
  if(!Number.isFinite(value) || value < 1){
    if(input){ input.value = String(fallbackValue); }
    return fallbackValue;
  }
  return Math.floor(value);
}

function rowsForSelectedAction(){
  const box = document.getElementById('response-box');
  if(!box || !selectedAction){ return 0; }
  try{
    const payload = JSON.parse(box.textContent || '{}');
    const sections = payload.datasets || {};
    const actionToDataset = {
      ubicacion_configurar_pstn: 'locations',
      ubicacion_alta_numeraciones_desactivadas: 'numbers',
      ubicacion_actualizar_cabecera: 'locations',
      ubicacion_configurar_llamadas_internas: 'locations',
      ubicacion_configurar_permisos_salientes_defecto: 'locations',
      usuarios_alta_people: 'users',
      usuarios_alta_scim: 'users',
      usuarios_modificar_licencias: 'users',
      usuarios_anadir_intercom_legacy: 'users',
      usuarios_configurar_desvio_prefijo53: 'users',
      usuarios_configurar_perfil_saliente_custom: 'users',
      workspaces_alta: 'numbers',
      workspaces_anadir_intercom_legacy: 'numbers',
      workspaces_configurar_desvio_prefijo53: 'numbers',
      workspaces_configurar_perfil_saliente_custom: 'numbers'
    };
    const key = actionToDataset[selectedAction];
    return key ? Number(sections[key]?.count || 0) : 0;
  }catch(_err){
    return 0;
  }
}

function updateBulkSummary(){
  const summary = document.getElementById('bulk-summary');
  if(!summary){ return; }
  const enabled = !!document.getElementById('bulk-enabled')?.checked;
  const chunkSize = readPositiveInt('bulk-chunk-size', 200);
  const maxWorkers = readPositiveInt('bulk-max-workers', 4);
  const totalRows = rowsForSelectedAction();
  if(!enabled){
    summary.textContent = 'Bulk desactivado. Se ejecutará fila a fila.';
    return;
  }
  const estimatedOrders = totalRows > 0 ? Math.ceil(totalRows / chunkSize) : 0;
  summary.textContent = `Bulk activado: ${estimatedOrders} lotes estimados para ${totalRows} filas · chunk=${chunkSize} · workers=${maxWorkers}.`;
}

async function previewAction(){
  if(!selectedAction){ return; }
  const res = await api('/api/action/preview', 'POST', {action_id: selectedAction});
  document.getElementById('params-box').textContent = JSON.stringify(res, null, 2);
}

async function applyAction(){
  if(!selectedAction){ return; }
  const bulkEnabled = !!document.getElementById('bulk-enabled')?.checked;
  const chunkSize = readPositiveInt('bulk-chunk-size', 200);
  const maxWorkers = readPositiveInt('bulk-max-workers', 4);
  const res = await api('/api/action/apply', 'POST', {
    action_id: selectedAction,
    bulk: {enabled: bulkEnabled, chunk_size: chunkSize, max_workers: maxWorkers}
  });
  document.getElementById('response-box').textContent = JSON.stringify(res, null, 2);
  updateBulkSummary();
}

document.getElementById('bulk-enabled').addEventListener('change', updateBulkSummary);
document.getElementById('bulk-chunk-size').addEventListener('input', updateBulkSummary);
document.getElementById('bulk-max-workers').addEventListener('input', updateBulkSummary);

buildMenu();
refreshState();
</script>
</body>
</html>"""
