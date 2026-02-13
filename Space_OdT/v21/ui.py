from __future__ import annotations

import asyncio
import csv
import io
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .engine import MissingV21InputsError, V21Runner
from .io import LOCATION_HEADERS, LOCATION_REQUIRED_CREATE_FIELDS, load_locations_from_json


def launch_v21_ui(*, token: str, out_dir: Path, host: str = '127.0.0.1', port: int = 8765) -> None:
    runner = V21Runner(token=token, out_dir=out_dir)

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
            if parsed.path == '/api/final-config':
                path = runner.v21_dir / 'results_locations.json'
                if not path.exists():
                    self._send({'items': []})
                    return
                self._send(json.loads(path.read_text(encoding='utf-8')))
                return
            self._send({'error': 'not found'}, status=404)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == '/api/upload-locations':
                try:
                    rows, preview = self._parse_upload()
                    self._send({'count': len(rows), 'preview': preview})
                except Exception as exc:  # pragma: no cover
                    self._send({'error': str(exc)}, status=400)
                return

            if parsed.path == '/api/run-locations':
                try:
                    content_length = int(self.headers.get('Content-Length', '0'))
                    body = self.rfile.read(content_length) if content_length else b'{}'
                    payload = json.loads(body.decode('utf-8'))
                    rows = load_locations_from_json(payload.get('rows', []))
                    apply = bool(payload.get('apply', True))
                    max_concurrency = int(payload.get('max_concurrency', 20))
                    result = asyncio.run(runner.run_locations_async(rows, apply=apply, max_concurrency=max_concurrency))
                    self._send(result)
                except Exception as exc:  # pragma: no cover
                    self._send({'error': str(exc)}, status=400)
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
  <title>Space_OdT v2.1 alta_locations</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; max-width: 1100px; }}
    .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 12px; margin-bottom: 14px; }}
    button {{ margin-right: 8px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 6px; font-size: 12px; }}
    pre {{ background: #f6f6f6; padding: 8px; border-radius: 6px; overflow-x: auto; }}
  </style>
</head>
<body>
  <h1>Space_OdT v2.1 - alta_locations</h1>

  <div class="card">
    <h3>Ver qué hay</h3>
    <input id="file" type="file" accept=".csv,.json" />
    <button onclick="uploadFile()">Cargar CSV/JSON</button>
    <div id="uploadInfo"></div>
    <div id="preview"></div>
  </div>

  <div class="card">
    <h3>Campos obligatorios</h3>
    <ul>{required}</ul>
  </div>

  <div class="card">
    <h3>Ejecutar acción</h3>
    <button onclick="runAction()">Ejecutar acción</button>
    <div id="summary"></div>
    <div id="resultTable"></div>
    <button onclick="showFinalConfig()">Ver configuración final</button>
    <pre id="finalConfig"></pre>
  </div>

  <script>
    let loadedRows = [];

    async function uploadFile() {{
      const fileEl = document.getElementById('file');
      if (!fileEl.files.length) {{
        alert('Seleccioná un archivo CSV o JSON');
        return;
      }}
      const fd = new FormData();
      fd.append('file', fileEl.files[0]);
      const r = await fetch('/api/upload-locations', {{ method: 'POST', body: fd }});
      const data = await r.json();
      if (data.error) {{
        document.getElementById('uploadInfo').innerHTML = '<span style="color:red">' + data.error + '</span>';
        return;
      }}
      loadedRows = data.preview ? [...data.preview] : [];
      document.getElementById('uploadInfo').innerHTML = `<b>${{data.count}}</b> filas parseadas`;
      renderTable('preview', data.preview || []);
    }}

    async function runAction() {{
      const rows = await collectRowsFromPreviewOrFile();
      const r = await fetch('/api/run-locations', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ rows, apply: true, max_concurrency: 20 }}),
      }});
      const data = await r.json();
      if (data.error) {{
        document.getElementById('summary').innerHTML = '<span style="color:red">' + data.error + '</span>';
        return;
      }}
      document.getElementById('summary').innerHTML = `Total: ${{data.summary.total}} | Success: ${{data.summary.success}} | Pending: ${{data.summary.pending}} | Rejected: ${{data.summary.rejected}}`;
      renderTable('resultTable', data.items || []);
    }}

    async function collectRowsFromPreviewOrFile() {{
      const fileEl = document.getElementById('file');
      if (!fileEl.files.length) return loadedRows;
      const file = fileEl.files[0];
      if (file.name.endsWith('.json')) {{
        return JSON.parse(await file.text());
      }}
      const text = await file.text();
      return csvToObjects(text);
    }}

    function csvToObjects(text) {{
      const lines = text.split(/\r?\n/).filter(Boolean);
      if (!lines.length) return [];
      const headers = lines[0].split(',').map(h => h.trim());
      return lines.slice(1).map(line => {{
        const cols = line.split(',');
        const obj = {{}};
        headers.forEach((h, idx) => obj[h] = (cols[idx] || '').trim());
        return obj;
      }});
    }}

    async function showFinalConfig() {{
      const r = await fetch('/api/final-config');
      const data = await r.json();
      document.getElementById('finalConfig').textContent = JSON.stringify(data, null, 2);
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
