# Spec 002 — Arranque automático de ComfyUI

| Campo | Valor |
|---|---|
| Estado | Hecha (1.1.0, 2026-11-15) |

## Contexto
Andrés: «lo suyo es que Bionic, Hermes o Claude puedan despertar automáticamente la app al solicitarlo».

## Requisitos (EARS)
- **RF-1** Cuando una herramienta que necesita ComfyUI (`estado`, `generar_imagen`, `editar_imagen`, `retocar_ultima`)
  no obtenga respuesta, el servidor deberá arrancarlo con `C:\ComfyUI\comfyui-launch.bat` en una ventana minimizada
  «ComfyUI servidor» y esperar a que responda (máx. `COMFY_MCP_ARRANQUE`, 40 s).
- **RF-2** Mientras ya haya un ComfyUI arrancando (proceso `main.py --port 8188` o marca de < 20 s), el servidor no
  deberá lanzar otro.
- **RF-3** El ComfyUI arrancado deberá seguir funcionando aunque se cierre la app que lo pidió y deberá recibir el
  entorno completo del usuario aunque la app pase un entorno reducido (Hermes).
- **RF-4** Si no responde a tiempo, la herramienta deberá pedir que se vuelva a llamar.
- **RF-5** Donde `COMFY_MCP_AUTOARRANQUE=0`, el servidor no deberá arrancar nada.

## Validación
| RF | Prueba | Resultado |
|---|---|---|
| RF-1 | Bionic 2026-11-15 19:30 con ComfyUI cerrado: 17 s + imagen 32,2 s | ✅ |
| RF-2 | `test_asegurar_no_lanza_dos_veces`, `test_asegurar_marca_reciente` | ✅ (pytest) |
| RF-3 | Hermes 19:35 (env reducido): 17 s + 36,2 s; perfil `--disable-mmap` aplicado | ✅ (entorno); supervivencia al cerrar la app: PENDIENTE de comprobar a propósito |
| RF-4 | `test_asegurar_no_lanza_dos_veces` (mensaje) | ✅ (pytest) |
| RF-5 | `test_autoarranque_desactivado` | ✅ (pytest) |
