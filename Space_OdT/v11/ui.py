from __future__ import annotations

import asyncio
import csv
import json
import threading
import time
import traceback
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ..io.artifact_paths import ensure_dirs
from ..modules.catalog import MODULE_SPECS, run_spec
from ..modules.common import as_list, call_with_supported_kwargs, model_to_dict, resolve_attr
from ..modules.v1_manifest import V1_ARTIFACT_SPECS, _iter_kwargs, _row_from_item
from ..sdk_client import create_api


@dataclass
class JobState:
    status: str = 'idle'
    message: str = ''
    artifact: str = ''
    rows: int = 0
    csv_path: str = ''
    error: str = ''


def launch_v11_ui(*, token: str, out_dir: Path, host: str = '127.0.0.1', port: int = 8772, open_browser: bool = True) -> None:
    api = create_api(token=token)
    paths = ensure_dirs(out_dir)

    module_specs = {spec.name: spec for spec in MODULE_SPECS}
    artifact_specs = {spec.module: spec for spec in V1_ARTIFACT_SPECS}
    job = JobState()
    lock = threading.Lock()
    cached_json: dict[str, list[dict]] = {}

    def _artifact_dependencies(module_name: str) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()

        def visit(name: str) -> None:
            if name in seen:
                return
            seen.add(name)
            spec = artifact_specs.get(name)
            if not spec:
                return
            for src in spec.param_sources:
                visit(src.module)
            ordered.append(name)

        visit(module_name)
        return ordered

    async def _run_artifact_async(module_name: str) -> tuple[int, str]:
        if module_name not in artifact_specs:
            raise ValueError(f'Artifact no soportado: {module_name}')

        # Prepara cache mínimo requerido en memoria para resolver parámetros dependientes.
        cache: dict[str, list[dict]] = {}
        for name, spec in module_specs.items():
            if name in {src.module for src in artifact_specs[module_name].param_sources}:
                result = await asyncio.to_thread(run_spec, api, spec)
                cache[name] = result.rows

        dependency_chain = _artifact_dependencies(module_name)
        for dep_name in dependency_chain:
            if dep_name in cache:
                continue
            dep_result = await _run_single_spec_async(spec=artifact_specs[dep_name], cache=cache)
            cache[dep_name] = dep_result

        rows = cache.get(module_name, [])
        csv_path = paths['exports'] / f'{module_name}.csv'
        _write_csv(csv_path=csv_path, rows=rows)
        return len(rows), str(csv_path)

    async def _run_single_spec_async(*, spec, cache: dict[str, list[dict]]) -> list[dict]:
        method = resolve_attr(api, spec.method_path)
        kwargs_list = _iter_kwargs_for_async(cache=cache, spec=spec)
        if not kwargs_list:
            return []

        semaphore = asyncio.Semaphore(5)

        async def worker(kwargs: dict) -> list[dict]:
            async with semaphore:
                payload = await _call_with_retry(method, kwargs)
            items = [model_to_dict(i) for i in as_list(payload)]
            if not items and isinstance(payload, object):
                maybe = model_to_dict(payload)
                if maybe:
                    items = [maybe]
            rows: list[dict] = []
            for item in items:
                rows.append(_row_from_item(item, spec.method_path, kwargs))
            return rows

        chunks = await asyncio.gather(*(worker(kwargs) for kwargs in kwargs_list), return_exceptions=True)
        rows: list[dict] = []
        for chunk in chunks:
            if isinstance(chunk, Exception):
                raise chunk
            rows.extend(chunk)
        return rows

    async def _call_with_retry(method, kwargs: dict, retries: int = 4):
        for attempt in range(retries + 1):
            try:
                return await asyncio.to_thread(call_with_supported_kwargs, method, **kwargs)
            except Exception as exc:  # noqa: BLE001
                if attempt >= retries or '429' not in str(exc):
                    raise
                await asyncio.sleep((2 ** attempt) * 0.4)
        raise RuntimeError('retry exhausted')

    def _iter_kwargs_for_async(cache: dict[str, list[dict]], spec):
        return _iter_kwargs(cache, spec)

    def _write_csv(*, csv_path: Path, rows: list[dict]) -> None:
        headers = sorted({k for row in rows for k in row.keys()}) if rows else ['id']
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open('w', encoding='utf-8', newline='') as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

    async def _load_routing_groups() -> list[dict]:
        method = resolve_attr(api, 'telephony.prem_pstn.route_group.list')
        payload = await asyncio.to_thread(call_with_supported_kwargs, method)
        return [model_to_dict(x) for x in as_list(payload)]

    async def _load_licenses() -> list[dict]:
        method = resolve_attr(api, 'licenses.list')
        payload = await asyncio.to_thread(call_with_supported_kwargs, method)
        return [model_to_dict(x) for x in as_list(payload)]

    async def _load_person_ids() -> list[dict]:
        method = resolve_attr(api, 'people.list')
        payload = await asyncio.to_thread(call_with_supported_kwargs, method, calling_data=True)
        return [{'person_id': model_to_dict(x).get('id')} for x in as_list(payload)]

    async def _load_group_ids() -> list[dict]:
        method = resolve_attr(api, 'groups.list')
        payload = await asyncio.to_thread(call_with_supported_kwargs, method)
        return [{'group_id': model_to_dict(x).get('id')} for x in as_list(payload)]

    async def _load_location_ids() -> list[dict]:
        method = resolve_attr(api, 'locations.list')
        payload = await asyncio.to_thread(call_with_supported_kwargs, method)
        return [{'location_id': model_to_dict(x).get('id')} for x in as_list(payload)]

    async def _load_workspace_ids() -> list[dict]:
        method = resolve_attr(api, 'workspaces.list')
        payload = await asyncio.to_thread(call_with_supported_kwargs, method)
        return [{'workspace_id': model_to_dict(x).get('id')} for x in as_list(payload)]

    json_item_loaders = {
        'routing_groups': _load_routing_groups,
        'licenses': _load_licenses,
        'person_ids': _load_person_ids,
        'group_ids': _load_group_ids,
        'location_ids': _load_location_ids,
        'workspace_ids': _load_workspace_ids,
    }

    async def _load_json_item(item: str) -> list[dict]:
        if item in cached_json:
            return cached_json[item]

        loader = json_item_loaders.get(item)
        if loader is None:
            raise ValueError(f'Consulta JSON no soportada: {item}')

        rows = await loader()
        cached_json[item] = rows
        return rows

    class Handler(BaseHTTPRequestHandler):
        def _send(self, payload: dict, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == '/':
                html = _html_page().encode('utf-8')
                self.send_response(HTTPStatus.OK)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(html)))
                self.end_headers()
                self.wfile.write(html)
                return
            if parsed.path == '/api/artifacts':
                self._send({'items': sorted(artifact_specs.keys())})
                return
            if parsed.path == '/api/status':
                with lock:
                    self._send(job.__dict__)
                return
            if parsed.path == '/api/json-query':
                try:
                    query = parse_qs(parsed.query)
                    item = (query.get('item') or [''])[0]
                    page = max(int((query.get('page') or ['1'])[0]), 1)
                    page_size = min(max(int((query.get('page_size') or ['100'])[0]), 10), 250)
                    rows = asyncio.run(_load_json_item(item))
                    total = len(rows)
                    start = (page - 1) * page_size
                    end = start + page_size
                    self._send({
                        'item': item,
                        'page': page,
                        'page_size': page_size,
                        'total': total,
                        'total_pages': max((total + page_size - 1) // page_size, 1),
                        'rows': rows[start:end],
                    })
                except Exception as exc:  # noqa: BLE001
                    self._send({'error': str(exc)}, status=400)
                return
            self._send({'error': 'not found'}, status=404)

        def do_POST(self):  # noqa: N802
            if self.path != '/api/artifacts/generate':
                self._send({'error': 'not found'}, status=404)
                return
            content_length = int(self.headers.get('Content-Length', '0'))
            payload = json.loads(self.rfile.read(content_length) or b'{}')
            artifact = str(payload.get('artifact', ''))
            if artifact not in artifact_specs:
                self._send({'error': 'artifact no válido'}, status=400)
                return

            def run_job():
                with lock:
                    job.status = 'running'
                    job.message = f'Generando {artifact}...'
                    job.artifact = artifact
                    job.error = ''
                    job.rows = 0
                    job.csv_path = ''
                try:
                    started = time.time()
                    rows, csv_path = asyncio.run(_run_artifact_async(artifact))
                    elapsed = time.time() - started
                    with lock:
                        job.status = 'done'
                        job.rows = rows
                        job.csv_path = csv_path
                        job.message = f'CSV creado correctamente en {elapsed:.2f}s'
                except Exception as exc:  # noqa: BLE001
                    with lock:
                        job.status = 'error'
                        job.error = f'{type(exc).__name__}: {exc}'
                        job.message = 'Error generando artifact'
                        traceback.print_exc()

            thread = threading.Thread(target=run_job, daemon=True)
            thread.start()
            self._send({'ok': True, 'status': 'running', 'artifact': artifact})

        def log_message(self, format, *args):  # noqa: A003
            return

    server = ThreadingHTTPServer((host, port), Handler)
    url = f'http://{host}:{port}'
    print(f'V11 UI listening on {url}')
    if open_browser:
        webbrowser.open(url)
    try:
        with api:
            server.serve_forever()
    finally:
        server.server_close()


def _html_page() -> str:
    return """<!doctype html>
<html lang=\"es\">
<head>
<meta charset=\"utf-8\" />
<title>Space_OdT V11 Retriever</title>
<style>
body{font-family:Arial,sans-serif;background:#0e1a2b;color:#f2f6ff;margin:0;padding:20px}
.card{background:#16243a;border:1px solid #2d466f;border-radius:10px;padding:14px;margin-bottom:16px}
button{padding:8px 12px;background:#2f6fed;border:0;border-radius:8px;color:#fff;cursor:pointer}
select,input{padding:8px;border-radius:8px;border:1px solid #466188;background:#0f1c2e;color:#fff}
pre{background:#0a1320;border:1px solid #2b4061;padding:12px;border-radius:8px;max-height:340px;overflow:auto}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
</style>
</head>
<body>
  <h1>Space_OdT v11 — Retriever on demand</h1>
  <div class=\"card\">
    <h2>Generar CSV de artifact (on-demand)</h2>
    <div class=\"row\">
      <select id=\"artifact\"></select>
      <button onclick=\"generateArtifact()\">GET CSV</button>
      <button onclick=\"refreshStatus()\">Refrescar estado</button>
    </div>
    <pre id=\"statusBox\">Esperando acción...</pre>
  </div>

  <div class=\"card\">
    <h2>Consultas JSON en pantalla</h2>
    <div class=\"row\">
      <select id=\"jsonItem\">
        <option value=\"routing_groups\">Lista de routing groups</option>
        <option value=\"licenses\">Listado de licencias</option>
        <option value=\"person_ids\">Obtener person_id de personas</option>
        <option value=\"group_ids\">Obtener group_id de grupos</option>
        <option value=\"location_ids\">Obtener location_id de ubicaciones</option>
        <option value=\"workspace_ids\">Lista de workspace_id</option>
      </select>
      <input id=\"page\" type=\"number\" min=\"1\" value=\"1\" />
      <input id=\"pageSize\" type=\"number\" min=\"10\" max=\"250\" value=\"100\" />
      <button onclick=\"runJsonQuery()\">Consultar JSON</button>
    </div>
    <pre id=\"jsonBox\">Sin resultados.</pre>
  </div>

<script>
async function api(path, method='GET', body=null){
  const res = await fetch(path,{method,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):null});
  const payload = await res.json();
  if(!res.ok) throw new Error(payload.error || JSON.stringify(payload));
  return payload;
}
async function loadArtifacts(){
  const data = await api('/api/artifacts');
  const sel = document.getElementById('artifact');
  sel.innerHTML = '';
  data.items.forEach(item=>{const opt=document.createElement('option');opt.value=item;opt.textContent=item;sel.appendChild(opt);});
}
async function generateArtifact(){
  const artifact = document.getElementById('artifact').value;
  const res = await api('/api/artifacts/generate','POST',{artifact});
  document.getElementById('statusBox').textContent = JSON.stringify(res,null,2);
}
async function refreshStatus(){
  const res = await api('/api/status');
  document.getElementById('statusBox').textContent = JSON.stringify(res,null,2);
}
async function runJsonQuery(){
  const item = document.getElementById('jsonItem').value;
  const page = document.getElementById('page').value || '1';
  const pageSize = document.getElementById('pageSize').value || '100';
  const res = await api(`/api/json-query?item=${encodeURIComponent(item)}&page=${page}&page_size=${pageSize}`);
  document.getElementById('jsonBox').textContent = JSON.stringify(res,null,2);
}
loadArtifacts();
</script>
</body></html>"""
