"""Pruebas sin ComfyUI (se simulan las llamadas HTTP). Ejecutar desde la raiz del repositorio:

    uv run --no-project --python 3.13 --with mcp==1.30.0 --with pillow==13.0.0 --with pytest pytest -q

Comprueban lo que se puede comprobar fuera del PC: las 9 herramientas (generar_video desde 1.3.0), como se rellenan los flujos
(prompt, semilla, tamano, 1-3 referencias sin enlaces rotos), el arranque automatico (sin lanzar nada)
y el entorno que se pasa a ComfyUI. Lo que depende de Windows/ComfyUI se prueba en el PC (scripts/03).
"""
import asyncio
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
SERVIDOR = RAIZ / "servidor" / "servidor_comfyui_mcp.py"
HERRAMIENTAS = {"estado", "generar_imagen", "editar_imagen", "retocar_ultima", "esperar_resultado",
                "ver_imagen", "listar_resultados", "liberar_memoria", "generar_video"}


@pytest.fixture()
def srv(tmp_path, monkeypatch):
    """Carga el servidor con IA_IMAGENES en una carpeta temporal y los flujos del repositorio."""
    monkeypatch.setenv("IA_IMAGENES", str(tmp_path / "IA_Imagenes"))
    monkeypatch.setenv("COMFY_MCP_ARRANQUE", "3")
    spec = importlib.util.spec_from_file_location("servidor_comfyui_mcp", SERVIDOR)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.FLUJOS = RAIZ / "flujos"  # en el PC estan junto al servidor; aqui, en flujos/
    m.FLUJOS_USUARIO = tmp_path / "imga_flujos"  # flujos editados desde ComfyUI (vacio salvo en su prueba)
    m.BASE.mkdir(parents=True, exist_ok=True)
    m.ENTRADA.mkdir(parents=True, exist_ok=True)
    return m


def _capturar(m, monkeypatch):
    """Sustituye arranque, subida, envio y espera; devuelve la lista donde quedan los grafos enviados."""
    enviados = []
    monkeypatch.setattr(m, "_asegurar_comfy", lambda limite=None: "")
    monkeypatch.setattr(m, "_subir", lambda ruta: f"subida_{ruta.name}")
    monkeypatch.setattr(m, "_lanzar", lambda g, tipo, meta: (enviados.append((g, tipo, meta)), "pid-1")[1])
    monkeypatch.setattr(m, "_esperar", lambda pid, espera=None: ["ok"])
    return enviados


def _enlaces_validos(g):
    for nid, n in g.items():
        for k, v in n.get("inputs", {}).items():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[1], int):
                assert str(v[0]) in g, f"{nid}.{k} apunta a un nodo inexistente {v[0]}"


def test_nueve_herramientas(srv):
    nombres = {t.name for t in asyncio.run(srv.mcp.list_tools())}
    assert nombres == HERRAMIENTAS


@pytest.mark.parametrize("modo,tipo,flujo", [("rapido", "rapido", "generar_rapido"), ("texto", "texto", "generar_texto"),
                                            ("calidad", "calidad", "generar_qwen21")])
def test_generar_rellena_flujo(srv, monkeypatch, modo, tipo, flujo):
    env = _capturar(srv, monkeypatch)
    srv.generar_imagen("una cantera", modo=modo, ancho=640, alto=480, semilla=7)
    g, t, meta = env[0]
    assert t == tipo and meta["flujo"] == flujo and meta["semilla"] == 7 and (meta["ancho"], meta["alto"]) == (640, 480)
    assert meta["modelo"] and meta["licencia"]
    if flujo == "generar_qwen21":
        assert "NO comercial" in meta["licencia"]
        sw = [n for n in g.values() if n["class_type"] == "ComfySwitchNode" and n["inputs"].get("on_false") == "una cantera"]
        assert sw and any(n["class_type"] == "TextGenerate" and n["inputs"]["prompt"] == "una cantera" for n in g.values())
    else:
        assert meta["licencia"] == "Apache-2.0"
        textos = [n["inputs"].get("text") for n in g.values() if n["class_type"] == "CLIPTextEncode"]
        assert "una cantera" in textos
    assert any(n["class_type"] == "KSampler" and n["inputs"]["seed"] == 7 for n in g.values())
    assert all(n["inputs"]["filename_prefix"] == f"IMGA/{tipo}" for n in g.values()
               if n["class_type"] in ("SaveImage", "SaveImageAdvanced"))
    _enlaces_validos(g)


