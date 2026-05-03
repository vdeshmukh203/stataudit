"""Browser-based GUI for stataudit.

Starts a local HTTP server and opens the interface in the default browser.
Requires only the Python standard library.
"""
from __future__ import annotations

import json
import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ._core import Severity, audit_text
from .report import AuditReport

# ---------------------------------------------------------------------------
# HTML template (single-page app, no external dependencies)
# ---------------------------------------------------------------------------

_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>stataudit — Statistical Reporting Auditor</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f4f6f9; color: #1a1a2e; min-height: 100vh;
  }
  header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    color: #fff; padding: 1.2em 2em; display: flex; align-items: center; gap: 1em;
  }
  header h1 { font-size: 1.4em; font-weight: 700; letter-spacing: .02em; }
  header span { font-size: .85em; opacity: .7; }
  .container { max-width: 1100px; margin: 2em auto; padding: 0 1.5em; }
  .card {
    background: #fff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.08);
    padding: 1.5em; margin-bottom: 1.5em;
  }
  .card h2 { font-size: 1em; text-transform: uppercase; letter-spacing: .08em;
             color: #555; margin-bottom: 1em; }
  textarea {
    width: 100%; height: 180px; font-family: "Courier New", monospace; font-size: .9em;
    border: 1px solid #ccd; border-radius: 6px; padding: .8em; resize: vertical;
    background: #fafbfc; color: #222; outline: none; transition: border-color .2s;
  }
  textarea:focus { border-color: #4e9af1; }
  .controls { display: flex; align-items: center; flex-wrap: wrap; gap: 1em; margin-top: 1em; }
  label { font-size: .9em; color: #444; }
  select {
    padding: .45em .8em; border: 1px solid #ccd; border-radius: 6px; font-size: .9em;
    background: #fff; cursor: pointer;
  }
  .btn {
    padding: .55em 1.4em; border: none; border-radius: 6px; font-size: .95em;
    cursor: pointer; font-weight: 600; transition: filter .15s;
  }
  .btn:hover { filter: brightness(1.08); }
  .btn-primary { background: #4e9af1; color: #fff; }
  .btn-secondary { background: #e8eaf0; color: #333; }
  .btn-success  { background: #27ae60; color: #fff; }
  #auditBtn { padding: .65em 2.2em; font-size: 1em; }
  .summary-bar {
    display: flex; gap: 1em; margin-bottom: 1em; flex-wrap: wrap;
  }
  .badge {
    padding: .35em .9em; border-radius: 20px; font-weight: 700; font-size: .85em;
    color: #fff;
  }
  .badge-error   { background: #c0392b; }
  .badge-warning { background: #e67e22; }
  .badge-info    { background: #2980b9; }
  .badge-total   { background: #555; }
  table { width: 100%; border-collapse: collapse; font-size: .88em; }
  th {
    background: #1a1a2e; color: #fff; padding: .6em .8em; text-align: left;
    position: sticky; top: 0;
  }
  td { padding: .55em .8em; border-bottom: 1px solid #eaecf0; vertical-align: top; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: #f0f4ff; }
  .sev-ERROR   { color: #c0392b; font-weight: 700; }
  .sev-WARNING { color: #d35400; font-weight: 700; }
  .sev-INFO    { color: #2471a3; font-weight: 700; }
  code { background: #f0f0f5; padding: .1em .35em; border-radius: 3px; font-size: .9em; }
  #results { display: none; }
  #empty { display: none; text-align: center; color: #888; padding: 2em; }
  .spinner {
    display: none; width: 22px; height: 22px; border: 3px solid #ccd;
    border-top-color: #4e9af1; border-radius: 50%; animation: spin .7s linear infinite;
    margin-left: .5em; vertical-align: middle;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .export-row { display: flex; gap: .8em; margin-top: 1em; }
  #statusMsg { font-size: .85em; color: #555; margin-top: .5em; min-height: 1.2em; }
  .table-wrap { max-height: 480px; overflow-y: auto; border-radius: 6px;
                border: 1px solid #eaecf0; }
</style>
</head>
<body>
<header>
  <div>
    <h1>stataudit</h1>
    <span>Statistical Reporting Auditor</span>
  </div>
</header>

<div class="container">
  <!-- Input -->
  <div class="card">
    <h2>Manuscript Text</h2>
    <textarea id="inputText"
      placeholder="Paste manuscript text here, e.g.:&#10;&#10;The intervention was significant (p &lt; 0.05). The regression model explained variance (R² = .42). A t-test was conducted (t = 3.21)."></textarea>
    <div class="controls">
      <label for="severityFilter">Min severity:</label>
      <select id="severityFilter">
        <option value="INFO" selected>INFO (all)</option>
        <option value="WARNING">WARNING</option>
        <option value="ERROR">ERROR</option>
      </select>
      <button class="btn btn-primary" id="auditBtn" onclick="runAudit()">
        Audit
      </button>
      <div class="spinner" id="spinner"></div>
      <button class="btn btn-secondary" onclick="clearAll()">Clear</button>
    </div>
    <div id="statusMsg"></div>
  </div>

  <!-- Results -->
  <div class="card" id="results">
    <h2>Findings</h2>
    <div class="summary-bar" id="summaryBar"></div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Severity</th>
            <th>Rule</th>
            <th>Location</th>
            <th>Matched Text</th>
            <th>Suggestion</th>
          </tr>
        </thead>
        <tbody id="findingsBody"></tbody>
      </table>
      <div id="empty">No findings for the selected severity level.</div>
    </div>
    <div class="export-row">
      <button class="btn btn-success" onclick="exportReport('json')">Export JSON</button>
      <button class="btn btn-success" onclick="exportReport('markdown')">Export Markdown</button>
      <button class="btn btn-success" onclick="exportReport('html')">Export HTML</button>
    </div>
  </div>
</div>

<script>
let lastData = null;

async function runAudit() {
  const text = document.getElementById('inputText').value.trim();
  if (!text) { setStatus('Please enter some text to audit.', 'orange'); return; }

  const severity = document.getElementById('severityFilter').value;
  document.getElementById('spinner').style.display = 'inline-block';
  document.getElementById('auditBtn').disabled = true;
  setStatus('Auditing…');

  try {
    const resp = await fetch('/audit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, min_severity: severity })
    });
    if (!resp.ok) throw new Error(await resp.text());
    lastData = await resp.json();
    renderResults(lastData);
    setStatus('');
  } catch (e) {
    setStatus('Error: ' + e.message, '#c0392b');
  } finally {
    document.getElementById('spinner').style.display = 'none';
    document.getElementById('auditBtn').disabled = false;
  }
}

function renderResults(data) {
  const findings = data.findings;
  const s = data.summary.by_severity;

  document.getElementById('results').style.display = 'block';

  const bar = document.getElementById('summaryBar');
  bar.innerHTML = `
    <span class="badge badge-total">Total: ${findings.length}</span>
    <span class="badge badge-error">ERROR: ${s.ERROR}</span>
    <span class="badge badge-warning">WARNING: ${s.WARNING}</span>
    <span class="badge badge-info">INFO: ${s.INFO}</span>`;

  const tbody = document.getElementById('findingsBody');
  tbody.innerHTML = '';
  const empty = document.getElementById('empty');

  if (findings.length === 0) {
    empty.style.display = 'block';
    return;
  }
  empty.style.display = 'none';

  findings.forEach(f => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="sev-${f.severity}">${f.severity}</td>
      <td><code>${esc(f.rule)}</code></td>
      <td>${esc(f.location)}</td>
      <td><code>${esc(f.text)}</code></td>
      <td>${esc(f.suggestion)}</td>`;
    tbody.appendChild(tr);
  });
}

function exportReport(fmt) {
  if (!lastData) return;
  const text = document.getElementById('inputText').value.trim();
  const severity = document.getElementById('severityFilter').value;
  const url = `/export?fmt=${fmt}&min_severity=${severity}`;
  const form = document.createElement('form');
  form.method = 'POST'; form.action = url;
  const inp = document.createElement('input');
  inp.type = 'hidden'; inp.name = 'text'; inp.value = text;
  form.appendChild(inp);
  document.body.appendChild(form);
  form.submit();
  document.body.removeChild(form);
}

function clearAll() {
  document.getElementById('inputText').value = '';
  document.getElementById('results').style.display = 'none';
  document.getElementById('findingsBody').innerHTML = '';
  lastData = null;
  setStatus('');
}

function setStatus(msg, color) {
  const el = document.getElementById('statusMsg');
  el.textContent = msg;
  el.style.color = color || '#555';
}

function esc(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Allow Ctrl/Cmd+Enter to run audit
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') runAudit();
});
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTTP request handler
# ---------------------------------------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    """Minimal HTTP handler serving the GUI and the audit API."""

    # Suppress access logs in normal use
    def log_message(self, fmt: str, *args: object) -> None:  # noqa: ARG002
        pass

    def log_error(self, fmt: str, *args: object) -> None:  # noqa: ARG002
        pass

    # ---- routing -----------------------------------------------------------

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", _HTML.encode())
        else:
            self._send(404, "text/plain", b"Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/audit":
            self._handle_audit()
        elif parsed.path == "/export":
            self._handle_export(parsed)
        else:
            self._send(404, "text/plain", b"Not found")

    # ---- API: /audit -------------------------------------------------------

    def _handle_audit(self) -> None:
        body = self._read_body()
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._send(400, "text/plain", b"Bad JSON")
            return

        text = payload.get("text", "")
        sev_str = payload.get("min_severity", "INFO").upper()
        try:
            min_sev = Severity(sev_str)
        except ValueError:
            min_sev = Severity.INFO

        findings = audit_text(text, min_sev)
        report = AuditReport(source="<gui>", findings=findings)
        result = json.dumps(
            {"summary": report.summary, "findings": [f.to_dict() for f in findings]},
            ensure_ascii=False,
        ).encode()
        self._send(200, "application/json; charset=utf-8", result)

    # ---- API: /export ------------------------------------------------------

    def _handle_export(self, parsed) -> None:
        params = parse_qs(parsed.query)
        fmt = params.get("fmt", ["text"])[0]
        sev_str = params.get("min_severity", ["INFO"])[0].upper()
        try:
            min_sev = Severity(sev_str)
        except ValueError:
            min_sev = Severity.INFO

        body = self._read_body()
        fields = parse_qs(body.decode(errors="replace"))
        text = fields.get("text", [""])[0]

        findings = audit_text(text, min_sev)
        report = AuditReport(source="<gui>", findings=findings)

        if fmt == "json":
            content = report.to_json().encode()
            mime = "application/json"
            filename = "stataudit_report.json"
        elif fmt == "markdown":
            content = report.to_markdown().encode()
            mime = "text/markdown"
            filename = "stataudit_report.md"
        elif fmt == "html":
            content = report._to_html().encode()
            mime = "text/html; charset=utf-8"
            filename = "stataudit_report.html"
        else:
            content = report.to_text().encode()
            mime = "text/plain"
            filename = "stataudit_report.txt"

        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header(
            "Content-Disposition", f'attachment; filename="{filename}"'
        )
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    # ---- helpers -----------------------------------------------------------

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length > 0 else b""

    def _send(self, code: int, mime: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def launch(port: int = 0, open_browser: bool = True) -> None:
    """Start the stataudit web GUI.

    Launches a local HTTP server and opens the interface in the default
    browser.  Blocks until interrupted with Ctrl-C.

    Parameters
    ----------
    port:
        TCP port to listen on.  ``0`` chooses a free port automatically.
    open_browser:
        Open the system's default browser on start-up.
    """
    if port == 0:
        port = _find_free_port()

    server = HTTPServer(("127.0.0.1", port), _Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"stataudit GUI → {url}  (press Ctrl-C to stop)")

    if open_browser:
        threading.Timer(0.3, webbrowser.open, args=(url,)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()
