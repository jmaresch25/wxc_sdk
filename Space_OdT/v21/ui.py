from __future__ import annotations

import csv
import io
import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .engine import MissingV21InputsError, V21Runner
from .io import LOCATION_HEADERS, LOCATION_REQUIRED_CREATE_FIELDS, load_locations_from_json


def launch_v21_ui(*, token: str, out_dir: Path, host: str = '127.0.0.1', port: int = 8765) -> None:
    runner = V21Runner(token=token, out_dir=out_dir)
    running_jobs: dict[str, threading.Thread] = {}

    class Handler(BaseHTTPRequestHandler):
        def _send(self, payload: dict, status: int = 200) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == '/':
                html = _html_page().encode('utf-8')
                self.send_response(HTTPStatus.OK)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(html)))
                self.end_headers()
                self.wfile.write(html)
                return
            if parsed.path == '/api/plan':
                try:
                    self._send({'items': runner.load_plan_rows()})
                except MissingV21InputsError as exc:
                    self._send({'error': str(exc)}, status=400)
                return
            if parsed.path == '/api/location-state/current':
                self._send(runner.get_latest_final_state())
                return
            if parsed.path == '/api/location-jobs/async-info':
                self._send(runner.get_async_execution_info())
                return
            if parsed.path.startswith('/api/location-jobs/'):
                path_parts = [part for part in parsed.path.split('/') if part]
                if len(path_parts) == 3:
                    _, _, job_id = path_parts
                    try:
                        self._send(runner.get_job(job_id).to_dict())
                    except FileNotFoundError:
                        self._send({'error': 'job not found'}, status=404)
                    return
                if len(path_parts) == 4 and path_parts[-1] == 'result':
                    job_id = path_parts[2]
                    try:
                        self._send(runner.get_job_result(job_id))
                    except FileNotFoundError as exc:
                        self._send({'error': str(exc)}, status=404)
                    return
            self._send({'error': 'not found'}, status=404)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path in {'/api/location-jobs', '/api/location-wbxc-jobs'}:
                try:
                    rows, preview = self._parse_upload()
                    entity_type = 'location' if parsed.path == '/api/location-jobs' else 'location_webex_calling'
                    job = runner.create_location_job(rows=rows, entity_type=entity_type)
                    self._send({'job': job.to_dict(), 'count': len(rows), 'preview': preview})
                except Exception as exc:  # noqa: BLE001
                    self._send({'error': str(exc)}, status=400)
                return

            if parsed.path.startswith('/api/location-jobs/') and parsed.path.endswith('/start'):
                path_parts = [part for part in parsed.path.split('/') if part]
                if len(path_parts) != 4:
                    self._send({'error': 'invalid path'}, status=400)
                    return
                job_id = path_parts[2]
                try:
                    job = runner.get_job(job_id)
                except FileNotFoundError:
                    self._send({'error': 'job not found'}, status=404)
                    return

                if job.status == 'running':
                    self._send({'job': job.to_dict(), 'message': 'job already running'})
                    return

                thread = threading.Thread(target=_run_job_background, args=(runner, job_id), daemon=True)
                thread.start()
                running_jobs[job_id] = thread
                self._send({'job': job.to_dict(), 'message': 'job started'})
                return

            self._send({'error': 'not found'}, status=404)

        def _parse_upload(self) -> tuple[list[dict], list[dict]]:
            content_length = int(self.headers.get('Content-Length', '0'))
            raw = self.rfile.read(content_length)
            ctype = self.headers.get('Content-Type', '')

            if 'application/json' in ctype:
                payload = json.loads(raw.decode('utf-8'))
                if not isinstance(payload, list):
                    raise ValueError('JSON debe ser una lista de objetos')
                rows = payload
            elif 'multipart/form-data' in ctype:
                boundary = ctype.split('boundary=')[-1].encode('utf-8')
                rows = _rows_from_multipart(raw, boundary)
            else:
                raise ValueError('Content-Type no soportado, usar multipart/form-data o application/json')

            parsed_rows = load_locations_from_json(rows)
            normalized_rows = [row.payload for row in parsed_rows]
            return normalized_rows, normalized_rows[:10]

        def log_message(self, format, *args):  # noqa: A003
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f'V2.1 UI listening on http://{host}:{port}')
    server.serve_forever()