def test_modo_por_defecto_es_calidad_qwen21(srv, monkeypatch):
    env = _capturar(srv, monkeypatch)
    srv.generar_imagen("x")
    assert env[0][2]["flujo"] == "generar_qwen21"
    monkeypatch.setattr(srv, "MODELO_DEF", "clasico")
    srv.generar_imagen("x")
    assert env[1][2]["flujo"] == "generar_texto"  # clasico: todo Apache-2.0


def test_modo_invalido(srv, monkeypatch):
    _capturar(srv, monkeypatch)
    with pytest.raises(RuntimeError, match="no valido"):
        srv.generar_imagen("x", modo="ultra")


@pytest.mark.parametrize("n", [1, 2, 3])
def test_editar_con_n_referencias(srv, monkeypatch, n):
    env = _capturar(srv, monkeypatch)
    refs = []
    for i in range(n):
        p = srv.ENTRADA / f"ref{i + 1}.png"
        p.write_bytes(b"x")
        refs.append(p.name)
    srv.editar_imagen("cambia el cielo", refs, semilla=3, modo="rapido")
    g, t, meta = env[0]
    assert meta["flujo"] == "editar"
    assert t == "editar" and len(meta["referencias"]) == n
    _enlaces_validos(g)
    cargas = [n_ for n_ in g.values() if n_["class_type"] == "LoadImage"]
    assert len(cargas) == n
    for cod in (x for x in g.values() if x["class_type"] == "TextEncodeQwenImageEditPlus"):
        for i in (2, 3):
            assert (f"image{i}" in cod["inputs"]) == (i <= n)


def test_editar_rechaza_4_referencias_en_rapido(srv, monkeypatch):
    _capturar(srv, monkeypatch)
    for i in range(4):
        (srv.ENTRADA / f"r{i}.png").write_bytes(b"x")
    with pytest.raises(RuntimeError, match="de 1 a 3"):
        srv.editar_imagen("x", [f"r{i}.png" for i in range(4)], modo="rapido")


@pytest.mark.parametrize("n", [1, 2, 5, 10])
def test_editar_qwen21_con_n_referencias(srv, monkeypatch, n):
    env = _capturar(srv, monkeypatch)
    for i in range(n):
        (srv.ENTRADA / f"q{i + 1}.png").write_bytes(b"x")
    srv.editar_imagen("pon el camion de la imagen 2", [f"q{i + 1}.png" for i in range(n)], semilla=9)
    g, t, meta = env[0]
    assert meta["flujo"] == "editar_qwen21" and len(meta["referencias"]) == n
    _enlaces_validos(g)
    assert len([x for x in g.values() if x["class_type"] == "LoadImage"]) == n
    enc = next(x for x in g.values() if x["class_type"] == "TextEncodeQwenImage21")
    assert sorted(k for k in enc["inputs"] if k.startswith("images.image_")) == sorted(f"images.image_{i}" for i in range(1, n + 1))
    lote = next(x for x in g.values() if x["class_type"] == "BatchImagesNode")
    assert len([k for k in lote["inputs"] if k.startswith("images.image")]) == n
    assert any(x["class_type"] == "ComfySwitchNode" and x["inputs"].get("on_false") == "pon el camion de la imagen 2"
               for x in g.values())


