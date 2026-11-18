# MCP de ComfyUI — `comfyui` (propio de IMGA)

| Campo | Valor |
|---|---|
| Proyecto | Propio de IMGA. **Repositorio (desarrollo, git):** `Z:\cu\SOFTWARE_APLIACIONES_IMGA\Desarrollado_IMGA\MCP_ConfyUI` → copia publicada `C:\Notas_IA\mcp\comfyui\` → instalado `C:\ComfyUI_MCP\` |
| Licencia | Código: MIT (`LICENSE`). Los modelos que usa tienen su propia licencia: Qwen-Image 2.1 es **no comercial** (ver «Modelos y licencias») |
| Versión | 1.3.1 (2026-11-16: aviso si el resultado sale gris o con ruido) · 1.3.0 (2026-11-16: vídeo con Wan 2.2, borrador y definitivo 1080p) · 1.2.0 (Qwen-Image 2.1 por defecto, visor en ComfyUI, flujos editables) · SDK `mcp==1.30.0` (la 2.x renombra FastMCP: no usar sin adaptar) · `pillow==13.0.0` · Python 3.13 (uv) |
| Transporte | stdio. Habla por HTTP con ComfyUI en `http://127.0.0.1:8188`; **si no responde, lo arranca él** (ver abajo) |
| Lanzador | `C:\ComfyUI_MCP\comfyui-mcp-launch.bat` (fuente: `lanzador\`). En apps Node: `cmd.exe /d /c C:\ComfyUI_MCP\comfyui-mcp-launch.bat` |
| Flujos | `C:\ComfyUI_MCP\flujos\` (fuente: `flujos\`): exportados en formato API de las plantillas oficiales de ComfyUI v0.45.0, con la LoRA de 4 pasos activada |
| Resultados | `C:\IA_Imagenes\AAAA-MM-DD\HHMMSS_<tipo>_N.png` + `.json` (prompt, semilla, flujo, referencias, tiempo). Última imagen: `C:\IA_Imagenes\ultima.json`. Vídeos: `HHMMSS_video_<calidad>.mp4` + `.png` (fotograma) + `.json`; en curso: `C:\IA_Imagenes\videos_pendientes\` |
| Referencias | Dejar las imágenes en `C:\IA_Imagenes\entrada\` (o dar la ruta completa) |
| Specs | Desarrollo: `specs\` de este repositorio · Equipo: `C:\Notas_IA\specs\006-comfyui-imagen-video\` |

## Herramientas (9)
| Herramienta | Qué hace |
|---|---|
| `estado` | ComfyUI responde, versión, memoria libre GPU/RAM, cola, flujos, carpetas, última imagen |
| `generar_imagen(prompt, modo, ancho, alto, semilla)` | `modo="calidad"` (por defecto) **Qwen-Image 2.1** · `"rapido"` Z-Image Turbo · `"texto"` Qwen-Image 2512 (rótulos) |
| `editar_imagen(instruccion, imagenes, semilla, modo)` | `calidad` (por defecto) Qwen-Image 2.1, 1-10 imágenes · `rapido` Qwen-Edit 2511, 1-3; «imagen 1/2/…»; la 1 marca el encuadre |
| `retocar_ultima(instruccion, imagenes_extra, semilla)` | Edita la última imagen generada (cadena de retoques) |
| `esperar_resultado(prompt_id, segundos)` | Recoge un trabajo que tardó más de `COMFY_MCP_ESPERA` (50 s) |
| `ver_imagen(ruta, max_lado)` | Devuelve una imagen del disco al chat |
| `listar_resultados(cuantos)` | Últimas imágenes con texto, semilla y tiempo |
| `liberar_memoria()` | Descarga los modelos de ComfyUI (antes de cargar algo grande en LM Studio) |
| `generar_video(prompt, imagen, calidad, segundos, semilla)` | Vídeo desde una imagen (primer fotograma) con Wan 2.2. `calidad="borrador"` (por defecto) 832×576 16 fps, ~8-9 min por 5 s · `"definitivo"` 1920×1080 32 fps (Wan 720p + RelayVSR ×2 + FILM ×2), ~25-30 min. Devuelve un `prompt_id` al momento; seguir con `esperar_resultado` |

Las herramientas que generan devuelven la imagen **dentro de la respuesta** (JPEG reducido a 1024 px),
así el modelo la ve y puede proponer el siguiente retoque. La imagen completa queda en disco.
Todo aparece también en la cola y el historial de ComfyUI (misma instancia).

## Modelos y licencias (1.2.0)
| Modo | Generar | Editar | Licencia |
|---|---|---|---|
| `calidad` (por defecto) | Qwen-Image 2.1 (~65 s cargado) | Qwen-Image 2.1, 1-10 refs (~90 s cargado) | **Qwen Research License: no comercial** sin licencia de Qwen |
| `rapido` | Z-Image Turbo (~20 s) | Qwen-Edit 2511 + 4 pasos, 1-3 refs (~40 s) | Apache-2.0 |
| `texto` | Qwen 2512 + 4 pasos | — | Apache-2.0 |
`COMFY_MCP_MODELO=clasico` en el lanzador hace que `calidad` use solo los Apache-2.0. Cada imagen lleva modelo y licencia en su `.json`.

## Ver y editar lo que hace el MCP (1.2.0)
- Complemento `imga_mcp` (se instala con el 03 en `C:\ComfyUI\ComfyUI\custom_nodes\imga_mcp`; reiniciar ComfyUI).
- Con la interfaz abierta, cada trabajo del MCP se abre en una pestaña «MCP HH:MM tipo» con su esquema de nodos.
- Si no hay interfaz abierta, el MCP la abre (Edge en modo aplicación, como mucho una vez cada 10 min). `COMFY_MCP_VISOR=0` lo quita.
- Menú **IMGA**: *Abrir último trabajo del MCP* · *Seguir al MCP* (activar/desactivar) · *Guardar como flujo del MCP*
  (guarda el esquema abierto como `generar_qwen21`, `editar_qwen21`, `generar_rapido`, `generar_texto` o `editar` en
  `C:\ComfyUI\ComfyUI\user\default\imga_flujos\`; copia del anterior en `copias\`). El MCP lo usa desde el siguiente
  trabajo si tiene los nodos imprescindibles; si no, usa el instalado y lo avisa.

## Arranque automático de ComfyUI (v1.1.0)
`estado`, `generar_imagen`, `editar_imagen` y `retocar_ultima` comprueban `/system_stats`; si ComfyUI no responde:
1. Mira si ya hay un `python main.py --port 8188` en marcha (arrancando) o si otro cliente lo lanzó hace < 20 s
   (`C:\IA_Imagenes\.arranque_comfyui`): entonces solo espera, no lanza otro.
2. Si no, lo lanza igual que el acceso directo: `start "ComfyUI servidor" /min cmd /d /c C:\ComfyUI\comfyui-launch.bat`
   (ventana minimizada en la barra de tareas; cerrarla = parar ComfyUI). Se lanza desligado de la app cliente
   (sigue en marcha si se cierra Claude/Bionic/Hermes/LM Studio) y con el entorno completo de Windows leído del
   registro (Hermes solo pasa unas pocas variables al MCP).
3. Espera hasta 40 s (`COMFY_MCP_ARRANQUE`; en este PC arranca en ≈ 15-20 s) y sigue con el trabajo; el tiempo
   de arranque cuenta dentro de los 50 s de `COMFY_MCP_ESPERA`. Si no da tiempo, la herramienta pide volver a llamarla.
`liberar_memoria` y `esperar_resultado` no lo arrancan. Desactivar: `COMFY_MCP_AUTOARRANQUE=0` en el lanzador.
No abre la interfaz web: para verla, el acceso directo «ComfyUI» (detecta que ya está en marcha y solo abre la ventana).

## Cómo funciona
1. Carga el flujo API (`flujos\*.json`), localiza los nodos por tipo y título (no por número), pone
   prompt, semilla, tamaño e imágenes; para 2–3 referencias añade nodos `LoadImage` y los conecta a
   `image2`/`image3` de los dos `TextEncodeQwenImageEditPlus`.
2. Sube las referencias con `POST /upload/image` (nombre único `imga_<id>_<nombre>`).
3. `POST /prompt`, espera hasta 50 s consultando `/history`; si no ha terminado devuelve el
   `prompt_id` para `esperar_resultado` (así no choca con el tiempo máximo de la app cliente).

## Uso diario
- Arrancar ComfyUI (acceso directo «ComfyUI»). En Claude Desktop: «genera una imagen de…»,
  «edita C:\IA_Imagenes\entrada\foto.jpg para que…», «ahora quita el camión» (→ `retocar_ultima`).
- **Las imágenes adjuntadas en el chat no llegan al MCP**: guardarlas en `C:\IA_Imagenes\entrada\`.
- Las imágenes que el MCP devuelve al chat se envían a Claude (nube), como con cualquier MCP.

## Desarrollo, publicación e instalación
1. **Desarrollar aquí** siguiendo `AGENTS.md` (spec → código → pruebas → versión → commit).
   Pruebas: `uv run --no-project --python 3.13 --with mcp==1.30.0 --with pillow==13.0.0 --with pytest pytest -q`
2. **Publicar** en `C:\Notas_IA`: `scripts\publicar_en_notas.bat` (pasa las pruebas y copia con SHA-256 a
   `C:\Notas_IA\mcp\comfyui\` y `C:\Notas_IA\scripts\comfyui\`).
3. **Instalar** en el PC: `C:\Notas_IA\scripts\comfyui\03_instalar_mcp_comfyui.bat` — crea `C:\ComfyUI_MCP\.venv`,
   copia servidor, flujos y lanzador (SHA-256) y prueba por stdio (9 herramientas, `estado`, imagen 768²).
4. **Configurar las apps** (solo la primera vez o si cambia el bloque): `04_configurar_mcp_comfyui.bat` — LM Studio,
   Hermes (con `env`) y Claude Desktop (cerrado; si está abierto: `--solo claude-desktop` después). Bionic desde su UI
   (Configuración → Integraciones → MCP → *Agregar MCP personalizado*: `comfyui`, «En esta computadora»,
   `C:\Windows\System32\cmd.exe`, argumentos `/d` · `/c` · `C:\ComfyUI_MCP\comfyui-mcp-launch.bat`, espera 120 s).
5. Tras reinstalar: reiniciar la app (Bionic: apagar/encender `comfyui`; Hermes: cerrar y abrir).
6. Cambiar un flujo: abrir la plantilla en ComfyUI, ajustarla, exportar en formato API a `flujos\<nombre>.json`,
   pasar las pruebas y publicar.

## Variables de entorno (en el lanzador)
`COMFY_URL` (http://127.0.0.1:8188) · `IA_IMAGENES` (C:\IA_Imagenes) · `COMFY_MCP_ESPERA` (50) ·
`COMFY_MCP_AUTOARRANQUE` (1) · `COMFY_MCP_ARRANQUE` (40) · `COMFY_LANZADOR` (C:\ComfyUI\comfyui-launch.bat) ·
`COMFY_MCP_REVISAR` (1: avisa si el resultado sale gris o con ruido; 0 = no revisa)

## Mantenimiento y problemas
- «No se puede conectar con ComfyUI» / «aún no responde»: el MCP lo intenta arrancar solo; si falla, mirar la
  ventana «ComfyUI servidor» o arrancarlo con el acceso directo y repetir.
- Tarda mucho la primera vez: ComfyUI carga el modelo (≈ 50 s Z-Image, ≈ 90 s edición, ≈ 2,5 min Qwen 2512).
- Modelos locales (LM Studio/Bionic/Hermes): Qwen3.6 35B A3B (~22 GB) y los modelos de ComfyUI comparten los 64 GB de GPU;
  si falta memoria, `liberar_memoria` o descargar el modelo de LM Studio. Sin verificar todavía si cada app muestra la
  imagen devuelta por la herramienta (la ruta del PNG va siempre en el texto).
- Vídeo (1.3.0): los pasos se encadenan solos en segundo plano mientras alguna app tenga el MCP abierto, y también
  al llamar a `esperar_resultado`; el estado queda en disco (`videos_pendientes`). Antes de lanzar comprueba que hay
  ≥ 45 GB libres de GPU (`COMFY_MCP_VIDEO_GB`): si ComfyUI retiene memoria tras un trabajo cortado, pide cerrar la
  ventana «ComfyUI servidor».
- Si una imagen o el fotograma de un vídeo sale gris uniforme o con ruido de colores, la respuesta empieza por
  **AVISO** (1.3.1): la GPU está calculando mal (pasó el 2026-11-16 con todos los modelos) → reiniciar el PC. Umbrales
  medidos en 16 imágenes del PC; una imagen real muy granulada podría dar un aviso falso (no bloquea nada).

## Estado (2026-11-15)
Verificado en Claude Desktop, LM Studio, Bionic y Hermes (Qwen3.6 35B A3B en las locales); arranque automático
verificado desde Bionic y Hermes (≈ 17 s). Detalle: `C:\Notas_IA\registro\CHANGELOG.md`.
2026-11-16: `generar_video` (1.3.0) verificado desde Claude Desktop: borrador 8,0 min y definitivo 1080p 25,5 min.
Desde LM Studio, Bionic y Hermes no se usa para vídeo (decisión de Andrés, 2026-11-16).
