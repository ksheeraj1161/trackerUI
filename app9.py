#!/usr/bin/env python3
import csv, os, time, unicodedata
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import html as _html  # keep module alias safe for html.escape

# ----------------------- CONFIG -----------------------
CSV_PATH = os.environ.get("TEMPLATES_CSV", "templates.csv")
PORT = int(os.environ.get("PORT", "8000"))
ID_HEADER_CANDIDATES = ("template", "template id", "template_id", "id")  # case/space tolerant

# --------------------- HELPERS ------------------------
def _norm(s: str) -> str:
    """Unicode-normalize, strip, collapse whitespace, lower-case."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = s.replace("\u200b", "").replace("\ufeff", "").strip()
    s = " ".join(s.split())
    return s.casefold()

def _file_mtime(path: str) -> str:
    try:
        ts = os.path.getmtime(path)
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
    except Exception:
        return "—"

# ---------------------- DATA IO -----------------------
def load_csv(path):
    """Return (headers_in_order, norm2orig_header_map, rows_as_dicts)."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        rdr = csv.DictReader(f)
        raw_headers = rdr.fieldnames or []
        norm2orig = {}
        for h in raw_headers:
            if h is None:
                continue
            n = _norm(h)
            if n and n not in norm2orig:
                norm2orig[n] = h

        rows = []
        for r in rdr:
            row = {}
            for k, v in r.items():
                if not k:
                    continue
                kk = k.strip()
                if kk:
                    row[kk] = v.strip() if isinstance(v, str) else v
            rows.append(row)
        return raw_headers, norm2orig, rows

def detect_id_key(norm2orig, raw_headers):
    for cand in ID_HEADER_CANDIDATES:
        if cand in norm2orig:
            return norm2orig[cand]
    for h in raw_headers:
        n = _norm(h)
        if "template" in n and "id" in n:
            return h
    if raw_headers and "template" in _norm(raw_headers[0]):
        return raw_headers[0]
    return None

def find_row(rows, id_key, q):
    target = _norm(q)
    if not target:
        return None
    for r in rows:
        if _norm(r.get(id_key, "")) == target:
            return r
    return None

# ---------------------- RENDERING ---------------------
def _render_value(header, value) -> str:
    """Turn Link/URL columns into a short hyperlink; otherwise escape text."""
    def esc(x): return _html.escape(str(x) if x is not None else "")
    if value is None:
        return ""
    h = (header or "").lower()
    v = str(value).strip()
    if v and ("link" in h or "url" in h) and v.startswith(("http://", "https://")):
        return f'<a class="btn-link" href="{esc(v)}" target="_blank" rel="noopener">Open</a>'
    return esc(v)

def _table_html(headers, row) -> str:
    def esc(x): return _html.escape(str(x) if x is not None else "")
    if not row:
        return ""
    out = ["<table class='kv'><tbody>"]
    for h in headers:
        val = row.get(h, "")
        if isinstance(val, str) and not val.strip():
            continue  # hide blanks
        out.append(f"<tr><th>{esc(h)}</th><td>{_render_value(h, val)}</td></tr>")
    out.append("</tbody></table>")
    return "".join(out)

