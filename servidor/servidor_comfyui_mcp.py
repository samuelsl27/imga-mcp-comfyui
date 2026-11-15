"""servidor_comfyui_mcp.py - MCP "comfyui" de IMGA (spec 006 de C:\\Notas_IA)

Servidor MCP (stdio) que deja a Claude Desktop (y a otras apps de IA) generar y editar imagenes
con el ComfyUI LOCAL del MS-S1 (http://127.0.0.1:8188), usando los flujos en formato API
exportados de las plantillas oficiales (carpeta flujos\\):

  generar_rapido.json  Z-Image Turbo (texto -> imagen, rapido)
  generar_texto.json   Qwen-Image 2512 + LoRA Lightning 4 pasos (rotulos y texto legible)
  editar.json          Qwen-Image-Edit 2511 + LoRA Lightning 4 pasos (1-3 imagenes de referencia)

Todo lo que genera aparece tambien en la cola/historial de ComfyUI (misma instancia) y se guarda en
C:\\IA_Imagenes\\AAAA-MM-DD\\ con un .json al lado (prompt, semilla, flujo, entradas, tiempo).

Variables de entorno (opcionales):
  COMFY_URL            (por defecto http://127.0.0.1:8188)
  IA_IMAGENES          (por defecto C:\\IA_Imagenes)
  COMFY_MCP_ESPERA     segundos que una herramienta espera al resultado antes de devolver
                       "en curso" (por defecto 50; luego se usa esperar_resultado). Incluye el arranque.
  COMFY_MCP_AUTOARRANQUE  1 (por defecto) = si ComfyUI no responde, lo arranca solo; 0 = no
  COMFY_LANZADOR       lanzador del servidor de ComfyUI (por defecto C:\\ComfyUI\\comfyui-launch.bat)
  COMFY_MCP_ARRANQUE   segundos maximos esperando a que ComfyUI arranque (por defecto 40)

Arranque automatico (v1.1.0): estado, generar_imagen, editar_imagen y retocar_ultima arrancan ComfyUI si
no responde: el mismo lanzador y la misma ventana minimizada "ComfyUI servidor" que el acceso directo,
desligada de la app cliente (sigue en marcha aunque se cierre Claude/Bionic/Hermes/LM Studio) y con el
entorno completo de Windows (Hermes solo pasa unas pocas variables). No arranca dos veces: comprueba si
ya hay un python main.py --port 8188 en marcha o un arranque de hace <20 s (C:\\IA_Imagenes\\.arranque_comfyui).
"""
from __future__ import annotations

import base64
import datetime as dt
import io
import json
import os
import random
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from mcp.server.fastmcp import FastMCP, Image
from PIL import Image as PILImage

