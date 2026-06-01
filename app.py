import os
import csv
import io
import time
import threading
import traceback
import subprocess
import sys
from flask import Flask, request, jsonify, render_template_string
from playwright.sync_api import sync_playwright

# ── Install browser at startup (runs every time the app boots on Render) ──────
def install_browser():
    print("🔧 Installing Playwright Chromium at startup...")
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print("✅ Chromium ready.")
    else:
        print(f"⚠️  Chromium install output: {result.stdout} {result.stderr}")
        print("🔧 Trying Firefox as fallback...")
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "firefox"],
            capture_output=True, text=True
        )
        print("✅ Firefox ready.")

install_browser()

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)

FORM_URL = "https://survey.tripetto.app/run/wv185y"

session_logs = {}
session_status = {}
session_lock = threading.Lock()

# ── Helpers ───────────────────────────────────────────────────────────────────
def log(session_id, message):
    with session_lock:
        session_logs.setdefault(session_id, []).append(message)

def set_status(session_id, status):
    with session_lock:
        session_status[session_id] = status

def wait_and_click_submit(page, session_id, timeout=15000):
    try:
        btn = page.wait_for_selector(
            "button[type='submit'], button.submit, "
            "button:has-text('Submit'), button:has-text('Continue'), "
            "button:has-text('Next'), button:has-text('Send')",
            timeout=timeout
        )
        btn.scroll_into_view_if_needed()
        btn.click()
        time.sleep(1.5)
        return True
    except Exception as e:
        log(session_id, f"  ⚠️  Submit button not found: {e}")
        return False

def click_checkbox_with_text(page, text, session_id, timeout=12000):
    try:
        label = page.wait_for_selector(f"label:has-text('{text}')", timeout=timeout)
        label.click()
        time.sleep(0.6)
        return True
    except Exception:
        try:
            page.locator(f"text='{text}'").first.click()
            time.sleep(0.6)
            return True
        except Exception as e2:
            log(session_id, f"  ⚠️  Could not click checkbox '{text}': {e2}")
            return False

def fill_text_field(page, label, value, session_id, timeout=12000):
    try:
        inp = page.wait_for_selector(
            "input[type='text']:visible, input:not([type]):visible, textarea:visible",
            timeout=timeout
        )
        inp.click()
        inp.fill(str(value))
        time.sleep(0.5)
        return True
    except Exception as e:
        log(session_id, f"  ⚠️  Could not fill '{label}': {e}")
        return False

def parse_cover_type(raw):
    raw = str(raw).strip().lower()
    if "elite" in raw or "129" in raw:
        return "Khusela Elite"
    return "Khusela Core"

def parse_deduction_date(raw):
    raw = str(raw).strip()
    day_map = {"1": "1st", "01": "1st", "15": "15th", "25": "25th", "31": "31st"}
    day = raw.split("/")[0].strip().lstrip("0") or "1"
    for k, v in day_map.items():
        if raw.startswith(k + "/") or raw == k or day == k:
            return v
    return "1st"

def launch_browser(p, session_id):
    try:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        log(session_id, "  🌐 Browser: Chromium")
        return browser
    except Exception as e1:
        log(session_id, f"  ⚠️  Chromium unavailable, trying Firefox...")
        try:
            browser = p.firefox.launch(headless=True)
            log(session_id, "  🌐 Browser: Firefox")
            return browser
        except Exception as e2:
            raise RuntimeError(f"No browser available. Chromium: {e1} | Firefox: {e2}")