def _run_job_background(runner: V21Runner, job_id: str) -> None:
    import asyncio

    try:
        asyncio.run(runner.process_location_job(job_id, chunk_size=200, max_concurrency=20))
    except Exception:  # noqa: BLE001
        job = runner.get_job(job_id)
        job.status = 'failed'
        runner.save_job(job)


def _rows_from_multipart(raw: bytes, boundary: bytes) -> list[dict]:
    parts = raw.split(b'--' + boundary)
    file_name = ''
    file_bytes = b''
    for part in parts:
        if b'filename=' not in part:
            continue
        header, _, content = part.partition(b'\r\n\r\n')
        disposition = header.decode('utf-8', errors='ignore')
        marker = 'filename="'
        if marker in disposition:
            file_name = disposition.split(marker, 1)[1].split('"', 1)[0]
        file_bytes = content.rstrip(b'\r\n-')
        break
    if not file_name:
        raise ValueError('No se recibió archivo')

    ext = Path(file_name).suffix.lower()
    if ext == '.csv':
        text = file_bytes.decode('utf-8-sig')
        return list(csv.DictReader(io.StringIO(text)))
    if ext == '.json':
        payload = json.loads(file_bytes.decode('utf-8'))
        if not isinstance(payload, list):
            raise ValueError('JSON debe ser una lista de objetos')
        return payload
    raise ValueError('Solo se aceptan archivos .csv o .json')


