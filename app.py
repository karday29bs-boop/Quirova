"""Servidor local de Quirova. En Vercel se usa api/index.py en su lugar."""
from http.server import ThreadingHTTPServer

from server import Handler

PORT = 8000

if __name__ == "__main__":
    print(f"Quirova en http://localhost:{PORT}")
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()