VERSION = "1.1.0"
COMFY = os.environ.get("COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
BASE = Path(os.environ.get("IA_IMAGENES", r"C:\IA_Imagenes"))
ENTRADA = BASE / "entrada"
ESPERA = float(os.environ.get("COMFY_MCP_ESPERA", "50"))
FLUJOS = Path(__file__).resolve().parent / "flujos"
ESTADO = BASE / "ultima.json"
CLIENTE = "mcp-comfyui-" + uuid.uuid4().hex[:8]
AUTOARRANQUE = os.environ.get("COMFY_MCP_AUTOARRANQUE", "1").strip() != "0"
LANZADOR_COMFY = Path(os.environ.get("COMFY_LANZADOR", r"C:\ComfyUI\comfyui-launch.bat"))
ARRANQUE = float(os.environ.get("COMFY_MCP_ARRANQUE", "40"))
MARCA_ARRANQUE = BASE / ".arranque_comfyui"
TITULO_VENTANA = "ComfyUI servidor"
SIN_VENTANA = 0x08000000  # CREATE_NO_WINDOW

mcp = FastMCP("comfyui")


# ------------------------------------------------------------------ utilidades HTTP
def _http(ruta: str, datos: bytes | None = None, tipo: str | None = None, timeout: float = 30):
    req = urllib.request.Request(COMFY + ruta, data=datos)
    if tipo:
        req.add_header("Content-Type", tipo)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _json(ruta: str, cuerpo: dict | None = None, timeout: float = 30):
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    try:
        return json.loads(_http(ruta, datos, "application/json" if datos else None, timeout) or b"null")
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", "replace")[:1500]
        raise RuntimeError(f"ComfyUI respondio {e.code} en {ruta}: {detalle}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"No se puede conectar con ComfyUI en {COMFY} ({e.reason}). Arrancalo con el acceso directo "
            "'ComfyUI' del escritorio (C:\\ComfyUI\\comfyui-app.bat) y vuelve a intentarlo.") from None


# ------------------------------------------------------------------ arranque automatico de ComfyUI
def _responde(timeout: float = 3) -> bool:
    try:
        _http("/system_stats", timeout=timeout)
        return True
    except Exception:
        return False


def _entorno_completo() -> dict:
    """Entorno de usuario completo leido del registro (como el de una ventana abierta desde el escritorio),
    con lo que traiga el proceso por encima. Hace falta porque Hermes solo pasa unas pocas variables.
    Las claves se guardan sin distinguir mayusculas (como en Windows) para no duplicar Path/PATH."""
    env: dict[str, tuple[str, str]] = {}  # MAYUSCULAS -> (nombre, valor)

    def poner(nombre: str, valor: str):
        env[nombre.upper()] = (env.get(nombre.upper(), (nombre, ""))[0], valor)

    def valor(nombre: str, defecto: str = "") -> str:
        return env.get(nombre.upper(), (nombre, os.environ.get(nombre, defecto)))[1]

    if os.name == "nt":
        import winreg

        def expandir(v: str) -> str:
            return re.sub(r"%([^%]+)%", lambda m: valor(m.group(1)) or m.group(0), v)

        def leer(raiz, clave, anadir_path=False):
            try:
                with winreg.OpenKey(raiz, clave) as k:
                    i = 0
                    while True:
                        try:
                            nombre, v, tipo = winreg.EnumValue(k, i)
                        except OSError:
                            break
                        i += 1
                        if not isinstance(v, str):
                            continue
                        v = expandir(v) if tipo == winreg.REG_EXPAND_SZ else v
                        if anadir_path and nombre.upper() == "PATH" and valor("PATH"):
                            v = valor("PATH").rstrip(";") + ";" + v
                        poner(nombre, v)
            except OSError:
                pass

        poner("SystemRoot", os.environ.get("SystemRoot", r"C:\Windows"))
        leer(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")
        leer(winreg.HKEY_CURRENT_USER, "Volatile Environment")
        leer(winreg.HKEY_CURRENT_USER, "Environment", anadir_path=True)
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SYSTEM\CurrentControlSet\Control\ComputerName\ActiveComputerName") as k:
                poner("COMPUTERNAME", winreg.QueryValueEx(k, "ComputerName")[0])
        except OSError:
            pass
    path_registro = valor("PATH") if "PATH" in env else ""
    for k, v in os.environ.items():  # lo del proceso manda (en Claude/LM Studio/Bionic es el entorno completo)
        if k.upper() not in ("VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME"):
            poner(k, v)
    if len(path_registro) > len(valor("PATH")):  # Hermes: PATH corto o ausente -> el del registro
        poner("Path", path_registro)
    for k in ("VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME"):
        env.pop(k, None)
    return {n: v for n, v in env.values()}


def _proceso_comfy(env: dict) -> bool:
    """True si ya hay un python main.py --port 8188 en marcha (p. ej. arrancando y aun sin responder)."""
    if os.name != "nt":
        return False
    ps = Path(env.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    orden = ("@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object { $_.CommandLine -like '*main.py*--port 8188*' }).Count")
    cod = base64.b64encode(orden.encode("utf-16-le")).decode("ascii")  # sin problemas de comillas
    try:
        r = subprocess.run([str(ps), "-NoProfile", "-NonInteractive", "-EncodedCommand", cod], capture_output=True,
                           text=True, errors="replace", env=env, timeout=20, creationflags=SIN_VENTANA,
                           stdin=subprocess.DEVNULL)
        return int((r.stdout or "0").strip() or 0) > 0
    except Exception:
        return False


def _arrancar_comfy(env: dict):
    """Arranca el servidor como el acceso directo: ventana minimizada 'ComfyUI servidor', desligada del cliente."""
    if not LANZADOR_COMFY.exists():
        raise RuntimeError(f"ComfyUI no responde y no encuentro su lanzador {LANZADOR_COMFY}.")
    cmd = env.get("ComSpec") or str(Path(env.get("SystemRoot", r"C:\Windows")) / "System32" / "cmd.exe")
    args = [cmd, "/d", "/c", "start", TITULO_VENTANA, "/min", cmd, "/d", "/c", str(LANZADOR_COMFY)]
    base = SIN_VENTANA | 0x00000200  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    for flags in (base | 0x01000000, base):  # primero fuera del 'job' del cliente (CREATE_BREAKAWAY_FROM_JOB)
        try:
            subprocess.Popen(args, env=env, cwd=str(LANZADOR_COMFY.parent), creationflags=flags, close_fds=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except OSError:
            continue
    raise RuntimeError("No se pudo lanzar ComfyUI.")


def _asegurar_comfy(limite: float | None = None) -> str:
    """Si ComfyUI no responde, lo arranca y espera. Devuelve '' si ya estaba, o una nota si lo ha arrancado."""
    if _responde():
        return ""
    if not AUTOARRANQUE:
        _json("/system_stats")  # lanza el error con la indicacion de arrancarlo a mano
    t0 = time.time()
    limite = min(ARRANQUE, limite) if limite else ARRANQUE
    env = _entorno_completo()
    # otro cliente acaba de lanzarlo (aun sin proceso python) o ya hay un main.py en marcha que no responde todavia
    reciente = MARCA_ARRANQUE.exists() and time.time() - MARCA_ARRANQUE.stat().st_mtime < 20
    if reciente or _proceso_comfy(env):
        nota = "ComfyUI ya se estaba arrancando"
    else:
        BASE.mkdir(parents=True, exist_ok=True)
        MARCA_ARRANQUE.write_text(dt.datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
        _arrancar_comfy(env)
        nota = "ComfyUI estaba parado: lo he arrancado (ventana minimizada 'ComfyUI servidor')"
    while time.time() - t0 < limite:
        time.sleep(2)
        if _responde():
            return f"{nota}; listo en {round(time.time() - t0)} s. "
    raise RuntimeError(f"{nota}, pero aun no responde tras {round(time.time() - t0)} s (suele tardar 15-30 s). "
                       "Vuelve a llamar a esta misma herramienta en unos 20 s. Si sigue sin responder, mirar la "
                       "ventana 'ComfyUI servidor' de la barra de tareas.")


def _subir(ruta: Path) -> str:
    """Sube una imagen a la carpeta input de ComfyUI y devuelve el nombre con el que queda."""
    lim = "----imga" + uuid.uuid4().hex
    nombre = f"imga_{uuid.uuid4().hex[:8]}_{ruta.name}"
    cuerpo = io.BytesIO()
    for campo, valor in (("overwrite", "true"), ("type", "input")):
        cuerpo.write(f"--{lim}\r\nContent-Disposition: form-data; name=\"{campo}\"\r\n\r\n{valor}\r\n".encode())
    cuerpo.write(f"--{lim}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{nombre}\"\r\n"
                 f"Content-Type: application/octet-stream\r\n\r\n".encode())
    cuerpo.write(ruta.read_bytes())
    cuerpo.write(f"\r\n--{lim}--\r\n".encode())
    r = json.loads(_http("/upload/image", cuerpo.getvalue(), f"multipart/form-data; boundary={lim}", 120))
    return (r.get("subfolder") + "/" if r.get("subfolder") else "") + r["name"]


# ------------------------------------------------------------------ flujos
def _flujo(nombre: str) -> dict:
    f = FLUJOS / f"{nombre}.json"
    if not f.exists():
        raise RuntimeError(f"Falta el flujo {f}. Reinstala el MCP (03_instalar_mcp_comfyui.bat).")
    return json.loads(f.read_text(encoding="utf-8"))


def _nodo(g: dict, clase: str, titulo: str | None = None) -> str:
    for nid, n in g.items():
        if n.get("class_type") == clase and (titulo is None or titulo.lower() in n.get("_meta", {}).get("title", "").lower()):
            return nid
    raise RuntimeError(f"El flujo no tiene un nodo {clase}" + (f" con titulo '{titulo}'" if titulo else ""))


def _semilla(semilla: int | None) -> int:
    return int(semilla) if semilla is not None and int(semilla) >= 0 else random.randint(1, 2**48)


def _resolver_imagen(ref: str) -> Path:
    p = Path(ref)
    candidatos = [p] if p.is_absolute() else [ENTRADA / p, BASE / p, Path.cwd() / p]
    for c in candidatos:
        if c.is_file():
            return c
    raise RuntimeError(f"No encuentro la imagen '{ref}'. Usa una ruta completa o deja el fichero en {ENTRADA}.")


# ------------------------------------------------------------------ ejecucion y resultados
def _lanzar(g: dict, tipo: str, meta: dict) -> str:
    r = _json("/prompt", {"prompt": g, "client_id": CLIENTE})
    pid = r["prompt_id"]
    pend = BASE / "pendientes"
    pend.mkdir(parents=True, exist_ok=True)
    (pend / f"{pid}.json").write_text(json.dumps({"tipo": tipo, "lanzado": dt.datetime.now().isoformat(timespec="seconds"),
                                                   **meta}, ensure_ascii=False, indent=1), encoding="utf-8")
    return pid


def _historial(pid: str) -> dict | None:
    return (_json(f"/history/{pid}") or {}).get(pid)


def _miniatura(ruta: Path, max_lado: int = 1024) -> Image:
    im = PILImage.open(ruta)
    im.thumbnail((max_lado, max_lado))
    buf = io.BytesIO()
    im.convert("RGB").save(buf, format="JPEG", quality=88)
    return Image(data=buf.getvalue(), format="jpeg")


def _recoger(pid: str):
    """Si el trabajo ha terminado, guarda las imagenes en C:\\IA_Imagenes y devuelve (texto, [Image]) ."""
    h = _historial(pid)
    if not h:
        q = _json("/queue")
        pos = next((i for i, t in enumerate(q.get("queue_pending", [])) if t[1] == pid), None)
        corriendo = any(t[1] == pid for t in q.get("queue_running", []))
        return None, ("ejecutandose" if corriendo else (f"en cola (posicion {pos + 1})" if pos is not None else "desconocido"))
    msgs = {k: v for k, v in h.get("status", {}).get("messages", [])}
    if "execution_error" in msgs:
        e = msgs["execution_error"]
        return (f"ERROR en ComfyUI (nodo {e.get('node_type')}): {str(e.get('exception_message'))[:800]}", []), "error"
    t0 = msgs.get("execution_start", {}).get("timestamp")
    t1 = msgs.get("execution_success", {}).get("timestamp")
    segundos = round((t1 - t0) / 1000, 1) if t0 and t1 else None
    pend = BASE / "pendientes" / f"{pid}.json"
    meta = json.loads(pend.read_text(encoding="utf-8")) if pend.exists() else {"tipo": "?"}
    dia = BASE / dt.date.today().isoformat()
    dia.mkdir(parents=True, exist_ok=True)
    rutas, imagenes = [], []
    for out in h.get("outputs", {}).values():
        for im in out.get("images", []):
            if im.get("type") != "output":
                continue
            q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""), "type": "output"})
            datos = _http(f"/view?{q}", timeout=120)
            destino = dia / f"{dt.datetime.now():%H%M%S}_{meta.get('tipo', 'img')}_{len(rutas) + 1}.png"
            destino.write_bytes(datos)
            rutas.append(destino)
            imagenes.append(_miniatura(destino))
    meta.update({"prompt_id": pid, "segundos": segundos, "resultados": [str(r) for r in rutas],
                 "comfyui": [f"{im.get('subfolder', '')}/{im['filename']}" for o in h.get("outputs", {}).values()
                             for im in o.get("images", [])]})
    for r in rutas:
        r.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    if rutas:
        ESTADO.write_text(json.dumps({"ruta": str(rutas[0]), **meta}, ensure_ascii=False, indent=1), encoding="utf-8")
    if pend.exists():
        pend.unlink()
    texto = (f"Hecho en {segundos} s. Guardado en: " + ", ".join(str(r) for r in rutas) +
             f". Semilla {meta.get('semilla')}. (Tambien en el historial de ComfyUI.)")
    return (texto, imagenes), "hecho"


def _con_nota(nota: str, res: list):
    if nota and res and isinstance(res[0], str):
        res[0] = nota + res[0]
    return res


def _esperar(pid: str, espera: float | None = None):
    limite = time.time() + (ESPERA if espera is None else espera)
    while True:
        res, estado = _recoger(pid)
        if res is not None:
            texto, imgs = res
            return [texto, *imgs]
        if time.time() >= limite:
            return [f"Sigue {estado} en ComfyUI (id {pid}). La primera vez que se usa un modelo tarda "
                    f"mas porque lo carga en memoria. Llama a esperar_resultado con prompt_id='{pid}'."]
        time.sleep(2)


# ------------------------------------------------------------------ herramientas
@mcp.tool()
def estado() -> str:
    """Estado del ComfyUI local: si responde, version, memoria libre (GPU y RAM), cola, flujos y carpetas.
    Si ComfyUI no esta arrancado, lo arranca (tarda 15-30 s)."""
    nota = _asegurar_comfy()
    s = _json("/system_stats")
    q = _json("/queue")
    d = (s.get("devices") or [{}])[0]
    sysd = s.get("system", {})
    flujos = sorted(p.stem for p in FLUJOS.glob("*.json"))
    return json.dumps({
        "comfyui": sysd.get("comfyui_version"), "pytorch": sysd.get("pytorch_version"), "url": COMFY,
        "argumentos": sysd.get("argv"), "gpu": d.get("name"),
        "memoria_gpu_libre_GB": round((d.get("vram_free") or 0) / 1e9, 1),
        "memoria_gpu_total_GB": round((d.get("vram_total") or 0) / 1e9, 1),
        "ram_libre_GB": round((sysd.get("ram_free") or 0) / 1e9, 1),
        "cola": {"ejecutando": len(q.get("queue_running", [])), "pendientes": len(q.get("queue_pending", []))},
        "flujos": flujos, "carpeta_resultados": str(BASE), "carpeta_referencias": str(ENTRADA),
        "ultima_imagen": json.loads(ESTADO.read_text(encoding="utf-8")).get("ruta") if ESTADO.exists() else None,
        "mcp": VERSION, "autoarranque": AUTOARRANQUE,
        **({"arranque": nota.strip()} if nota else {}),
    }, ensure_ascii=False, indent=1)


@mcp.tool()
def generar_imagen(prompt: str, modo: str = "rapido", ancho: int | None = None, alto: int | None = None,
                   semilla: int | None = None):
    """Genera una imagen desde texto con el ComfyUI local y la devuelve.
    modo="rapido": Z-Image Turbo (por defecto 1024x1024): ~20 s con el modelo cargado, ~50 s si hay que cargarlo.
    modo="texto": Qwen-Image 2512 con LoRA de 4 pasos (por defecto 1328x1328): ~35 s cargado, ~2,5 min si hay
    que cargarlo; mejor para carteles y rotulos legibles (los acentos pueden salir mal: revisar).
    Cambiar de modo/herramienta obliga a ComfyUI a cargar otro modelo: agrupar los trabajos del mismo tipo.
    ancho/alto en pixeles (multiplos de 16 recomendados). semilla fija para repetir un resultado.
    El prompt puede ir en espanol o en ingles; describir escena, estilo, luz y encuadre.
    Si ComfyUI no esta arrancado, lo arranca solo."""
    t0 = time.time()
    nota = _asegurar_comfy(ESPERA - 10)
    s = _semilla(semilla)
    if modo == "texto":
        g = _flujo("generar_texto")
        g[_nodo(g, "CLIPTextEncode", "positive")]["inputs"]["text"] = prompt
        lat = _nodo(g, "EmptySD3LatentImage")
        tipo = "texto"
    else:
        g = _flujo("generar_rapido")
        g[_nodo(g, "CLIPTextEncode")]["inputs"]["text"] = prompt
        lat = _nodo(g, "EmptySD3LatentImage")
        tipo = "rapido"
    if ancho:
        g[lat]["inputs"]["width"] = int(ancho)
    if alto:
        g[lat]["inputs"]["height"] = int(alto)
    g[_nodo(g, "KSampler")]["inputs"]["seed"] = s
    g[_nodo(g, "SaveImage")]["inputs"]["filename_prefix"] = f"IMGA/{tipo}"
    pid = _lanzar(g, tipo, {"flujo": "generar_" + tipo, "prompt": prompt, "semilla": s,
                            "ancho": g[lat]["inputs"]["width"], "alto": g[lat]["inputs"]["height"]})
    return _con_nota(nota, _esperar(pid, max(5.0, ESPERA - (time.time() - t0))))


def _editar(instruccion: str, refs: list[Path], semilla: int | None, tipo: str):
    if not 1 <= len(refs) <= 3:
        raise RuntimeError("editar_imagen admite de 1 a 3 imagenes de referencia.")
    t0 = time.time()
    nota = _asegurar_comfy(ESPERA - 10)
    g = _flujo("editar")
    s = _semilla(semilla)
    cargas = [nid for nid, n in g.items() if n.get("class_type") == "LoadImage"]
    cod = [nid for nid, n in g.items() if n.get("class_type") == "TextEncodeQwenImageEditPlus"]
    pos = _nodo(g, "TextEncodeQwenImageEditPlus", "positive")
    # imagen 1: el nodo LoadImage que alimenta la escala (FluxKontextImageScale) del flujo
    esc = _nodo(g, "FluxKontextImageScale")
    n1 = g[esc]["inputs"]["image"][0]
    otros = [c for c in cargas if c != n1]
    subidas = [_subir(r) for r in refs]
    g[n1]["inputs"]["image"] = subidas[0]
    for c in otros:  # se rehacen las entradas 2 y 3
        del g[c]
    for k in cod:
        for e in ("image2", "image3"):
            g[k]["inputs"].pop(e, None)
    for i, nombre in enumerate(subidas[1:], start=2):
        nid = f"imga_ref{i}"
        g[nid] = {"inputs": {"image": nombre}, "class_type": "LoadImage", "_meta": {"title": f"Referencia {i}"}}
        for k in cod:
            g[k]["inputs"][f"image{i}"] = [nid, 0]
    g[pos]["inputs"]["prompt"] = instruccion
    g[_nodo(g, "KSampler")]["inputs"]["seed"] = s
    g[_nodo(g, "SaveImage")]["inputs"]["filename_prefix"] = f"IMGA/{tipo}"
    pid = _lanzar(g, tipo, {"flujo": "editar", "instruccion": instruccion, "semilla": s,
                            "referencias": [str(r) for r in refs]})
    return _con_nota(nota, _esperar(pid, max(5.0, ESPERA - (time.time() - t0))))


@mcp.tool()
def editar_imagen(instruccion: str, imagenes: list[str], semilla: int | None = None):
    """Edita o crea una imagen a partir de 1 a 3 imagenes de referencia (Qwen-Image-Edit 2511, 4 pasos).
    imagenes: rutas completas, o nombres de ficheros que esten en C:\\IA_Imagenes\\entrada.
    En la instruccion, referirse a ellas como 'imagen 1', 'imagen 2'... (p. ej. 'pon el camion de la imagen 2
    en la escena de la imagen 1'). La imagen 1 marca el encuadre y el tamano del resultado.
    Tiempo: ~40 s con el modelo cargado; ~90 s la primera vez o despues de usar otro modo.
    Las imagenes adjuntadas en el chat NO llegan aqui: tienen que estar en disco."""
    return _editar(instruccion, [_resolver_imagen(i) for i in imagenes], semilla, "editar")


@mcp.tool()
def retocar_ultima(instruccion: str, imagenes_extra: list[str] | None = None, semilla: int | None = None):
    """Aplica un cambio a la ULTIMA imagen generada o editada (encadena retoques sin repetir rutas).
    imagenes_extra: hasta 2 referencias adicionales (serian 'imagen 2' e 'imagen 3' en la instruccion)."""
    if not ESTADO.exists():
        raise RuntimeError("Todavia no hay ninguna imagen anterior: usa generar_imagen o editar_imagen.")
    ultima = Path(json.loads(ESTADO.read_text(encoding="utf-8"))["ruta"])
    refs = [ultima] + [_resolver_imagen(i) for i in (imagenes_extra or [])]
    return _editar(instruccion, refs, semilla, "retoque")


@mcp.tool()
def esperar_resultado(prompt_id: str, segundos: float = 50):
    """Espera (hasta 'segundos') a un trabajo lanzado antes y devuelve la imagen cuando termine."""
    return _esperar(prompt_id, segundos)


@mcp.tool()
def ver_imagen(ruta: str, max_lado: int = 1024):
    """Devuelve una imagen del disco para verla en el chat (reducida a max_lado pixeles)."""
    p = _resolver_imagen(ruta)
    return [f"{p} ({PILImage.open(p).size[0]}x{PILImage.open(p).size[1]} px)", _miniatura(p, max_lado)]


@mcp.tool()
def listar_resultados(cuantos: int = 10) -> str:
    """Lista las ultimas imagenes guardadas en C:\\IA_Imagenes con su prompt/instruccion, semilla y tiempo."""
    fichas = sorted(BASE.glob("20??-??-??/*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:max(1, cuantos)]
    filas = []
    for f in fichas:
        m = json.loads(f.read_text(encoding="utf-8"))
        filas.append({"imagen": str(f.with_suffix(".png")), "flujo": m.get("flujo"),
                      "texto": m.get("prompt") or m.get("instruccion"), "semilla": m.get("semilla"),
                      "segundos": m.get("segundos"), "referencias": m.get("referencias")})
    return json.dumps(filas, ensure_ascii=False, indent=1)


@mcp.tool()
def liberar_memoria() -> str:
    """Descarga los modelos de ComfyUI de la memoria (p. ej. antes de cargar un modelo grande en LM Studio).
    La siguiente imagen tardara mas porque tendra que volver a cargarlos."""
    if not _responde():
        return "ComfyUI no esta arrancado: no hay nada que liberar."
    _json("/free", {"unload_models": True, "free_memory": True})
    time.sleep(2)
    s = _json("/system_stats")
    return (f"Modelos descargados. RAM libre {round(s['system']['ram_free'] / 1e9, 1)} GB, "
            f"memoria GPU libre {round(s['devices'][0]['vram_free'] / 1e9, 1)} GB.")


def main():
    for d in (BASE, ENTRADA):
        d.mkdir(parents=True, exist_ok=True)
    mcp.run()


if __name__ == "__main__":
    main()