def _html_page() -> str:
    required = ''.join(
        f"<li><code>{field}</code>{' <b>(obligatorio)</b>' if field in LOCATION_REQUIRED_CREATE_FIELDS else ''}</li>"
        for field in LOCATION_HEADERS
    )
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <title>Space_OdT v2.1 location changes</title>
  <style>
    :root {{
      --bg: #083f1f;
      --panel: #0f6b31;
      --panel-2: #0d5b2a;
      --line: #2ea15a;
      --text: #f3fff6;
      --muted: #c9f5d8;
      --accent: #ffde59;
      --danger: #ffd2d2;
      --progress: #31d46f;
      --sidebar: #052d15;
      --sidebar-active: #1a8e43;
    }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: Inter, Arial, sans-serif; margin: 0; background: var(--bg); color: var(--text); }}
    .layout {{ display: grid; grid-template-columns: 240px 1fr; min-height: 100vh; }}
    .sidebar {{ background: var(--sidebar); border-right: 1px solid #176a35; padding: 16px 12px; }}
    .brand {{ color: var(--accent); margin: 0 0 14px; font-size: 18px; }}
    .menu button {{ display:block; width:100%; text-align:left; margin: 0 0 8px; border:1px solid #176a35; background:#0a4a24; color:var(--text); border-radius:8px; padding:10px; cursor:pointer; font-weight:600; }}
    .menu button.active {{ background: var(--sidebar-active); }}
    .content {{ padding: 20px; }}
    .card {{ background: linear-gradient(180deg, var(--panel) 0%, var(--panel-2) 100%); border: 1px solid var(--line); border-radius: 10px; padding: 14px; margin-bottom: 14px; }}
    h1 {{ margin-top: 0; color: var(--accent); }}
    p.lead {{ color: var(--muted); margin-top: -6px; }}
    .actions {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0; }}
    button {{ border: 1px solid #1d8e45; background: #18863f; color: #fff; border-radius: 8px; padding: 9px 12px; cursor: pointer; font-weight: 600; }}
    button.secondary {{ background: #126e34; }}
    button.warning {{ background: #8d6b00; border-color: #a37c00; color: #fff8d2; }}
    input[type=file] {{ color: var(--muted); }}
    .progress {{ width: 100%; height: 18px; background: #093d1d; border-radius: 12px; overflow: hidden; border: 1px solid #1d8e45; }}
    .progress > div {{ height: 100%; background: var(--progress); width: 0%; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 8px; }}
    th, td {{ border: 1px solid #1e8842; padding: 6px; font-size: 12px; }}
    th {{ background: #0f592b; }}
    pre {{ background: #072f17; color: #d9ffe6; padding: 10px; border-radius: 8px; overflow-x: auto; max-height: 280px; border: 1px solid #1e8842; }}
    .error {{ color: var(--danger); }}
    .hidden {{ display: none; }}
  </style>
</head>
<body>
  <div class="layout">
    <aside class="sidebar">
      <h2 class="brand">Space_OdT v2.1</h2>
      <nav class="menu">
        <button id="menu-alta" class="active" onclick="selectAction('alta_sedes')">Alta_Sedes</button>
        <button id="menu-wbxc" onclick="selectAction('alta_sedes_wbxc')">Alta_Sedes+WBXC</button>
      </nav>
    </aside>
    <main class="content">
      <h1 id="screenTitle">Space_OdT v2.1 · Cambios de sedes</h1>
      <p class="lead" id="screenLead">UI enfocada en alta/actualización de sedes mediante CSV/JSON.</p>

      <div class="card">
        <h3>1) Cargar archivo de cambios</h3>
        <input id="file" type="file" accept=".csv,.json" />
        <div class="actions">
          <button onclick="createJob()">Crear job</button>
        </div>
        <div id="uploadInfo"></div>
        <div id="preview"></div>
      </div>

      <div class="card">
        <h3>2) Ejecutar cambio</h3>
        <div class="actions">
          <button onclick="startJob()">Aplicar cambios</button>
          <button class="secondary" onclick="refreshJob()">Actualizar estado</button>
          <button class="warning" onclick="showFinalConfig()">Ver respuesta API</button>
        </div>
        <div id="jobStatus"></div>
        <div class="progress"><div id="bar"></div></div>
        <div id="errorSummary"></div>
        <pre id="finalConfig"></pre>
      </div>

      <div class="card">
        <h3>Campos esperados</h3>
        <p class="lead">Alta_Sedes+WBXC usa el mismo CSV/JSON que Alta_Sedes (incluyendo <code>location_id</code> cuando exista).</p>
        <ul>{required}</ul>
      </div>
    </main>
  </div>

  <script>
    let currentJobId = null;
    let currentAction = 'alta_sedes';

    window.addEventListener('DOMContentLoaded', () => {{
      const output = document.getElementById('finalConfig');
      output.textContent = 'Aquí se verá únicamente: status + api_response';
    }});

    function selectAction(action) {{
      currentAction = action;
      currentJobId = null;
      document.getElementById('uploadInfo').innerHTML = '';
      document.getElementById('preview').innerHTML = '';
      document.getElementById('jobStatus').innerHTML = '';
      document.getElementById('bar').style.width = '0%';
      document.getElementById('errorSummary').innerHTML = '';
      document.getElementById('finalConfig').textContent = 'Aquí se verá únicamente: status + api_response';

      document.getElementById('menu-alta').classList.toggle('active', action === 'alta_sedes');
      document.getElementById('menu-wbxc').classList.toggle('active', action === 'alta_sedes_wbxc');

      const title = document.getElementById('screenTitle');
      const lead = document.getElementById('screenLead');
      if (action === 'alta_sedes_wbxc') {{
        title.textContent = 'Space_OdT v2.1 · Alta_Sedes+WBXC';
        lead.textContent = 'Habilita sedes existentes para Webex Calling usando API oficial (POST /telephony/config/locations).';
      }} else {{
        title.textContent = 'Space_OdT v2.1 · Cambios de sedes';
        lead.textContent = 'UI enfocada en alta/actualización de sedes mediante CSV/JSON.';
      }}
    }}

    function currentCreateEndpoint() {{
      return currentAction === 'alta_sedes_wbxc' ? '/api/location-wbxc-jobs' : '/api/location-jobs';
    }}

    async function createJob() {{
      const fileEl = document.getElementById('file');
      if (!fileEl.files.length) {{
        alert('Seleccioná un archivo CSV o JSON');
        return;
      }}
      const fd = new FormData();
      fd.append('file', fileEl.files[0]);
      const r = await fetch(currentCreateEndpoint(), {{ method: 'POST', body: fd }});
      const data = await r.json();
      if (data.error) {{
        document.getElementById('uploadInfo').innerHTML = '<span class="error">' + data.error + '</span>';
        return;
      }}
      currentJobId = data.job.job_id;
      document.getElementById('uploadInfo').innerHTML = `Job <code>${{currentJobId}}</code> creado con ${{data.count}} filas`;
      renderTable('preview', data.preview || []);
      renderJob(data.job);
    }}

    async function startJob() {{
      if (!currentJobId) {{ alert('Primero creá un job'); return; }}
      const r = await fetch(`/api/location-jobs/${{currentJobId}}/start`, {{ method: 'POST' }});
      const data = await r.json();
      if (data.error) {{ alert(data.error); return; }}
      renderJob(data.job);
      pollUntilDone();
    }}

    async function refreshJob() {{
      if (!currentJobId) return;
      const r = await fetch(`/api/location-jobs/${{currentJobId}}`);
      const data = await r.json();
      if (!data.error) renderJob(data);
    }}

    async function pollUntilDone() {{
      for (let i = 0; i < 120; i++) {{
        await refreshJob();
        const status = document.getElementById('jobStatus').dataset.status;
        if (status === 'completed' || status === 'failed') return;
        await new Promise(res => setTimeout(res, 1200));
      }}
    }}

    async function showFinalConfig() {{
      if (!currentJobId) return;
      const r = await fetch(`/api/location-jobs/${{currentJobId}}/result`);
      const data = await r.json();
      if (data.error) {{
        document.getElementById('finalConfig').textContent = data.error;
        return;
      }}
      const simplified = toStatusAndApiResponse(data);
      document.getElementById('finalConfig').textContent = JSON.stringify(simplified, null, 2);
      const errors = data.totals?.rejected || 0;
      document.getElementById('errorSummary').innerHTML = `Errores rechazados: <b>${{errors}}</b>`;
    }}

    function toStatusAndApiResponse(payload) {{
      const status = payload?.job?.status || payload?.status || 'unknown';
      const apiResponse = payload?.remote_final_state?.items || payload?.api_response || [];
      return {{ status, api_response: sanitizeApiResponse(apiResponse) }};
    }}

    function sanitizeApiResponse(payload) {{
      if (!payload || typeof payload !== 'object') return payload;
      if (Array.isArray(payload)) return payload.map(item => sanitizeApiResponse(item));
      const out = {{}};
      Object.entries(payload).forEach(([key, value]) => {{
        if (key === 'before' || key === 'after' || key === 'changed' || key === 'action') return;
        out[key] = sanitizeApiResponse(value);
      }});
      return out;
    }}

    function renderJob(job) {{
      const totals = job.totals || {{}};
      const processed = totals.processed || 0;
      const total = totals.total || 0;
      const pct = total ? Math.floor((processed / total) * 100) : 0;
      const label = `Estado: <b>${{job.status}}</b> | Procesadas: ${{processed}}/${{total}} | OK: ${{totals.success||0}} | Rechazadas: ${{totals.rejected||0}}`;
      const el = document.getElementById('jobStatus');
      el.innerHTML = label;
      el.dataset.status = job.status;
      document.getElementById('bar').style.width = pct + '%';
    }}

    function renderTable(targetId, items) {{
      const target = document.getElementById(targetId);
      if (!items.length) {{
        target.innerHTML = '<p>(sin datos)</p>';
        return;
      }}
      const headers = Object.keys(items[0]);
      const thead = '<tr>' + headers.map(h => `<th>${{h}}</th>`).join('') + '</tr>';
      const rows = items.map(row => '<tr>' + headers.map(h => `<td>${{row[h] ?? ''}}</td>`).join('') + '</tr>').join('');
      target.innerHTML = `<table><thead>${{thead}}</thead><tbody>${{rows}}</tbody></table>`;
    }}
  </script>
</body>
</html>
"""