def page_html(headers, row, id_key, error=None, q="") -> str:
    """Return the complete HTML page as a string (never None)."""
    def esc(x): return _html.escape(str(x) if x is not None else "")

    # split exactly at OUT_CHN (left <= OUT_CHN; right > OUT_CHN)
    if "OUT_CHN" in headers:
        split_idx = headers.index("OUT_CHN") + 1
    else:
        split_idx = (len(headers) + 1) // 2  # fallback if header missing
    left_headers = headers[:split_idx]
    right_headers = headers[split_idx:]

    details_tbl = _table_html(left_headers, row) if row else ""
    docs_tbl = _table_html(right_headers, row) if row else ""

    data_line = f"{esc(os.path.basename(CSV_PATH))} · updated {esc(_file_mtime(CSV_PATH))}"
    err_html = f"<div class='error'>⚠ {esc(error)}</div>" if error else ""
    if row:
        result_html = f"""
        <div class="two-col">
          <section class="acc">
            <button class="acc-btn" data-target="left">
              <span class="label">Details</span>
              <span class="chev" aria-hidden="true"></span>
            </button>
            <div class="panel" id="panel-left">{details_tbl}</div>
          </section>

          <section class="acc">
            <button class="acc-btn" data-target="right">
              <span class="label">Doc Details</span>
              <span class="chev" aria-hidden="true"></span>
            </button>
            <div class="panel" id="panel-right">{docs_tbl}</div>
          </section>
        </div>
        """
    elif q:
        result_html = f"<p class='warn'>No match for <b>{esc(q)}</b>.</p>"
    else:
        result_html = ""

    # full HTML (JS braces doubled for f-string)
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
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
         background: var(--bg); color: var(--fg); }}
  .band {{ height:6px; background: linear-gradient(90deg, var(--brand), #69D2F1 60%, var(--brand)); }}
  .wrap {{ max-width: 1180px; margin: .8rem auto 1.6rem; padding: 0 14px; }}
  .card {{ background: var(--card); border:1px solid var(--border); border-radius: 12px;
          padding: .9rem .9rem .6rem; box-shadow: 0 4px 16px rgba(0,0,0,.05); }}
  h1 {{ margin: .1rem 0 .2rem; font-size: 1.8rem; }}
  .sub {{ margin: .1rem 0 .6rem; color: var(--muted); }}
  form {{ display:flex; gap: .5rem; flex-wrap: wrap; margin-bottom: .2rem; }}
  input[type=text] {{ flex:1 1 520px; padding: .62rem .72rem; border:1px solid var(--border);
                      border-radius: 8px; outline:none; }}
  input[type=text]:focus {{ border-color: var(--brand); box-shadow: 0 0 0 3px rgba(0,174,239,.12); }}
  button.search {{ padding:.62rem .85rem; border:0; border-radius:8px; background:var(--brand); color:#fff; font-weight:600; cursor:pointer; }}
  button.search:hover {{ background: var(--brand-dark); }}
  a.clear {{ align-self:center; color:var(--brand); text-decoration:none; font-weight:500; }}
  .meta {{ font-size:.9rem; color:var(--muted); margin:.3rem 0 .4rem; }}

  .two-col {{ display:grid; grid-template-columns: 1fr 1fr; gap: 1.0rem 1.4rem; }}
  .acc {{ display:flex; flex-direction:column; }}
  .acc-btn {{
      display:flex; justify-content:space-between; align-items:center;
      background: var(--brand); color:#fff; border:0; border-radius:8px;
      padding:.55rem .7rem; cursor:pointer; font-weight:700; letter-spacing:.1px;
  }}
  .acc-btn .chev {{
      width: 10px; height: 10px; border-right: 2px solid #fff; border-bottom: 2px solid #fff;
      transform: rotate(-45deg); transition: transform .18s ease; margin-left:.6rem;
  }}
  .acc-btn.open .chev {{ transform: rotate(45deg); }}

  .panel {{ display:none; padding:.45rem 0 0; }}
  .panel.open {{ display:block; }}

  table.kv {{ width:100%; border-collapse:collapse; table-layout:fixed; }}
  table.kv th, table.kv td {{ padding:.45rem .55rem; line-height:1.2rem; vertical-align:top; word-wrap:break-word; }}
  table.kv th {{ width:37%; background:var(--row); border-right:1px solid var(--border); font-weight:600; color:#0b2942; text-align:left; }}
  table.kv tr+tr th, table.kv tr+tr td {{ border-top:1px solid var(--border); }}
  .btn-link {{ color:var(--brand); font-weight:600; text-decoration:none; }}
  .btn-link:hover {{ text-decoration:underline; }}
  .warn {{ color:#b45309; margin:.6rem 0 0; }}
  .error {{ color:#b91c1c; margin:.6rem 0 0; }}

  @media (max-width: 900px) {{
    .two-col {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
  <div class="band"></div>
  <div class="wrap">
    <div class="card">
      <h1>Template Lookup</h1>
      <div class="sub">Search by <b>{_html.escape(id_key or 'Template ID')}</b>.</div>

      <form method="GET" action="/" onsubmit="return !!this.id.value.trim()">
        <input name="id" id="id" type="text" placeholder="Enter Template ID" value="{_html.escape(q)}" autofocus />
        <button class="search" type="submit">Search</button>
        <a class="clear" href="/">Clear</a>
      </form>

      <div class="meta">Data: { _html.escape(os.path.basename(CSV_PATH)) } · updated { _html.escape(_file_mtime(CSV_PATH)) }</div>

      {err_html}
      {result_html}
    </div>
  </div>

<script>
  // accordion open/close + arrow rotate
  document.querySelectorAll('.acc-btn').forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      var target = this.getAttribute('data-target');
      var panel  = document.getElementById('panel-' + target);
      var isOpen = panel.classList.contains('open');
      if (isOpen) {{
        panel.classList.remove('open');
        this.classList.remove('open');
      }} else {{
        panel.classList.add('open');
        this.classList.add('open');
      }}
    }});
  }});

  // auto-open left panel after a successful search
  (function() {{
    var leftPanel = document.getElementById('panel-left');
    var leftBtn   = document.querySelector('.acc-btn[data-target="left"]');
    if (leftPanel && leftPanel.innerText.trim()) {{
      leftPanel.classList.add('open');
      if (leftBtn) leftBtn.classList.add('open');
    }}
  }})();
</script>
</body>
</html>"""

# ---------------------- SERVER -----------------------
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        query_val = (qs.get("id") or [""])[0]

        try:
            headers, norm2orig, rows = load_csv(CSV_PATH)
            id_key = detect_id_key(norm2orig, headers)
            row = find_row(rows, id_key, query_val) if (id_key and query_val) else None
            page = page_html(headers, row, id_key, None, query_val)
            self._send(200, page)
        except FileNotFoundError:
            page = page_html([], None, None, f"CSV not found at '{CSV_PATH}'.", query_val)
            self._send(500, page)
        except Exception as e:
            page = page_html([], None, None, str(e), query_val)
            self._send(500, page)

    def log_message(self, *a, **kw):
        return  # be quiet

    def _send(self, status, content):
        # Defensive: always send a string
        data = (content if isinstance(content, str) else str(content or "")).encode("utf-8", errors="replace")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

if __name__ == "__main__":
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
