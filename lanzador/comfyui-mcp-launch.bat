@echo off
REM ====================================================================
REM  comfyui-mcp-launch.bat  -  Lanzador UNICO del MCP "comfyui" de IMGA (spec 006)
REM  Ubicacion instalada: C:\ComfyUI_MCP\comfyui-mcp-launch.bat
REM  Referencia:          C:\Notas_IA\mcp\comfyui\lanzador\comfyui-mcp-launch.bat
REM  Documentacion:       C:\Notas_IA\mcp\comfyui\README.md
REM
REM  Uso desde una app basada en Node (no ejecutan .bat directamente):
REM     command: C:\Windows\System32\cmd.exe
REM     args:    /d /c C:\ComfyUI_MCP\comfyui-mcp-launch.bat
REM
REM  Habla con ComfyUI en http://127.0.0.1:8188 (tiene que estar arrancado:
REM  acceso directo "ComfyUI"). Guarda resultados en C:\IA_Imagenes.
REM  IMPORTANTE: no escribir nada por stdout (es el canal MCP); errores a stderr.
REM ====================================================================
setlocal
set "VIRTUAL_ENV="
set "PYTHONPATH="
set "PYTHONHOME="
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
if not defined COMFY_URL set "COMFY_URL=http://127.0.0.1:8188"
if not defined IA_IMAGENES set "IA_IMAGENES=C:\IA_Imagenes"
if not defined COMFY_MCP_ESPERA set "COMFY_MCP_ESPERA=50"
set "MCP_ROOT=%~dp0"
if not exist "%MCP_ROOT%.venv\Scripts\python.exe" (
  echo [comfyui-mcp-launch] ERROR: falta %MCP_ROOT%.venv. Ejecuta C:\Notas_IA\scripts\comfyui\03_instalar_mcp_comfyui.bat 1>&2
  exit /b 1
)
"%MCP_ROOT%.venv\Scripts\python.exe" "%MCP_ROOT%servidor_comfyui_mcp.py"
exit /b %ERRORLEVEL%
