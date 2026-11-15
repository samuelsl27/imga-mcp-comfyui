@echo off
REM ====================================================================
REM  03_instalar_mcp_comfyui.bat  -  Spec 006 de C:\Notas_IA
REM  T6 - Instala o actualiza el MCP propio comfyui en C:ComfyUI_MCP y lo prueba por stdio (si ComfyUI esta arrancado, genera una imagen de prueba). No toca ninguna app de IA.
REM  Informe: C:\Notas_IA\inventario\auto\instalacion_mcp_comfyui_<fecha>.txt
REM ====================================================================
setlocal
chcp 65001 >nul
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmm"') do set "TS=%%i"
set "NOTAS=C:\Notas_IA"
set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not exist "%UV%" set "UV=uv"

"%UV%" run --no-project --python 3.13 python "%~dp0instalar_mcp_comfyui.py" ^
  --informe "%NOTAS%\inventario\auto\instalacion_mcp_comfyui_%TS%.txt" %*

echo.
echo Informe: %NOTAS%\inventario\auto\instalacion_mcp_comfyui_%TS%.txt
pause
