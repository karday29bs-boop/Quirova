"""Modelo predictivo local de Cirvia.

Estima el riesgo de retraso de cada procedimiento con una regresión logística
escrita en Python puro (sin librerías externas). Se entrena al iniciar el
servidor con un historial sintético generado con semilla fija, así que siempre
produce el mismo modelo. Es una herramienta de apoyo, no un modelo clínico.
"""
import math
import random
from datetime import date

IPQ_COMPONENTS = 7

FEATURES = [
    ("ipq", "Índice de preparación (IPQ)"),
    ("pendientes", "Componentes pendientes"),
    ("sin_evaluar", "Componentes sin evaluar"),
    ("seguimiento", "Registros de trazabilidad"),
    ("dias", "Días hasta la cirugía"),
]

BASE_DURATION = {
    "colecistectom": 90,
    "artroscop": 75,
    "herniorraf": 60,
    "apendicectom": 60,
    "cesare": 60,
    "cesáre": 60,
    "reemplazo": 150,
    "bypass": 240,
}
DEFAULT_DURATION = 90


def sigmoid(z):
    return 1 / (1 + math.exp(-z))


def synthetic_history(n=800, seed=42):
    """Historial simulado: más preparación y trazabilidad → menos retrasos."""
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        sin_evaluar = rng.choice([0, 0, 0, 0, 0, 0, 1, 2, 3, 7])
        evaluados = IPQ_COMPONENTS - sin_evaluar
        pendientes = rng.randint(0, evaluados) if rng.random() < 0.5 else 0
        ipq = (evaluados - pendientes) / evaluados if evaluados else 0.5
        seguimiento = rng.randint(0, 4)
        dias = rng.randint(0, 30)
        z = 1.2 - 3.5 * ipq + 0.5 * pendientes + 0.35 * sin_evaluar - 0.25 * seguimiento - 0.04 * dias
        y = 1 if rng.random() < sigmoid(z + rng.gauss(0, 0.6)) else 0
        rows.append(([ipq, pendientes, sin_evaluar, seguimiento, dias], y))
    return rows


class DelayModel:
    def __init__(self, epochs=400, lr=0.5):
        history = synthetic_history()
        X = [x for x, _ in history]
        Y = [y for _, y in history]
        k, n = len(FEATURES), len(X)

        self.mean = [sum(r[j] for r in X) / n for j in range(k)]
        self.std = [(sum((r[j] - self.mean[j]) ** 2 for r in X) / n) ** 0.5 or 1 for j in range(k)]
        Z = [self._scale(r) for r in X]

        self.w, self.b = [0.0] * k, 0.0
        for _ in range(epochs):
            gw, gb = [0.0] * k, 0.0
            for z, y in zip(Z, Y):
                err = self._prob(z) - y
                gb += err
                for j in range(k):
                    gw[j] += err * z[j]
            self.b -= lr * gb / n
            self.w = [w - lr * g / n for w, g in zip(self.w, gw)]

        hits = sum((self._prob(z) >= 0.5) == bool(y) for z, y in zip(Z, Y))
        self.info = {"tipo": "Regresión logística", "muestras": n, "exactitud": round(hits / n * 100)}

    def _scale(self, x):
        return [(v - m) / s for v, m, s in zip(x, self.mean, self.std)]

    def _prob(self, z):
        return sigmoid(self.b + sum(w * v for w, v in zip(self.w, z)))

    def predict(self, x, procedimiento=""):
        z = self._scale(x)
        p = self._prob(z)
        riesgo = round(p * 100)
        nivel = "Bajo" if riesgo < 30 else "Medio" if riesgo < 60 else "Alto"

        shown = [f"{round(x[0] * 100)}%", *(str(v) for v in x[1:])]
        contrib = sorted(((w * v, f"{label} ({s})") for w, v, (_, label), s in zip(self.w, z, FEATURES, shown)),
                         key=lambda c: -abs(c[0]))
        factores = [{"factor": label, "efecto": "aumenta" if c > 0 else "reduce"} for c, label in contrib[:3] if abs(c) > 0.05]

        name = procedimiento.lower()
        base = next((m for key, m in BASE_DURATION.items() if key in name), DEFAULT_DURATION)
        duracion = round(base * (1 + 0.3 * p) / 5) * 5

        return {"riesgo": riesgo, "nivel": nivel, "duracion": duracion, "duracion_base": base, "factores": factores}


def features_for(proc, data, today=None):
    today = today or date.today()
    answers = data.get("ipq", {}).get(proc.get("id"), {}).get("answers", {})
    values = [answers.get(str(i)) for i in range(IPQ_COMPONENTS)]
    sin_evaluar = values.count(None)
    pendientes = values.count("pendiente")
    aplicables = [v for v in values if v and v != "na"]
    ipq = sum(v == "listo" for v in aplicables) / len(aplicables) if aplicables else 0.5
    seguimiento = sum(s.get("procedimiento") == proc.get("id") for s in data.get("seguimiento", []))
    try:
        dias = min(30, max(0, (date.fromisoformat(proc.get("fecha", "")) - today).days))
    except ValueError:
        dias = 15
    return [ipq, pendientes, sin_evaluar, seguimiento, dias]


def predict_all(model, data):
    return {
        p["id"]: model.predict(features_for(p, data), p.get("procedimiento", ""))
        for p in data.get("procedimientos", [])
        if "id" in p
    }


if __name__ == "__main__":
    m = DelayModel()
    print("Modelo:", m.info)
    print("Pesos:", {key: round(w, 2) for (key, _), w in zip(FEATURES, m.w)})
