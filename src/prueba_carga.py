"""
prueba_carga.py — Prueba de carga: Monolito vs. Microservicios (Caso A)
=======================================================================
Script autocontenido (solo biblioteca estándar de Python) que:

1. Implementa dos arquitecturas con EXACTAMENTE la misma lógica de negocio
   (consultar un pedido: validar usuario + inventario + precio):
     * MONOLITO (puerto 8000): un solo proceso; los tres módulos se invocan
       como llamadas a función en memoria.
     * MICROSERVICIOS: un API Gateway (puerto 8100) que orquesta, vía
       HTTP/JSON, tres servicios independientes —usuarios (8101),
       inventario (8102) y precios (8103)—, cada uno en su PROPIO proceso.
   Como el cómputo es idéntico, la única diferencia sistemática entre
   arquitecturas es la sobrecarga de red (conexión TCP, JSON y saltos HTTP).

2. Lanza los 5 servidores, hace un calentamiento (peticiones descartadas) y
   envía N peticiones a cada arquitectura en ORDEN ALEATORIO INTERCALADO, para
   que el ruido del sistema (caché, planificador del SO) afecte por igual a
   ambos grupos.

3. Mide la latencia extremo a extremo con time.perf_counter() y guarda el CSV.

Uso:
    python src/prueba_carga.py [N_por_grupo] [--salida RUTA.csv]
    (por defecto N = 300 y salida = data/dataset_caso_a_raw.csv)
"""
import argparse
import csv
import hashlib
import json
import random
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SALIDA_DEFECTO = RAIZ / "data" / "dataset_caso_a_raw.csv"
CALENTAMIENTO = 40
SEMILLA = 42

_rng = random.Random(42)
USUARIOS = {i: {"id": i, "nombre": f"usuario_{i}", "nivel": _rng.choice(["basico", "premium"])}
            for i in range(1, 2001)}
INVENTARIO = {i: _rng.randint(0, 500) for i in range(1, 501)}
PRECIOS = {i: round(_rng.uniform(50, 5000), 2) for i in range(1, 501)}


def logica_usuario(uid: int) -> dict:
    u = USUARIOS[uid]
    # validación de sesión simulada (trabajo de CPU)
    token = hashlib.sha256(f"{uid}-{u['nombre']}".encode()).hexdigest()
    for _ in range(150):
        token = hashlib.sha256(token.encode()).hexdigest()
    return {**u, "token": token[:16]}


def logica_inventario(pid: int) -> dict:
    stock = INVENTARIO[pid]
    # cálculo de disponibilidad en almacenes (trabajo de CPU)
    almacenes = sorted(((pid * k) % 97, k) for k in range(1, 800))
    return {"producto": pid, "stock": stock, "almacen": almacenes[0][1]}


def logica_precio(pid: int, nivel: str) -> dict:
    base = PRECIOS[pid]
    desc = 0.15 if nivel == "premium" else 0.0
    total = base
    for _ in range(300):              # cálculo de impuestos/redondeos
        total = round(total * 1.0000001, 6)
    return {"producto": pid, "precio": round(total * (1 - desc), 2)}


def _params(path: str) -> dict:
    if "?" not in path:
        return {}
    q = path.split("?", 1)[1]
    return dict(p.split("=", 1) for p in q.split("&") if "=" in p)


def _responder(handler, payload: dict, code: int = 200):
    body = json.dumps(payload).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _get_json(url: str) -> dict:
    # Nueva conexión TCP por llamada (cliente HTTP sin pool entre servicios)
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


class _Base(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass


class Monolito(_Base):
    def do_GET(self):
        p = _params(self.path)
        uid, pid = int(p["uid"]), int(p["pid"])
        u = logica_usuario(uid)
        inv = logica_inventario(pid)
        pr = logica_precio(pid, u["nivel"])
        _responder(self, {"usuario": u, "inventario": inv, "precio": pr})


class SvcUsuarios(_Base):
    def do_GET(self):
        _responder(self, logica_usuario(int(_params(self.path)["uid"])))


class SvcInventario(_Base):
    def do_GET(self):
        _responder(self, logica_inventario(int(_params(self.path)["pid"])))


class SvcPrecios(_Base):
    def do_GET(self):
        p = _params(self.path)
        _responder(self, logica_precio(int(p["pid"]), p["nivel"]))


class Gateway(_Base):
    def do_GET(self):
        p = _params(self.path)
        uid, pid = p["uid"], p["pid"]
        u = _get_json(f"http://127.0.0.1:8101/usuario?uid={uid}")
        inv = _get_json(f"http://127.0.0.1:8102/inventario?pid={pid}")
        pr = _get_json(f"http://127.0.0.1:8103/precio?pid={pid}&nivel={u['nivel']}")
        _responder(self, {"usuario": u, "inventario": inv, "precio": pr})


SERVIDORES = {8000: Monolito, 8100: Gateway, 8101: SvcUsuarios, 8102: SvcInventario, 8103: SvcPrecios}


def levantar_servidor(puerto: int):
    """Arranca un único servidor (bloqueante) en el proceso actual."""
    ThreadingHTTPServer(("127.0.0.1", puerto), SERVIDORES[puerto]).serve_forever()


ENDPOINTS = {
    "Monolito": "http://127.0.0.1:8000/pedido",
    "Microservicios": "http://127.0.0.1:8100/pedido",
}


def esperar(puerto: int, intentos: int = 50):
    for _ in range(intentos):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{puerto}/x?uid=1&pid=1&nivel=basico", timeout=1)
            return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError(f"El servidor :{puerto} no respondió")


def medir(url: str) -> float:
    t0 = time.perf_counter()
    with urllib.request.urlopen(url, timeout=10) as r:
        r.read()
    return (time.perf_counter() - t0) * 1000.0


def prueba_de_carga(n: int, salida: Path):
    puertos = (8101, 8102, 8103, 8100, 8000)
    procs = [subprocess.Popen([sys.executable, __file__, "--servidor", str(p)]) for p in puertos]
    try:
        for p in puertos:
            esperar(p)

        rng = random.Random(SEMILLA)
        for _ in range(CALENTAMIENTO):
            for url in ENDPOINTS.values():
                medir(f"{url}?uid=1&pid=1")

        plan = ["Monolito"] * n + ["Microservicios"] * n
        rng.shuffle(plan)

        filas = []
        for i, grupo in enumerate(plan, start=1):
            uid, pid = rng.randint(1, 2000), rng.randint(1, 500)
            lat = medir(f"{ENDPOINTS[grupo]}?uid={uid}&pid={pid}")
            filas.append({
                "id_peticion": i,
                "timestamp": datetime.now().isoformat(timespec="milliseconds"),
                "grupo": grupo,
                "uid": uid,
                "pid": pid,
                "latencia_ms": round(lat, 4),
            })
            time.sleep(rng.uniform(0.0, 0.01))          # tiempo de reflexión entre peticiones

        salida.parent.mkdir(parents=True, exist_ok=True)
        with open(salida, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=filas[0].keys())
            w.writeheader()
            w.writerows(filas)
        print(f"Guardadas {len(filas)} observaciones en {salida}")
    finally:
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Prueba de carga Monolito vs. Microservicios")
    ap.add_argument("n", nargs="?", type=int, default=300, help="peticiones por arquitectura (defecto: 300)")
    ap.add_argument("--salida", type=Path, default=SALIDA_DEFECTO, help="ruta del CSV de salida")
    ap.add_argument("--servidor", type=int, choices=sorted(SERVIDORES), help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.servidor:
        levantar_servidor(args.servidor)
    else:
        prueba_de_carga(args.n, args.salida)
