import socket
import threading
import time
import urllib.request
import wsgiref.simple_server

import pytest

from app.publish import youtube


def _server():
    return wsgiref.simple_server.make_server("localhost", 0, lambda e, r: [], handler_class=youtube._QuietHandler)


def test_redirect_listener_ignores_idle_and_unrelated_requests():
    server = _server()
    port = server.server_port
    out = {}
    t = threading.Thread(target=lambda: out.update(uri=youtube._wait_for_redirect(server, time.time() + 30)))
    t.start()

    idle = socket.create_connection(("localhost", port))  # browser preconnect that never sends anything
    assert b"Waiting" in urllib.request.urlopen(f"http://localhost:{port}/favicon.ico").read()
    assert b"connected" in urllib.request.urlopen(f"http://localhost:{port}/?state=s&code=abc").read()
    t.join(15)
    idle.close()
    server.server_close()

    assert not t.is_alive()
    assert "code=abc" in out["uri"]


def test_redirect_listener_gives_up_after_the_deadline():
    server = _server()
    try:
        with pytest.raises(RuntimeError, match="took too long"):
            youtube._wait_for_redirect(server, time.time() + 1.5)
    finally:
        server.server_close()
