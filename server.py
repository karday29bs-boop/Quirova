"""Lógica del servidor de Cirvia.

La usan tanto `app.py` (servidor local) como `api/index.py` (función de Vercel).
No guarda nada en disco: los datos viven en el navegador de cada usuario y la
sesión es una cookie firmada, así funciona igual en Vercel que en local.
"""
import hashlib
import hmac
import json
import os
import secrets
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs

from model import DelayModel, predict_all

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
SEED_FILE = BASE_DIR / "seed_data.json"

USER_EMAIL = "pruebaQuirofano@correo.com"
USER_PASSWORD = "quirofano123"

# En Vercel define CIRVIA_SECRET; sin ella cualquiera que lea el código podría falsificar sesiones
SECRET = os.environ.get("CIRVIA_SECRET", "cirvia-clave-de-desarrollo").encode()
SESSION_SECONDS = 30 * 24 * 3600
MAX_BODY = 2 * 1024 * 1024

# El modelo predictivo se entrena una vez al cargar el módulo
MODEL = DelayModel()


def sign(expires):
    return hmac.new(SECRET, f"{USER_EMAIL}|{expires}".encode(), hashlib.sha256).hexdigest()


def new_session():
    expires = int(time.time()) + SESSION_SECONDS
    return f"{expires}.{sign(expires)}"


def valid_session(token):
    try:
        expires, signature = token.split(".", 1)
        return int(expires) > time.time() and hmac.compare_digest(signature, sign(int(expires)))
    except (AttributeError, ValueError):
        return False


class Handler(BaseHTTPRequestHandler):
    def logged_in(self):
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        return "session" in cookie and valid_session(cookie["session"].value)

    def cookie(self, value, max_age):
        secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
        return f"session={value}; Path=/; HttpOnly; SameSite=Lax; Max-Age={max_age}{secure}"

    def redirect(self, location, cookie=None):
        self.send_response(303)
        self.send_header("Location", location)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def send_body(self, body, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, value):
        self.send_body(json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def send_page(self, name):
        self.send_body((TEMPLATES_DIR / name).read_bytes(), "text/html; charset=utf-8")

    def read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_BODY:
            raise ValueError("cuerpo demasiado grande")
        return self.rfile.read(length)

    def do_GET(self):
        path = self.path.split("?")[0]
        logged_in = self.logged_in()

        if path == "/api/seed":
            if not logged_in:
                return self.send_error(401)
            return self.send_json(json.loads(SEED_FILE.read_text(encoding="utf-8")))
        if path == "/logout":
            return self.redirect("/login", self.cookie("", 0))
        if path == "/login":
            return self.redirect("/") if logged_in else self.send_page("login.html")
        if path in ("/", "/index.html"):
            return self.send_page("index.html") if logged_in else self.redirect("/login")
        self.send_error(404)

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/login":
            return self.login()
        if path == "/api/predicciones":
            if not self.logged_in():
                return self.send_error(401)
            # El navegador envía sus datos; el servidor solo calcula y no guarda nada
            try:
                data = json.loads(self.read_body())
            except ValueError:
                return self.send_error(400)
            if not isinstance(data, dict):
                return self.send_error(400)
            return self.send_json({"modelo": MODEL.info, "procedimientos": predict_all(MODEL, data)})
        self.send_error(404)

    def login(self):
        try:
            form = parse_qs(self.read_body().decode("utf-8"))
        except ValueError:
            return self.send_error(400)
        email = form.get("email", [""])[0].strip()
        password = form.get("password", [""])[0]

        valid_email = email.lower() == USER_EMAIL.lower()
        valid_password = secrets.compare_digest(password.encode(), USER_PASSWORD.encode())
        if valid_email and valid_password:
            return self.redirect("/", self.cookie(new_session(), SESSION_SECONDS))
        self.redirect("/login?error=1")
