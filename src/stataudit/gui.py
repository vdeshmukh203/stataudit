"""
Web-based GUI for stataudit.

Starts a local HTTP server and opens the browser at http://localhost:<port>.
Requires only the Python standard library (no tkinter, no external packages).

Usage
-----
From the CLI::

    stataudit --gui
    stataudit-gui          # installed entry-point

Programmatically::

    from stataudit.gui import launch
    launch()
"""
from __future__ import annotations

import json
import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlparse

from .core import audit_text
from .models import Severity
from .report import AuditReport
from .rules import _RULES

# ── shared server state ───────────────────────────────────────────────────────

_state: dict = {"report": None}

# ── embedded single-page application ─────────────────────────────────────────

_PAGE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>stataudit — Statistical Reporting Auditor</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,-apple-system,sans-serif;background:#f8f9fa;color:#212529;min-height:100vh}
header{background:#1a1a2e;color:#fff;padding:.75rem 1.5rem;display:flex;align-items:center;gap:1rem}
header h1{font-size:1.25rem;font-family:monospace;letter-spacing:.05em}
header span{color:#9ba3af;font-size:.8rem}
main{max-width:1100px;margin:0 auto;padding:1.25rem 1rem}
.card{background:#fff;border:1px solid #dee2e6;border-radius:8px;padding:1rem;margin-bottom:1rem}
.toolbar{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;margin-bottom:.75rem}
label.sev-label{font-size:.85rem;color:#555}
select{padding:.3rem .5rem;border:1px solid #ced4da;border-radius:4px;font-size:.85rem}
button{padding:.38rem .75rem;border:1px solid #ced4da;border-radius:4px;cursor:pointer;
       background:#fff;font-size:.85rem;transition:background .12s}
button:hover{background:#e9ecef}
#run-btn{background:#0d6efd;color:#fff;border-color:#0d6efd;font-weight:600}
#run-btn:hover{background:#0b5ed7}
#run-btn:disabled{opacity:.55;cursor:not-allowed}
.sep{width:1px;height:22px;background:#dee2e6;margin:0 .25rem}
textarea{width:100%;height:200px;font-family:monospace;font-size:.82rem;padding:.6rem;
         border:1px solid #ced4da;border-radius:4px;resize:vertical;line-height:1.5}
textarea:focus{outline:2px solid #86b7fe;border-color:#86b7fe}
.file-row{display:flex;align-items:center;gap:.5rem;margin-top:.5rem;font-size:.8rem;color:#6c757d}
.summary-bar{display:flex;align-items:center;gap:.75rem;flex-wrap:wrap}
.sum-title{font-weight:600;flex:1;font-size:.9rem}
.badge{display:inline-block;padding:.18rem .6rem;border-radius:10px;font-size:.78rem;
       font-weight:700;color:#fff;white-space:nowrap}
.badge.ERROR,.finding.ERROR{--accent:#dc3545}
.badge.WARNING,.finding.WARNING{--accent:#fd7e14}
.badge.INFO,.finding.INFO{--accent:#0d6efd}
.badge.ERROR{background:#dc3545}
.badge.WARNING{background:#fd7e14}
.badge.INFO{background:#0d6efd}
.findings-list{margin-top:.75rem;display:flex;flex-direction:column;gap:.4rem}
.finding{border:1px solid #dee2e6;border-left:4px solid var(--accent);border-radius:4px;
         cursor:pointer;transition:box-shadow .12s}
.finding:hover{box-shadow:0 2px 8px rgba(0,0,0,.08)}
.f-header{padding:.5rem .9rem;display:flex;align-items:center;gap:.6rem;flex-wrap:wrap}
.f-header code{font-size:.8rem;background:#f5f5f5;padding:.05rem .3rem;border-radius:3px}
.f-loc{color:#6c757d;font-size:.78rem;white-space:nowrap}
.f-snip{font-family:monospace;font-size:.78rem;color:#444;flex:1;
        overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.f-detail{border-top:1px solid #f0f0f0;padding:.6rem .9rem;background:#fafafa;
          font-size:.82rem;display:none;line-height:1.6}
.f-detail p{margin-bottom:.25rem}
.f-detail code{background:#efefef;padding:.05rem .3rem;border-radius:3px;font-size:.78rem}
.no-findings{text-align:center;padding:2.5rem 1rem;color:#198754;font-size:1rem}
#results{display:none}
#export-group{display:none}
kbd{background:#eee;border:1px solid #ccc;border-radius:3px;padding:.1rem .35rem;font-size:.75rem}
.rules-table{width:100%;border-collapse:collapse;font-size:.82rem}
.rules-table th{text-align:left;padding:.4rem .6rem;background:#f5f5f5;border-bottom:2px solid #dee2e6}
.rules-table td{padding:.35rem .6rem;border-bottom:1px solid #f0f0f0;vertical-align:top}
.rules-table tr:last-child td{border:none}
.rules-table tr.ERROR td{background:#fff5f5}
.rules-table tr.WARNING td{background:#fff8f0}
.rules-table tr.INFO td{background:#f0f5ff}
dialog{border:none;border-radius:8px;padding:1.25rem;max-width:780px;width:90%;
       box-shadow:0 8px 32px rgba(0,0,0,.18)}
dialog::backdrop{background:rgba(0,0,0,.35)}
.dialog-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem}
.dialog-header h2{font-size:1rem}
.close-btn{border:none;background:none;font-size:1.2rem;cursor:pointer;color:#6c757d;line-height:1}
.close-btn:hover{color:#000}
</style>
</head>
<body>
<header>
  <h1>stataudit</h1>
  <span>Statistical Reporting Auditor &mdash; paste or load your manuscript text</span>
</header>
<main>
  <div class="card">
    <div class="toolbar">
      <button id="run-btn" onclick="runAudit()">&#9654; Run Audit</button>
      <button onclick="clearAll()">Clear</button>
      <div class="sep"></div>
      <label class="sev-label">Min severity:
        <select id="severity">
          <option value="INFO">INFO</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
        </select>
      </label>
      <div class="sep"></div>
      <span id="export-group">
        Export:&nbsp;
        <button onclick="exportAs('text')">Text</button>
        <button onclick="exportAs('markdown')">Markdown</button>
        <button onclick="exportAs('json')">JSON</button>
        <button onclick="exportAs('html')">HTML</button>
        <div class="sep"></div>
      </span>
      <button onclick="showRules()">List rules</button>
      <button onclick="showAbout()">About</button>
      <span style="margin-left:auto;color:#6c757d;font-size:.78rem"><kbd>Ctrl</kbd>+<kbd>Enter</kbd> to run</span>
    </div>
    <textarea id="text-input"
      placeholder="Paste manuscript text here, or use the file picker below…&#10;&#10;Example: The groups differed significantly, t = 3.45, p = .031. The CI was [1.2, 3.4]. Regression was conducted."></textarea>
    <div class="file-row">
      <input type="file" id="file-input" accept=".txt,.md,.tex,.text" onchange="loadFile(event)">
      <span id="file-label"></span>
    </div>
  </div>

  <div class="card" id="results">
    <div class="summary-bar" id="summary-bar"></div>
    <div class="findings-list" id="findings-list"></div>
  </div>
</main>

<!-- Rules dialog -->
<dialog id="rules-dialog">
  <div class="dialog-header">
    <h2>Detection Rules (<span id="rules-count"></span>)</h2>
    <button class="close-btn" onclick="document.getElementById('rules-dialog').close()">&#215;</button>
  </div>
  <div id="rules-body"></div>
</dialog>

<!-- About dialog -->
<dialog id="about-dialog">
  <div class="dialog-header">
    <h2>About stataudit</h2>
    <button class="close-btn" onclick="document.getElementById('about-dialog').close()">&#215;</button>
  </div>
  <div id="about-body"></div>
</dialog>

<script>
'use strict';
let _findings = [];
let _summary = null;

async function runAudit() {
  const text = document.getElementById('text-input').value.trim();
  if (!text) { alert('Please enter or load text before auditing.'); return; }
  const severity = document.getElementById('severity').value;
  const btn = document.getElementById('run-btn');
  btn.textContent = '⏳ Running…'; btn.disabled = true;
  try {
    const res = await fetch('/audit', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({text, min_severity: severity})
    });
    if (!res.ok) { alert('Server error: ' + res.status); return; }
    const data = await res.json();
    _findings = data.findings;
    _summary = data.summary;
    renderResults(data);
  } catch(e) {
    alert('Error communicating with server: ' + e.message);
  } finally {
    btn.textContent = '▶ Run Audit'; btn.disabled = false;
  }
}

function renderResults(data) {
  const s = data.summary.by_severity;
  const sb = document.getElementById('summary-bar');
  sb.innerHTML =
    '<span class="sum-title">Audit complete &mdash; ' + data.summary.total + ' findings</span>' +
    '<span class="badge ERROR">ERROR&nbsp;' + s.ERROR + '</span>' +
    '<span class="badge WARNING">WARNING&nbsp;' + s.WARNING + '</span>' +
    '<span class="badge INFO">INFO&nbsp;' + s.INFO + '</span>';

  const fl = document.getElementById('findings-list');
  if (!data.findings.length) {
    fl.innerHTML = '<div class="no-findings">&#10003;&nbsp; No findings — well-reported statistics!</div>';
  } else {
    fl.innerHTML = data.findings.map((f, i) =>
      '<div class="finding ' + f.severity + '" onclick="toggleDetail(' + i + ')">' +
        '<div class="f-header">' +
          '<span class="badge ' + f.severity + '">' + f.severity + '</span>' +
          '<code>' + esc(f.rule) + '</code>' +
          '<span class="f-loc">' + esc(f.location) + '</span>' +
          '<span class="f-snip">' + esc(f.text.slice(0,90)) + (f.text.length>90?'&hellip;':'') + '</span>' +
        '</div>' +
        '<div class="f-detail" id="det-' + i + '">' +
          '<p><strong>Rule:</strong> <code>' + esc(f.rule) + '</code></p>' +
          '<p><strong>Severity:</strong> ' + f.severity + '</p>' +
          '<p><strong>Location:</strong> ' + esc(f.location) + '</p>' +
          '<p><strong>Text:</strong> <code>' + esc(f.text) + '</code></p>' +
          '<p><strong>Suggestion:</strong> ' + esc(f.suggestion) + '</p>' +
        '</div>' +
      '</div>'
    ).join('');
  }
  document.getElementById('results').style.display = 'block';
  document.getElementById('export-group').style.display = '';
  document.getElementById('results').scrollIntoView({behavior:'smooth', block:'start'});
}

function toggleDetail(i) {
  const d = document.getElementById('det-' + i);
  d.style.display = d.style.display === 'block' ? 'none' : 'block';
}

function esc(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function loadFile(ev) {
  const f = ev.target.files[0];
  if (!f) return;
  document.getElementById('file-label').textContent = f.name;
  const reader = new FileReader();
  reader.onload = e => { document.getElementById('text-input').value = e.target.result; };
  reader.readAsText(f);
}

function clearAll() {
  document.getElementById('text-input').value = '';
  document.getElementById('file-input').value = '';
  document.getElementById('file-label').textContent = '';
  document.getElementById('results').style.display = 'none';
  document.getElementById('export-group').style.display = 'none';
  _findings = []; _summary = null;
}

async function exportAs(fmt) {
  const res = await fetch('/export?format=' + fmt);
  if (!res.ok) { alert('No report to export — run an audit first.'); return; }
  const blob = await res.blob();
  const exts = {text:'.txt', markdown:'.md', json:'.json', html:'.html'};
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'stataudit_report' + (exts[fmt] || '.txt');
  a.click();
}

async function showRules() {
  const res = await fetch('/rules');
  const rules = await res.json();
  document.getElementById('rules-count').textContent = rules.length;
  const rows = rules.map(r =>
    '<tr class="' + r.severity + '">' +
    '<td><code>' + esc(r.name) + '</code></td>' +
    '<td><span class="badge ' + r.severity + '">' + r.severity + '</span></td>' +
    '<td>' + esc(r.suggestion) + '</td></tr>'
  ).join('');
  document.getElementById('rules-body').innerHTML =
    '<table class="rules-table"><thead><tr><th>Name</th><th>Severity</th><th>Suggestion</th></tr></thead>' +
    '<tbody>' + rows + '</tbody></table>';
  document.getElementById('rules-dialog').showModal();
}

async function showAbout() {
  const res = await fetch('/about');
  const info = await res.json();
  document.getElementById('about-body').innerHTML =
    '<p><strong>stataudit</strong> v' + esc(info.version) + '</p>' +
    '<p style="margin:.5rem 0;color:#555">' + esc(info.description) + '</p>' +
    '<p>Author: ' + esc(info.author) + '</p>' +
    '<p>License: ' + esc(info.license) + '</p>' +
    '<p style="margin-top:.75rem;font-size:.8rem;color:#6c757d">' +
    'Checks p-values, CIs, effect sizes, degrees of freedom,<br>' +
    'sample sizes, regression R², and other reporting standards.</p>';
  document.getElementById('about-dialog').showModal();
}

document.addEventListener('keydown', e => {
  if (e.ctrlKey && e.key === 'Enter') runAudit();
});
</script>
</body>
</html>
"""


# ── HTTP handler ──────────────────────────────────────────────────────────────

class _Handler(BaseHTTPRequestHandler):
    """Minimal HTTP handler serving the stataudit web GUI."""

    def log_message(self, fmt: str, *args) -> None:  # silence default access log
        pass

    # ── routing ───────────────────────────────────────────────────────────

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._html(_PAGE.encode())
        elif path == "/rules":
            payload = [
                {"name": n, "severity": s.value, "suggestion": sg}
                for n, _, s, sg in _RULES
            ]
            self._json(payload)
        elif path == "/about":
            from . import __author__, __license__, __version__

            self._json(
                {
                    "version": __version__,
                    "author": __author__,
                    "license": __license__,
                    "description": (
                        "Automated statistical reporting auditor "
                        "for academic manuscripts."
                    ),
                }
            )
        elif path == "/export":
            self._handle_export()
        else:
            self._not_found()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/audit":
            self._handle_audit()
        else:
            self._not_found()

    # ── handlers ──────────────────────────────────────────────────────────

    def _handle_audit(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        text: str = body.get("text", "")
        min_sev = Severity(body.get("min_severity", "INFO"))
        findings = audit_text(text, min_sev)
        _state["report"] = AuditReport(source="<web>", findings=findings)
        self._json(
            {
                "summary": _state["report"].summary,
                "findings": [f.to_dict() for f in findings],
            }
        )

    def _handle_export(self) -> None:
        report: Optional[AuditReport] = _state.get("report")
        if report is None:
            self.send_response(404)
            self.end_headers()
            return
        params = parse_qs(urlparse(self.path).query)
        fmt = params.get("format", ["text"])[0]
        renderers = {
            "text": (report.to_text, "text/plain", ".txt"),
            "markdown": (report.to_markdown, "text/markdown", ".md"),
            "json": (report.to_json, "application/json", ".json"),
            "html": (report.to_html, "text/html", ".html"),
        }
        render_fn, mime, _ = renderers.get(fmt, renderers["text"])
        content = render_fn().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", f"{mime}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header(
            "Content-Disposition",
            f'attachment; filename="stataudit_report{renderers.get(fmt, renderers["text"])[2]}"',
        )
        self.end_headers()
        self.wfile.write(content)

    # ── helpers ───────────────────────────────────────────────────────────

    def _html(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _not_found(self) -> None:
        self.send_response(404)
        self.end_headers()


# ── public API ────────────────────────────────────────────────────────────────

def _free_port(preferred: int = 8557) -> int:
    """Return *preferred* if free, otherwise any available OS-assigned port."""
    for port in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    return 0


def launch(port: int = 8557, open_browser: bool = True) -> None:
    """
    Start the stataudit web GUI.

    Opens ``http://localhost:<port>`` in the default browser and blocks
    until the server is stopped (Ctrl-C).

    Parameters
    ----------
    port:
        Preferred TCP port (falls back to any free port if taken).
    open_browser:
        Set to *False* to suppress automatic browser opening.
    """
    port = _free_port(port)
    server = HTTPServer(("127.0.0.1", port), _Handler)
    url = f"http://localhost:{port}"
    print(f"stataudit GUI running at  {url}")
    print("Press Ctrl-C to stop.")
    if open_browser:
        threading.Thread(
            target=lambda: webbrowser.open(url), daemon=True
        ).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


def main() -> None:
    """Entry point for the ``stataudit-gui`` console script."""
    launch()
