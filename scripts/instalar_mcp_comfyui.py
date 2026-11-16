"""instalar_mcp_comfyui.py - Spec 006 de C:\\Notas_IA (T6)

Instala (o actualiza) el MCP propio "comfyui" de IMGA en C:\\ComfyUI_MCP y lo prueba:
  1. Requisitos: uv, ficheros de referencia en C:\\Notas_IA\\mcp\\comfyui
  2. Entorno C:\\ComfyUI_MCP\\.venv (Python 3.13 de uv) con mcp==1.30.0 y pillow==13.0.0
     (mcp 2.x cambia la API de FastMCP: se fija la 1.x con la que esta escrito el servidor)
  3. Copia servidor, flujos (5 de imagen + 2 de video desde 1.3.0) y lanzador (SHA-256 contra la referencia) y el complemento de interfaz imga_mcp
     en C:\\ComfyUI\\ComfyUI\\custom_nodes\\imga_mcp (se carga al reiniciar ComfyUI)
  4. Carpetas C:\\IA_Imagenes y C:\\IA_Imagenes\\entrada
  5. Prueba real por stdio a traves del lanzador: initialize -> tools/list (9) -> estado
     y, si ComfyUI esta arrancado, generar_imagen (Z-Image, 768x768, semilla 42) con la imagen devuelta
No toca la configuracion de ninguna app de IA (eso es 04_configurar_mcp_comfyui.bat).

  uv run --no-project --python 3.13 python instalar_mcp_comfyui.py --informe F [--sin-generar]
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ap = argparse.ArgumentParser()
ap.add_argument("--informe", required=True)
ap.add_argument("--sin-generar", action="store_true")
A = ap.parse_args()

HOME = Path(os.environ["USERPROFILE"])
NOTAS = Path(r"C:\Notas_IA")
REF = NOTAS / "mcp" / "comfyui"
DEST = Path(r"C:\ComfyUI_MCP")
VPY = DEST / ".venv" / "Scripts" / "python.exe"
LANZ = DEST / "comfyui-mcp-launch.bat"
BASE = Path(r"C:\IA_Imagenes")
UV = shutil.which("uv") or str(HOME / ".local" / "bin" / "uv.exe")
CMD = str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "cmd.exe")
PAQUETES = ["mcp==1.30.0", "pillow==13.0.0"]
HERRAMIENTAS = {"estado", "generar_imagen", "editar_imagen", "retocar_ultima", "esperar_resultado",
                "ver_imagen", "listar_resultados", "liberar_memoria", "generar_video"}

LINEAS, FALLOS, AVISOS = [], [], []


def log(m=""):
    print(m, flush=True)
    LINEAS.append(str(m))


def paso(n, ok, d="", aviso=False):
    log(f"   [{'OK ' if ok else ('AVISO' if aviso else 'FALLO')}] {n}{(' - ' + d) if d else ''}")
    if not ok:
        (AVISOS if aviso else FALLOS).append(n)
    return ok


def terminar():
    log("")
    log("RESULTADO: " + ("TODO OK" if not FALLOS else f"{len(FALLOS)} FALLO(S): {', '.join(FALLOS)}")
        + (f" | {len(AVISOS)} AVISO(S): {', '.join(AVISOS)}" if AVISOS else ""))
    p = Path(A.informe)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(LINEAS) + "\n", encoding="utf-8")
    sys.exit(0 if not FALLOS else 1)


def env_limpio():
    e = os.environ.copy()
    for k in ("VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME"):
        e.pop(k, None)
    e["COMFY_MCP_VISOR"] = "0"  # la prueba no abre ventanas de la interfaz
    return e


def run(args, timeout=1800):
    log(f"   > {' '.join(str(a) for a in args)}")
    r = subprocess.run([str(a) for a in args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env_limpio(), timeout=timeout)
    out = (r.stdout + ("\n" + r.stderr if r.stderr.strip() else "")).strip()
    for l in out.splitlines()[-8:]:
        log(f"     {l}")
    return r.returncode, out


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def copiar(ref: Path, dst: Path):
    if not paso(f"referencia {ref.name}", ref.exists(), str(ref)):
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ref, dst)
    paso(f"copiado {dst}", sha256(ref) == sha256(dst), f"SHA-256 {sha256(dst)[:16]}...")


def prueba_mcp(generar: bool):
    p = subprocess.Popen([CMD, "/d", "/c", str(LANZ)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, env=env_limpio())
    q, err = queue.Queue(), []
    threading.Thread(target=lambda: [q.put(l) for l in iter(p.stdout.readline, b"")], daemon=True).start()
    threading.Thread(target=lambda: [err.append(l.decode("utf-8", "replace").rstrip())
                                     for l in iter(p.stderr.readline, b"")], daemon=True).start()

    def send(o):
        p.stdin.write((json.dumps(o) + "\n").encode())
        p.stdin.flush()

    def wait(i, t):
        fin = time.time() + t
        while time.time() < fin:
            try:
                m = json.loads(q.get(timeout=1))
            except queue.Empty:
                if p.poll() is not None:
                    return None
                continue
            except Exception:
                continue
            if m.get("id") == i:
                return m
        return None

    def llamar(i, nombre, args, t):
        send({"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": nombre, "arguments": args}})
        r = wait(i, t)
        if not r:
            return False, "sin respuesta", []
        res = r.get("result", {})
        c = res.get("content", [])
        txt = " ".join(x.get("text", "") for x in c if x.get("type") == "text").replace("\n", " ")
        return not res.get("isError"), txt, [x for x in c if x.get("type") == "image"]

    try:
        t0 = time.time()
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "notas-ia-test", "version": "1"}}})
        r = wait(1, 120)
        if not paso("initialize", bool(r and "result" in r), f"{round(time.time() - t0, 1)} s"):
            return
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        r = wait(2, 60)
        nombres = {t["name"] for t in (r or {}).get("result", {}).get("tools", [])}
        paso(f"tools/list ({len(nombres)} herramientas)", nombres == HERRAMIENTAS, ", ".join(sorted(nombres)))
        ok, txt, _ = llamar(3, "estado", {}, 60)
        comfy_ok = ok and '"comfyui"' in txt
        paso("estado", True, txt[:500])
        if not comfy_ok:
            paso("ComfyUI arrancado", False, "no responde: se omite la prueba de generar (arrancalo y repite)", aviso=True)
            return
        if not generar:
            return
        ok, txt, imgs = llamar(4, "generar_imagen", {"prompt": "Fotografia de una cantera de caliza al atardecer, "
                                                     "excavadora amarilla", "modo": "rapido", "ancho": 768,
                                                     "alto": 768, "semilla": 42}, 240)
        if "esperar_resultado" in txt:
            pid = txt.split("prompt_id='")[-1].split("'")[0]
            ok, txt, imgs = llamar(5, "esperar_resultado", {"prompt_id": pid, "segundos": 180}, 240)
        paso("generar_imagen (Z-Image 768x768) con imagen devuelta al cliente", ok and len(imgs) == 1,
             f"{txt[:300]} | imagenes en la respuesta: {len(imgs)}")
    finally:
        try:
            p.stdin.close()
            p.wait(timeout=5)
        except Exception:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
        if err:
            log("   stderr (ultimas lineas):")
            for l in err[-5:]:
                log(f"     {l}")


log(f"INSTALACION DEL MCP comfyui (spec 006, T6) - {dt.datetime.now():%Y-%m-%d %H:%M:%S}")
log(f"Destino {DEST} | paquetes {', '.join(PAQUETES)} | referencia {REF}")
log("")
log("== 1. Requisitos")
rc, out = run([UV, "--version"])
if not paso("uv", rc == 0):
    terminar()
log("")
log("== 2. Entorno Python")
if not VPY.exists():
    rc, _ = run([UV, "venv", str(DEST / ".venv"), "--python", "3.13"])
    if not paso("uv venv (Python 3.13)", rc == 0 and VPY.exists()):
        terminar()
rc, _ = run([UV, "pip", "install", "--python", str(VPY), *PAQUETES])
paso("uv pip install " + " ".join(PAQUETES), rc == 0)
rc, out = run([VPY, "-c", "import importlib.metadata as m; print(m.version('mcp'), m.version('pillow'))"])
paso("versiones instaladas", rc == 0 and out.strip().splitlines()[-1] == "1.30.0 13.0.0", out.strip()[-40:])
if FALLOS:
    terminar()
log("")
log("== 3. Ficheros (copia + SHA-256)")
copiar(REF / "servidor" / "servidor_comfyui_mcp.py", DEST / "servidor_comfyui_mcp.py")
copiar(REF / "lanzador" / "comfyui-mcp-launch.bat", LANZ)
for f in ("generar_qwen21", "editar_qwen21", "generar_rapido", "generar_texto", "editar", "video_wan", "video_acabado"):
    copiar(REF / "flujos" / f"{f}.json", DEST / "flujos" / f"{f}.json")
EXT = Path(r"C:\ComfyUI\ComfyUI\custom_nodes\imga_mcp")
copiar(REF / "complemento_comfyui" / "imga_mcp" / "__init__.py", EXT / "__init__.py")
copiar(REF / "complemento_comfyui" / "imga_mcp" / "web" / "imga_mcp.js", EXT / "web" / "imga_mcp.js")
log("   (el complemento imga_mcp se carga al reiniciar ComfyUI: Gestor -> Reiniciar, o cerrar y abrir)")
log("")
log("== 4. Carpetas de imagenes")
for d in (BASE, BASE / "entrada"):
    d.mkdir(parents=True, exist_ok=True)
    paso(f"carpeta {d}", d.is_dir())
if FALLOS:
    terminar()
log("")
log("== 5. Prueba real del MCP por stdio (a traves del lanzador)")
prueba_mcp(not A.sin_generar)
terminar()