def test_editar_qwen21_rechaza_11(srv, monkeypatch):
    _capturar(srv, monkeypatch)
    for i in range(11):
        (srv.ENTRADA / f"z{i}.png").write_bytes(b"x")
    with pytest.raises(RuntimeError, match="de 1 a 10"):
        srv.editar_imagen("x", [f"z{i}.png" for i in range(11)])


def test_flujo_editado_por_el_usuario(srv, monkeypatch):
    env = _capturar(srv, monkeypatch)
    srv.FLUJOS_USUARIO.mkdir(parents=True)
    g = json.loads((RAIZ / "flujos" / "generar_qwen21.json").read_text(encoding="utf-8"))
    next(n for n in g.values() if n["class_type"] == "KSampler")["inputs"]["steps"] = 40
    (srv.FLUJOS_USUARIO / "generar_qwen21.json").write_text(json.dumps(g), encoding="utf-8")
    srv.generar_imagen("x")
    assert "flujo editado" in env[0][2]["origen_flujo"]
    assert next(n for n in env[0][0].values() if n["class_type"] == "KSampler")["inputs"]["steps"] == 40
    # un flujo editado al que le falta un nodo imprescindible no se usa
    del g[next(i for i, n in g.items() if n["class_type"] == "TextGenerate")]
    (srv.FLUJOS_USUARIO / "generar_qwen21.json").write_text(json.dumps(g), encoding="utf-8")
    srv.generar_imagen("x")
    assert "no vale" in env[1][2]["origen_flujo"] and "instalado" in env[1][2]["origen_flujo"]


def test_retocar_sin_imagen_previa(srv, monkeypatch):
    _capturar(srv, monkeypatch)
    with pytest.raises(RuntimeError, match="Todavia no hay"):
        srv.retocar_ultima("x")


def test_asegurar_ya_responde(srv, monkeypatch):
    monkeypatch.setattr(srv, "_responde", lambda timeout=3: True)
    monkeypatch.setattr(srv, "_arrancar_comfy", lambda env: pytest.fail("no debe arrancar"))
    assert srv._asegurar_comfy() == ""


def test_asegurar_arranca_y_espera(srv, monkeypatch):
    estado = {"up": False, "lanzados": 0}
    monkeypatch.setattr(srv, "_responde", lambda timeout=3: estado["up"])
    monkeypatch.setattr(srv, "_proceso_comfy", lambda env: False)

    def lanzar(env):
        estado["lanzados"] += 1
        estado["up"] = True
    monkeypatch.setattr(srv, "_arrancar_comfy", lanzar)
    nota = srv._asegurar_comfy(30)
    assert estado["lanzados"] == 1 and "lo he arrancado" in nota
    assert srv.MARCA_ARRANQUE.exists()


def test_asegurar_no_lanza_dos_veces(srv, monkeypatch):
    monkeypatch.setattr(srv, "_responde", lambda timeout=3: False)
    monkeypatch.setattr(srv, "_proceso_comfy", lambda env: True)  # ya hay un main.py arrancando
    monkeypatch.setattr(srv, "_arrancar_comfy", lambda env: pytest.fail("no debe lanzar otro"))
    monkeypatch.setattr(srv.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="ya se estaba arrancando"):
        srv._asegurar_comfy(0.01)