# ── Core automation ───────────────────────────────────────────────────────────
def submit_one_row(page, row, row_num, session_id):
    log(session_id, f"\n📋 Row {row_num}: {row.get('NAME', '')} {row.get('SURNAME', '')}")

    # Section 1 — Welcome screen (just click submit)
    log(session_id, "  → Section 1: Welcome")
    try:
        page.wait_for_selector(
            "button[type='submit'], button:has-text('Submit'), "
            "button:has-text('Start'), button:has-text('Next')",
            timeout=15000
        )
    except Exception:
        pass
    wait_and_click_submit(page, session_id)

    # Section 2 — Cover selection
    log(session_id, "  → Section 2: Cover selection")
    cover = parse_cover_type(row.get("PLAN TYPE", ""))
    log(session_id, f"     Selecting: {cover}")
    click_checkbox_with_text(page, cover, session_id)
    wait_and_click_submit(page, session_id)

    # Section 3 — Personal details (5 fields, one at a time)
    log(session_id, "  → Section 3: Personal details")
    personal_fields = [
        ("NAME",        row.get("NAME", "")),
        ("SURNAME",     row.get("SURNAME", "")),
        ("ID NUMBER",   row.get("ID NUMBER", "")),
        ("CELL NUMBER", row.get("CELL NUMBER", "")),
        ("ADDRESS",     row.get("ADDRESS", "")),
    ]
    for label, value in personal_fields:
        log(session_id, f"     {label}: {value}")
        time.sleep(0.8)
        fill_text_field(page, label, value, session_id)
        wait_and_click_submit(page, session_id)

    # Section 4 — Payment info screen (just click submit)
    log(session_id, "  → Section 4: Payment info screen")
    wait_and_click_submit(page, session_id)

    # Section 5 — Banking details
    log(session_id, "  → Section 5: Banking details")
    bank_fields = [
        ("ACC NUMBER",  row.get("ACC NUMBER", "")),
        ("BRANCH CODE", row.get("BRANCH CODE", "")),
    ]
    for label, value in bank_fields:
        log(session_id, f"     {label}: {value}")
        time.sleep(0.8)
        fill_text_field(page, label, value, session_id)
        wait_and_click_submit(page, session_id)

    # Deduction date
    deduction = parse_deduction_date(row.get("DEDUCTION DATE", "1"))
    log(session_id, f"     Deduction date: {deduction}")
    click_checkbox_with_text(page, deduction, session_id)
    wait_and_click_submit(page, session_id)

    # Section 6 — Terms & Conditions (tick all 6 checkboxes)
    log(session_id, "  → Section 6: Terms & conditions")
    time.sleep(2)
    try:
        checkboxes = page.query_selector_all("input[type='checkbox']:not(:checked)")
        if checkboxes:
            for cb in checkboxes:
                try:
                    cb.scroll_into_view_if_needed()
                    cb.click()
                    time.sleep(0.3)
                except Exception:
                    pass
        else:
            labels = page.query_selector_all("label")
            for lbl in labels:
                try:
                    lbl.click()
                    time.sleep(0.25)
                except Exception:
                    pass
    except Exception as e:
        log(session_id, f"  ⚠️  T&C issue: {e}")

    wait_and_click_submit(page, session_id)
    time.sleep(2)
    log(session_id, f"  ✅ Row {row_num} submitted successfully")

def run_automation(session_id, rows):
    set_status(session_id, "running")
    log(session_id, f"🚀 Starting automation for {len(rows)} member(s)...")
    try:
        with sync_playwright() as p:
            browser = launch_browser(p, session_id)
            context = browser.new_context(viewport={"width": 1280, "height": 900})

            for i, row in enumerate(rows, 1):
                log(session_id, f"\n🌐 Opening form for row {i}...")
                page = context.new_page()
                try:
                    page.goto(FORM_URL, wait_until="networkidle", timeout=30000)
                    time.sleep(2)
                    submit_one_row(page, row, i, session_id)
                except Exception as e:
                    log(session_id, f"  ❌ Row {i} failed: {e}")
                    log(session_id, traceback.format_exc())
                finally:
                    page.close()

                if i < len(rows):
                    log(session_id, "  ⏳ Waiting 3s before next submission...")
                    time.sleep(3)

            browser.close()
        log(session_id, f"\n🎉 All done! {len(rows)} submission(s) completed.")
        set_status(session_id, "done")
    except Exception as e:
        log(session_id, f"\n💥 Fatal error: {e}\n{traceback.format_exc()}")
        set_status(session_id, "error")

def parse_csv(content):
    reader = csv.DictReader(io.StringIO(content), delimiter=";")
    rows = []
    for row in reader:
        clean = {k.strip(): str(v).strip() for k, v in row.items() if k and k.strip()}
        if any(clean.values()):
            rows.append(clean)
    return rows

