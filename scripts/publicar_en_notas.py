"""publicar_en_notas.py - copia la version del repositorio a C:\\Notas_IA (referencia desde la que instala el 03).

Destinos:
  servidor\\, flujos\\, lanzador\\, plantillas\\  ->  C:\\Notas_IA\\mcp\\comfyui\\<igual>
  scripts\\03_*, 04_*, instalar_*.py, configurar_*.py  ->  C:\\Notas_IA\\scripts\\comfyui\\
No toca la ficha C:\\Notas_IA\\mcp\\comfyui\\README.md (es la ficha del equipo; se actualiza aparte).
Comprueba cada copia por SHA-256 y deja informe en C:\\Notas_IA\\inventario\\auto\\publicacion_mcp_comfyui_<fecha>.txt.

  uv run --no-project --python 3.13 python scripts\\publicar_en_notas.py [--notas C:\\Notas_IA] [--simular]
"""
import argparse
import datetime as dt
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ap = argparse.ArgumentParser()
ap.add_argument("--notas", default=r"C:\Notas_IA")
ap.add_argument("--simular", action="store_true", help="no copia nada, solo dice que cambiaria")
A = ap.parse_args()

RAIZ = Path(__file__).resolve().parents[1]
NOTAS = Path(A.notas)
MAPA = []
for carpeta in ("servidor", "flujos", "lanzador", "plantillas"):
    for f in sorted((RAIZ / carpeta).iterdir()):
        if f.is_file() and f.suffix in (".py", ".json", ".md", ".bat", ".yaml"):
            MAPA.append((f, NOTAS / "mcp" / "comfyui" / carpeta / f.name))
for nombre in ("03_instalar_mcp_comfyui.bat", "instalar_mcp_comfyui.py",
               "04_configurar_mcp_comfyui.bat", "configurar_mcp_comfyui.py"):
    MAPA.append((RAIZ / "scripts" / nombre, NOTAS / "scripts" / "comfyui" / nombre))

lineas, fallos = [], 0


def log(m=""):
    print(m, flush=True)
    lineas.append(m)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "-"


def git(*args) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, errors="replace", timeout=30)
        return r.stdout.strip() if r.returncode == 0 else f"(git: {r.stderr.strip()[:200]})"
    except Exception as e:
        return f"(sin git: {e})"


log(f"PUBLICAR MCP comfyui EN {NOTAS} - {dt.datetime.now():%Y-%m-%d %H:%M:%S}{'  [SIMULACION]' if A.simular else ''}")
log(f"Repositorio: {RAIZ}")
log(f"Commit: {git('rev-parse', '--short', 'HEAD')}  {git('log', '-1', '--format=%s')}")
pend = git("status", "--porcelain")
if pend and not pend.startswith("("):
    log("AVISO: hay cambios sin commit en el repositorio (se publican igual):")
    for l in pend.splitlines()[:20]:
        log(f"   {l}")
log("")
for src, dst in MAPA:
    if not src.exists():
        log(f"   [FALLO] falta en el repositorio: {src.relative_to(RAIZ)}")
        fallos += 1
        continue
    antes, nuevo = sha(dst), sha(src)
    if antes == nuevo:
        log(f"   [igual] {dst}")
        continue
    if not A.simular:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        ok = sha(dst) == nuevo
        fallos += 0 if ok else 1
        log(f"   [{'OK   ' if ok else 'FALLO'}] {dst}  {antes[:12]} -> {nuevo[:12]}")
    else:
        log(f"   [cambia] {dst}  {antes[:12]} -> {nuevo[:12]}")
log("")
log("RESULTADO: " + ("TODO OK" if not fallos else f"{fallos} FALLO(S)"))
if not A.simular:
    log("Siguiente: C:\\Notas_IA\\scripts\\comfyui\\03_instalar_mcp_comfyui.bat (con ComfyUI arrancado o no: lo arranca)")
inf = NOTAS / "inventario" / "auto" / f"publicacion_mcp_comfyui_{dt.datetime.now():%Y%m%d_%H%M}.txt"
if not A.simular and inf.parent.exists():
    inf.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"Informe: {inf}")
sys.exit(1 if fallos else 0)
