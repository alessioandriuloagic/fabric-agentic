"""Read-only local console showing the state of the agent chain."""

import html
from datetime import datetime, timezone
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from fabric_agentic import __version__
from fabric_agentic.control import AgentStatus, agent_home, describe_all


LOOPBACK = "127.0.0.1"
ALLOWED_HOSTS = ("127.0.0.1", "localhost")


def render_html(statuses: tuple[AgentStatus, ...], home: Path) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ready = sum(1 for status in statuses if status.ready)
    cards = "\n".join(_render_card(status) for status in statuses)
    return f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<title>Fabric Agentic — console</title>
<style>
 :root {{ color-scheme: light dark; }}
 body {{ font: 15px/1.5 system-ui, sans-serif; margin: 0; padding: 2rem; max-width: 62rem; }}
 h1 {{ font-size: 1.4rem; margin: 0 0 .25rem; }}
 .meta {{ color: #666; margin-bottom: 2rem; }}
 .card {{ border: 1px solid #8883; border-radius: .6rem; padding: 1rem 1.25rem; margin-bottom: 1rem; }}
 .head {{ display: flex; align-items: baseline; gap: .75rem; }}
 .name {{ font-weight: 600; font-size: 1.1rem; }}
 .role {{ color: #666; }}
 .badge {{ margin-left: auto; border-radius: 1rem; padding: .1rem .7rem; font-size: .8rem; font-weight: 600; }}
 .ok {{ background: #1a7f371f; color: #1a7f37; }}
 .ko {{ background: #d1242f1f; color: #d1242f; }}
 ul {{ list-style: none; padding: 0; margin: .9rem 0 0; }}
 li {{ display: flex; gap: .6rem; padding: .15rem 0; }}
 li .mark {{ width: 1rem; }}
 li .label {{ width: 9rem; color: #666; }}
 code {{ display: block; margin-top: .9rem; padding: .6rem .8rem; background: #8881; border-radius: .4rem;
        font-size: .82rem; overflow-x: auto; white-space: pre; }}
 .note {{ color: #666; font-size: .85rem; margin-top: .5rem; }}
 footer {{ color: #666; font-size: .85rem; margin-top: 2rem; }}
</style>
</head>
<body>
<h1>Fabric Agentic — console</h1>
<p class="meta">{ready} di {len(statuses)} agenti pronti · home <code style="display:inline">{html.escape(str(home))}</code> · {generated} · v{html.escape(__version__)}</p>
{cards}
<footer>Sola lettura: questa pagina non avvia processi, non chiama GitHub o Fabric e non legge credenziali.
Le sessioni si avviano dal terminale con i comandi qui sopra.</footer>
</body>
</html>
"""


def _render_card(status: AgentStatus) -> str:
    badge = '<span class="badge ok">pronto</span>' if status.ready else '<span class="badge ko">da configurare</span>'
    checks = "\n".join(
        f'<li><span class="mark">{"✓" if check.ok else "✗"}</span>'
        f'<span class="label">{html.escape(check.name)}</span>'
        f"<span>{html.escape(check.detail)}</span></li>"
        for check in status.checks
    )
    cadence = "ciclo continuo" if status.continuous else "un ciclo per invocazione"
    return f"""<div class="card">
 <div class="head">
  <span class="name">{html.escape(status.agent)}</span>
  <span class="role">{html.escape(status.role)}</span>
  {badge}
 </div>
 <ul>{checks}</ul>
 <code>{html.escape(status.start_command)}</code>
 <p class="note">{html.escape(status.repository)} · {cadence} · {html.escape(status.activity)}</p>
</div>"""


class ConsoleHandler(BaseHTTPRequestHandler):
    """Serves one read-only page. No other method or path is answered."""

    server_version = "FabricAgenticConsole"

    def __init__(self, *args, home: Path, **kwargs):
        self.home = home
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        if not self._host_is_loopback():
            self.send_error(421, "Misdirected Request")
            return
        if self.path not in ("/", "/index.html"):
            self.send_error(404)
            return

        body = render_html(describe_all(self.home), self.home).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
        self.end_headers()
        self.wfile.write(body)

    def _host_is_loopback(self) -> bool:
        """Reject rebound host names, so a remote page cannot read local state through the browser."""
        host = self.headers.get("Host", "").rsplit(":", 1)[0].strip("[]")
        return host in ALLOWED_HOSTS

    def log_message(self, format: str, *args) -> None:
        return


def serve(port: int, home: Path | None = None) -> None:
    root = home or agent_home()
    handler = partial(ConsoleHandler, home=root)
    with HTTPServer((LOOPBACK, port), handler) as server:
        print(f"console su http://{LOOPBACK}:{server.server_port}/  (Ctrl+C per fermare)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("console fermata")
