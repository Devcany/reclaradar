"""
app.py — ReclaRadar API  (Päckchen 3)
======================================
FastAPI-App: Reklamation (JSON/PDF) → 8D-Report via Claude

Start:
    uvicorn app:app --host 0.0.0.0 --port 8003

Umgebungsvariablen:
    ANTHROPIC_API_KEY     — Pflicht für POST /api/analyze
    RECLARADAR_API_KEY    — Auth-Key für geschützte Endpoints
"""

import os
import sys
import json
import time
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# Sys-Path: generate_8d_report.py muss importierbar sein
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from generate_8d_report import load_input, build_user_prompt, call_claude, SYSTEM_PROMPT  # noqa: E402

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------
VERSION        = "0.1.0"
MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB
API_KEY        = os.getenv("RECLARADAR_API_KEY", "")
ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY", "")

ALLOWED_EXTENSIONS = {".json", ".pdf"}

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _verify_key(x_api_key: str | None) -> None:
    if not API_KEY:
        return  # Kein Key konfiguriert → offen (Dev-Modus)
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail={"status": "error", "error": "Ungültiger oder fehlender API Key"},
        )

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not ANTHROPIC_KEY:
        print("⚠️  ANTHROPIC_API_KEY nicht gesetzt — POST /api/analyze liefert 500", file=sys.stderr)
    if not API_KEY:
        print("ℹ️  RECLARADAR_API_KEY nicht gesetzt — API läuft ohne Auth (Dev-Modus)", file=sys.stderr)
    print(f"✅ ReclaRadar v{VERSION} gestartet auf Port 8003")
    yield

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ReclaRadar API",
    version=VERSION,
    description="Reklamationsdokument (JSON/PDF) → 8D-Report via Claude",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Exception Handler
# ---------------------------------------------------------------------------

@app.exception_handler(HTTPException)
async def _http_handler(request: Request, exc: HTTPException):
    content = exc.detail if isinstance(exc.detail, dict) else {"status": "error", "error": exc.detail}
    return JSONResponse(status_code=exc.status_code, content=content)

@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"status": "error", "error": "Ungültige Anfrage", "detail": str(exc)},
    )

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": VERSION,
        "anthropic_key_set": bool(ANTHROPIC_KEY),
        "auth_enabled": bool(API_KEY),
    }


@app.post("/api/analyze")
async def analyze_endpoint(
    request:   Request,
    file:      UploadFile = File(..., description="Reklamationsdokument (.json oder .pdf)"),
    x_api_key: str | None = Header(default=None),
):
    """
    Reklamationsdokument hochladen → 8D-Report.

    **Auth:** `X-API-Key` Header (wenn RECLARADAR_API_KEY gesetzt).
    **Formate:** JSON oder PDF.
    **Antwort:** Vollständiger 8D-Report als JSON.
    """
    _verify_key(x_api_key)

    if not ANTHROPIC_KEY:
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "error": "ANTHROPIC_API_KEY nicht konfiguriert"},
        )

    # Format prüfen
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "error": f"Nicht unterstütztes Format: '{suffix}'. Erlaubt: {', '.join(ALLOWED_EXTENSIONS)}",
            },
        )

    # Datei lesen
    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=400,
            detail={"status": "error", "error": f"Datei zu groß (max {MAX_FILE_BYTES // (1024*1024)} MB)"},
        )
    if not content.strip():
        raise HTTPException(status_code=400, detail={"status": "error", "error": "Datei ist leer"})

    start = time.perf_counter()
    tmp_path: Path | None = None

    try:
        # Temp-Datei mit korrekter Extension anlegen (load_input braucht Suffix)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, dir=tempfile.gettempdir()) as tf:
            tf.write(content)
            tmp_path = Path(tf.name)

        try:
            input_text, input_mode = load_input(str(tmp_path))
        except SystemExit:
            raise HTTPException(
                status_code=400,
                detail={"status": "error", "error": "Datei konnte nicht gelesen werden"},
            )

        user_prompt = build_user_prompt(input_text, input_mode)

        try:
            report = call_claude(SYSTEM_PROMPT, user_prompt)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail={"status": "error", "error": "Claude API Fehler", "detail": str(exc)},
            )

    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    elapsed = round(time.perf_counter() - start, 2)

    # Statistik
    ki_fields = []
    placeholder_fields = []
    if "_parse_error" not in report:
        ki_fields = [k for k, v in report.items() if isinstance(v, dict) and v.get("status") == "KI_GENERIERT"]
        placeholder_fields = [k for k, v in report.items() if isinstance(v, dict) and v.get("status") == "PLATZHALTER"]

    return {
        "status": "success",
        "processing_time_seconds": elapsed,
        "input_mode": input_mode,
        "filename": file.filename,
        "stats": {
            "ki_generiert": len(ki_fields),
            "platzhalter": len(placeholder_fields),
            "ki_felder": ki_fields,
            "platzhalter_felder": placeholder_fields,
        },
        "report": report,
    }


