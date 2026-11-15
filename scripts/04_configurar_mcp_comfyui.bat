@echo off
REM ====================================================================
REM  04_configurar_mcp_comfyui.bat  -  Spec 006 de C:\Notas_IA (rev3)
REM  T6 - Anade el MCP comfyui a Claude Desktop, LM Studio y Hermes con copia de seguridad,
REM  sin tocar los demas MCP. Bionic: desde su UI (instrucciones al final del informe).
REM  Claude Desktop solo se toca si esta CERRADO del todo (tambien la bandeja); si esta abierto
REM  se salta y queda pendiente:   04_configurar_mcp_comfyui.bat --solo claude-desktop
REM  Opciones: --solo claude-desktop,lmstudio,hermes   --sin-prueba
REM  Informe: C:\Notas_IA\inventario\auto\configuracion_mcp_comfyui_<fecha>.txt
REM ====================================================================
setlocal
chcp 65001 >nul
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmm"') do set "TS=%%i"
set "NOTAS=C:\Notas_IA"
set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not exist "%UV%" set "UV=uv"

"%UV%" run --no-project --python 3.13 --with ruamel.yaml python "%~dp0configurar_mcp_comfyui.py" ^
  --informe "%NOTAS%\inventario\auto\configuracion_mcp_comfyui_%TS%.txt" %*

echo.
echo Informe: %NOTAS%\inventario\auto\configuracion_mcp_comfyui_%TS%.txt
pause
