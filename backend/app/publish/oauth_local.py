"""Catch an OAuth redirect on localhost (desktop sign-in for YouTube and TikTok).

Only a request carrying `code` or `error` ends the wait, idle browser connections time out, and a
deadline drops the attempt, so a blocked or closed sign-in tab can never leave it hanging.
"""

import time
import wsgiref.simple_server
import wsgiref.util
from urllib.parse import parse_qs


class QuietHandler(wsgiref.simple_server.WSGIRequestHandler):
    timeout = 10  # an idle connection (browser preconnect) can't hold the listener forever

    def log_message(self, *args):
        pass


def make_server(port: int = 0, host: str = "localhost"):
    return wsgiref.simple_server.make_server(host, port, lambda e, r: [], handler_class=QuietHandler)


def wait_for_redirect(server, deadline: float, service: str = "YouTube") -> str:
    """Serve the local redirect until the provider sends back a code or an error; returns the full URI."""
    result: dict[str, str] = {}

    def app(environ, start_response):
        query = parse_qs(environ.get("QUERY_STRING", ""))
        if "code" in query or "error" in query:
            result["uri"] = wsgiref.util.request_uri(environ)
            body = f"PeakCut is connected to {service}. You can close this tab."
            if "error" in query:
                body = f"Sign-in was cancelled. Go back to PeakCut and click Connect {service} to try again."
        else:
            body = f"Waiting for {service} sign-in."
        start_response("200 OK", [("Content-Type", "text/plain; charset=utf-8")])
        return [body.encode()]

    server.set_app(app)
    server.timeout = 1
    while "uri" not in result:
        if time.time() > deadline:
            raise RuntimeError(f"Sign-in took too long. Click Connect {service} to try again.")
        server.handle_request()
    return result["uri"]
