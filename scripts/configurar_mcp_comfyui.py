"""configurar_mcp_comfyui.py - Spec 006 de C:\\Notas_IA (T6) - rev3 (2026-11-15)

Anade (o sustituye) la entrada "comfyui" en Claude Desktop, LM Studio y Hermes Agent,
SIN tocar los demas servidores (qgis, bricscad, word, vectorcraft, pdfcraft, blender...) ni el resto
de cada configuracion. Copia previa de cada fichero en C:\\Notas_IA\\copias_seguridad\\AAAAMMDD_HHMM\\.
Bionic no lee ficheros: se configura desde su UI (las instrucciones salen al final del informe).

  - Claude Desktop (MSIX): %LOCALAPPDATA%\\Claude-Data\\claude_*\\claude_desktop_config.json.
    Solo si Claude Desktop esta CERRADO (si esta abierto reescribe el fichero): si esta abierto se
    salta y queda PENDIENTE -> repetir con Claude cerrado:  04_configurar_mcp_comfyui.bat --solo claude-desktop
  - LM Studio: %USERPROFILE%\\.lmstudio\\mcp.json (se puede editar con LM Studio abierto: recarga al guardar)
  - Hermes:    %LOCALAPPDATA%\\hermes\\config.yaml (HERMES_HOME), clave mcp_servers, con bloque env
    (Hermes no pasa todo el entorno de Windows a los MCP). Recargar: /reload-mcp o reiniciar Hermes.
Despues prueba el lanzador por stdio dos veces: con el entorno completo (Claude/LM Studio/Bionic) y
SOLO con el bloque env de Hermes (lo mas restrictivo).

  uv run --no-project --python 3.13 --with ruamel.yaml python configurar_mcp_comfyui.py --informe F
        [--solo claude-desktop,lmstudio,hermes] [--sin-prueba]
        [--claude-config RUTA] [--lmstudio-config RUTA] [--hermes-config RUTA]   (rutas alternativas, pruebas)
"""
import argparse
import datetime as dt
import glob
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ap = argparse.ArgumentParser()
ap.add_argument("--informe", required=True)
ap.add_argument("--solo", default="", help="lista separada por comas: claude-desktop,lmstudio,hermes")
ap.add_argument("--sin-prueba", action="store_true", help="no prueba el lanzador por stdio")
ap.add_argument("--claude-config", default="")
ap.add_argument("--lmstudio-config", default="")
ap.add_argument("--hermes-config", default="")
A = ap.parse_args()

NOMBRE = "comfyui"
NOTAS = Path(os.environ.get("NOTAS_IA", r"C:\Notas_IA"))
PLANT = NOTAS / "mcp" / "comfyui" / "plantillas"
LANZ = r"C:\ComfyUI_MCP\comfyui-mcp-launch.bat"
CMD = r"C:\Windows\System32\cmd.exe"
ENTRY = {"command": CMD, "args": ["/d", "/c", LANZ]}
COMENTARIO = "MCP comfyui de IMGA: imagenes con ComfyUI local (C:\\Notas_IA, spec 006)"
HOME = Path(os.environ.get("USERPROFILE", str(Path.home())))
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", str(HOME / "AppData" / "Local")))
ENV_HERMES = ("USERPROFILE", "LOCALAPPDATA", "APPDATA", "SystemRoot", "TEMP", "TMP",
              "USERNAME", "HOMEDRIVE", "HOMEPATH", "ProgramFiles", "ProgramW6432")
TS = dt.datetime.now().strftime("%Y%m%d_%H%M")
BACKUP = NOTAS / "copias_seguridad" / TS
LINEAS, FALLOS, PENDIENTES = [], [], []


def log(m=""):
    print(m, flush=True)
    LINEAS.append(str(m))


def paso(n, ok, d=""):
    log(f"   [{'OK ' if ok else 'FALLO'}] {n}{(' - ' + d) if d else ''}")
    if not ok:
        FALLOS.append(n)
    return ok


def terminar():
    log("")
    if PENDIENTES:
        log("PENDIENTE: " + " | ".join(PENDIENTES))
    log("RESULTADO: " + ("TODO OK" if not FALLOS else f"{len(FALLOS)} FALLO(S): {', '.join(FALLOS)}")
        + (" (con pendientes)" if PENDIENTES and not FALLOS else ""))
    p = Path(A.informe)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(LINEAS) + "\n", encoding="utf-8")
    sys.exit(0 if not FALLOS else 1)


