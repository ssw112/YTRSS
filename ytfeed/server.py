"""HTTP server: /feed.xml, /article/{id}, /status, /setup, /healthz.

ThreadingHTTPServer is mandatory: v1's single-threaded server wedged
permanently on one hung client connection and served nothing for weeks.
"""
import html as html_mod
import http.server
import json
import os
import secrets
import urllib.parse

from . import feed as feed_mod
from .summarize import test_provider

ARTICLE_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
       Helvetica, Arial, sans-serif; line-height: 1.6; color: #333;
       max-width: 800px; margin: 40px auto; padding: 0 20px; background: #fcfcfc; }
a { color: #0066cc; text-decoration: none; } a:hover { text-decoration: underline; }
pre, code { background: #f4f4f4; padding: 2px 5px; border-radius: 4px;
            font-family: Menlo, Consolas, monospace; font-size: .9em; }
pre { padding: 15px; overflow-x: auto; border-left: 4px solid #ccc; }
table { border-collapse: collapse; } td, th { border: 1px solid #ddd; padding: 6px 10px; }
"""


def make_handler(app):
    """app: object with .cfg (may be None in setup-only mode), .state,
    .config_path, .setup_token."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            app.log.info("http: " + fmt, *args)

        def _send(self, code, body, ctype="text/html; charset=utf-8"):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authed(self):
            q = urllib.parse.urlparse(self.path).query
            token = urllib.parse.parse_qs(q).get("token", [""])[0]
            if not token:
                token = self.headers.get("X-Setup-Token", "")
            return secrets.compare_digest(token, app.setup_token)

        # ------------------------------------------------------------------
        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path

            if path == "/healthz":
                return self._send(200, "ok", "text/plain")

            if path in ("/feed.xml", "/feed"):
                return self._serve_feed()

            if path.startswith("/article/"):
                return self._serve_article(path.rsplit("/", 1)[-1])

            if path == "/status":
                return self._serve_status()

            if path == "/setup":
                if not self._authed():
                    return self._send(401, "<h1>401</h1><p>setup token required "
                                           "(?token=...)</p>")
                return self._serve_setup_form()

            if path == "/":
                return self._send(200, "<h1>ytfeed</h1><p>Endpoints: /feed.xml, "
                                       "/article/{id}, /status, /setup, /healthz</p>")
            self._send(404, "not found", "text/plain")

        def do_POST(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/setup":
                if not self._authed():
                    return self._send(401, "unauthorized", "text/plain")
                return self._handle_setup_post()
            if path == "/test-provider":
                if not self._authed():
                    return self._send(401, "unauthorized", "text/plain")
                return self._handle_test_provider()
            self._send(404, "not found", "text/plain")

        # ------------------------------------------------------------------
        def _serve_feed(self):
            if app.cfg is None:
                return self._send(503, "not configured yet", "text/plain")
            path = feed_mod._feed_path(app.cfg)
            if not os.path.exists(path):
                return self._send(404, "feed not generated yet", "text/plain")
            with open(path, "rb") as f:
                self._send(200, f.read(), "application/xml; charset=utf-8")

        def _serve_article(self, video_id):
            if app.cfg is None:
                return self._send(503, "not configured yet", "text/plain")
            title, content = feed_mod.get_article(app.cfg, video_id)
            if not content:
                self.send_response(302)
                self.send_header("Location",
                                 f"https://www.youtube.com/watch?v={video_id}")
                self.end_headers()
                return
            page = (f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
                    f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
                    f"<title>{html_mod.escape(title)}</title>"
                    f"<style>{ARTICLE_CSS}</style></head><body>{content}</body></html>")
            self._send(200, page)

        def _serve_status(self):
            snap = app.state.snapshot() if app.state else {}
            configured = app.cfg is not None
            rows = ""
            for label, p in snap.get("providers", {}).items():
                rows += (f"<tr><td>{html_mod.escape(label)}</td>"
                         f"<td>{p.get('last_ok', '—')}</td>"
                         f"<td>{p.get('last_error', '—')}</td>"
                         f"<td>{html_mod.escape(str(p.get('error_msg', ''))[:120])}</td></tr>")
            body = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>ytfeed status</title><style>{ARTICLE_CSS}</style></head><body>
<h1>ytfeed status</h1>
<p>Configured: <strong>{configured}</strong></p>
<p>Feed URL (import this in your RSS reader):
<strong>{(app.cfg or {}).get('feed', {}).get('public_base_url', '').rstrip('/')}/feed.xml</strong></p>
<ul>
<li>Started: {snap.get('started_at', '—')}</li>
<li>Last run: {snap.get('last_run_at', '—')} → {html_mod.escape(str(snap.get('last_run_result', '—')))}</li>
<li>Runs since start: {snap.get('runs', 0)}</li>
<li>Last article published: {snap.get('last_success_at', '—')} — {html_mod.escape(str(snap.get('last_article', '—')))}</li>
</ul>
<h2>Providers</h2>
<table><tr><th>provider</th><th>last OK</th><th>last error</th><th>message</th></tr>{rows}</table>
<p><small>POST /test-provider?token=…&label=… runs a live one-token completion.</small></p>
</body></html>"""
            self._send(200, body)

        def _serve_setup_form(self):
            current = ""
            if os.path.exists(app.config_path):
                with open(app.config_path) as f:
                    current = f.read()
            body = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>ytfeed setup</title><style>{ARTICLE_CSS}
textarea {{ width: 100%; height: 420px; font-family: Menlo, monospace; font-size: 13px; }}
</style></head><body>
<h1>ytfeed setup</h1>
<p>Edit <code>config.yml</code> directly. Saving validates before writing;
the scheduler picks the new config up on its next cycle.</p>
<form method="POST" action="/setup?token={html_mod.escape(app.setup_token)}">
<textarea name="config">{html_mod.escape(current)}</textarea><br>
<button type="submit">Save config</button>
</form></body></html>"""
            self._send(200, body)

        def _handle_setup_post(self):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8")
            fields = urllib.parse.parse_qs(raw)
            new_yaml = fields.get("config", [""])[0]
            import yaml as yaml_mod
            from .config import validate, ConfigError
            try:
                parsed = yaml_mod.safe_load(new_yaml) or {}
                validate(parsed)
            except (yaml_mod.YAMLError, ConfigError) as e:
                return self._send(400, f"<h1>Invalid config</h1><pre>"
                                       f"{html_mod.escape(str(e))}</pre>"
                                       f"<p><a href='/setup?token={app.setup_token}'>back</a></p>")
            os.makedirs(os.path.dirname(app.config_path), exist_ok=True)
            with open(app.config_path, "w") as f:
                f.write(new_yaml)
            app.reload_config()
            self._send(200, "<h1>Saved.</h1><p>Scheduler will use the new config "
                            "on its next cycle. <a href='/status'>status</a></p>")

        def _handle_test_provider(self):
            if app.cfg is None:
                return self._send(503, "not configured", "text/plain")
            q = urllib.parse.urlparse(self.path).query
            label = urllib.parse.parse_qs(q).get("label", [""])[0]
            results = {}
            for p in app.cfg["llm"]["providers"]:
                if label and p["label"] != label:
                    continue
                ok, msg = test_provider(p)
                results[p["label"]] = {"ok": ok, "detail": msg}
            self._send(200, json.dumps(results, indent=2),
                       "application/json; charset=utf-8")

    return Handler


def serve(app, port):
    handler = make_handler(app)
    httpd = http.server.ThreadingHTTPServer(("", port), handler)
    app.log.info("HTTP server listening on :%d", port)
    httpd.serve_forever()
