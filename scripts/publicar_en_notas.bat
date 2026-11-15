@echo off
REM ====================================================================
REM  publicar_en_notas.bat - MCP comfyui de IMGA
REM  1. Pasa las pruebas (pytest, sin ComfyUI). Si fallan, no publica.
REM  2. Copia servidor, flujos, lanzador, plantillas y scripts 03/04 a C:\Notas_IA (SHA-256).
REM  Despues: C:\Notas_IA\scripts\comfyui\03_instalar_mcp_comfyui.bat
REM  Opcion: --simular (no copia, solo dice que cambiaria)
REM ====================================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0.."
set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not exist "%UV%" set "UV=uv"
echo == Pruebas
"%UV%" run --no-project --python 3.13 --with mcp==1.30.0 --with pillow==13.0.0 --with pytest python -m pytest -q -p no:cacheprovider
if errorlevel 1 (
  echo.
  echo LAS PRUEBAS FALLAN: no se publica.
  pause
  exit /b 1
)
echo.
echo == Publicar en C:\Notas_IA
"%UV%" run --no-project --python 3.13 python "%~dp0publicar_en_notas.py" %*
echo.
pause
