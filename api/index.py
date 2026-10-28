"""Función de Vercel: todas las rutas llegan aquí (ver vercel.json)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402

# Vercel busca una variable `app` con una aplicación WSGI
app = server.app
