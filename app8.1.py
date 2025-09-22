    return f"""<!doctype html>
<html>
<head> ... your styles ... </head>
<body>
  <div class="band"></div>
  <div class="wrap">
    <div class="card">
      <h1>Template Lookup</h1>
      <div class="sub">Search by <b>{html.escape(id_key or 'Template ID')}</b>.</div>

      <form method="GET" action="/" onsubmit="return !!this.id.value.trim()">
        <input name="id" id="id" type="text" placeholder="Enter Template ID" value="{html.escape(q)}" autofocus />
        <button class="search" type="submit">Search</button>
        <a class="clear" href="/">Clear</a>
      </form>

      <div class="meta">Data: {html.escape(os.path.basename(CSV_PATH))} · updated {html.escape(_file_mtime(CSV_PATH))}</div>

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
