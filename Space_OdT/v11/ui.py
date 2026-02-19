from __future__ import annotations

import asyncio
import json
import threading
import time
import traceback
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from itertools import product
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..io.artifact_paths import ensure_dirs
from ..io.csv_writer import write_csv
from ..modules.catalog import MODULE_SPECS, run_spec
from ..modules.common import as_list, call_with_supported_kwargs, model_to_dict, resolve_attr
from ..modules.v1_manifest import STANDARD_COLUMNS, V1_ARTIFACT_SPECS
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

    def _id_values(cache: dict[str, list[dict]], source) -> list[Any]:
        rows = cache.get(source.module, [])
        values = [
            r.get(source.field)
            for r in rows
            if r.get(source.field) and (source.required_field is None or r.get(source.required_field))
        ]
        seen: set[Any] = set()
        uniq: list[Any] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            uniq.append(value)
        return uniq

    def _iter_kwargs(cache: dict[str, list[dict]], spec) -> list[dict[str, Any]]:
        if not spec.param_sources:
            return [dict(spec.static_kwargs)]
        value_lists = [_id_values(cache, src) for src in spec.param_sources]
        if any(not vals for vals in value_lists):
            return []
        keys = [s.name for s in spec.param_sources]
        out: list[dict[str, Any]] = []
        for combo in product(*value_lists):
            kwargs = dict(spec.static_kwargs)
            kwargs.update(dict(zip(keys, combo)))
            out.append(kwargs)
        return out

    def _row_from_item(item: dict[str, Any], method_path: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        row = {k: item.get(k, '') for k in STANDARD_COLUMNS}
        for key in ('location_id', 'person_id', 'workspace_id', 'license_id', 'virtual_line_id', 'group_id', 'id', 'name'):
            if not row.get(key) and kwargs.get(key):
                row[key] = kwargs[key]
        for key, value in kwargs.items():
            if key.endswith('_id') and key not in row:
                row[key] = value
        row['source_method'] = method_path
        row['raw_keys'] = ','.join(sorted(item.keys()))
        row['raw_json'] = json.dumps(item, ensure_ascii=False, sort_keys=True)
        return row

    async def _call_with_retry(method, kwargs: dict[str, Any], retries: int = 4) -> Any:
        for attempt in range(retries + 1):
            try:
                return await asyncio.to_thread(call_with_supported_kwargs, method, **kwargs)
            except Exception as exc:  # noqa: BLE001
                if attempt >= retries or '429' not in str(exc):
                    raise
                await asyncio.sleep((2**attempt) * 0.5)
        raise RuntimeError('retry exhausted')

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

    async def _run_single_spec_async(*, spec, cache: dict[str, list[dict]]) -> list[dict]:
        kwargs_list = _iter_kwargs(cache=cache, spec=spec)
        if not kwargs_list:
            return []

        semaphore = asyncio.Semaphore(4)

        async def worker(kwargs: dict[str, Any]) -> list[dict]:
            method = resolve_attr(api, spec.method_path)
            async with semaphore:
                payload = await _call_with_retry(method, kwargs)
            items = [model_to_dict(item) for item in as_list(payload)]
            if not items:
                maybe = model_to_dict(payload)
                if maybe:
                    items = [maybe]
            return [_row_from_item(item, spec.method_path, kwargs) for item in items]

        rows: list[dict] = []
        batch_size = 50
        for start in range(0, len(kwargs_list), batch_size):
            batch = kwargs_list[start:start + batch_size]
            chunk_results = await asyncio.gather(*(worker(kwargs) for kwargs in batch))
            for partial in chunk_results:
                rows.extend(partial)
        return rows

    async def _run_artifact_async(module_name: str) -> tuple[int, str]:
        if module_name not in artifact_specs:
            raise ValueError(f'Artifact no soportado: {module_name}')

        cache: dict[str, list[dict]] = {}
        dependency_chain = _artifact_dependencies(module_name)

        for dep_name in dependency_chain:
            if dep_name in cache:
                continue
            spec = artifact_specs[dep_name]
            for src in spec.param_sources:
                if src.module in cache:
                    continue
                if src.module in module_specs:
                    result = await asyncio.to_thread(run_spec, api, module_specs[src.module])
                    cache[src.module] = result.rows
            cache[dep_name] = await _run_single_spec_async(spec=spec, cache=cache)

        rows = cache.get(module_name, [])
        csv_path = paths['exports'] / f'{module_name}.csv'
        write_csv(csv_path, rows, STANDARD_COLUMNS)
        return len(rows), str(csv_path)

    async def _load_json_item(item: str) -> list[dict]:
        if item in cached_json:
            return cached_json[item]

        if item == 'routing_groups':
            method_path, kwargs = 'telephony.prem_pstn.route_group.list', {}
        elif item == 'licenses':
            method_path, kwargs = 'licenses.list', {}
        elif item == 'person_ids':
            method_path, kwargs = 'people.list', {'calling_data': True}
        elif item == 'workspace_ids':
            method_path, kwargs = 'workspaces.list', {}
        else:
            raise ValueError(f'Consulta JSON no soportada: {item}')

        method = resolve_attr(api, method_path)
        payload = await _call_with_retry(method, kwargs)
        objects = [model_to_dict(x) for x in as_list(payload)]

        if item == 'person_ids':
            rows = [{'person_id': obj.get('id'), 'display_name': obj.get('displayName', obj.get('display_name', ''))} for obj in objects]
        elif item == 'workspace_ids':
            rows = [{'workspace_id': obj.get('id'), 'name': obj.get('displayName', obj.get('name', ''))} for obj in objects]
        else:
            rows = objects

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

            with lock:
                if job.status == 'running':
                    self._send({'error': 'Ya existe un job en ejecución. Espera a que termine.'}, status=409)
                    return

            def run_job() -> None:
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

            threading.Thread(target=run_job, daemon=True).start()
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
  try {
    const artifact = document.getElementById('artifact').value;
    const res = await api('/api/artifacts/generate','POST',{artifact});
    document.getElementById('statusBox').textContent = JSON.stringify(res,null,2);
  } catch (err){
    document.getElementById('statusBox').textContent = String(err);
  }
}
async function refreshStatus(){
  const res = await api('/api/status');
  document.getElementById('statusBox').textContent = JSON.stringify(res,null,2);
}
async function runJsonQuery(){
  try {
    const item = document.getElementById('jsonItem').value;
    const page = document.getElementById('page').value || '1';
    const pageSize = document.getElementById('pageSize').value || '100';
    const res = await api(`/api/json-query?item=${encodeURIComponent(item)}&page=${page}&page_size=${pageSize}`);
    document.getElementById('jsonBox').textContent = JSON.stringify(res,null,2);
  } catch (err) {
    document.getElementById('jsonBox').textContent = String(err);
  }
}
loadArtifacts();
</script>
</body></html>"""
