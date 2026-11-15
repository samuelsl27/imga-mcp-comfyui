"""Pruebas sin ComfyUI (se simulan las llamadas HTTP). Ejecutar desde la raiz del repositorio:

    uv run --no-project --python 3.13 --with mcp==1.30.0 --with pillow==13.0.0 --with pytest pytest -q

Comprueban lo que se puede comprobar fuera del PC: las 8 herramientas, como se rellenan los flujos
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
                "ver_imagen", "listar_resultados", "liberar_memoria"}


@pytest.fixture()
def srv(tmp_path, monkeypatch):
    """Carga el servidor con IA_IMAGENES en una carpeta temporal y los flujos del repositorio."""
    monkeypatch.setenv("IA_IMAGENES", str(tmp_path / "IA_Imagenes"))
    monkeypatch.setenv("COMFY_MCP_ARRANQUE", "3")
    spec = importlib.util.spec_from_file_location("servidor_comfyui_mcp", SERVIDOR)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.FLUJOS = RAIZ / "flujos"  # en el PC estan junto al servidor; aqui, en flujos/
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


def test_ocho_herramientas(srv):
    nombres = {t.name for t in asyncio.run(srv.mcp.list_tools())}
    assert nombres == HERRAMIENTAS


@pytest.mark.parametrize("modo,tipo", [("rapido", "rapido"), ("texto", "texto")])
def test_generar_rellena_flujo(srv, monkeypatch, modo, tipo):
    env = _capturar(srv, monkeypatch)
    srv.generar_imagen("una cantera", modo=modo, ancho=640, alto=480, semilla=7)
    g, t, meta = env[0]
    assert t == tipo and meta["semilla"] == 7 and (meta["ancho"], meta["alto"]) == (640, 480)
    textos = [n["inputs"].get("text") for n in g.values() if n["class_type"] == "CLIPTextEncode"]
    assert "una cantera" in textos
    assert any(n["class_type"] == "KSampler" and n["inputs"]["seed"] == 7 for n in g.values())
    _enlaces_validos(g)


@pytest.mark.parametrize("n", [1, 2, 3])
def test_editar_con_n_referencias(srv, monkeypatch, n):
    env = _capturar(srv, monkeypatch)
    refs = []
    for i in range(n):
        p = srv.ENTRADA / f"ref{i + 1}.png"
        p.write_bytes(b"x")
        refs.append(p.name)
    srv.editar_imagen("cambia el cielo", refs, semilla=3)
    g, t, meta = env[0]
    assert t == "editar" and len(meta["referencias"]) == n
    _enlaces_validos(g)
    cargas = [n_ for n_ in g.values() if n_["class_type"] == "LoadImage"]
    assert len(cargas) == n
    for cod in (x for x in g.values() if x["class_type"] == "TextEncodeQwenImageEditPlus"):
        for i in (2, 3):
            assert (f"image{i}" in cod["inputs"]) == (i <= n)


def test_editar_rechaza_4_referencias(srv, monkeypatch):
    _capturar(srv, monkeypatch)
    for i in range(4):
        (srv.ENTRADA / f"r{i}.png").write_bytes(b"x")
    with pytest.raises(RuntimeError):
        srv.editar_imagen("x", [f"r{i}.png" for i in range(4)])


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
    with pytest.raises(RuntimeError, match="No se puede conectar"):
        srv._asegurar_comfy()


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
    for f in ("generar_rapido", "generar_texto", "editar"):
        g = json.loads((RAIZ / "flujos" / f"{f}.json").read_text(encoding="utf-8"))
        assert all("class_type" in n for n in g.values()), f
        _enlaces_validos(g)


def test_version_coincide_con_pyproject(srv):
    import tomllib
    proyecto = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert srv.VERSION == proyecto, "subir la version en pyproject.toml y en VERSION del servidor a la vez"