def test_asegurar_marca_reciente(srv, monkeypatch):
    srv.MARCA_ARRANQUE.write_text("x")
    monkeypatch.setattr(srv, "_responde", lambda timeout=3: False)
    monkeypatch.setattr(srv, "_proceso_comfy", lambda env: False)
    monkeypatch.setattr(srv, "_arrancar_comfy", lambda env: pytest.fail("marca de < 20 s: no debe lanzar"))
    monkeypatch.setattr(srv.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        srv._asegurar_comfy(0.01)
    os.utime(srv.MARCA_ARRANQUE, (time.time() - 60, time.time() - 60))
    lanzados = []
    monkeypatch.setattr(srv, "_arrancar_comfy", lambda env: lanzados.append(1))
    with pytest.raises(RuntimeError):
        srv._asegurar_comfy(0.01)
    assert lanzados == [1]


def test_autoarranque_desactivado(srv, monkeypatch):
    monkeypatch.setattr(srv, "AUTOARRANQUE", False)
    monkeypatch.setattr(srv, "_responde", lambda timeout=3: False)
    monkeypatch.setattr(srv, "_arrancar_comfy", lambda env: pytest.fail("desactivado"))
    monkeypatch.setattr(srv, "_proceso_comfy", lambda env: pytest.fail("desactivado: no debe buscar procesos"))
    monkeypatch.setattr(srv, "COMFY", "http://127.0.0.1:9")  # puerto cerrado: no depende de que ComfyUI este en marcha
    with pytest.raises(RuntimeError, match="No se puede conectar"):
        srv._asegurar_comfy()


def test_autoarranque_desactivado_pero_responde(srv, monkeypatch):
    """Fallo visto en el PC (2026-11-16): si la segunda comprobacion responde, no debe ir a arrancar."""
    monkeypatch.setattr(srv, "AUTOARRANQUE", False)
    monkeypatch.setattr(srv, "_responde", lambda timeout=3: False)
    monkeypatch.setattr(srv, "_json", lambda ruta, cuerpo=None, timeout=30: {"system": {}})
    monkeypatch.setattr(srv, "_proceso_comfy", lambda env: pytest.fail("no debe buscar procesos"))
    assert srv._asegurar_comfy() == ""


def test_entorno_sin_variables_de_python(srv, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "x")
    monkeypatch.setenv("VIRTUAL_ENV", "y")
    env = srv._entorno_completo()
    assert not {"PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME"} & {k.upper() for k in env}
    claves = [k.upper() for k in env]
    assert len(claves) == len(set(claves)), "claves repetidas con distinta capitalizacion"


def test_liberar_sin_comfyui(srv, monkeypatch):
    monkeypatch.setattr(srv, "_responde", lambda timeout=3: False)
    assert "no esta arrancado" in srv.liberar_memoria()


def test_flujos_son_json_api(srv):
    for f in ("generar_rapido", "generar_texto", "editar", "generar_qwen21", "editar_qwen21", "video_wan",
              "video_acabado"):
        g = json.loads((RAIZ / "flujos" / f"{f}.json").read_text(encoding="utf-8"))
        assert all("class_type" in n for n in g.values()), f
        _enlaces_validos(g)


def test_version_coincide_con_pyproject(srv):
    import tomllib
    proyecto = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert srv.VERSION == proyecto, "subir la version en pyproject.toml y en VERSION del servidor a la vez"



# ------------------------------------------------------------------ video (1.3.0)
def _imagen(srv, nombre, w, h):
    from PIL import Image as I
    p = srv.ENTRADA / nombre
    I.new("RGB", (w, h), (120, 110, 90)).save(p)
    return p


def _capturar_video(m, monkeypatch, memoria=""):
    enviados = []
    monkeypatch.setattr(m, "_asegurar_comfy", lambda limite=None: "")
    monkeypatch.setattr(m, "_comprobar_memoria_video", lambda: memoria)
    monkeypatch.setattr(m, "_subir", lambda ruta: f"subida_{ruta.name}")
    monkeypatch.setattr(m, "_enviar", lambda g: (enviados.append(g), f"pid-{len(enviados)}")[1])
    return enviados


def test_video_borrador_rellena_flujo(srv, monkeypatch):
    env = _capturar_video(srv, monkeypatch)
    _imagen(srv, "frente.png", 1216, 832)
    txt = srv.generar_video("dron avanzando", "frente.png", semilla=11)
    g = env[0]
    _enlaces_validos(g)
    wan = next(n for n in g.values() if n["class_type"] == "WanImageToVideo")
    assert (wan["inputs"]["width"], wan["inputs"]["height"]) == (832, 576)
    assert g[wan["inputs"]["positive"][0]]["inputs"]["text"] == "dron avanzando"
    assert any(n["class_type"] == "KSamplerAdvanced" and n["inputs"].get("noise_seed") == 11 for n in g.values())
    assert any(n["class_type"] == "PrimitiveBoolean" and n["inputs"]["value"] is True for n in g.values())
    assert any(n["class_type"] == "ImageFromBatch" and n["inputs"]["batch_index"] == 40 for n in g.values())
    assert any(n["class_type"] == "SaveImage" for n in g.values())
    t = json.loads((srv.VIDEOS_PEND / "pid-1.json").read_text(encoding="utf-8"))
    assert t["pasos"] == 1 and t["calidad"] == "borrador" and t["licencia"] == "Apache-2.0"
    assert "pid-1" in txt and "8-9 min" in txt and "AVISO" not in txt  # 1216x832 ~ 832x576


def test_video_definitivo_vertical_y_aviso(srv, monkeypatch):
    env = _capturar_video(srv, monkeypatch)
    _imagen(srv, "vertical.png", 800, 1200)
    txt = srv.generar_video("x", "vertical.png", calidad="definitivo", segundos=4)
    g = env[0]
    _enlaces_validos(g)
    wan = next(n for n in g.values() if n["class_type"] == "WanImageToVideo")
    assert (wan["inputs"]["width"], wan["inputs"]["height"]) == (720, 1280)
    assert not any(n["class_type"] in ("ImageFromBatch", "SaveImage") for n in g.values())  # paso intermedio
    assert any(n["class_type"] == "PrimitiveFloat" and n["inputs"]["value"] == 4.0 for n in g.values())
    t = json.loads((srv.VIDEOS_PEND / "pid-1.json").read_text(encoding="utf-8"))
    assert t["pasos"] == 2 and (t["ancho_final"], t["alto_final"], t["fps_final"]) == (1080, 1920, 32)
    assert "AVISO" in txt and "se estira" in txt


def test_video_parametros_invalidos(srv, monkeypatch):
    _capturar_video(srv, monkeypatch)
    _imagen(srv, "a.png", 1280, 720)
    with pytest.raises(RuntimeError, match="no valida"):
        srv.generar_video("x", "a.png", calidad="4k")
    with pytest.raises(RuntimeError, match="entre 2 y 8"):
        srv.generar_video("x", "a.png", segundos=12)


def test_preparar_acabado(srv):
    g = json.loads((RAIZ / "flujos" / "video_acabado.json").read_text(encoding="utf-8"))
    srv._preparar_acabado(g, "imga_x_wan720p.mp4", 5, vertical=False)
    _enlaces_validos(g)
    assert next(n for n in g.values() if n["class_type"] == "LoadVideo")["inputs"]["file"] == "imga_x_wan720p.mp4"
    esc = next(n for n in g.values() if n["class_type"] == "ImageScale")["inputs"]
    assert (esc["width"], esc["height"]) == (1920, 1080)
    assert next(n for n in g.values() if n["class_type"] == "CreateVideo")["inputs"]["fps"] == 32.0
    assert next(n for n in g.values() if n["class_type"] == "ImageFromBatch")["inputs"]["batch_index"] == 80


def _hist(video, imagen=None):
    salidas = {"12": {"images": [{"filename": video, "subfolder": "video", "type": "output"}], "animated": [True]}}
    if imagen:
        salidas["14"] = {"images": [{"filename": imagen, "subfolder": "IMGA", "type": "output"}]}
    return {"status": {"messages": [["execution_start", {"timestamp": 1000}], ["execution_success", {"timestamp": 61000}]]},
            "outputs": salidas}


def test_video_definitivo_encadena_y_recoge(srv, monkeypatch):
    env = _capturar_video(srv, monkeypatch)
    _imagen(srv, "f.png", 1280, 720)
    srv.generar_video("x", "f.png", calidad="definitivo")
    historial = {"pid-1": _hist("IMGA_video_00001_.mp4")}
    monkeypatch.setattr(srv, "_historial", lambda pid: historial.get(pid))
    monkeypatch.setattr(srv, "_json", lambda ruta, cuerpo=None, timeout=30: {"queue_running": [[0, "pid-2"]], "queue_pending": []})
    monkeypatch.setattr(srv, "_bajar", lambda f: b"MP4" if f["filename"].endswith(".mp4") else _png())
    monkeypatch.setattr(srv, "_subir_bytes", lambda datos, nombre: "subida_" + nombre)
    estado, txt = srv._avanzar_video("pid-1")
    assert estado == "en_curso" and "paso 2 de 2" in txt[0]
    g2 = env[1]
    _enlaces_validos(g2)
    assert next(n for n in g2.values() if n["class_type"] == "LoadVideo")["inputs"]["file"].endswith("_wan720p.mp4")
    historial["pid-2"] = _hist("IMGA_video_00002_.mp4", "video_fotograma_00001_.png")
    estado, res = srv._avanzar_video("pid-1")
    assert estado == "hecho" and res[0].startswith("Hecho: video definitivo 1920x1080 a 32 fps")  # sin AVISO
    t = json.loads((srv.VIDEOS_PEND / "pid-1.hecho.json").read_text(encoding="utf-8"))
    assert Path(t["resultado"]).read_bytes() == b"MP4" and Path(t["fotograma"]).exists()
    assert Path(t["resultado"]).with_suffix(".json").exists() and t["segundos"] == 120.0
    assert not (srv.VIDEOS_PEND / "pid-1.json").exists()
    assert srv.esperar_resultado("pid-1")[0].startswith("Hecho")  # se puede volver a pedir


def _png(tipo="normal", w=320, h=180):
    """PNG de prueba: 'normal' (degradado con formas, como una foto), 'gris' (uniforme) o 'ruido'."""
    import io
    import random
    from PIL import Image as I, ImageDraw
    if tipo == "gris":
        im = I.new("RGB", (w, h), (127, 127, 127))
    elif tipo == "ruido":
        rnd = random.Random(1)
        im = I.frombytes("RGB", (w, h), bytes(rnd.randrange(256) for _ in range(w * h * 3)))
    else:
        im = I.linear_gradient("L").resize((w, h)).convert("RGB")
        d = ImageDraw.Draw(im)
        d.ellipse((w // 4, h // 4, w // 2, h // 2 + 20), fill=(200, 170, 120))
        d.rectangle((w // 2, h // 3, w - 30, h - 20), fill=(60, 90, 50))
    b = io.BytesIO()
    im.save(b, format="PNG")
    return b.getvalue()


def test_video_error_en_comfyui(srv, monkeypatch):
    _capturar_video(srv, monkeypatch)
    _imagen(srv, "f.png", 1280, 720)
    srv.generar_video("x", "f.png")
    monkeypatch.setattr(srv, "_historial", lambda pid: {"status": {"messages": [
        ["execution_error", {"node_type": "KSamplerAdvanced", "exception_message": "sin memoria"}]]}, "outputs": {}})
    estado, txt = srv._avanzar_video("pid-1")
    assert estado == "error" and "sin memoria" in txt[0]


def test_video_trabajo_perdido(srv, monkeypatch):
    _capturar_video(srv, monkeypatch)
    _imagen(srv, "f.png", 1280, 720)
    srv.generar_video("x", "f.png")
    monkeypatch.setattr(srv, "_historial", lambda pid: None)
    monkeypatch.setattr(srv, "_json", lambda ruta, cuerpo=None, timeout=30: {"queue_running": [], "queue_pending": []})
    estado, txt = srv._avanzar_video("pid-1")
    assert estado == "error" and "ya no tiene este trabajo" in txt[0]


def test_video_sin_memoria(srv, monkeypatch):
    llamadas = []
    monkeypatch.setattr(srv, "_memoria_gpu_gb", lambda: 0.7)
    monkeypatch.setattr(srv, "_json", lambda ruta, cuerpo=None, timeout=30: llamadas.append(ruta))
    monkeypatch.setattr(srv.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="ComfyUI servidor"):
        srv._comprobar_memoria_video()
    assert llamadas == ["/free"]
    estados = iter([10.0, 90.0])
    monkeypatch.setattr(srv, "_memoria_gpu_gb", lambda: next(estados))
    assert "liberado" in srv._comprobar_memoria_video()


def test_video_cerrojo_entre_clientes(srv, monkeypatch):
    _capturar_video(srv, monkeypatch)
    _imagen(srv, "f.png", 1280, 720)
    srv.generar_video("x", "f.png")
    (srv.VIDEOS_PEND / "pid-1.lock").write_text("")
    monkeypatch.setattr(srv, "_historial", lambda pid: pytest.fail("con cerrojo no debe consultar"))
    estado, txt = srv._avanzar_video("pid-1")
    assert estado == "en_curso" and "otro cliente" in txt[0]


# ------------------------------------------------------------------ revision del resultado (1.3.1)
@pytest.mark.parametrize("tipo,espera", [("normal", ""), ("gris", "color plano"), ("ruido", "ruido de colores")])
def test_revisar_imagen(srv, tmp_path, tipo, espera):
    f = tmp_path / f"{tipo}.png"
    f.write_bytes(_png(tipo))
    aviso = srv._revisar(f)
    assert (aviso == "") if not espera else (espera in aviso and "reiniciar el PC" in aviso)


def test_revisar_desactivado_y_fichero_roto(srv, tmp_path, monkeypatch):
    f = tmp_path / "gris.png"
    f.write_bytes(_png("gris"))
    monkeypatch.setattr(srv, "REVISAR", False)
    assert srv._revisar(f) == ""
    monkeypatch.setattr(srv, "REVISAR", True)
    roto = tmp_path / "roto.png"
    roto.write_bytes(b"no es un png")
    assert "no he podido revisar" in srv._revisar(roto)


def test_recoger_imagen_gris_avisa(srv, monkeypatch):
    h = {"status": {"messages": [["execution_start", {"timestamp": 1000}], ["execution_success", {"timestamp": 3000}]]},
         "outputs": {"9": {"images": [{"filename": "rapido_00001_.png", "subfolder": "IMGA", "type": "output"}]}}}
    monkeypatch.setattr(srv, "_historial", lambda pid: h)
    monkeypatch.setattr(srv, "_http", lambda ruta, datos=None, tipo=None, timeout=30: _png("ruido"))
    (texto, imgs), estado = srv._recoger("pid-9")
    assert estado == "hecho" and texto.startswith("AVISO") and "Hecho en 2.0 s" in texto and imgs
    png = next(srv.BASE.glob("*/*.png"))
    assert png.name.endswith("_img_1.png") and not set(png.name) & set('<>:"/\\|?*')  # sin pendiente: nombre valido en Windows
    meta = json.loads(next(srv.BASE.glob("*/*.json")).read_text(encoding="utf-8"))
    assert "ruido" in meta["aviso"]


def test_video_gris_avisa(srv, monkeypatch):
    _capturar_video(srv, monkeypatch)
    _imagen(srv, "f.png", 1280, 720)
    srv.generar_video("x", "f.png")
    monkeypatch.setattr(srv, "_historial", lambda pid: _hist("IMGA_video_00001_.mp4", "video_fotograma_00001_.png"))
    monkeypatch.setattr(srv, "_bajar", lambda f: b"MP4" if f["filename"].endswith(".mp4") else _png("gris"))
    estado, res = srv._avanzar_video("pid-1")
    assert estado == "hecho" and res[0].startswith("AVISO") and "color plano" in res[0] and "Hecho: video borrador" in res[0]
    t = json.loads((srv.VIDEOS_PEND / "pid-1.hecho.json").read_text(encoding="utf-8"))
    assert "color plano" in t["aviso"]