def backup(p: Path) -> Path:
    BACKUP.mkdir(parents=True, exist_ok=True)
    base = re.sub(r"[:\\/]+", "_", str(p)).strip("_")
    dst, n = BACKUP / base, 2
    while dst.exists():  # dos ejecuciones en el mismo minuto: no pisar la copia del estado original
        dst, n = BACKUP / f"{base}.{n}", n + 1
    shutil.copy2(p, dst)
    with open(BACKUP / "rutas.txt", "a", encoding="utf-8") as f:
        f.write(f"{dst.name}\t{p}\n")
    if dst.read_bytes() != p.read_bytes():
        raise RuntimeError(f"la copia {dst} no coincide con el original")
    return dst


def write_atomic(p: Path, text: str):
    tmp = p.with_name(p.name + ".tmp_notas_ia")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, p)


def load_json(p: Path):
    txt = p.read_text(encoding="utf-8-sig")
    return {} if not txt.strip() else json.loads(txt)


def merge_json(p: Path, create=False):
    """data['mcpServers']['comfyui'] = ENTRY conservando todo lo demas. Devuelve (ok, detalle)."""
    if not p.exists():
        if not create:
            return False, f"{p} NO EXISTE (no se crea)"
        p.parent.mkdir(parents=True, exist_ok=True)
        data, bk = {}, None
    else:
        try:
            data = load_json(p)
        except Exception as e:
            return False, f"{p}: JSON invalido, NO se modifica ({e})"
        bk = backup(p)
    if not isinstance(data, dict) or not isinstance(data.setdefault("mcpServers", {}), dict):
        return False, f"{p}: forma inesperada (raiz o mcpServers no son objetos), NO se modifica"
    servers = data["mcpServers"]
    antes_resto = {k: v for k, v in data.items() if k != "mcpServers"}
    antes_otros = {k: v for k, v in servers.items() if k != NOMBRE}
    accion = "sustituida" if NOMBRE in servers else "anadida"
    servers[NOMBRE] = ENTRY
    write_atomic(p, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    chk = load_json(p)
    cs = chk.get("mcpServers", {})
    ok = (cs.get(NOMBRE) == ENTRY and {k: v for k, v in cs.items() if k != NOMBRE} == antes_otros
          and {k: v for k, v in chk.items() if k != "mcpServers"} == antes_resto)
    return ok, (f"{p}: entrada {NOMBRE} {accion}; otros MCP sin cambios: {sorted(antes_otros) or 'ninguno'}; "
                f"resto del fichero sin cambios" + ("" if bk is None else f"; copia: {bk.name}"))


def claude_abierto():
    if os.name != "nt":
        return 0
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq claude.exe", "/FO", "CSV", "/NH"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return len([l for l in r.stdout.splitlines() if l.lower().startswith('"claude.exe"')])


def conf_claude_desktop():
    n = claude_abierto() if not A.claude_config else 0
    if n:
        log(f"   [SALTADO] Claude Desktop esta abierto ({n} procesos claude.exe): no se toca su config.")
        PENDIENTES.append("Claude Desktop: cerrarlo del todo (tambien la bandeja) y ejecutar "
                          "04_configurar_mcp_comfyui.bat --solo claude-desktop")
        return
    cands = [A.claude_config] if A.claude_config else sorted(
        glob.glob(str(LOCALAPPDATA / "Claude-Data" / "claude_*" / "claude_desktop_config.json")))
    if not paso("config de Claude Desktop localizada", bool(cands),
                "; ".join(cands) or r"no hay %LOCALAPPDATA%\Claude-Data\claude_*\claude_desktop_config.json"):
        return
    for c in cands:
        ok, d = merge_json(Path(c))
        paso("Claude Desktop", ok, d)
    log("   Abrir Claude Desktop -> Configuracion -> Desarrollador: 'comfyui' debe salir en ejecucion.")


def conf_lmstudio():
    p = Path(A.lmstudio_config) if A.lmstudio_config else HOME / ".lmstudio" / "mcp.json"
    ok, d = merge_json(p, create=True)
    paso("LM Studio", ok, d)
    log("   En cada chat: activar la integracion mcp/comfyui (boton de herramientas junto al cuadro de mensaje).")


def hermes_config_path():
    if A.hermes_config:
        return Path(A.hermes_config)
    for c in [os.environ.get("HERMES_HOME"), LOCALAPPDATA / "hermes", HOME / ".hermes"]:
        if c and (Path(c) / "config.yaml").exists():
            return Path(c) / "config.yaml"
    return None


def insertar_yaml(text, value, envs):
    """Inserta comfyui al final del bloque mcp_servers sin reescribir el resto del fichero.
    Si ya existe o el bloque no tiene la forma esperada, reescribe con ruamel (conserva comentarios)."""
    lines = text.split("\n")
    idx = next((i for i, l in enumerate(lines) if re.match(r"^mcp_servers[ \t]*:\s*$", l)), None)
    if idx is not None:
        j = idx + 1
        child = []
        while j < len(lines) and (lines[j].strip() == "" or lines[j].startswith((" ", "\t", "#"))):
            if lines[j].strip() and not lines[j].lstrip().startswith("#"):
                child.append(lines[j])
            j += 1
        if child:
            ind = len(child[0]) - len(child[0].lstrip(" "))
            ya = any(re.match(rf"^ {{{ind}}}{NOMBRE}[ \t]*:", c) for c in child)
            if not ya and ind > 0:
                sp = " " * ind
                blk = [f"{sp}{NOMBRE}:  # {COMENTARIO}",
                       f"{sp}  command: {json.dumps(value['command'])}",
                       f"{sp}  args: [" + ", ".join(json.dumps(a) for a in value["args"]) + "]",
                       f"{sp}  env:"] + [f"{sp}    {k}: {json.dumps(v)}" for k, v in envs.items()]
                last = idx
                for k in range(idx + 1, j):
                    if lines[k].strip():
                        last = k
                lines[last + 1:last + 1] = blk
                return "\n".join(lines), "insertado al final de mcp_servers (resto del texto intacto)"
    from io import StringIO
    from ruamel.yaml import YAML
    y = YAML()
    y.preserve_quotes = True
    y.width = 100000
    data = y.load(text)
    if data.get("mcp_servers") is None:
        data["mcp_servers"] = {}
    data["mcp_servers"][NOMBRE] = value
    buf = StringIO()
    y.dump(data, buf)
    return buf.getvalue(), "escrito con ruamel (ya existia o forma no estandar; comentarios conservados)"


def env_hermes():
    return {k: os.environ[k] for k in ENV_HERMES if os.environ.get(k)}


def conf_hermes():
    p = hermes_config_path()
    if not paso("config.yaml de Hermes localizado", bool(p and p.exists()),
                str(p) if p else r"ni HERMES_HOME, ni %LOCALAPPDATA%\hermes, ni ~\.hermes"):
        return
    from ruamel.yaml import YAML
    text = p.read_text(encoding="utf-8-sig")
    antes = YAML(typ="safe").load(text) or {}
    antes_ms = antes.get("mcp_servers") or {}
    bk = backup(p)
    envs = env_hermes()
    valor = {**ENTRY, "env": envs}
    nuevo, modo = insertar_yaml(text, valor, envs)
    YAML(typ="safe").load(nuevo)  # si no es YAML valido, excepcion antes de escribir
    write_atomic(p, nuevo)
    chk = YAML(typ="safe").load(p.read_text(encoding="utf-8")) or {}
    ms = chk.get("mcp_servers") or {}
    e = ms.get(NOMBRE) or {}
    paso("Hermes", e.get("command") == CMD and e.get("args") == ENTRY["args"] and e.get("env") == envs,
         f"{p}: {NOMBRE} {modo}; copia: {bk.name}")
    paso("Hermes: otros MCP sin cambios", all(ms.get(k) == v for k, v in antes_ms.items() if k != NOMBRE),
         ", ".join(k for k in ms if k != NOMBRE) or "(ninguno)")
    paso("Hermes: resto de config.yaml sin cambios",
         {k: v for k, v in chk.items() if k != "mcp_servers"} == {k: v for k, v in antes.items() if k != "mcp_servers"})
    log("   Recargar en Hermes: /reload-mcp (o reiniciarlo) y pulsar 'Activar' en el servidor comfyui.")


def prueba_stdio(etiqueta, env):
    """initialize -> tools/list -> estado por el lanzador, como lo haria una app cliente."""
    try:
        pr = subprocess.Popen([CMD, "/d", "/c", LANZ], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=env, cwd=str(Path(LANZ).parent))
    except Exception as ex:
        paso(f"stdio ({etiqueta}): arranque", False, f"{type(ex).__name__}: {ex}")
        return
    q = queue.Queue()
    err = []
    threading.Thread(target=lambda: [q.put(l) for l in pr.stdout], daemon=True).start()
    threading.Thread(target=lambda: [err.append(l.decode("utf-8", "replace")) for l in pr.stderr], daemon=True).start()

    def enviar(o):
        pr.stdin.write((json.dumps(o) + "\n").encode("utf-8"))
        pr.stdin.flush()

    def esperar(i, seg):
        fin = time.time() + seg
        while time.time() < fin:
            try:
                l = q.get(timeout=0.5)
            except queue.Empty:
                if pr.poll() is not None:
                    return None
                continue
            try:
                o = json.loads(l)
            except Exception:
                continue
            if o.get("id") == i:
                return o
        return None

    try:
        enviar({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                           "clientInfo": {"name": "notas-ia-04", "version": "3"}}})
        r = esperar(1, 60)
        if not paso(f"stdio ({etiqueta}): initialize", bool(r and "result" in r),
                    (r or {}).get("result", {}).get("serverInfo", {}).get("name", "") if r else
                    ("sin respuesta; stderr: " + "".join(err)[-400:].strip())):
            return
        enviar({"jsonrpc": "2.0", "method": "notifications/initialized"})
        enviar({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        r = esperar(2, 30)
        nombres = [t["name"] for t in (r or {}).get("result", {}).get("tools", [])]
        paso(f"stdio ({etiqueta}): tools/list", len(nombres) == 8, f"{len(nombres)}: {', '.join(nombres)}")
        enviar({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "estado", "arguments": {}}})
        r = esperar(3, 30)
        txt = " ".join(c.get("text", "") for c in (r or {}).get("result", {}).get("content", []) if c.get("type") == "text")
        paso(f"stdio ({etiqueta}): estado", bool(r and "result" in r), re.sub(r"\s+", " ", txt)[:300])
    finally:
        try:
            pr.stdin.close()
        except Exception:
            pass
        try:
            pr.wait(timeout=5)
        except Exception:
            pr.kill()


log(f"CONFIGURAR MCP comfyui EN CLAUDE DESKTOP, LM STUDIO Y HERMES (spec 006, rev3) - {dt.datetime.now():%Y-%m-%d %H:%M:%S}")
log(f"Lanzador: {LANZ}    Copias: {BACKUP}")
log("")
pruebas_fuera = bool(A.claude_config or A.lmstudio_config or A.hermes_config)
if not pruebas_fuera and not Path(LANZ).exists():
    paso("MCP instalado (lanzador)", False, f"no existe {LANZ}: ejecuta antes 03_instalar_mcp_comfyui.bat")
    terminar()

SOLO = [x.strip() for x in A.solo.split(",") if x.strip()]
desconocidas = [s for s in SOLO if s not in ("claude-desktop", "lmstudio", "hermes")]
if desconocidas:
    paso("--solo", False, f"valores no validos: {desconocidas} (usar claude-desktop, lmstudio, hermes)")
    terminar()
for clave, titulo, fn in [("claude-desktop", "Claude Desktop", conf_claude_desktop),
                          ("lmstudio", "LM Studio", conf_lmstudio),
                          ("hermes", "Hermes Agent", conf_hermes)]:
    if SOLO and clave not in SOLO:
        continue
    log(f"== {titulo}")
    try:
        fn()
    except Exception as ex:
        paso(titulo, False, f"{type(ex).__name__}: {ex}")
    log("")

log("== Bionic (no lee ficheros: desde su UI)")
log("   Configuracion -> Integraciones -> MCP -> Agregar MCP personalizado")
log(f"   Nombre {NOMBRE} ; En esta computadora ; Comando {CMD} ;")
log(f"   Argumentos (Mostrar opciones avanzadas) /d  /c  {LANZ} ; tiempo de espera 120 s")
log("")

if not A.sin_prueba and os.name == "nt" and Path(LANZ).exists():
    log("== Prueba del lanzador por stdio (no genera imagenes; 'estado' solo informa si ComfyUI esta arrancado)")
    prueba_stdio("entorno completo: Claude, LM Studio, Bionic", dict(os.environ))
    prueba_stdio("solo env de Hermes", env_hermes())
    log("")
terminar()
