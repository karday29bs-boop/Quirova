"""Servidor local de Cirvia. En Vercel se usa api/index.py en su lugar."""
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, make_server

from server import app

PORT = 8000


# Atiende varias peticiones a la vez para que una conexión ociosa no bloquee a las demás
class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


if __name__ == "__main__":
    print(f"Cirvia en http://localhost:{PORT}")
    make_server("", PORT, app, server_class=ThreadingWSGIServer).serve_forever()
