"""Función de Vercel: todas las rutas llegan aquí (ver vercel.json)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import Handler  # noqa: E402


# Vercel busca una clase llamada `handler` definida en este archivo
class handler(Handler):
    pass
