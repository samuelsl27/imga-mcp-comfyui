# Arquitectura del MCP `comfyui`

```
App de IA (Claude Desktop / LM Studio / Bionic / Hermes)
   │ stdio (JSON-RPC MCP)
   ▼
cmd.exe /d /c C:\ComfyUI_MCP\comfyui-mcp-launch.bat      ← vacía VIRTUAL_ENV/PYTHONPATH, fija variables
   ▼
C:\ComfyUI_MCP\.venv\Scripts\python.exe servidor_comfyui_mcp.py   (FastMCP, mcp 1.30.0)
   │ HTTP 127.0.0.1:8188                 │ si no responde: start "ComfyUI servidor" /min … comfyui-launch.bat
   ▼                                     ▼
ComfyUI v0.45.0 (C:\ComfyUI, ROCm)  ◄────┘   cola/historial compartidos con la interfaz web
   │
   ▼
C:\IA_Imagenes\AAAA-MM-DD\HHMMSS_<tipo>_N.png + .json     (y C:\ComfyUI\ComfyUI\output\IMGA\)
```

## Flujos (formato API)
| Fichero | Modelo | Herramienta |
|---|---|---|
| `generar_rapido.json` | Z-Image Turbo bf16 + Qwen3-4B + ae | `generar_imagen(modo="rapido")` |
| `generar_texto.json` | Qwen-Image 2512 fp8 + LoRA Lightning 4 pasos | `generar_imagen(modo="texto")` |
| `editar.json` | Qwen-Image-Edit 2511 fp8mixed + LoRA Lightning 4 pasos | `editar_imagen`, `retocar_ultima` |

El servidor carga el flujo, localiza nodos por `class_type` y título (`_nodo`), pone prompt/semilla/tamaño y, en
edición, sustituye la imagen 1 (el `LoadImage` que alimenta `FluxKontextImageScale`) y añade `LoadImage`
`imga_ref2`/`imga_ref3` conectados a `image2`/`image3` de los dos `TextEncodeQwenImageEditPlus`.

## Ejecución y tiempos
`POST /prompt` → sondeo de `/history/{id}` cada 2 s hasta `COMFY_MCP_ESPERA` (50 s, incluido el arranque). Si no
ha terminado, devuelve el `prompt_id` y un `pendientes\<id>.json`; `esperar_resultado` lo recoge. Al terminar baja
las imágenes por `/view`, las guarda con su `.json` y devuelve texto + JPEG ≤ 1024 px.

## Arranque automático (1.1.0)
`_asegurar_comfy`: `/system_stats` (3 s) → si no responde y `COMFY_MCP_AUTOARRANQUE≠0`: ¿hay `python … main.py
… --port 8188` (PowerShell/CIM) o marca `C:\IA_Imagenes\.arranque_comfyui` de < 20 s? → solo espera; si no, escribe
la marca y lanza `cmd /c start "ComfyUI servidor" /min cmd /d /c C:\ComfyUI\comfyui-launch.bat` con
`CREATE_BREAKAWAY_FROM_JOB` (si se puede) y el entorno completo del usuario leído del registro (Hermes pasa un `env`
reducido). Espera hasta `COMFY_MCP_ARRANQUE` (40 s). Medido en el PC: ≈ 17 s.

## Rendimiento de referencia (MS-S1, perfil `--disable-mmap`)
Z-Image 1024² 8 pasos ≈ 20 s cargado · Qwen 2512 1328² ≈ 35 s (≈ 2,5 min la 1.ª) · edición 1024² ≈ 40 s (≈ 80-90 s
la 1.ª o tras cambiar de modelo). Cambiar de flujo obliga a cargar otro modelo.
