#!/usr/bin/env python3
import csv, os, html, time, unicodedata
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

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
            if h is None: continue
            n = normalize_text(h)
            if n and n not in header_map:
                header_map[n] = h
        rows = []
        for r in rdr:
            row = {}
            for k, v in r.items():
                if k is None: continue
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
    if raw_headers and "template" in normalize_text(raw_headers[0]):
        return raw_headers[0]
    return None

def find_row_by_id(rows, id_key, q):
    target = normalize_text(q)
    if not target: return None
    for r in rows:
        if normalize_text(r.get(id_key, "")) == target:
            return r
    return None

# ---------- UI ----------
def render_value(header, value):
    def esc(x): return html.escape(str(x) if x is not None else "")
    if value is None: return ""
    h = (header or "").lower()
    v = str(value).strip()
    if v and ("link" in h or "url" in h):
        if v.startswith(("http://", "https://")):
            return f'<a class="btn-link" href="{esc(v)}" target="_blank" rel="noopener">Open</a>'
    return esc(v)

def table_html(headers, row):
    def esc(x): return html.escape(str(x) if x is not None else "")
    if not row: return ""
    out = ["<table class='kv'><tbody>"]
    for h in headers:
        val = row.get(h, "")
        if val.strip():
            out.append(f"<tr><th>{esc(h)}</th><td>{render_value(h,val)}</td></tr>")
    out.append("</tbody></table>")
    return "".join(out)

def render_page(headers, row, id_key, error=None, query_val=""):
    def esc(x): return html.escape(str(x) if x is not None else "")
    data_line = f"{esc(os.path.basename(CSV_PATH))} · updated {esc(file_mtime(CSV_PATH))}"
    id_label = esc(id_key or "Template ID")

    result_html = ""
    if row:
        # Split at OUT_CHN
        if "OUT_CHN" in headers:
            split_index = headers.index("OUT_CHN")+1
        else:
            split_index = len(headers)//2
        left_headers = headers[:split_index]
        right_headers = headers[split_index:]

        left_html = table_html(left_headers, row)
        right_html = table_html(right_headers, row)

        result_html = f"""
        <div class="accordion">
          <button class="accordion-btn">Details</button>
          <div class="panel">{left_html}</div>
          <button class="accordion-btn">Doc Details</button>
          <div class="panel">{right_html}</div>
        </div>
        """
    elif query_val:
        result_html = f"<p class='warn'>No match for <b>{esc(query_val)}</b>.</p>"

    err_html = f"<div class='error'>⚠ {esc(error)}</div>" if error else ""

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>Template Lookup</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>
  :root {{
    --brand:#00AEEF; --brand-dark:#008EC2;
    --bg:#F6FAFD; --card:#fff; --fg:#0f172a;
    --muted:#667085; --border:#E5EAF0; --row:#F8FAFC;
  }}
  body {{ margin:0; font-family:system-ui,Segoe UI,Arial,sans-serif; background:var(--bg); color:var(--fg); }}
  .band {{ height:8px; background:linear-gradient(90deg,var(--brand),#69D2F1 60%,var(--brand)); }}
  .wrap {{ max-width:1100px; margin:1.2rem auto 2rem; padding:0 16px; }}
  .card {{ background:var(--card); border:1px solid var(--border); border-radius:14px; padding:1.1rem 1.1rem .9rem; box-shadow:0 6px 20px rgba(0,0,0,.05); }}
  h1 {{ margin:.2rem 0 .15rem; font-size:2rem; }}
  .sub {{ margin:.15rem 0 .9rem; color:var(--muted); }}
  form {{ display:flex; gap:.6rem; flex-wrap:wrap; }}
  input[type=text] {{ flex:1 1 520px; padding:.7rem .8rem; border:1px solid var(--border); border-radius:10px; }}
  button {{ padding:.7rem 1rem; border:0; border-radius:10px; cursor:pointer; background:var(--brand); color:#fff; font-weight:600; }}
  button:hover {{ background:var(--brand-dark); }}
  a.clear {{ align-self:center; color:var(--brand); text-decoration:none; font-weight:500; }}
  .meta {{ margin:.55rem 0 0; font-size:.9rem; color:var(--muted); }}
  table.kv {{ width:100%; border-collapse:collapse; }}
  table.kv th, table.kv td {{ padding:.55rem .65rem; vertical-align:top; line-height:1.3rem; }}
  table.kv th {{ width:35%; background:var(--row); border-right:1px solid var(--border); text-align:left; font-weight:600; color:#0b2942; }}
  table.kv tr+tr td, table.kv tr+tr th {{ border-top:1px solid var(--border); }}
  .btn-link {{ color:var(--brand); font-weight:600; text-decoration:none; }}
  .btn-link:hover {{ text-decoration:underline; }}
  .accordion-btn {{
    background-color:var(--brand); color:white; cursor:pointer; padding:12px 16px; width:100%;
    border:none; text-align:left; outline:none; font-size:1.05rem; font-weight:600; border-radius:8px; margin-top:1rem;
  }}
  .accordion-btn:hover {{ background-color:var(--brand-dark); }}
  .panel {{ display:none; padding:12px 0; }}
  .warn {{ color:#b45309; margin:.9rem 0 0; }}
  .error {{ color:#b91c1c; margin:.9rem 0 0; }}
</style>
</head>
<body>
  <div class="band"></div>
  <div class="wrap">
    <div class="card">
      <h1>Template Lookup</h1>
      <div class="sub">Search by <b>{id_label}</b>.</div>
      <form method="GET" action="/" onsubmit="return !!this.id.value.trim()">
        <input name="id" id="id" type="text" placeholder="Enter Template ID" value="{esc(query_val)}" autofocus />
        <button type="submit">Search</button>
        <a class="clear" href="/">Clear</a>
      </form>
      <div class="meta">Data: {esc(os.path.basename(CSV_PATH))} · updated {esc(file_mtime(CSV_PATH))}</div>
      {err_html}
      {result_html}
    </div>
  </div>
<script>
  var acc=document.getElementsByClassName("accordion-btn");
  for (var i=0;i<acc.length;i++) {{
    acc[i].addEventListener("click", function(){{
      this.classList.toggle("active");
      var panel=this.nextElementSibling;
      if(panel.style.display==="block"){{ panel.style.display="none"; }}
      else{{ panel.style.display="block"; }}
    }});
  }}
</script>
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
        except Exception as e:
            page = render_page([], None, None, str(e), query_val)
            self._send(500, page)

    def log_message(self, *a, **kw): return
    def _send(self, status, content):
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        self.wfile.write(data)

if __name__=="__main__":
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
