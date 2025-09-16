#!/usr/bin/env python3
import csv, os, html, time, unicodedata
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ---- CONFIG ----
CSV_PATH = os.environ.get("TEMPLATES_CSV", "templates.csv")
PORT = int(os.environ.get("PORT", "8000"))

# Any of these will be accepted as the ID column (case/space tolerant)
ID_HEADER_CANDIDATES = ("template", "template id", "template_id", "id")

# ---------- helpers ----------
def normalize_text(s: str) -> str:
    """Trim, collapse whitespace, remove zero-width chars, casefold."""
    if s is None:
        return ""
    # normalize unicode, strip, remove zero-width chars
    s = unicodedata.normalize("NFKC", str(s))
    s = s.replace("\u200b", "").replace("\ufeff", "")
    s = s.strip()
    # collapse internal whitespace to single spaces
    s = " ".join(s.split())
    return s.casefold()

def file_mtime(path):
    try:
        ts = os.path.getmtime(path)
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
    except Exception:
        return "—"

# ---------- data loading ----------
def load_csv_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rdr = csv.DictReader(f)
        raw_headers = rdr.fieldnames or []
        # map normalized -> original
        header_map = {}
        for h in raw_headers:
            if h is None: 
                continue
            norm = normalize_text(h)
            if norm and norm not in header_map:
                header_map[norm] = h

        rows = []
        for r in rdr:
            row = {}
            for k, v in r.items():
                if k is None:
                    continue
                kk = k.strip()
                if kk:
                    # keep original header; trim values
                    vv = v.strip() if isinstance(v, str) else v
                    row[kk] = vv
            rows.append(row)
        return raw_headers, header_map, rows

def detect_id_key(header_map, raw_headers):
    # prefer explicit candidates
    for cand in ID_HEADER_CANDIDATES:
        if cand in header_map:
            return header_map[cand]
    # fallback: something that contains 'template' and 'id'
    for h in raw_headers:
        n = normalize_text(h)
        if "template" in n and "id" in n:
            return h
    # fallback: if first column looks like "template"
    if raw_headers:
        n0 = normalize_text(raw_headers[0])
        if "template" in n0:
            return raw_headers[0]
    return None

def find_row_by_id(rows, id_key, query):
    q = normalize_text(query)
    if not q:
        return None
    for r in rows:
        val = normalize_text(r.get(id_key, ""))
        if val == q:
            return r
    return None