# ---------------------------------------------------------------------------
# Demo UI — GET /
# ---------------------------------------------------------------------------

HTML = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ReclaRadar — 8D-Report Generator</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:       #0f1117;
    --surface:  #1a1d27;
    --border:   #2a2d3a;
    --text:     #e2e8f0;
    --muted:    #64748b;
    --accent:   #6366f1;
    --accent-h: #818cf8;
    --green:    #22c55e;
    --green-bg: #052e16;
    --orange:   #f97316;
    --orange-bg:#431407;
    --red:      #ef4444;
    --radius:   10px;
  }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    min-height: 100vh;
    padding: 2rem 1rem;
  }

  .container { max-width: 860px; margin: 0 auto; }

  /* Header */
  .header { text-align: center; margin-bottom: 2.5rem; }
  .header h1 { font-size: 2rem; font-weight: 700; letter-spacing: -0.02em; }
  .header h1 span { color: var(--accent); }
  .header p { color: var(--muted); margin-top: 0.5rem; font-size: 0.95rem; }

  /* Card */
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.5rem;
    margin-bottom: 1.5rem;
  }
  .card h2 { font-size: 1rem; font-weight: 600; margin-bottom: 1rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }

  /* Upload Zone */
  .upload-zone {
    border: 2px dashed var(--border);
    border-radius: var(--radius);
    padding: 2.5rem 1rem;
    text-align: center;
    cursor: pointer;
    transition: border-color 0.2s, background 0.2s;
    position: relative;
  }
  .upload-zone:hover, .upload-zone.drag-over {
    border-color: var(--accent);
    background: rgba(99,102,241,0.05);
  }
  .upload-zone input[type="file"] {
    position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%;
  }
  .upload-icon { font-size: 2.5rem; margin-bottom: 0.75rem; }
  .upload-zone p { color: var(--muted); font-size: 0.9rem; }
  .upload-zone .file-name { color: var(--accent); font-weight: 600; margin-top: 0.5rem; font-size: 0.95rem; }

  /* Input */
  .field { margin-bottom: 1rem; }
  .field label { display: block; font-size: 0.85rem; color: var(--muted); margin-bottom: 0.4rem; }
  .field input {
    width: 100%; background: var(--bg); border: 1px solid var(--border);
    border-radius: 6px; padding: 0.6rem 0.85rem; color: var(--text);
    font-size: 0.9rem; transition: border-color 0.2s;
  }
  .field input:focus { outline: none; border-color: var(--accent); }
  .field input::placeholder { color: var(--muted); }

  /* Button */
  .btn {
    display: inline-flex; align-items: center; gap: 0.5rem;
    background: var(--accent); color: #fff;
    border: none; border-radius: 8px; padding: 0.75rem 1.75rem;
    font-size: 0.95rem; font-weight: 600; cursor: pointer;
    transition: background 0.2s, transform 0.1s;
    width: 100%;
    justify-content: center;
  }
  .btn:hover:not(:disabled) { background: var(--accent-h); }
  .btn:active:not(:disabled) { transform: scale(0.98); }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }

  /* Spinner */
  .spinner {
    width: 18px; height: 18px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* Status bar */
  .status-bar {
    display: none; align-items: center; gap: 0.75rem;
    padding: 0.85rem 1rem; border-radius: 8px;
    font-size: 0.9rem; margin-top: 1rem;
    background: rgba(99,102,241,0.1); border: 1px solid rgba(99,102,241,0.3);
  }
  .status-bar.visible { display: flex; }
  .status-bar.error { background: rgba(239,68,68,0.1); border-color: rgba(239,68,68,0.3); color: var(--red); }

  /* Report */
  #report-section { display: none; }
  #report-section.visible { display: block; }

  .report-meta {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 0.75rem; margin-bottom: 1.5rem;
  }
  .meta-item { background: var(--bg); border-radius: 8px; padding: 0.75rem 1rem; border: 1px solid var(--border); }
  .meta-item .label { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
  .meta-item .value { font-weight: 600; font-size: 0.95rem; margin-top: 0.25rem; }

  .stats-bar {
    display: flex; gap: 1rem; flex-wrap: wrap;
    padding: 0.75rem 1rem; background: var(--bg); border-radius: 8px;
    border: 1px solid var(--border); margin-bottom: 1.5rem; font-size: 0.85rem;
  }
  .stat-badge {
    display: inline-flex; align-items: center; gap: 0.4rem;
    padding: 0.25rem 0.75rem; border-radius: 20px; font-weight: 600; font-size: 0.8rem;
  }
  .stat-badge.green { background: var(--green-bg); color: var(--green); border: 1px solid rgba(34,197,94,0.3); }
  .stat-badge.orange { background: var(--orange-bg); color: var(--orange); border: 1px solid rgba(249,115,22,0.3); }

  /* Accordion */
  .accordion { display: flex; flex-direction: column; gap: 0.75rem; }

  .d-block {
    border-radius: var(--radius);
    border: 1px solid var(--border);
    overflow: hidden;
    transition: border-color 0.2s;
  }
  .d-block.ki { border-color: rgba(34,197,94,0.3); }
  .d-block.placeholder { border-color: rgba(249,115,22,0.3); }

  .d-header {
    display: flex; align-items: center; gap: 0.75rem;
    padding: 0.9rem 1.1rem; cursor: pointer;
    background: var(--surface);
    user-select: none;
    transition: background 0.15s;
  }
  .d-header:hover { background: #1f2235; }

  .d-badge {
    font-size: 0.7rem; font-weight: 700; padding: 0.2rem 0.55rem;
    border-radius: 20px; text-transform: uppercase; letter-spacing: 0.04em; white-space: nowrap;
  }
  .d-badge.ki { background: var(--green-bg); color: var(--green); border: 1px solid rgba(34,197,94,0.3); }
  .d-badge.placeholder { background: var(--orange-bg); color: var(--orange); border: 1px solid rgba(249,115,22,0.3); }

  .d-num { font-size: 0.8rem; font-weight: 700; color: var(--muted); min-width: 24px; }
  .d-title { font-weight: 600; font-size: 0.95rem; flex: 1; }
  .d-chevron { color: var(--muted); transition: transform 0.2s; font-size: 0.8rem; }
  .d-block.open .d-chevron { transform: rotate(180deg); }

  .d-body {
    display: none; padding: 1rem 1.1rem 1.25rem;
    background: var(--bg); border-top: 1px solid var(--border);
    font-size: 0.875rem; line-height: 1.65;
  }
  .d-block.open .d-body { display: block; }

  .field-row { display: grid; grid-template-columns: 160px 1fr; gap: 0.4rem; margin-bottom: 0.4rem; align-items: start; }
  .field-key { color: var(--muted); font-size: 0.8rem; font-weight: 600; padding-top: 0.15rem; }
  .field-val { color: var(--text); }

  .list-item { display: flex; gap: 0.6rem; margin-bottom: 0.5rem; }
  .list-item .num { color: var(--accent); font-weight: 700; min-width: 20px; }

  .hint-box {
    background: rgba(249,115,22,0.08); border: 1px solid rgba(249,115,22,0.25);
    border-radius: 6px; padding: 0.6rem 0.85rem; margin-top: 0.75rem;
    font-size: 0.82rem; color: var(--orange);
  }
  .hint-box strong { display: block; margin-bottom: 0.2rem; }

  .sub-item {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 7px; padding: 0.75rem 1rem; margin-bottom: 0.6rem;
  }
  .sub-item:last-child { margin-bottom: 0; }
  .sub-item .sub-header { display: flex; gap: 0.6rem; align-items: flex-start; margin-bottom: 0.4rem; }
  .sub-item .sub-num { color: var(--accent); font-weight: 700; font-size: 0.9rem; min-width: 20px; }
  .sub-item .sub-title { font-weight: 600; }
  .sub-item .sub-meta { display: flex; flex-wrap: wrap; gap: 0.5rem 1.5rem; margin-top: 0.4rem; }
  .sub-item .sub-meta span { font-size: 0.78rem; color: var(--muted); }
  .sub-item .sub-meta span strong { color: var(--text); }

  .tag {
    display: inline-block; font-size: 0.7rem; font-weight: 600; padding: 0.15rem 0.5rem;
    border-radius: 20px; vertical-align: middle; margin-left: 0.4rem;
  }
  .tag.offen { background: rgba(99,102,241,0.2); color: var(--accent); }
  .tag.abgeschlossen { background: var(--green-bg); color: var(--green); }
  .tag.laufend { background: rgba(249,115,22,0.15); color: var(--orange); }

  .timing { color: var(--muted); font-size: 0.8rem; text-align: right; margin-top: 0.5rem; }

  @media (max-width: 600px) {
    .field-row { grid-template-columns: 1fr; }
    .field-key { padding-top: 0; }
    .report-meta { grid-template-columns: 1fr 1fr; }
  }
</style>
</head>
<body>
<div class="container">

  <div class="header">
    <h1>Recla<span>Radar</span> 🔍</h1>
    <p>Reklamationsdokument hochladen — 8D-Report automatisch per KI generieren</p>
  </div>

  <!-- Upload Card -->
  <div class="card">
    <h2>Dokument hochladen</h2>

    <div class="upload-zone" id="dropZone">
      <input type="file" id="fileInput" accept=".json,.pdf">
      <div class="upload-icon">📂</div>
      <p>JSON oder PDF hier ablegen oder klicken</p>
      <div class="file-name" id="fileName"></div>
    </div>

    <div class="field" style="margin-top:1rem;">
      <label>API Key (X-API-Key) — optional wenn nicht konfiguriert</label>
      <input type="password" id="apiKey" placeholder="sk-...">
    </div>

    <button class="btn" id="analyzeBtn" disabled>
      <span id="btnIcon">⚡</span>
      <span id="btnText">Analysieren</span>
    </button>

    <div class="status-bar" id="statusBar">
      <div class="spinner" id="statusSpinner"></div>
      <span id="statusText">Reklamation wird analysiert…</span>
    </div>
  </div>

  <!-- Report Section -->
  <div id="report-section">
    <div class="card">
      <h2>8D-Report</h2>

      <div class="report-meta" id="reportMeta"></div>
      <div class="stats-bar" id="statsBar"></div>
      <div class="accordion" id="accordion"></div>

      <div class="timing" id="timing"></div>
    </div>
  </div>

</div>

<script>
const fileInput  = document.getElementById('fileInput');
const dropZone   = document.getElementById('dropZone');
const fileName   = document.getElementById('fileName');
const analyzeBtn = document.getElementById('analyzeBtn');
const btnIcon    = document.getElementById('btnIcon');
const btnText    = document.getElementById('btnText');
const statusBar  = document.getElementById('statusBar');
const statusText = document.getElementById('statusText');
const statusSpinner = document.getElementById('statusSpinner');

let selectedFile = null;

function setFile(f) {
  selectedFile = f;
  fileName.textContent = f ? `📄 ${f.name}` : '';
  analyzeBtn.disabled = !f;
}

fileInput.addEventListener('change', () => setFile(fileInput.files[0] || null));
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f) { fileInput.files = e.dataTransfer.files; setFile(f); }
});

