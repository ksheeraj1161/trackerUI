#!/usr/bin/env python3
import csv, os, html, time, unicodedata
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ---- CONFIG ----
CSV_PATH = os.environ.get("TEMPLATES_CSV", "templates.csv")
PORT = int(os.environ.get("PORT", "8000"))
ID_HEADER_CANDIDATES = ("template", "template id", "template_id", "id")

# ---------- helpers ----------
def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = s.replace("\u200b", "").replace("\ufeff", "").strip()
    s = " ".join(s.split())
    return s.casefold()

def file_mtime(path):
    try:
        ts = os.path.getmtime(path)
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
    except Exception:
        return "—"

# ---------- data ----------
def load_csv_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rdr = csv.DictReader(f)
        raw_headers = rdr.fieldnames or []
        header_map = {}
        for h in raw_headers:
            if h is None:
                continue
            n = normalize_text(h)
            if n and n not in header_map:
                header_map[n] = h
        rows = []
        for r in rdr:
            row = {}
            for k, v in r.items():
                if k is None: 
                    continue
                kk = k.strip()
                if kk:
                    row[kk] = v.strip() if isinstance(v, str) else v
            rows.append(row)
        return raw_headers, header_map, rows

def detect_id_key(header_map, raw_headers):
    for cand in ID_HEADER_CANDIDATES:
        if cand in header_map:
            return header_map[cand]
    for h in raw_headers:
        n = normalize_text(h)
        if "template" in n and "id" in n:
            return h
    if raw_headers:
        if "template" in normalize_text(raw_headers[0]):
            return raw_headers[0]
    return None

def find_row_by_id(rows, id_key, q):
    target = normalize_text(q)
    if not target:
        return None
    for r in rows:
        if normalize_text(r.get(id_key, "")) == target:
            return r
    return None

# ---------- UI ----------
def render_value(header, value):
    """Turn linkish fields into a short 'Open' hyperlink; otherwise escape text."""
    def esc(x): return html.escape(str(x) if x is not None else "")
    if value is None:
        return ""
    h = (header or "").lower()
    v = str(value).strip()
    if v and ("link" in h or "url" in h):
        if v.startswith(("http://", "https://")):
            return f'<a href="{esc(v)}" target="_blank" rel="noopener">Open</a>'
        # not a proper URL; just show as text
    return esc(v)

def render_page(headers, row, id_key, error=None, query_val=""):
    def esc(x): return html.escape(str(x) if x is not None else "")
    def nonempty(v): return not (v is None or (isinstance(v, str) and v.strip() == ""))

    data_line = f"{esc(os.path.basename(CSV_PATH))} · updated {esc(file_mtime(CSV_PATH))}"
    id_label = esc(id_key or "Template ID")

    # Build items (label/value) and split into two columns
    left_items, right_items = [], []
    if row:
        cols = [h for h in headers if h and nonempty(row.get(h))]
        # split roughly in half
        mid = (len(cols) + 1) // 2
        for h in cols[:mid]:
            left_items.append((h, render_value(h, row.get(h))))
        for h in cols[mid:]:
            right_items.append((h, render_value(h, row.get(h))))

    # HTML fragments
    def table_html(items):
        if not items:
            return ""
        out = ["<table class='kv'><tbody>"]
        for h, v in items:
            out.append(f"<tr><th>{esc(h)}</th><td>{v}</td></tr>")
        out.append("</tbody></table>")
        return "".join(out)

    err_html = f"<div class='error'>⚠ {esc(error)}</div>" if error else ""

    result_html = ""
    if row:
        result_html = f"""
        <div class="grid">
          <div class="col">{table_html(left_items)}</div>
          <div class="col">{table_html(right_items)}</div>
        </div>
        """
    elif query_val:
        result_html = f"<p class='warn'>No match for <b>{esc(query_val)}</b>.</p>"

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
  .wrap {{ max-width:1100px; margin:2rem auto; padding:0 1rem; }} /* pushed higher */
  .card {{ background:var(--card); border:1px solid var(--border); border-radius:12px;
           padding:1.25rem 1.25rem 1rem; box-shadow:0 1px 2px rgb(0 0 0 / 5%); }}
  h1 {{ margin:0 0 .25rem; font-size:1.9rem; }}
  .sub {{ margin:.25rem 0 1rem; color:var(--muted); }}
  form {{ display:flex; gap:.5rem; flex-wrap:wrap; }}
  input[type=text] {{ flex:1 1 420px; padding:.6rem .7rem; border:1px solid var(--border);
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
  .grid {{ display:grid; grid-template-columns: 1fr 1fr; gap:1rem; margin-top:1rem; }}
  .col {{ min-width:0; }}
  table.kv {{ width:100%; border-collapse:collapse; }}
  table.kv th, table.kv td {{ padding:.55rem .6rem; vertical-align:top; }}
  table.kv th {{ width:35%; background:#f9fafb; border-right:1px solid var(--border); text-align:left; }}
  table.kv tr+tr td, table.kv tr+tr th {{ border-top:1px solid var(--border); }}
  a {{ color:var(--accent); }}
  @media (max-width: 820px) {{
    .grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Template Lookup</h1>
      <div class="sub">Search by <b>{html.escape(id_key or 'Template ID')}</b>.</div>

      <form method="GET" action="/" onsubmit="return !!this.id.value.trim()">
        <input name="id" id="id" type="text" placeholder="Enter Template ID" value="{html.escape(query_val)}" autofocus />
        <button type="submit">Search</button>
        <a class="clear" href="/">Clear</a>
      </form>

      <div class="meta">Data: {html.escape(os.path.basename(CSV_PATH))} · updated {html.escape(file_mtime(CSV_PATH))}</div>

      {err_html}
      {result_html}
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

        try:
            headers, header_map, rows = load_csv_rows(CSV_PATH)
            id_key = detect_id_key(header_map, headers)
            match = find_row_by_id(rows, id_key, query_val) if (id_key and query_val) else None
            page = render_page(headers, match, id_key, None, query_val)
            self._send(200, page)
        except FileNotFoundError:
            page = render_page([], None, None,
                               f"CSV not found at '{CSV_PATH}'. Place it next to app.py or set TEMPLATES_CSV.",
                               query_val)
            self._send(500, page)
        except Exception as e:
            page = render_page([], None, None, str(e), query_val)
            self._send(500, page)

    def log_message(self, *args, **kwargs):
        return  # silence logs

    def _send(self, status, content):
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

if __name__ == "__main__":
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