# ---------- UI ----------
def render_page(headers, row, id_key, error=None, query_val="", debug_info=None):
    def esc(x): return html.escape(str(x) if x is not None else "")
    def nonempty(v): return not (v is None or (isinstance(v, str) and v.strip() == ""))

    data_line = f"{esc(os.path.basename(CSV_PATH))} · updated {esc(file_mtime(CSV_PATH))}"
    id_label = esc(id_key or "—")

    table_html = ""
    if row:
        cols = [h for h in headers if h and nonempty(row.get(h))]
        if cols:
            table_html = "<table><tbody>"
            for h in cols:
                table_html += f"<tr><th>{esc(h)}</th><td>{esc(row.get(h,''))}</td></tr>"
            table_html += "</tbody></table>"
        else:
            table_html = "<p class='muted'>No non-empty fields for this Template.</p>"
    elif query_val:
        table_html = f"<p class='warn'>No match for <b>{esc(query_val)}</b>.</p>"

    err_html = f"<div class='error'>⚠ {esc(error)}</div>" if error else ""
    dbg_html = ""
    if debug_info:
        dbg_html = "<div class='debug'><h3>Debug</h3><pre>" + esc(debug_info) + "</pre></div>"

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>Template Lookup</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>
  :root {{
    --bg:#f7f7f9; --fg:#111; --muted:#6b7280; --card:#fff; --border:#e5e7eb;
    --accent:#2563eb; --accent-2:#1e40af; --warn:#b45309; --err:#b91c1c;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
         background:var(--bg); color:var(--fg); }}
  .wrap {{ max-width:900px; margin:4rem auto; padding:0 1rem; }}
  .card {{ background:var(--card); border:1px solid var(--border); border-radius:12px;
           padding:1.25rem 1.25rem 1rem; box-shadow:0 1px 2px rgb(0 0 0 / 5%); }}
  h1 {{ margin:0 0 .25rem; font-size:1.9rem; }}
  .sub {{ margin:.25rem 0 1rem; color:var(--muted); }}
  form {{ display:flex; gap:.5rem; flex-wrap:wrap; }}
  input[type=text] {{ flex:1 1 320px; padding:.6rem .7rem; border:1px solid var(--border);
                      border-radius:8px; outline:none; }}
  input[type=text]:focus {{ border-color:var(--accent); }}
  button {{ padding:.6rem .9rem; border:0; border-radius:8px; cursor:pointer;
            background:var(--accent); color:#fff; font-weight:600; }}
  button:hover {{ background:var(--accent-2); }}
  a.clear {{ align-self:center; color:var(--accent); text-decoration:none; }}
  a.clear:hover {{ text-decoration:underline; }}
  .meta {{ margin:.6rem 0 0; font-size:.9rem; color:var(--muted); }}
  .error {{ margin:.75rem 0 0; padding:.6rem .8rem; border:1px solid #fecaca;
           background:#fef2f2; color:var(--err); border-radius:8px; }}
  .warn {{ color:var(--warn); margin:.75rem 0 0; }}
  table {{ width:100%; border-collapse:collapse; margin:1rem 0 0; }}
  th, td {{ padding:.6rem .7rem; vertical-align:top; }}
  th {{ width:28%; background:#f9fafb; border-right:1px solid var(--border); text-align:left; }}
  tr+tr td, tr+tr th {{ border-top:1px solid var(--border); }}
  .debug {{ margin-top:1rem; font-size:.9rem; background:#f9fafb; border:1px dashed var(--border);
           border-radius:8px; padding:.8rem; color:#111; }}
</style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Template Lookup</h1>
      <div class="sub">Search by <b>{esc(id_key or 'Template')}</b>.</div>

      <form method="GET" action="/" onsubmit="return !!this.id.value.trim()">
        <input name="id" id="id" type="text" placeholder="Enter Template ID" value="{esc(query_val)}" autofocus />
        <button type="submit">Search</button>
        <a class="clear" href="/">Clear</a>
      </form>

      <div class="meta">Data: {data_line} · ID column detected: <b>{id_label}</b></div>

      {err_html}
      {table_html}
      {dbg_html}
    </div>
  </div>
</body>
</html>"""

# ---------- server ----------
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        query_val = (qs.get("id") or [""])[0]
        debug = "debug" in qs  # any value triggers debug

        try:
            headers, header_map, rows = load_csv_rows(CSV_PATH)
            id_key = detect_id_key(header_map, headers)
            match = find_row_by_id(rows, id_key, query_val) if (id_key and query_val) else None

            dbg = None
            if debug:
                sample_ids = []
                if id_key:
                    for r in rows[:10]:
                        sample_ids.append(str(r.get(id_key, ""))[:60])
                dbg = (
                    "Raw headers:\n  - " + "\n  - ".join(headers) +
                    f"\n\nDetected ID key: {id_key}\n\nFirst IDs:\n  - " + "\n  - ".join(sample_ids or ["<none>"])
                )

            page = render_page(headers, match, id_key, None, query_val, dbg)
            self._send(200, page)
        except FileNotFoundError:
            page = render_page([], None, None,
                               f"CSV not found at '{CSV_PATH}'. Place it next to app.py or set TEMPLATES_CSV.",
                               query_val, None)
            self._send(500, page)
        except Exception as e:
            page = render_page([], None, None, str(e), query_val, None)
            self._send(500, page)

    def log_message(self, *args, **kwargs):  # silence logs
        return

    def _send(self, status, content):
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

if __name__ == "__main__":
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
