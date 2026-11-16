"""servidor_comfyui_mcp.py - MCP "comfyui" de IMGA (spec 006 de C:\\Notas_IA)

Servidor MCP (stdio) que deja a Claude Desktop (y a otras apps de IA) generar y editar imagenes
con el ComfyUI LOCAL del MS-S1 (http://127.0.0.1:8188), usando los flujos en formato API
exportados de las plantillas oficiales (carpeta flujos\\):

  generar_qwen21.json  Qwen-Image 2.1 (texto -> imagen, calidad; POR DEFECTO desde 1.2.0)
  editar_qwen21.json   Qwen-Image 2.1 (edicion con 1-10 imagenes de referencia; POR DEFECTO desde 1.2.0)
  generar_rapido.json  Z-Image Turbo (texto -> imagen, rapido)
  generar_texto.json   Qwen-Image 2512 + LoRA Lightning 4 pasos (rotulos y texto legible)
  editar.json          Qwen-Image-Edit 2511 + LoRA Lightning 4 pasos (1-3 imagenes de referencia, rapido)
  video_wan.json       Wan 2.2 14B imagen -> video (LoRA lightx2v 4 pasos) + fotograma de muestra (desde 1.3.0)
  video_acabado.json   RelayVSR x2 + 1920x1080 + FILM x2 (32 fps) + fotograma de muestra (desde 1.3.0)
Licencias: Qwen-Image 2.1 = Qwen Research License (investigacion/evaluacion, NO comercial sin licencia de
Qwen); los demas (Wan 2.2, RelayVSR, FILM incluidos), Apache-2.0. Cada imagen guarda en su .json el modelo y la licencia.
Flujos editados desde ComfyUI (menu IMGA -> Guardar como flujo del MCP) en
C:\\ComfyUI\\ComfyUI\\user\\default\\imga_flujos\\ tienen prioridad sobre los instalados, si son validos.

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
  COMFY_MCP_MODELO     qwen21 (por defecto: modo "calidad" = Qwen-Image 2.1) o clasico (modo "calidad" =
                       Qwen 2512 para generar y Qwen-Edit 2511 para editar, todo Apache-2.0)
  COMFY_MCP_VISOR      1 (por defecto) = abre la interfaz de ComfyUI si no esta abierta, para ver lo que hace
                       el MCP (el complemento IMGA abre cada trabajo como pestana); 0 = no
  COMFY_FLUJOS_USUARIO carpeta de flujos editados (por defecto C:\\ComfyUI\\ComfyUI\\user\\default\\imga_flujos)
  COMFY_MCP_REVISAR    1 (por defecto) = avisa si una imagen o el fotograma de un video sale gris/plano o ruido
                       (GPU calculando mal, caso del 2026-11-16); 0 = no revisa

Video (v1.3.0, spec 005): generar_video(prompt, imagen, calidad) devuelve enseguida un prompt_id.
  calidad="borrador"   (por defecto) Wan 2.2 a 832x576, 16 fps, ~8-9 min por 5 s.
  calidad="definitivo" Wan 2.2 a 1280x720 (~23 min) -> RelayVSR x2 -> 1920x1080 -> FILM x2 = 32 fps (~4 min mas).
  Los pasos se encadenan solos (hilo en segundo plano y esperar_resultado) con el estado en
  C:\\IA_Imagenes\\videos_pendientes\\<prompt_id>.json, asi que sobreviven a un reinicio del cliente.
  Resultado: C:\\IA_Imagenes\\AAAA-MM-DD\\HHMMSS_video_<calidad>.mp4 + .png (fotograma) + .json.
  Antes de lanzar comprueba la memoria de la GPU (RF-7): si ComfyUI retiene memoria pide reiniciarlo.
  Medido desde Claude Desktop (2026-11-16): borrador 8,0 min, definitivo 25,5 min (5 s).

Revision del resultado (v1.3.1): cada imagen guardada y el fotograma de muestra de un video se miden (desviacion
y rugosidad de la luminancia); si parecen gris uniforme o ruido de colores la respuesta empieza por AVISO y
el .json lleva "aviso". No bloquea nada: el resultado se guarda igual.

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
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from mcp.server.fastmcp import FastMCP, Image
from PIL import Image as PILImage
from PIL import ImageChops, ImageStat

VERSION = "1.3.1"
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
MODELO_DEF = os.environ.get("COMFY_MCP_MODELO", "qwen21").strip().lower()
VISOR = os.environ.get("COMFY_MCP_VISOR", "1").strip() != "0"
FLUJOS_USUARIO = Path(os.environ.get("COMFY_FLUJOS_USUARIO", r"C:\ComfyUI\ComfyUI\user\default\imga_flujos"))
LATIDO_VISOR = FLUJOS_USUARIO.parent / "imga_visor_latido.json"
MARCA_VISOR = BASE / ".visor_abierto"
LIC_QWEN21 = "Qwen Research License (investigacion/evaluacion, NO comercial sin licencia de Qwen)"
MODELOS = {
    "generar_qwen21": ("Qwen-Image 2.1", LIC_QWEN21),
    "editar_qwen21": ("Qwen-Image 2.1 (edicion)", LIC_QWEN21),
    "generar_rapido": ("Z-Image Turbo", "Apache-2.0"),
    "generar_texto": ("Qwen-Image 2512 + LoRA Lightning 4 pasos", "Apache-2.0"),
    "editar": ("Qwen-Image-Edit 2511 + LoRA Lightning 4 pasos", "Apache-2.0"),
    "video_borrador": ("Wan 2.2 14B i2v + LoRA lightx2v 4 pasos (832x576, 16 fps)", "Apache-2.0"),
    "video_definitivo": ("Wan 2.2 14B i2v 1280x720 + RelayVSR x2 + FILM x2 (1920x1080, 32 fps)", "Apache-2.0"),
}
# nodos imprescindibles de cada flujo (para aceptar un flujo editado por el usuario)
REQUISITOS = {
    "generar_qwen21": ["TextGenerate", "ComfySwitchNode", "EmptyLatentImage", "KSampler", "TextEncodeQwenImage21"],
    "editar_qwen21": ["LoadImage", "TextEncodeQwenImage21", "KSampler", "TextGenerate", "ComfySwitchNode"],
    "generar_rapido": ["CLIPTextEncode", "EmptySD3LatentImage", "KSampler", "SaveImage"],
    "generar_texto": ["CLIPTextEncode", "EmptySD3LatentImage", "KSampler", "SaveImage"],
    "editar": ["LoadImage", "FluxKontextImageScale", "TextEncodeQwenImageEditPlus", "KSampler", "SaveImage"],
    "video_wan": ["LoadImage", "WanImageToVideo", "KSamplerAdvanced", "CLIPTextEncode", "CreateVideo", "SaveVideo"],
    "video_acabado": ["LoadVideo", "VSRDecode", "ImageScale", "FrameInterpolate", "CreateVideo", "SaveVideo"],
}
VIDEOS_PEND = BASE / "videos_pendientes"
VIDEO_GB_MIN = float(os.environ.get("COMFY_MCP_VIDEO_GB", "45"))  # memoria GPU libre minima para un video
VIDEO_FPS = 16  # Wan 2.2
VIDEO_TAM = {"borrador": (832, 576), "definitivo": (1280, 720)}  # apaisado; en vertical se giran
VIDEO_FINAL = (1920, 1080)
VIDEO_MINUTOS = {"borrador": "8-9", "definitivo": "25-30"}  # medidos con 5 s (spec 005; MCP 2026-11-16: 8,0 y 25,5)
# Revision del resultado (1.3.1): con la GPU calculando mal (2026-11-16) salio gris uniforme o ruido de colores.
# Medido en 16 imagenes del PC (lado mayor 512 px, luminancia): buenas desviacion 38-62 y rugosidad 0,11-0,34;
# grises desviacion 0; ruido rugosidad 0,84-1,16. Rugosidad = diferencia media entre pixeles vecinos / desviacion.
REVISAR = os.environ.get("COMFY_MCP_REVISAR", "1").strip() != "0"
REV_DESV_PLANA = 3.0
REV_RUGOSIDAD = 0.6
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
        return ""  # si responde a la segunda (respuesta lenta), no hay nada que arrancar
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
def _faltan(nombre: str, g: dict) -> list[str]:
    clases = {n.get("class_type") for n in g.values() if isinstance(n, dict)}
    faltan = [c for c in REQUISITOS.get(nombre, []) if c not in clases]
    if nombre.startswith("video_"):
        return faltan
    if not any(c in clases for c in ("SaveImage", "SaveImageAdvanced")):
        faltan.append("SaveImage")
    return faltan


def _flujo_y_origen(nombre: str) -> tuple[dict, str]:
    """Flujo editado por el usuario (si existe y es valido) o el instalado. Devuelve (grafo, nota de origen)."""
    u = FLUJOS_USUARIO / f"{nombre}.json"
    nota = ""
    if u.exists():
        try:
            g = json.loads(u.read_text(encoding="utf-8"))
            faltan = _faltan(nombre, g)
            if not faltan:
                return g, f"flujo editado {u}"
            nota = f"AVISO: tu flujo {u.name} no vale (falta {', '.join(faltan)}); uso el instalado. "
        except Exception as e:
            nota = f"AVISO: tu flujo {u.name} no se puede leer ({e}); uso el instalado. "
    f = FLUJOS / f"{nombre}.json"
    if not f.exists():
        raise RuntimeError(f"Falta el flujo {f}. Reinstala el MCP (03_instalar_mcp_comfyui.bat).")
    return json.loads(f.read_text(encoding="utf-8")), nota + f"flujo instalado {f.name}"


def _flujo(nombre: str) -> dict:
    return _flujo_y_origen(nombre)[0]


def _poner_prompt_qwen21(g: dict, texto: str):
    """En los flujos de Qwen 2.1 el texto entra por un interruptor (directo / mejorador de prompt)."""
    tg = _nodo(g, "TextGenerate")
    g[tg]["inputs"]["prompt"] = texto
    sw = [i for i, n in g.items() if n.get("class_type") == "ComfySwitchNode"
          and n["inputs"].get("on_true") == [tg, 0]]
    if not sw:
        raise RuntimeError("El flujo de Qwen 2.1 no tiene el interruptor del prompt (on_true <- TextGenerate).")
    g[sw[0]]["inputs"]["on_false"] = texto


def _poner_guardado(g: dict, tipo: str):
    for n in g.values():
        if n.get("class_type") in ("SaveImage", "SaveImageAdvanced"):
            n["inputs"]["filename_prefix"] = f"IMGA/{tipo}"


def _modo_flujos(modo: str, accion: str) -> str:
    """Traduce modo (calidad/rapido/texto) + accion (generar/editar) al nombre del flujo."""
    modo = (modo or "calidad").strip().lower()
    if modo in ("rapido", "rápido"):
        return "generar_rapido" if accion == "generar" else "editar"
    if modo == "texto" and accion == "generar":
        return "generar_texto"
    if modo not in ("calidad", "texto"):
        raise RuntimeError(f"modo '{modo}' no valido: usa 'calidad' (por defecto), 'rapido' o 'texto'.")
    if MODELO_DEF == "clasico":
        return "generar_texto" if accion == "generar" else "editar"
    return "generar_qwen21" if accion == "generar" else "editar_qwen21"


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
def _abrir_visor():
    """Abre la interfaz de ComfyUI (ventana de Edge) si no hay ninguna abierta con el complemento IMGA,
    para que Andres vea el trabajo. El complemento escribe un latido cada 15 s; sin latido reciente se abre
    una ventana (como mucho una cada 10 min, por si el complemento no esta instalado)."""
    if not VISOR or os.name != "nt":
        return
    try:
        if LATIDO_VISOR.exists() and time.time() - LATIDO_VISOR.stat().st_mtime < 45:
            return
        if MARCA_VISOR.exists() and time.time() - MARCA_VISOR.stat().st_mtime < 600:
            return
        MARCA_VISOR.write_text(dt.datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
        env = _entorno_completo()
        cmd = env.get("ComSpec") or r"C:\Windows\System32\cmd.exe"
        subprocess.Popen([cmd, "/d", "/c", "start", "", "msedge.exe", f"--app={COMFY}/"], env=env,
                         creationflags=SIN_VENTANA | 0x00000200, close_fds=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass  # el visor es una ayuda: nunca debe romper el trabajo


def _lanzar(g: dict, tipo: str, meta: dict) -> str:
    r = _json("/prompt", {"prompt": g, "client_id": CLIENTE})
    pid = r["prompt_id"]
    pend = BASE / "pendientes"
    pend.mkdir(parents=True, exist_ok=True)
    (pend / f"{pid}.json").write_text(json.dumps({"tipo": tipo, "lanzado": dt.datetime.now().isoformat(timespec="seconds"),
                                                   **meta}, ensure_ascii=False, indent=1), encoding="utf-8")
    _abrir_visor()
    return pid


def _historial(pid: str) -> dict | None:
    return (_json(f"/history/{pid}") or {}).get(pid)


def _miniatura(ruta: Path, max_lado: int = 1024) -> Image:
    im = PILImage.open(ruta)
    im.thumbnail((max_lado, max_lado))
    buf = io.BytesIO()
    im.convert("RGB").save(buf, format="JPEG", quality=88)
    return Image(data=buf.getvalue(), format="jpeg")


def _medir(ruta: Path) -> tuple[float, float]:
    """(desviacion de la luminancia, rugosidad) de una imagen reducida a 512 px de lado mayor."""
    im = PILImage.open(ruta).convert("L")
    im.thumbnail((512, 512), PILImage.LANCZOS)
    desv = ImageStat.Stat(im).stddev[0]
    w, h = im.size
    if w < 2 or h < 2 or desv < 1e-6:
        return desv, 0.0
    dh = ImageStat.Stat(ImageChops.difference(im.crop((0, 0, w - 1, h)), im.crop((1, 0, w, h)))).mean[0]
    dv = ImageStat.Stat(ImageChops.difference(im.crop((0, 0, w, h - 1)), im.crop((0, 1, w, h)))).mean[0]
    return desv, (dh + dv) / 2 / desv


def _revisar(ruta: Path) -> str:
    """Aviso si el resultado parece gris/plano o ruido (GPU calculando mal); '' si parece una imagen normal."""
    if not REVISAR:
        return ""
    try:
        desv, rug = _medir(ruta)
    except Exception as e:  # una imagen que no se puede leer no debe tumbar la respuesta
        return f"AVISO: no he podido revisar {ruta.name} ({e}). "
    if desv < REV_DESV_PLANA:
        como = "un color plano (gris o uniforme)"
    elif rug > REV_RUGOSIDAD:
        como = "ruido de colores"
    else:
        return ""
    return (f"AVISO: el resultado parece {como} (desviacion {desv:.1f}, rugosidad {rug:.2f}), no una imagen. "
            "Suele indicar que la GPU esta calculando mal: reiniciar el PC y probar con generar_imagen modo='rapido' "
            "(unos 20 s). Si la imagen es asi a proposito, ignorar este aviso. ")


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
            tipo = re.sub(r"[^\w-]", "", str(meta.get("tipo") or "")) or "img"  # sin '?' ni otros caracteres no validos en Windows
            destino = dia / f"{dt.datetime.now():%H%M%S}_{tipo}_{len(rutas) + 1}.png"
            destino.write_bytes(datos)
            rutas.append(destino)
            imagenes.append(_miniatura(destino))
    aviso = "".join(_revisar(r) for r in rutas)
    meta.update({"prompt_id": pid, "segundos": segundos, "resultados": [str(r) for r in rutas],
                 "comfyui": [f"{im.get('subfolder', '')}/{im['filename']}" for o in h.get("outputs", {}).values()
                             for im in o.get("images", [])]})
    if aviso:
        meta["aviso"] = aviso.strip()
    for r in rutas:
        r.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    if rutas:
        ESTADO.write_text(json.dumps({"ruta": str(rutas[0]), **meta}, ensure_ascii=False, indent=1), encoding="utf-8")
    if pend.exists():
        pend.unlink()
    texto = aviso + (f"Hecho en {segundos} s. Guardado en: " + ", ".join(str(r) for r in rutas) +
             f". Semilla {meta.get('semilla')}. Modelo: {meta.get('modelo', '?')} - licencia: {meta.get('licencia', '?')}."
             " (Tambien en el historial de ComfyUI.)")
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
        "mcp": VERSION, "autoarranque": AUTOARRANQUE, "modelo_por_defecto": MODELO_DEF, "visor": VISOR,
        "flujos_editados": sorted(p.stem for p in FLUJOS_USUARIO.glob("*.json")) if FLUJOS_USUARIO.exists() else [],
        **({"arranque": nota.strip()} if nota else {}),
    }, ensure_ascii=False, indent=1)


@mcp.tool()
def generar_imagen(prompt: str, modo: str = "calidad", ancho: int | None = None, alto: int | None = None,
                   semilla: int | None = None):
    """Genera una imagen desde texto con el ComfyUI local y la devuelve.
    modo="calidad" (POR DEFECTO): Qwen-Image 2.1, el mas realista y fiel al texto (~65 s con el modelo cargado,
      ~2-3 min si hay que cargarlo; devuelve un prompt_id para esperar_resultado si tarda). Licencia de
      investigacion: NO comercial sin licencia de Qwen (se avisa en la respuesta).
    modo="rapido": Z-Image Turbo (~20 s). Usar SOLO si el usuario pide expresamente algo rapido.
    modo="texto": Qwen-Image 2512 + LoRA 4 pasos, para carteles y rotulos legibles.
    Tamano por defecto 1024x1024 (ancho/alto en pixeles, multiplos de 32 recomendados). semilla fija para repetir.
    El prompt puede ir en espanol o en ingles; describir escena, estilo, luz, encuadre y tipo de camara.
    Si ComfyUI no esta arrancado, lo arranca solo."""
    t0 = time.time()
    nota = _asegurar_comfy(ESPERA - 10)
    nombre = _modo_flujos(modo, "generar")
    g, origen = _flujo_y_origen(nombre)
    s = _semilla(semilla)
    if nombre == "generar_qwen21":
        _poner_prompt_qwen21(g, prompt)
        lat = _nodo(g, "EmptyLatentImage")
        g[lat]["inputs"]["width"] = int(ancho or 1024)
        g[lat]["inputs"]["height"] = int(alto or 1024)
        tipo = "calidad"
    else:
        if nombre == "generar_texto":
            g[_nodo(g, "CLIPTextEncode", "positive")]["inputs"]["text"] = prompt
            tipo = "texto"
        else:
            g[_nodo(g, "CLIPTextEncode")]["inputs"]["text"] = prompt
            tipo = "rapido"
        lat = _nodo(g, "EmptySD3LatentImage")
        if ancho:
            g[lat]["inputs"]["width"] = int(ancho)
        if alto:
            g[lat]["inputs"]["height"] = int(alto)
    g[_nodo(g, "KSampler")]["inputs"]["seed"] = s
    _poner_guardado(g, tipo)
    modelo, licencia = MODELOS[nombre]
    pid = _lanzar(g, tipo, {"flujo": nombre, "origen_flujo": origen, "modelo": modelo, "licencia": licencia,
                            "prompt": prompt, "semilla": s,
                            "ancho": g[lat]["inputs"]["width"], "alto": g[lat]["inputs"]["height"]})
    return _con_nota(nota, _esperar(pid, max(5.0, ESPERA - (time.time() - t0))))


def _editar_qwen21(g: dict, subidas: list[str]):
    """Imagen 1 = el LoadImage conectado a images.image_1 del codificador; el resto se rehace (hasta 10)."""
    enc = _nodo(g, "TextEncodeQwenImage21")
    ent = g[enc]["inputs"]
    n1 = ent.get("images.image_1", [None])[0]
    if not n1 or g.get(n1, {}).get("class_type") != "LoadImage":
        raise RuntimeError("El flujo de edicion de Qwen 2.1 no tiene un LoadImage en images.image_1.")
    g[n1]["inputs"]["image"] = subidas[0]
    for c in [i for i, n in g.items() if n.get("class_type") == "LoadImage" and i != n1]:
        del g[c]
    lotes = [i for i, n in g.items() if n.get("class_type") == "BatchImagesNode"]
    for k in [k for k in ent if k.startswith("images.image_") and k != "images.image_1"]:
        del ent[k]
    for lb in lotes:
        for k in [k for k in g[lb]["inputs"] if k.startswith("images.image") and k != "images.image0"]:
            del g[lb]["inputs"][k]
    for i, nombre in enumerate(subidas[1:], start=2):
        nid = f"imga_ref{i}"
        g[nid] = {"inputs": {"image": nombre}, "class_type": "LoadImage", "_meta": {"title": f"Referencia {i}"}}
        ent[f"images.image_{i}"] = [nid, 0]
        for lb in lotes:
            g[lb]["inputs"][f"images.image{i - 1}"] = [nid, 0]
    # nodos que apuntaban a cargas borradas (p. ej. comparadores de la plantilla): fuera
    for i in [i for i, n in g.items() if any(isinstance(v, list) and len(v) == 2 and isinstance(v[1], int)
                                             and str(v[0]) not in g for v in n.get("inputs", {}).values())]:
        del g[i]


def _editar_2511(g: dict, subidas: list[str]):
    cargas = [nid for nid, n in g.items() if n.get("class_type") == "LoadImage"]
    cod = [nid for nid, n in g.items() if n.get("class_type") == "TextEncodeQwenImageEditPlus"]
    esc = _nodo(g, "FluxKontextImageScale")
    n1 = g[esc]["inputs"]["image"][0]
    g[n1]["inputs"]["image"] = subidas[0]
    for c in cargas:
        if c != n1:
            del g[c]
    for k in cod:
        for e in ("image2", "image3"):
            g[k]["inputs"].pop(e, None)
    for i, nombre in enumerate(subidas[1:], start=2):
        nid = f"imga_ref{i}"
        g[nid] = {"inputs": {"image": nombre}, "class_type": "LoadImage", "_meta": {"title": f"Referencia {i}"}}
        for k in cod:
            g[k]["inputs"][f"image{i}"] = [nid, 0]


def _editar(instruccion: str, refs: list[Path], semilla: int | None, tipo: str, modo: str = "calidad"):
    nombre = _modo_flujos(modo, "editar")
    maximo = 10 if nombre == "editar_qwen21" else 3
    if not 1 <= len(refs) <= maximo:
        raise RuntimeError(f"Con este modo se admiten de 1 a {maximo} imagenes de referencia.")
    t0 = time.time()
    nota = _asegurar_comfy(ESPERA - 10)
    g, origen = _flujo_y_origen(nombre)
    s = _semilla(semilla)
    subidas = [_subir(r) for r in refs]
    if nombre == "editar_qwen21":
        _editar_qwen21(g, subidas)
        _poner_prompt_qwen21(g, instruccion)
    else:
        _editar_2511(g, subidas)
        g[_nodo(g, "TextEncodeQwenImageEditPlus", "positive")]["inputs"]["prompt"] = instruccion
    g[_nodo(g, "KSampler")]["inputs"]["seed"] = s
    _poner_guardado(g, tipo)
    modelo, licencia = MODELOS[nombre]
    pid = _lanzar(g, tipo, {"flujo": nombre, "origen_flujo": origen, "modelo": modelo, "licencia": licencia,
                            "instruccion": instruccion, "semilla": s, "referencias": [str(r) for r in refs]})
    return _con_nota(nota, _esperar(pid, max(5.0, ESPERA - (time.time() - t0))))


@mcp.tool()
def editar_imagen(instruccion: str, imagenes: list[str], semilla: int | None = None, modo: str = "calidad"):
    """Edita o crea una imagen a partir de imagenes de referencia.
    modo="calidad" (POR DEFECTO): Qwen-Image 2.1, de 1 a 10 imagenes, el mas fiel (~90 s cargado, ~3 min la 1.a vez;
      si tarda devuelve un prompt_id para esperar_resultado). Licencia NO comercial sin licencia de Qwen.
    modo="rapido": Qwen-Image-Edit 2511 con 4 pasos, de 1 a 3 imagenes (~40 s). Solo si el usuario pide rapidez.
    imagenes: rutas completas, o nombres de ficheros que esten en C:\\IA_Imagenes\\entrada.
    En la instruccion, referirse a ellas como 'imagen 1', 'imagen 2'... La imagen 1 marca el encuadre y el tamano.
    Las imagenes adjuntadas en el chat NO llegan aqui: tienen que estar en disco."""
    return _editar(instruccion, [_resolver_imagen(i) for i in imagenes], semilla, "editar", modo)


@mcp.tool()
def retocar_ultima(instruccion: str, imagenes_extra: list[str] | None = None, semilla: int | None = None,
                   modo: str = "calidad"):
    """Aplica un cambio a la ULTIMA imagen generada o editada (encadena retoques sin repetir rutas).
    modo="calidad" (por defecto, Qwen-Image 2.1, hasta 9 referencias extra) o "rapido" (2511, hasta 2 extra)."""
    if not ESTADO.exists():
        raise RuntimeError("Todavia no hay ninguna imagen anterior: usa generar_imagen o editar_imagen.")
    ultima = Path(json.loads(ESTADO.read_text(encoding="utf-8"))["ruta"])
    refs = [ultima] + [_resolver_imagen(i) for i in (imagenes_extra or [])]
    return _editar(instruccion, refs, semilla, "retoque", modo)


@mcp.tool()
def esperar_resultado(prompt_id: str, segundos: float = 50):
    """Espera (hasta 'segundos') a un trabajo lanzado antes y devuelve la imagen (o el video) cuando termine.
    Con un video, cada llamada informa del paso en que va; llamar de nuevo hasta que diga 'Hecho'."""
    if (VIDEOS_PEND / f"{prompt_id}.json").exists() or (VIDEOS_PEND / f"{prompt_id}.hecho.json").exists():
        return _esperar_video(prompt_id, segundos)
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
                      **({"video": str(f.with_suffix(".mp4"))} if f.with_suffix(".mp4").exists() else {}),
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


# ------------------------------------------------------------------ video (v1.3.0, spec 005)
def _memoria_gpu_gb() -> float:
    s = _json("/system_stats")
    return round((s.get("devices") or [{}])[0].get("vram_free", 0) / 1e9, 1)


def _comprobar_memoria_video():
    """RF-7: un video necesita mucha memoria. Si falta, libera la de ComfyUI; si sigue faltando, lo explica."""
    libre = _memoria_gpu_gb()
    if libre >= VIDEO_GB_MIN:
        return ""
    _json("/free", {"unload_models": True, "free_memory": True})
    time.sleep(3)
    libre2 = _memoria_gpu_gb()
    if libre2 >= VIDEO_GB_MIN:
        return f"(He liberado memoria de ComfyUI: {libre} -> {libre2} GB libres.) "
    raise RuntimeError(
        f"Solo hay {libre2} GB libres de memoria de la GPU y un video necesita al menos {VIDEO_GB_MIN:.0f} GB. "
        "Si ComfyUI acaba de hacer un trabajo cortado, retiene memoria aunque se le pida liberarla: hay que cerrar la "
        "ventana 'ComfyUI servidor' de la barra de tareas (el MCP lo vuelve a arrancar solo). Si no, cerrar o "
        "descargar el modelo grande de otra app (LM Studio) y volver a intentarlo.")


def _orientacion(ruta: Path, calidad: str) -> tuple[int, int, str]:
    """Tamano de Wan segun la forma de la imagen (apaisada o vertical) y aviso si se va a deformar."""
    w, h = PILImage.open(ruta).size
    a, b = VIDEO_TAM[calidad]
    ancho, alto = (a, b) if w >= h else (b, a)
    aviso = ""
    if abs((w / h) / (ancho / alto) - 1) > 0.05:
        aviso = (f"AVISO: la imagen es {w}x{h} y el video sale {ancho}x{alto}: se estira. Para que no se deforme, "
                 f"usa una imagen en {'16:9' if calidad == 'definitivo' else 'proporcion 13:9'}. ")
    return ancho, alto, aviso


def _preparar_wan(g: dict, subida: str, prompt: str, ancho: int, alto: int, segundos: float, semilla: int,
                  fotograma: bool) -> dict:
    """Rellena el flujo de Wan: imagen, texto, tamano, duracion (fotogramas = 16*s+1), semilla, LoRA 4 pasos."""
    carga = _nodo(g, "LoadImage")
    g[carga]["inputs"]["image"] = subida
    wan = _nodo(g, "WanImageToVideo")
    g[wan]["inputs"]["width"], g[wan]["inputs"]["height"] = int(ancho), int(alto)
    pos = g[wan]["inputs"]["positive"][0]
    if g.get(pos, {}).get("class_type") != "CLIPTextEncode":
        raise RuntimeError("El flujo de Wan no tiene el texto positivo conectado a WanImageToVideo.")
    g[pos]["inputs"]["text"] = prompt
    largo = g[wan]["inputs"].get("length")
    if isinstance(largo, list):  # plantilla oficial: duracion (s) x fps + 1 con nodos Primitive
        for n in g.values():
            if n.get("class_type") == "PrimitiveFloat" and "duration" in n.get("_meta", {}).get("title", "").lower():
                n["inputs"]["value"] = float(segundos)
            if n.get("class_type") == "PrimitiveFloat" and "fps" in n.get("_meta", {}).get("title", "").lower():
                n["inputs"]["value"] = float(VIDEO_FPS)
    else:
        g[wan]["inputs"]["length"] = int(segundos * VIDEO_FPS) + 1
    for n in g.values():
        if n.get("class_type") == "KSamplerAdvanced" and n["inputs"].get("add_noise") == "enable":
            n["inputs"]["noise_seed"] = int(semilla)
        if n.get("class_type") == "PrimitiveBoolean" and "lora" in n.get("_meta", {}).get("title", "").lower():
            n["inputs"]["value"] = True
    for n in g.values():
        if n.get("class_type") == "SaveVideo":
            n["inputs"]["filename_prefix"] = "video/IMGA_video"
    _ajustar_fotograma(g, fotograma, int(segundos * VIDEO_FPS) // 2)
    return g


def _ajustar_fotograma(g: dict, quiere: bool, indice: int):
    """El fotograma de muestra: ImageFromBatch -> SaveImage. Se quita si no se quiere (paso intermedio)."""
    sacar = [i for i, n in g.items() if n.get("class_type") == "ImageFromBatch"]
    for i in sacar:
        if quiere:
            g[i]["inputs"]["batch_index"] = max(0, int(indice))
    if not quiere:
        destino = {i for i, n in g.items() if n.get("class_type") in ("SaveImage", "SaveImageAdvanced")
                   and any(isinstance(v, list) and v[0] in sacar for v in n["inputs"].values())}
        for i in set(sacar) | destino:
            g.pop(i, None)
    for n in g.values():
        if n.get("class_type") in ("SaveImage", "SaveImageAdvanced"):
            n["inputs"]["filename_prefix"] = "IMGA/video_fotograma"


def _preparar_acabado(g: dict, video_entrada: str, segundos: float, vertical: bool) -> dict:
    g[_nodo(g, "LoadVideo")]["inputs"]["file"] = video_entrada
    esc = _nodo(g, "ImageScale")
    g[esc]["inputs"]["width"], g[esc]["inputs"]["height"] = (VIDEO_FINAL[1], VIDEO_FINAL[0]) if vertical else VIDEO_FINAL
    fi = _nodo(g, "FrameInterpolate")
    mult = int(g[fi]["inputs"].get("multiplier", 2)) if not isinstance(g[fi]["inputs"].get("multiplier"), list) else 2
    for n in g.values():
        if n.get("class_type") == "CreateVideo" and not isinstance(n["inputs"].get("fps"), list):
            n["inputs"]["fps"] = float(VIDEO_FPS * mult)
        if n.get("class_type") == "SaveVideo":
            n["inputs"]["filename_prefix"] = "video/IMGA_video"
    _ajustar_fotograma(g, True, int(segundos * VIDEO_FPS * mult) // 2)
    return g


def _ruta_trabajo(jid: str, hecho: bool = False) -> Path:
    return VIDEOS_PEND / (f"{jid}.hecho.json" if hecho else f"{jid}.json")


def _guardar_trabajo(t: dict):
    VIDEOS_PEND.mkdir(parents=True, exist_ok=True)
    tmp = _ruta_trabajo(t["id"]).with_suffix(".tmp")
    tmp.write_text(json.dumps(t, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, _ruta_trabajo(t["id"]))


def _enviar(g: dict) -> str:
    pid = _json("/prompt", {"prompt": g, "client_id": CLIENTE})["prompt_id"]
    _abrir_visor()
    return pid


def _salidas(h: dict) -> tuple[list[dict], list[dict]]:
    """(videos, imagenes) de salida de un trabajo terminado."""
    videos, imagenes = [], []
    for out in h.get("outputs", {}).values():
        for f in out.get("images", []) + out.get("videos", []) + out.get("gifs", []):
            if f.get("type") != "output":
                continue
            (videos if str(f.get("filename", "")).lower().endswith((".mp4", ".webm", ".mov")) else imagenes).append(f)
    return videos, imagenes


def _bajar(f: dict) -> bytes:
    q = urllib.parse.urlencode({"filename": f["filename"], "subfolder": f.get("subfolder", ""), "type": "output"})
    return _http(f"/view?{q}", timeout=600)


def _subir_bytes(datos: bytes, nombre: str) -> str:
    tmp = BASE / "videos_pendientes" / nombre
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(datos)
    try:
        return _subir(tmp)
    finally:
        tmp.unlink(missing_ok=True)


def _segundos_trabajo(h: dict) -> float | None:
    msgs = {k: v for k, v in h.get("status", {}).get("messages", [])}
    t0 = msgs.get("execution_start", {}).get("timestamp")
    t1 = msgs.get("execution_success", {}).get("timestamp")
    return round((t1 - t0) / 1000, 1) if t0 and t1 else None


def _bloqueo(jid: str):
    """Evita que dos clientes (p. ej. Claude y Hermes) avancen a la vez el mismo video."""
    VIDEOS_PEND.mkdir(parents=True, exist_ok=True)
    cerrojo = VIDEOS_PEND / f"{jid}.lock"
    try:
        if cerrojo.exists() and time.time() - cerrojo.stat().st_mtime > 300:
            cerrojo.unlink(missing_ok=True)
        fd = os.open(cerrojo, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return cerrojo
    except FileExistsError:
        return None


def _avanzar_video(jid: str) -> tuple[str, list]:
    """Mira el paso actual del video y, si ha terminado, lanza el siguiente o recoge el resultado.
    Devuelve (estado, contenido): estado = 'en_curso' | 'hecho' | 'error'."""
    hecho = _ruta_trabajo(jid, True)
    if hecho.exists():
        t = json.loads(hecho.read_text(encoding="utf-8"))
        return "hecho", _texto_video(t)
    ruta = _ruta_trabajo(jid)
    if not ruta.exists():
        return "error", [f"No conozco el video {jid}."]
    cerrojo = _bloqueo(jid)
    if cerrojo is None:
        t = json.loads(ruta.read_text(encoding="utf-8"))
        return "en_curso", [_texto_en_curso(t, "otro cliente lo esta actualizando")]
    try:
        t = json.loads(ruta.read_text(encoding="utf-8"))
        h = _historial(t["actual"])
        if not h:
            q = _json("/queue")
            corriendo = any(x[1] == t["actual"] for x in q.get("queue_running", []))
            en_cola = any(x[1] == t["actual"] for x in q.get("queue_pending", []))
            if not corriendo and not en_cola:
                t["error"] = ("ComfyUI ya no tiene este trabajo (se reinicio o se cancelo). Vuelve a lanzar el video "
                              "con generar_video.")
                _guardar_trabajo(t)
                return "error", [t["error"]]
            return "en_curso", [_texto_en_curso(t, "ejecutandose" if corriendo else "en cola")]
        msgs = {k: v for k, v in h.get("status", {}).get("messages", [])}
        if "execution_error" in msgs or "execution_interrupted" in msgs:
            e = msgs.get("execution_error") or {}
            t["error"] = (f"ERROR en ComfyUI en el paso {t['paso']} (nodo {e.get('node_type')}): "
                          f"{str(e.get('exception_message', 'cancelado'))[:600]}")
            _guardar_trabajo(t)
            return "error", [t["error"]]
        t.setdefault("tiempos", {})[str(t["paso"])] = _segundos_trabajo(h)
        videos, imagenes = _salidas(h)
        if not videos:
            t["error"] = f"El paso {t['paso']} termino sin video de salida."
            _guardar_trabajo(t)
            return "error", [t["error"]]
        if t["paso"] < t["pasos"]:  # definitivo: paso 1 (Wan 720p) -> paso 2 (acabado)
            subida = _subir_bytes(_bajar(videos[0]), f"{jid[:8]}_wan720p.mp4")
            g, origen = _flujo_y_origen("video_acabado")
            _preparar_acabado(g, subida, t["segundos_video"], t["vertical"])
            t["origen_flujo"] += f"; {origen}"
            t["actual"] = _enviar(g)
            t["paso"] += 1
            t["paso_iniciado"] = dt.datetime.now().isoformat(timespec="seconds")
            _guardar_trabajo(t)
            return "en_curso", [_texto_en_curso(t, "en cola")]
        dia = BASE / dt.date.today().isoformat()
        dia.mkdir(parents=True, exist_ok=True)
        base = dia / f"{dt.datetime.now():%H%M%S}_video_{t['calidad']}"
        base.with_suffix(".mp4").write_bytes(_bajar(videos[0]))
        if imagenes:
            base.with_suffix(".png").write_bytes(_bajar(imagenes[0]))
        aviso = _revisar(base.with_suffix(".png")) if imagenes else ""
        t.update({"resultado": str(base.with_suffix(".mp4")),
                  "fotograma": str(base.with_suffix(".png")) if imagenes else None,
                  "aviso": aviso.strip() or None,
                  "segundos": round(sum(v for v in t["tiempos"].values() if v), 1),
                  "terminado": dt.datetime.now().isoformat(timespec="seconds")})
        base.with_suffix(".json").write_text(json.dumps(t, ensure_ascii=False, indent=1), encoding="utf-8")
        hecho.write_text(json.dumps(t, ensure_ascii=False, indent=1), encoding="utf-8")
        ruta.unlink(missing_ok=True)
        return "hecho", _texto_video(t)
    finally:
        cerrojo.unlink(missing_ok=True)


def _texto_en_curso(t: dict, estado: str) -> str:
    desde = dt.datetime.fromisoformat(t["lanzado"])
    minutos = round((dt.datetime.now() - desde).total_seconds() / 60, 1)
    paso = ("Wan 2.2" if t["paso"] == 1 else "RelayVSR + 1080p + FILM") + (f" (paso {t['paso']} de {t['pasos']})"
                                                                          if t["pasos"] > 1 else "")
    return (f"Video {t['calidad']} en marcha: {paso}, {estado}. Llevamos {minutos} min de unos "
            f"{VIDEO_MINUTOS[t['calidad']]} min previstos (5 s de video). Llama a esperar_resultado con "
            f"prompt_id='{t['id']}' (cada llamada espera como mucho ~50 s). Se ve en la pestana de ComfyUI.")


def _texto_video(t: dict) -> list:
    if t.get("error"):
        return [t["error"]]
    texto = ((t["aviso"] + " ") if t.get("aviso") else "") + (f"Hecho: video {t['calidad']} {t['ancho_final']}x{t['alto_final']} a {t['fps_final']} fps, "
             f"{t['segundos_video']} s, en {round((t.get('segundos') or 0) / 60, 1)} min. Guardado en: {t['resultado']}"
             + (f" (fotograma de muestra: {t['fotograma']})" if t.get("fotograma") else "") +
             f". Semilla {t['semilla']}. Modelo: {t['modelo']} - licencia: {t['licencia']}.")
    out = [texto]
    if t.get("fotograma") and Path(t["fotograma"]).exists():
        out.append(_miniatura(Path(t["fotograma"])))
    return out


def _esperar_video(jid: str, espera: float | None = None) -> list:
    limite = time.time() + (ESPERA if espera is None else min(float(espera), 55))
    while True:
        estado_v, contenido = _avanzar_video(jid)
        if estado_v != "en_curso" or time.time() >= limite:
            return contenido
        time.sleep(5)


def _hilo_videos():
    """Avanza los videos pendientes aunque nadie llame a esperar_resultado (mientras viva el MCP)."""
    while True:
        time.sleep(20)
        try:
            for f in sorted(VIDEOS_PEND.glob("*.json")):
                if f.name.endswith(".hecho.json"):
                    continue
                if _responde():
                    _avanzar_video(f.stem)
        except Exception:
            pass


@mcp.tool()
def generar_video(prompt: str, imagen: str, calidad: str = "borrador", segundos: float = 5,
                  semilla: int | None = None) -> str:
    """Crea un video corto a partir de una imagen (la imagen es el primer fotograma) con Wan 2.2 en el ComfyUI local.
    calidad="borrador" (POR DEFECTO): 832x576, 16 fps, ~8-9 min por 5 s. Para probar encuadre y movimiento.
    calidad="definitivo": 1920x1080 a 32 fps (Wan 720p + RelayVSR x2 + FILM), ~25-30 min por 5 s. Solo si el usuario
      lo pide (definitivo, final, 1080p, alta calidad).
    imagen: ruta completa o nombre de un fichero de C:\\IA_Imagenes\\entrada (vale una imagen generada antes, p. ej.
      la ruta que devolvio generar_imagen). Mejor apaisada 16:9 (si es vertical, el video sale vertical).
    prompt: describir el MOVIMIENTO (camara y escena), p. ej. "dron avanzando despacio sobre el frente de la cantera,
      camara estable, luz natural". En ingles suele seguirlo mejor.
    segundos: de 2 a 8 (Wan esta entrenado para 5). Todo con licencia Apache-2.0.
    Devuelve enseguida un prompt_id: llamar a esperar_resultado(prompt_id) hasta que diga 'Hecho'. Los pasos siguen
    solos en segundo plano; el resultado queda en C:\\IA_Imagenes\\AAAA-MM-DD\\ (mp4 + fotograma png + json)."""
    calidad = (calidad or "borrador").strip().lower()
    if calidad not in VIDEO_TAM:
        raise RuntimeError(f"calidad '{calidad}' no valida: usa 'borrador' (por defecto) o 'definitivo'.")
    segundos = float(segundos or 5)
    if not 2 <= segundos <= 8:
        raise RuntimeError("segundos debe estar entre 2 y 8 (Wan 2.2 esta entrenado para 5 s).")
    ref = _resolver_imagen(imagen)
    nota = _asegurar_comfy(ESPERA - 10)
    nota += _comprobar_memoria_video()
    ancho, alto, aviso = _orientacion(ref, calidad)
    s = _semilla(semilla)
    g, origen = _flujo_y_origen("video_wan")
    _preparar_wan(g, _subir(ref), prompt, ancho, alto, segundos, s, fotograma=(calidad == "borrador"))
    pid = _enviar(g)
    vertical = alto > ancho
    fin = (ancho, alto) if calidad == "borrador" else ((VIDEO_FINAL[1], VIDEO_FINAL[0]) if vertical else VIDEO_FINAL)
    modelo, licencia = MODELOS[f"video_{calidad}"]
    t = {"id": pid, "tipo": "video", "calidad": calidad, "prompt": prompt, "imagen": str(ref), "semilla": s,
         "segundos_video": segundos, "ancho_wan": ancho, "alto_wan": alto, "vertical": vertical,
         "ancho_final": fin[0], "alto_final": fin[1], "fps_final": VIDEO_FPS * (2 if calidad == "definitivo" else 1),
         "modelo": modelo, "licencia": licencia, "origen_flujo": origen,
         "pasos": 2 if calidad == "definitivo" else 1, "paso": 1, "actual": pid,
         "lanzado": dt.datetime.now().isoformat(timespec="seconds")}
    _guardar_trabajo(t)
    return (nota + aviso + f"Video {calidad} lanzado (prompt_id='{pid}'): {fin[0]}x{fin[1]}, {segundos} s, semilla {s}. "
            f"Tardara unos {VIDEO_MINUTOS[calidad]} min (por 5 s de video). Llama a esperar_resultado con ese "
            "prompt_id para seguirlo; el trabajo se ve en la pestana de ComfyUI. Modelo: "
            f"{modelo} - licencia: {licencia}.")


def main():
    for d in (BASE, ENTRADA):
        d.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=_hilo_videos, daemon=True, name="videos").start()
    mcp.run()


if __name__ == "__main__":
    main()