analyzeBtn.addEventListener('click', analyze);

function setLoading(on) {
  analyzeBtn.disabled = on;
  btnIcon.textContent = on ? '' : '⚡';
  btnIcon.innerHTML   = on ? '<div class="spinner"></div>' : '⚡';
  btnText.textContent = on ? 'Wird analysiert…' : 'Analysieren';
  statusBar.className = on ? 'status-bar visible' : 'status-bar';
  statusSpinner.style.display = on ? '' : 'none';
  statusText.textContent = 'Reklamation wird analysiert… (kann 15–30s dauern)';
}

function setError(msg) {
  statusBar.className = 'status-bar visible error';
  statusSpinner.style.display = 'none';
  statusText.textContent = '❌ ' + msg;
  analyzeBtn.disabled = false;
  btnIcon.innerHTML = '⚡';
  btnText.textContent = 'Analysieren';
}

async function analyze() {
  if (!selectedFile) return;
  setLoading(true);
  document.getElementById('report-section').classList.remove('visible');

  const fd = new FormData();
  fd.append('file', selectedFile);

  const apiKey = document.getElementById('apiKey').value.trim();
  const headers = {};
  if (apiKey) headers['X-API-Key'] = apiKey;

  try {
    const res = await fetch('/api/analyze', { method: 'POST', headers, body: fd });
    const data = await res.json();
    if (!res.ok) {
      setError(data.error || data.detail || `HTTP ${res.status}`);
      return;
    }
    renderReport(data);
  } catch (e) {
    setError('Netzwerkfehler: ' + e.message);
  } finally {
    setLoading(false);
  }
}

