"""Lógica del servidor de Cirvia como aplicación WSGI (`app`).

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
from pathlib import Path
from urllib.parse import parse_qs

from model import DelayModel, predict_all

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
SEED_FILE = BASE_DIR / "seed_data.json"

USER_EMAIL = "pruebaQuirofano@correo.com"
USER_PASSWORD = "quirofano123"


SECRET = os.environ.get("CIRVIA_SECRET", "cirvia-clave-de-desarrollo").encode()
SESSION_SECONDS = 30 * 24 * 3600
MAX_BODY = 2 * 1024 * 1024


MODEL = DelayModel()

STATUS = {200: "200 OK", 303: "303 See Other", 400: "400 Bad Request", 401: "401 Unauthorized", 404: "404 Not Found"}


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


class Request:
    def __init__(self, environ):
        self.environ = environ
        self.method = environ.get("REQUEST_METHOD", "GET")
        self.path = environ.get("PATH_INFO") or "/"
        cookie = SimpleCookie(environ.get("HTTP_COOKIE", ""))
        self.logged_in = "session" in cookie and valid_session(cookie["session"].value)
        self.https = (environ.get("HTTP_X_FORWARDED_PROTO") or environ.get("wsgi.url_scheme")) == "https"

    def body(self):
        length = int(self.environ.get("CONTENT_LENGTH") or 0)
        if length > MAX_BODY:
            raise ValueError("cuerpo demasiado grande")
        return self.environ["wsgi.input"].read(length) if length else b""

    def cookie(self, value, max_age):
        secure = "; Secure" if self.https else ""
        return f"session={value}; Path=/; HttpOnly; SameSite=Lax; Max-Age={max_age}{secure}"



def redirect(location, cookie=None):
    headers = [("Location", location)]
    if cookie:
        headers.append(("Set-Cookie", cookie))
    return 303, headers, b""


def body_response(body, content_type):
    return 200, [("Content-Type", content_type), ("Cache-Control", "no-store")], body


def json_response(value):
    return body_response(json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")


def page(name):
    return body_response((TEMPLATES_DIR / name).read_bytes(), "text/html; charset=utf-8")


def error(code):
    return code, [("Content-Type", "text/plain; charset=utf-8")], STATUS[code].encode()


def login(req):
    try:
        form = parse_qs(req.body().decode("utf-8"))
    except ValueError:
        return error(400)
    email = form.get("email", [""])[0].strip()
    password = form.get("password", [""])[0]

    valid_email = email.lower() == USER_EMAIL.lower()
    valid_password = secrets.compare_digest(password.encode(), USER_PASSWORD.encode())
    if valid_email and valid_password:
        return redirect("/", req.cookie(new_session(), SESSION_SECONDS))
    return redirect("/login?error=1")


def predictions(req):
    if not req.logged_in:
        return error(401)
    
    try:
        data = json.loads(req.body())
    except ValueError:
        return error(400)
    if not isinstance(data, dict):
        return error(400)
    return json_response({"modelo": MODEL.info, "procedimientos": predict_all(MODEL, data)})


def route(req):
    if req.method == "POST":
        if req.path == "/login":
            return login(req)
        if req.path == "/api/predicciones":
            return predictions(req)
        return error(404)

    if req.path == "/api/seed":
        if not req.logged_in:
            return error(401)
        return json_response(json.loads(SEED_FILE.read_text(encoding="utf-8")))
    if req.path == "/logout":
        return redirect("/login", req.cookie("", 0))
    if req.path == "/login":
        return redirect("/") if req.logged_in else page("login.html")
    if req.path in ("/", "/index.html"):
        return page("index.html") if req.logged_in else redirect("/login")
    return error(404)


def app(environ, start_response):
    code, headers, body = route(Request(environ))
    start_response(STATUS[code], headers + [("Content-Length", str(len(body)))])
    return [body]
