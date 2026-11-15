@echo off
REM ====================================================================
REM  00_inicializar_git.bat - MCP comfyui de IMGA
REM  Crea el repositorio git en esta carpeta (rama main) y hace el primer commit.
REM  Si ya existe .git, solo muestra el estado. Doble clic desde el Explorador.
REM  Si git no confia en la unidad de red (Z:), anade SOLO esta ruta a safe.directory.
REM ====================================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0.."
where git >nul 2>&1
if errorlevel 1 (
  echo ERROR: no encuentro git en el PATH. Instala Git for Windows y repite.
  pause
  exit /b 1
)
git --version
echo Carpeta: %CD%
if exist ".git" goto ya
git init -b main
git status >nul 2>&1
if errorlevel 1 (
  echo Git no confia en esta carpeta de red: se anade esta ruta a safe.directory global
  git config --global --add safe.directory "%CD:\=/%"
)
git add -A
git commit -q -m "Importa el MCP comfyui 1.1.0 con estructura SDD" -m "Servidor, flujos API, lanzador, plantillas por app, scripts de instalacion/configuracion/publicacion, pruebas pytest, specs 001-003 y documentacion para agentes." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
if errorlevel 1 (
  echo ERROR al hacer el commit.
  pause
  exit /b 1
)
:ya
echo.
git status --short
git log --oneline -5
git ls-files | find /c /v ""
echo.
pause