// ── Render ────────────────────────────────────────────────────────────────

function esc(s) {
  if (s == null) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function renderReport(data) {
  const r = data.report;
  const m = r.report_meta || {};

  // Meta
  const metaEl = document.getElementById('reportMeta');
  metaEl.innerHTML = [
    ['Reklamations-Nr.', m.reklamations_nr],
    ['Erstellt', m.erstelldatum],
    ['Produkt', m.produkt],
    ['Lieferant', m.lieferant],
    ['Kunde', m.kunde],
  ].map(([l,v]) => `
    <div class="meta-item">
      <div class="label">${esc(l)}</div>
      <div class="value">${esc(v) || '—'}</div>
    </div>`).join('');

  // Stats
  const s = data.stats || {};
  document.getElementById('statsBar').innerHTML = `
    <span class="stat-badge green">✅ KI-generiert: ${s.ki_generiert ?? '?'}</span>
    <span class="stat-badge orange">⏳ Platzhalter: ${s.platzhalter ?? '?'}</span>
    <span style="color:var(--muted); font-size:0.8rem; margin-left:auto;">
      Datei: <strong style="color:var(--text)">${esc(data.filename)}</strong>
      &nbsp;|&nbsp; Modus: <strong style="color:var(--text)">${esc(data.input_mode)}</strong>
    </span>`;

  // Accordion
  const acc = document.getElementById('accordion');
  acc.innerHTML = '';

  const dKeys = ['d1_team','d2_problembeschreibung','d3_sofortmassnahmen',
                 'd4_grundursache','d5_abstellmassnahmen','d6_wirksamkeit',
                 'd7_vorbeugung','d8_abschluss'];

  dKeys.forEach((key, idx) => {
    const block = r[key];
    if (!block) return;
    const isKI = block.status === 'KI_GENERIERT';
    const dNum = `D${idx+1}`;

    const el = document.createElement('div');
    el.className = `d-block ${isKI ? 'ki' : 'placeholder'}`;
    el.innerHTML = `
      <div class="d-header">
        <span class="d-num">${dNum}</span>
        <span class="d-title">${esc(block.titel)}</span>
        <span class="d-badge ${isKI ? 'ki' : 'placeholder'}">${isKI ? 'KI-generiert' : 'Platzhalter'}</span>
        <span class="d-chevron">▼</span>
      </div>
      <div class="d-body">${renderBlock(key, block)}</div>`;

    el.querySelector('.d-header').addEventListener('click', () => el.classList.toggle('open'));
    // KI-Felder automatisch aufklappen
    if (isKI) el.classList.add('open');
    acc.appendChild(el);
  });

  // Timing
  document.getElementById('timing').textContent =
    `Verarbeitungszeit: ${data.processing_time_seconds}s`;

  document.getElementById('report-section').classList.add('visible');
  statusBar.className = 'status-bar';
}

function renderBlock(key, b) {
  let html = '';

  // Platzhalter-Hinweis
  if (b.status === 'PLATZHALTER' && b.hinweis) {
    html += `<div class="hint-box"><strong>📋 Was hier eingetragen werden muss:</strong>${esc(b.hinweis)}</div>`;
    if (b.inhalt) html += `<div class="field-row" style="margin-top:0.75rem"><div class="field-key">Vorlage</div><div class="field-val">${esc(b.inhalt)}</div></div>`;
    return html;
  }

  // D2 Problembeschreibung
  if (key === 'd2_problembeschreibung') {
    html += fields(b, ['ist_zustand','soll_zustand','abweichung','betroffene_menge','auswirkung']);
    return html;
  }

  // D3/D5 Maßnahmen-Listen
  if ((key === 'd3_sofortmassnahmen' || key === 'd5_abstellmassnahmen') && b.massnahmen) {
    b.massnahmen.forEach(m => {
      const tag = tagBadge(m.status_vorschlag);
      html += `<div class="sub-item">
        <div class="sub-header">
          <span class="sub-num">${m.nr}.</span>
          <span class="sub-title">${esc(m.massnahme)}${tag}</span>
        </div>
        <div class="sub-meta">
          <span><strong>Verantwortlich:</strong> ${esc(m.verantwortlich)}</span>
          <span><strong>Termin:</strong> ${esc(m.termin)}</span>
          ${m.nachweis ? `<span><strong>Nachweis:</strong> ${esc(m.nachweis)}</span>` : ''}
        </div>
      </div>`;
    });
    return html;
  }

  // D4 Grundursache
  if (key === 'd4_grundursache') {
    html += `<div class="field-row"><div class="field-key">Methode</div><div class="field-val">${esc(b.methode)}</div></div>`;
    if (b.moegliche_ursachen) {
      html += `<div style="margin: 0.75rem 0 0.4rem; font-size:0.8rem; color:var(--muted); font-weight:600; text-transform:uppercase; letter-spacing:0.04em;">Mögliche Ursachen</div>`;
      b.moegliche_ursachen.forEach(u => {
        html += `<div class="sub-item">
          <div class="sub-header">
            <span class="sub-title">📌 ${esc(u.ursache)}</span>
          </div>
          <div class="sub-meta">
            <span><strong>Kategorie:</strong> ${esc(u.kategorie)}</span>
            <span><strong>Bewertung:</strong> ${esc(u.bewertung)}</span>
          </div>
        </div>`;
      });
    }
    html += `<div style="margin-top:0.75rem; padding:0.75rem 1rem; background:rgba(34,197,94,0.08); border:1px solid rgba(34,197,94,0.25); border-radius:6px;">
      <div style="font-size:0.8rem; color:var(--green); font-weight:700; margin-bottom:0.3rem;">✅ Wahrscheinlichste Grundursache</div>
      <div>${esc(b.wahrscheinlichste_grundursache)}</div>
      ${b.begruendung ? `<div style="margin-top:0.4rem; color:var(--muted); font-size:0.85rem;">${esc(b.begruendung)}</div>` : ''}
    </div>`;
    return html;
  }

  // D7 Vorbeugung
  if (key === 'd7_vorbeugung') {
    if (b.massnahmen) {
      b.massnahmen.forEach(m => {
        html += `<div class="sub-item">
          <div class="sub-header">
            <span class="sub-num">${m.nr}.</span>
            <span class="sub-title">${esc(m.massnahme)}</span>
          </div>
          <div class="sub-meta">
            <span><strong>Bezug:</strong> ${esc(m.bezug)}</span>
            <span><strong>Umsetzung:</strong> ${esc(m.umsetzung)}</span>
          </div>
        </div>`;
      });
    }
    if (b.fmea_update) html += `<div class="field-row" style="margin-top:0.75rem"><div class="field-key">FMEA-Update</div><div class="field-val">${esc(b.fmea_update)}</div></div>`;
    if (b.lessons_learned) html += `<div class="field-row"><div class="field-key">Lessons Learned</div><div class="field-val">${esc(b.lessons_learned)}</div></div>`;
    return html;
  }

  // Fallback: alle Felder als key/value
  const skip = ['status','titel'];
  Object.entries(b).forEach(([k, v]) => {
    if (skip.includes(k)) return;
    if (typeof v === 'string') {
      html += `<div class="field-row"><div class="field-key">${esc(k)}</div><div class="field-val">${esc(v)}</div></div>`;
    } else if (Array.isArray(v)) {
      v.forEach((item, i) => {
        html += `<div class="list-item"><span class="num">${i+1}.</span><span>${esc(typeof item === 'string' ? item : JSON.stringify(item))}</span></div>`;
      });
    }
  });
  return html || '<span style="color:var(--muted)">Keine Daten</span>';
}

function fields(b, keys) {
  return keys.filter(k => b[k]).map(k =>
    `<div class="field-row"><div class="field-key">${esc(k.replace(/_/g,' '))}</div><div class="field-val">${esc(b[k])}</div></div>`
  ).join('');
}

function tagBadge(status) {
  if (!status) return '';
  const cls = status.toLowerCase();
  const label = status === 'OFFEN' ? 'Offen' : status === 'ABGESCHLOSSEN' ? 'Erledigt' : 'Laufend';
  return `<span class="tag ${cls}">${label}</span>`;
}
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def ui():
    return HTMLResponse(content=HTML)
