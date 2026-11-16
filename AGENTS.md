# AGENTS.md — MCP `comfyui` de IMGA

> Punto de entrada para **cualquier agente de IA** (Claude Code, Claude Desktop, Hermes, Bionic…)
> que trabaje en este repositorio. Léelo entero antes de cambiar nada.

## Qué es

Servidor MCP propio de IMGA, S.L.P. que deja a las apps de IA del Minisforum MS-S1 (Claude Desktop,
LM Studio, Bionic, Hermes Agent) **generar y editar imágenes con el ComfyUI local** (por defecto Qwen-Image 2.1, licencia no comercial: ver spec 004)
(`http://127.0.0.1:8188`, GPU Radeon 8060S con ROCm). Si ComfyUI está parado, lo arranca.

- Propietario: Andrés M. Sáez Vizcaíno — IMGA, S.L.P. Uso interno.
- Idioma de trabajo: **español** (código, comentarios, mensajes y documentación).
- Método: *Spec-Driven Development* adaptado de mouredev/hello-sdd (`docs/flujo-sdd.md`).
- Repositorio (desarrollo): `Z:\cu\SOFTWARE_APLIACIONES_IMGA\Desarrollado_IMGA\MCP_ConfyUI`
- Instalación en el PC: `C:\ComfyUI_MCP\` (la hace `scripts\03_instalar_mcp_comfyui.bat` desde la copia publicada
  en `C:\Notas_IA\mcp\comfyui\`). Documentación del equipo: `C:\Notas_IA` (spec 006, fichas de apps, matriz).

## Orden de lectura

1. `docs/constitucion.md` — reglas no negociables.
2. `docs/arquitectura.md` — cómo funciona el servidor, de dónde salen los flujos, arranque automático.
3. `README.md` — herramientas, instalación, uso.
4. `specs/` — cambios numerados (spec → plan → tareas). El último abierto es el trabajo en curso.
5. `CHANGELOG.md` — versiones.

## Estructura

```
MCP_ConfyUI\
├── AGENTS.md / CLAUDE.md      ← contexto para agentes (CLAUDE.md solo importa AGENTS.md)
├── README.md / CHANGELOG.md
├── pyproject.toml             ← versión y dependencias fijadas (mcp==1.30.0, pillow==13.0.0)
├── servidor\                  ← servidor_comfyui_mcp.py (un solo fichero, stdio)
├── flujos\                    ← flujos ComfyUI en formato API (exportados desde la interfaz, no a mano)
├── complemento_comfyui\       ← imga_mcp: complemento de interfaz (menú IMGA, pestaña por trabajo, guardar flujo)
├── lanzador\                  ← comfyui-mcp-launch.bat (lo que ejecutan las apps)
├── plantillas\                ← bloques de configuración por app (Claude Desktop, LM Studio, Bionic, Hermes)
├── scripts\                   ← 00 git, 01 commit (mensaje en mensaje_commit.txt), 03 instalar, 04 configurar apps, publicar en C:\Notas_IA
├── tests\                     ← pytest sin ComfyUI (HTTP simulado)
├── docs\                      ← constitución, flujo SDD, arquitectura, plantillas de spec/plan/tareas
└── specs\NNN-nombre\          ← spec.md, plan.md, tasks.md
```

## Ciclo de un cambio

1. Spec en `specs/NNN-x/` (plantillas en `docs/plantillas_sdd/`), con preguntas abiertas resueltas.
2. Código + pruebas en `tests/` → `uv run --no-project --python 3.13 --with mcp==1.30.0 --with pillow==13.0.0 --with pytest pytest -q`
3. Subir versión en `pyproject.toml` **y** en `VERSION` de `servidor/servidor_comfyui_mcp.py` (deben coincidir;
   lo comprueba una prueba), y anotar en `CHANGELOG.md`.
4. Commit en git (mensajes en español, en presente: «Añade…», «Corrige…»): el agente escribe el mensaje en
   `scripts\mensaje_commit.txt` (no se versiona) y Andrés ejecuta `scripts\01_commit_git.bat` (pasa las pruebas antes).
5. `scripts\publicar_en_notas.bat` → copia a `C:\Notas_IA` (SHA-256) tras pasar las pruebas.
6. Andrés ejecuta `C:\Notas_IA\scripts\comfyui\03_instalar_mcp_comfyui.bat` (y `04_…` si cambian las apps).
7. Probar en las apps y documentar en `C:\Notas_IA` (ficha, matriz, CHANGELOG del equipo).

## Reglas para agentes

1. **No inventes.** Lo no comprobado se marca `PENDIENTE` o como hipótesis con su efecto.
2. **stdout es el canal MCP**: el servidor y el lanzador no escriben nada por stdout (errores a stderr).
3. **Los flujos no se editan a mano**: se ajustan en la interfaz de ComfyUI y se exportan en formato API.
   El servidor localiza los nodos por **tipo y título**, nunca por número.
4. **Tiempos**: ninguna herramienta debe pasar de ~60 s (límite de algunas apps). Lo largo devuelve un
   `prompt_id` para `esperar_resultado`. El arranque automático cuenta dentro de `COMFY_MCP_ESPERA`.
5. **No subir `mcp` a 2.x** sin adaptar el código (FastMCP pasó a llamarse MCPServer).
6. **Licencias de modelos**: antes de añadir un modelo o flujo nuevo, comprobar su licencia (uso comercial).
   Ejemplo de error ya cometido: Qwen-Image-2.1 es no comercial.
7. **Nada de secretos** en el repositorio.
8. **En el PC**: los agentes en la nube no escriben en la terminal; escriben `.bat` y Andrés los ejecuta.
   Tras copiar un fichero al PC, comprobar el contenido por checksum, no solo la fecha.
9. **No cerrar la ventana «ComfyUI servidor»** ni pedir que se cierre sin decir que es ComfyUI.

## Entorno de referencia

Minisforum MS-S1 · Ryzen AI Max+ 395 · Radeon 8060S (gfx1151) · 128 GB (64 GB asignados a la GPU; ComfyUI ve
≈ 102-107 GB) · Windows 11 · ComfyUI v0.45.0 en `C:\ComfyUI` (Python 3.12, torch 2.9.1+rocm7.2.1), perfil
`--disable-mmap` · MCP con Python 3.13 (uv) en `C:\ComfyUI_MCP\.venv`.
