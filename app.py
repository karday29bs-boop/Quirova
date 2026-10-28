import json
import secrets
import threading
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from model import DelayModel, predict_all

PORT = 8000
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
DATA_FILE = BASE_DIR / "data.json"
SEED_FILE = BASE_DIR / "seed_data.json"
SESSIONS_FILE = BASE_DIR / "sessions.json"

USER_EMAIL = "pruebaQuirofano@correo.com"
USER_PASSWORD = "quirofano123"

MODEL = DelayModel()


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


write_lock = threading.Lock()


def write_json(path, value):
    with write_lock:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

sessions = set(read_json(SESSIONS_FILE, []))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def session_token(self):
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        return cookie["session"].value if "session" in cookie else None

    def redirect(self, location, cookie=None):
        self.send_response(303)
        self.send_header("Location", location)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def send_json(self, body):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        logged_in = self.session_token() in sessions

        if path == "/api/data":
            if not logged_in:
                return self.send_error(401)
            # Sin datos guardados todavía, se arranca con los datos de prueba
            data = read_json(DATA_FILE, None) or read_json(SEED_FILE, {})
            return self.send_json(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        if path == "/api/predicciones":
            if not logged_in:
                return self.send_error(401)
            data = read_json(DATA_FILE, None) or read_json(SEED_FILE, {})
            body = {"modelo": MODEL.info, "procedimientos": predict_all(MODEL, data)}
            return self.send_json(json.dumps(body, ensure_ascii=False).encode("utf-8"))
        if path == "/logout":
            sessions.discard(self.session_token())
            write_json(SESSIONS_FILE, list(sessions))
            return self.redirect("/login", "session=; Path=/; Max-Age=0")
        if path == "/login":
            if logged_in:
                return self.redirect("/")
            self.path = "/login.html"
        elif path == "/login.html" or not logged_in:
            return self.redirect("/login")
        super().do_GET()

    def do_PUT(self):
        if self.path.split("?")[0] != "/api/data":
            return self.send_error(404)
        if self.session_token() not in sessions:
            return self.send_error(401)
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length))
        except ValueError:
            return self.send_error(400)
        write_json(DATA_FILE, payload)
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        if self.path.split("?")[0] != "/login":
            return self.send_error(404)
        length = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        email = form.get("email", [""])[0].strip()
        password = form.get("password", [""])[0]

        valid_email = email.lower() == USER_EMAIL.lower()
        valid_password = secrets.compare_digest(password.encode(), USER_PASSWORD.encode())
        if valid_email and valid_password:
            token = secrets.token_urlsafe(32)
            sessions.add(token)
            write_json(SESSIONS_FILE, list(sessions))
            return self.redirect("/", f"session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000")
        self.redirect("/login?error=1")


if __name__ == "__main__":
    print(f"Quirova en http://localhost:{PORT}")
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()
