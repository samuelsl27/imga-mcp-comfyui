@echo off
REM ====================================================================
REM  01_commit_git.bat - MCP comfyui de IMGA
REM  1. Pasa las pruebas (pytest, sin ComfyUI). Si fallan, no hace commit.
REM  2. git add -A (respeta .gitignore) y commit con el mensaje de
REM     scripts\mensaje_commit.txt (UTF-8; lo escribe el agente).
REM  3. Muestra el ultimo commit y deja el estado.
REM  Doble clic desde el Explorador. No sube nada a ningun servidor (no hay remoto).
REM ====================================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0.."
where git >nul 2>&1
if errorlevel 1 (
  echo ERROR: no encuentro git en el PATH.
  pause
  exit /b 1
)
if not exist "scripts\mensaje_commit.txt" (
  echo ERROR: falta scripts\mensaje_commit.txt ^(el mensaje del commit^).
  pause
  exit /b 1
)
set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not exist "%UV%" set "UV=uv"
echo == Pruebas
"%UV%" run --no-project --python 3.13 --with mcp==1.30.0 --with pillow==13.0.0 --with pytest python -m pytest -q -p no:cacheprovider
if errorlevel 1 (
  echo.
  echo LAS PRUEBAS FALLAN: no se hace el commit.
  pause
  exit /b 1
)
echo.
echo == Antes del commit
git log --oneline -1
git status --short
echo.
git add -A
if errorlevel 1 goto fallo
git -c core.quotepath=false diff --cached --stat
echo.
git commit -q -F "scripts\mensaje_commit.txt"
if errorlevel 1 goto fallo
echo == Despues del commit
git log --oneline -3
echo Ficheros versionados:
git ls-files | find /c /v ""
echo Cambios sin confirmar (deberia salir vacio):
git status --short
echo.
echo RESULTADO: COMMIT OK
pause
exit /b 0
:fallo
echo.
echo ERROR en git: no se ha hecho el commit.
pause
exit /b 1
