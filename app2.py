#!/usr/bin/env python3
import csv
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import html

# ---- CONFIG ----
CSV_PATH = os.environ.get("TEMPLATES_CSV", "templates.csv")
PORT = int(os.environ.get("PORT", "8000"))
TEMPLATE_ID_HEADER = "Template"   # your unique ID column


# ---- DATA ACCESS ----
def load_rows(csv_path):
    """Load CSV file into list of dicts"""
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
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


def find_by_template(rows, query_id):
    """Find row by Template ID"""
    q = (query_id or "").strip()
    for r in rows:
        if r.get(TEMPLATE_ID_HEADER, "").strip() == q:
            return r
    return None


# ---- HTML ----
def page_html(headers, result_row, error_msg=None, query_val=""):
    def esc(x): return html.escape(str(x) if x is not None else "")

    def is_blank(v):
        return v is None or (isinstance(v, str) and v.strip() == "")

    # Build results table if found
    result_html = ""
    if result_row:
        # only keep non-empty columns
        display_headers = [h for h in headers if h and not is_blank(result_row.get(h))]
        if not display_headers:
            result_html = "<p><i>No non-empty fields for this Template.</i></p>"
        else:
            result_html = "<table border='1' cellpadding='6' cellspacing='0'>"
            for h in display_headers:
                result_html += f"<tr><th align='left'>{esc(h)}</th><td>{esc(result_row.get(h,''))}</td></tr>"
            result_html += "</table>"
    elif query_val:
        result_html = f"<p><b>No match for Template:</b> {esc(query_val)}</p>"

    if error_msg:
        result_html = f"<p style='color:#b00'><b>Error:</b> {esc(error_msg)}</p>" + result_html

    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Template Lookup</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 2rem; }}
      form {{ margin-bottom: 1rem; display: flex; gap: .5rem; flex-wrap: wrap; }}
      input[type="text"] {{ padding: .5rem; min-width: 260px; }}
      button {{ padding: .5rem .8rem; cursor: pointer; }}
      table {{ border-collapse: collapse; margin-top: 1rem; max-width: 1100px; }}
      th {{ background: #f0f3f5; white-space: nowrap; vertical-align: top; }}
      td {{ vertical-align: top; }}
      footer {{ margin-top: 2rem; color: #666; font-size: .9rem; }}
    </style>
  </head>
  <body>
    <h1>Template Lookup</h1>
    <p>Type a <b>Template</b> ID and hit Search. Data is read from <code>{esc(CSV_PATH)}</code>.</p>

    <form method="GET" action="/">
      <input name="id" type="text" placeholder="Enter Template ID" value="{esc(query_val)}" required />
      <button type="submit">Search</button>
      <a href="/">Clear</a>
    </form>

    {result_html}

    <footer>
      <p>Tip: update the CSV and refresh to see latest data. Empty fields are hidden.</p>
    </footer>
  </body>
</html>"""


# ---- HTTP SERVER ----
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        query_id = (params.get("id") or [""])[0]

        try:
            headers, rows = load_rows(CSV_PATH)
            match = find_by_template(rows, query_id) if query_id else None
            page = page_html(headers, match, None, query_id)
            self._send_html(200, page)
        except FileNotFoundError:
            page = page_html([], None,
                             f"CSV file not found at '{CSV_PATH}'. Place templates.csv next to app.py or set TEMPLATES_CSV env var.",
                             query_id)
            self._send_html(500, page)
        except Exception as e:
            page = page_html([], None, str(e), query_id)
            self._send_html(500, page)

    def log_message(self, fmt, *args):
        return  # silence logs

    def _send_html(self, status, content):
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Serving on http://127.0.0.1:{PORT}  (CSV: {CSV_PATH})")
    server.serve_forever()


if __name__ == "__main__":
    main()