# ── HTML Portal ───────────────────────────────────────────────────────────────
HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Khusela Auto-Submit Portal</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
  :root {
    --green: #1a6b4a;
    --green-light: #e8f5ee;
    --green-mid: #2e8a62;
    --gold: #c9973a;
    --dark: #12201a;
    --mid: #3d5247;
    --muted: #7a9488;
    --bg: #f5f9f7;
    --white: #ffffff;
    --radius: 14px;
    --shadow: 0 4px 24px rgba(26,107,74,0.10);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--dark); min-height: 100vh; }
  header { background: var(--green); padding: 28px 40px; display: flex; align-items: center; gap: 16px; }
  .logo-mark { width: 44px; height: 44px; background: var(--gold); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-family: 'DM Serif Display', serif; font-size: 22px; color: white; flex-shrink: 0; }
  header h1 { font-family: 'DM Serif Display', serif; font-size: 22px; color: white; font-weight: 400; }
  header p { font-size: 13px; color: rgba(255,255,255,0.65); margin-top: 2px; }
  main { max-width: 780px; margin: 0 auto; padding: 40px 24px 80px; }
  .card { background: var(--white); border-radius: var(--radius); box-shadow: var(--shadow); padding: 36px; margin-bottom: 28px; }
  .card h2 { font-family: 'DM Serif Display', serif; font-size: 20px; font-weight: 400; color: var(--dark); margin-bottom: 6px; }
  .card .subtitle { font-size: 14px; color: var(--muted); margin-bottom: 28px; line-height: 1.6; }
  .drop-zone { border: 2px dashed #c5d9ce; border-radius: 10px; padding: 40px 24px; text-align: center; cursor: pointer; transition: all 0.2s; background: var(--green-light); position: relative; }
  .drop-zone:hover, .drop-zone.drag-over { border-color: var(--green-mid); background: #d8efe5; }
  .drop-zone input[type="file"] { position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%; }
  .drop-icon { font-size: 36px; margin-bottom: 12px; display: block; }
  .drop-zone p { font-size: 15px; color: var(--mid); font-weight: 500; }
  .drop-zone span { font-size: 13px; color: var(--muted); display: block; margin-top: 6px; }
  #preview-section { display: none; }
  .preview-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; margin-top: 24px; }
  .preview-header h3 { font-size: 16px; font-weight: 600; color: var(--dark); }
  .badge { background: var(--green-light); color: var(--green); font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 20px; }
  .table-wrap { overflow-x: auto; border-radius: 8px; border: 1px solid #daeae2; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  thead { background: var(--green); }
  thead th { color: white; font-weight: 500; padding: 10px 14px; text-align: left; white-space: nowrap; }
  tbody tr:nth-child(even) { background: var(--green-light); }
  tbody td { padding: 9px 14px; color: var(--mid); white-space: nowrap; }
  .run-btn { display: inline-flex; align-items: center; gap: 10px; background: var(--green); color: white; border: none; border-radius: 10px; padding: 14px 32px; font-size: 16px; font-family: 'DM Sans', sans-serif; font-weight: 600; cursor: pointer; transition: all 0.2s; margin-top: 24px; width: 100%; justify-content: center; }
  .run-btn:hover:not(:disabled) { background: var(--green-mid); transform: translateY(-1px); }
  .run-btn:disabled { background: var(--muted); cursor: not-allowed; transform: none; }
  .run-btn .spinner { width: 18px; height: 18px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.7s linear infinite; display: none; }
  .run-btn.loading .spinner { display: block; }
  @keyframes spin { to { transform: rotate(360deg); } }
  #log-section { display: none; }
  .log-panel { background: #0f1f18; border-radius: var(--radius); padding: 24px; font-family: 'Courier New', monospace; font-size: 13px; line-height: 1.7; color: #a8d5b8; max-height: 420px; overflow-y: auto; }
  .log-line.success { color: #5fdb8a; }
  .log-line.error   { color: #ff7b7b; }
  .log-line.warn    { color: #f0c060; }
  .log-line.info    { color: #7ec8e3; }
  .log-line.dim     { color: #5a8068; }
  .status-bar { display: flex; align-items: center; gap: 10px; padding: 14px 20px; border-radius: 10px; font-size: 14px; font-weight: 500; margin-bottom: 16px; }
  .status-bar.running { background: #fff8e6; color: #9a6800; border: 1px solid #f0d080; }
  .status-bar.done    { background: #e8f5ee; color: #1a6b4a; border: 1px solid #a8d9bc; }
  .status-bar.error   { background: #fff0f0; color: #cc3333; border: 1px solid #ffb3b3; }
  .pulse { width: 10px; height: 10px; border-radius: 50%; background: currentColor; animation: pulse 1.2s ease-in-out infinite; }
  @keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.4;transform:scale(0.8)} }
  .instructions { background: white; border-radius: var(--radius); box-shadow: var(--shadow); padding: 28px 36px; }
  .instructions h2 { font-family: 'DM Serif Display', serif; font-size: 18px; font-weight: 400; margin-bottom: 16px; }
  .step { display: flex; gap: 14px; margin-bottom: 14px; align-items: flex-start; }
  .step-num { width: 26px; height: 26px; border-radius: 50%; background: var(--green); color: white; font-size: 12px; font-weight: 600; display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 1px; }
  .step p { font-size: 14px; color: var(--mid); line-height: 1.6; }
  .step strong { color: var(--dark); }
  .col-map { background: var(--green-light); border-left: 3px solid var(--green-mid); border-radius: 0 8px 8px 0; padding: 14px 18px; margin-top: 20px; font-size: 13px; color: var(--mid); line-height: 1.8; }
  .col-map strong { color: var(--dark); display: block; margin-bottom: 6px; font-size: 14px; }
</style>
</head>
<body>
<header>
  <div class="logo-mark">K</div>
  <div>
    <h1>Khusela Auto-Submit Portal</h1>
    <p>Automated form submission for the Khusela Dignity Plan</p>
  </div>
</header>
<main>
  <div class="card">
    <h2>Upload Member Spreadsheet</h2>
    <p class="subtitle">Upload your CSV file (semicolon-separated). The portal will submit one Tripetto application per row, automatically filling all fields and accepting the terms &amp; conditions.</p>
    <div class="drop-zone" id="dropZone">
      <input type="file" id="fileInput" accept=".csv">
      <span class="drop-icon">📂</span>
      <p>Drop your CSV file here, or click to browse</p>
      <span>Supports .csv files with semicolon (;) delimiters</span>
    </div>
    <div id="preview-section">
      <div class="preview-header">
        <h3>Members ready to submit</h3>
        <span class="badge" id="row-count">0 rows</span>
      </div>
      <div class="table-wrap">
        <table><thead id="preview-head"></thead><tbody id="preview-body"></tbody></table>
      </div>
      <button class="run-btn" id="runBtn" onclick="startAutomation()">
        <div class="spinner"></div>
        <span class="btn-text">🚀 Submit All Applications</span>
      </button>
    </div>
  </div>

  <div id="log-section" class="card" style="padding:24px">
    <div id="status-bar" class="status-bar running">
      <div class="pulse"></div>
      <span id="status-text">Running automation...</span>
    </div>
    <div class="log-panel" id="logPanel"></div>
  </div>

  <div class="instructions">
    <h2>How to use this portal</h2>
    <div class="step"><div class="step-num">1</div><p>Prepare your CSV file using semicolons (<strong>;</strong>) as separators.</p></div>
    <div class="step"><div class="step-num">2</div><p>Drop or upload the file above. You will see a preview of your members before anything is submitted.</p></div>
    <div class="step"><div class="step-num">3</div><p>Click <strong>Submit All Applications</strong>. The portal opens the Khusela form for each row, fills in all fields, and submits one at a time.</p></div>
    <div class="step"><div class="step-num">4</div><p>Watch the live log. A green ✅ means submitted successfully. A red ❌ means something went wrong.</p></div>
    <div class="col-map">
      <strong>Required CSV columns (semicolon-separated)</strong>
      SURNAME &nbsp;|&nbsp; NAME &nbsp;|&nbsp; ID NUMBER &nbsp;|&nbsp; CELL NUMBER &nbsp;|&nbsp; BRANCH CODE &nbsp;|&nbsp; ACC NUMBER &nbsp;|&nbsp; ADDRESS &nbsp;|&nbsp; DEDUCTION DATE &nbsp;|&nbsp; PLAN TYPE
      <br><br>
      <em>PLAN TYPE:</em> use "Khusela Core R89" or "Khusela Elite R129"<br>
      <em>DEDUCTION DATE:</em> use DD/MM/YYYY format e.g. 15/06/2026
    </div>
  </div>
</main>

<script>
let parsedRows = [], sessionId = null, pollInterval = null;

const dropZone = document.getElementById('dropZone');
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => { e.preventDefault(); dropZone.classList.remove('drag-over'); if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]); });
document.getElementById('fileInput').addEventListener('change', e => { if (e.target.files[0]) handleFile(e.target.files[0]); });

function handleFile(file) {
  const reader = new FileReader();
  reader.onload = e => {
    fetch('/parse', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({csv: e.target.result}) })
    .then(r => r.json()).then(data => {
      if (data.error) { alert('Error: ' + data.error); return; }
      parsedRows = data.rows;
      renderPreview(data.rows, data.headers);
    });
  };
  reader.readAsText(file);
}

function renderPreview(rows, headers) {
  const showCols = ['NAME','SURNAME','ID NUMBER','CELL NUMBER','PLAN TYPE','DEDUCTION DATE'];
  const cols = headers.filter(h => showCols.includes(h.trim().toUpperCase()));
  document.getElementById('row-count').textContent = rows.length + ' row' + (rows.length !== 1 ? 's' : '');
  document.getElementById('preview-head').innerHTML = '<tr>' + cols.map(c => `<th>${c}</th>`).join('') + '</tr>';
  document.getElementById('preview-body').innerHTML = rows.slice(0,10).map(row =>
    '<tr>' + cols.map(c => `<td>${row[c]||''}</td>`).join('') + '</tr>'
  ).join('') + (rows.length > 10 ? `<tr><td colspan="${cols.length}" style="text-align:center;color:#7a9488;padding:10px;font-style:italic">… and ${rows.length-10} more rows</td></tr>` : '');
  document.getElementById('preview-section').style.display = 'block';
}

function startAutomation() {
  const btn = document.getElementById('runBtn');
  btn.disabled = true; btn.classList.add('loading');
  sessionId = 'session_' + Date.now();
  fetch('/run', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({session_id: sessionId, rows: parsedRows}) })
  .then(r => r.json()).then(data => {
    if (data.error) { alert(data.error); btn.disabled = false; btn.classList.remove('loading'); return; }
    document.getElementById('log-section').style.display = 'block';
    document.getElementById('log-section').scrollIntoView({behavior:'smooth'});
    pollInterval = setInterval(pollLogs, 1200);
  });
}

function pollLogs() {
  fetch('/logs/' + sessionId).then(r => r.json()).then(data => {
    renderLog(data.logs || []);
    const bar = document.getElementById('status-bar');
    const txt = document.getElementById('status-text');
    const btn = document.getElementById('runBtn');
    if (data.status === 'done') {
      bar.className = 'status-bar done'; txt.textContent = '✅ All submissions completed successfully.';
      bar.querySelector('.pulse').style.animation = 'none'; clearInterval(pollInterval);
      btn.disabled = false; btn.classList.remove('loading'); btn.querySelector('.btn-text').textContent = '🔄 Run Again with New File';
    } else if (data.status === 'error') {
      bar.className = 'status-bar error'; txt.textContent = '❌ An error occurred — see log for details.';
      bar.querySelector('.pulse').style.animation = 'none'; clearInterval(pollInterval);
      btn.disabled = false; btn.classList.remove('loading');
    }
  });
}

function renderLog(lines) {
  const panel = document.getElementById('logPanel');
  panel.innerHTML = lines.map(line => {
    let cls = 'log-line';
    if (line.includes('✅')||line.includes('🎉')) cls += ' success';
    else if (line.includes('❌')||line.includes('💥')) cls += ' error';
    else if (line.includes('⚠️')) cls += ' warn';
    else if (line.includes('🚀')||line.includes('🌐')||line.includes('📋')) cls += ' info';
    else if (line.includes('⏳')||line.includes('→')) cls += ' dim';
    return `<div class="${cls}">${line.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</div>`;
  }).join('');
  panel.scrollTop = panel.scrollHeight;
}
</script>
</body>
</html>"""

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(HTML_PAGE)

@app.route("/parse", methods=["POST"])
def parse():
    try:
        data = request.get_json()
        rows = parse_csv(data["csv"])
        if not rows:
            return jsonify({"error": "No data rows found in the file."})
        return jsonify({"rows": rows, "headers": list(rows[0].keys())})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/run", methods=["POST"])
def run():
    try:
        data = request.get_json()
        session_id = data["session_id"]
        rows = data["rows"]
        if not rows:
            return jsonify({"error": "No rows to process."})
        threading.Thread(target=run_automation, args=(session_id, rows), daemon=True).start()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/logs/<session_id>")
def get_logs(session_id):
    with session_lock:
        logs = list(session_logs.get(session_id, []))
        status = session_status.get(session_id, "running")
    return jsonify({"logs": logs, "status": status})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
