#!/usr/bin/env python3
import csv, os, html, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ---- CONFIG ----
CSV_PATH = os.environ.get("TEMPLATES_CSV", "templates.csv")
PORT = int(os.environ.get("PORT", "8000"))
TEMPLATE_ID_HEADER = "Template"   # unique ID col name in your sheet

# ---- DATA ----
def load_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = [h.strip() for h in (reader.fieldnames or [])]
        rows = []
        for r in reader:
            row = {}
            for k, v in r.items():
                k = (k or "").strip()
                if k:
                    row[k] = v.strip() if isinstance(v, str) else v
            rows.append(row)
        return headers, rows

def find_by_id(rows, q):
    q = (q or "").strip()
    for r in rows:
        if r.get(TEMPLATE_ID_HEADER, "").strip() == q:
            return r
    return None

def human_mtime(path):
    try:
        ts = os.path.getmtime(path)
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
    except Exception:
        return "—"

# ---- UI ----
def page_html(headers, row, error_msg=None, query_val=""):
    def esc(x): return html.escape(str(x) if x is not None else "")
    def nonempty(v): return not (v is None or (isinstance(v, str) and v.strip() == ""))

    # build results table (only non-empty fields)
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

    err_html = f"<div class='error'>⚠ {esc(error_msg)}</div>" if error_msg else ""

    data_line = f"{esc(os.path.basename(CSV_PATH))} · updated {esc(human_mtime(CSV_PATH))}"

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
  body {{
    margin:0; font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
    background:var(--bg); color:var(--fg);
  }}
  .wrap {{
    max-width:900px; margin:4rem auto; padding:0 1rem;
  }}
  .card {{
    background:var(--card); border:1px solid var(--border); border-radius:12px;
    padding:1.25rem 1.25rem 1rem;
    box-shadow:0 1px 2px rgb(0 0 0 / 5%);
  }}
  h1 {{ margin:0 0 .25rem 0; font-size:1.9rem; }}
  .sub {{ margin:.25rem 0 1rem; color:var(--muted); }}
  form {{
    display:flex; gap:.5rem; flex-wrap:wrap; margin:.25rem 0 0;
  }}
  input[type=text] {{
    flex:1 1 320px; padding:.6rem .7rem; border:1px solid var(--border);
    border-radius:8px; outline:none;
  }}
  input[type=text]:focus {{ border-color:var(--accent); }}
  button {{
    padding:.6rem .9rem; border:0; border-radius:8px; cursor:pointer;
    background:var(--accent); color:#fff; font-weight:600;
  }}
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
</style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Template Lookup</h1>
      <div class="sub">Search by <b>{esc(TEMPLATE_ID_HEADER)}</b>.</div>

      <form method="GET" action="/" onsubmit="return !!this.id.value.trim()">
        <input name="id" id="id" type="text" placeholder="Enter {esc(TEMPLATE_ID_HEADER)}" value="{esc(query_val)}" autofocus />
        <button type="submit">Search</button>
        <a class="clear" href="/">Clear</a>
      </form>

      <div class="meta">Data: {data_line}</div>

      {err_html}
      {table_html}
    </div>
  </div>
<script>
  // submit on Enter is native; form guard prevents empty searches
</script>
</body>
</html>"""

# ---- HTTP ----
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        query_id = (parse_qs(parsed.query).get("id") or [""])[0]
        try:
            headers, rows = load_rows(CSV_PATH)
            match = find_by_id(rows, query_id) if query_id else None
            page = page_html(headers, match, None, query_id)
            self._send(200, page)
        except FileNotFoundError:
            page = page_html([], None, f"CSV not found at '{CSV_PATH}'. Place it next to app.py or set TEMPLATES_CSV.", query_id)
            self._send(500, page)
        except Exception as e:
            page = page_html([], None, str(e), query_id)
            self._send(500, page)

    def log_message(self, *args, **kwargs):  # silence server logs
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
