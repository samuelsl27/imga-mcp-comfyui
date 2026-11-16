# CHANGELOG — MCP `comfyui`

Formato: versión — fecha — cambios. Lo más reciente arriba.

## 1.3.1 — 2026-11-16 (spec 005, RF-8)
- **Revisión del resultado**: cada imagen guardada y el fotograma de muestra de un vídeo se miden (desviación de la
  luminancia y rugosidad = diferencia media entre píxeles vecinos / desviación, con la imagen a 512 px). Gris o plano
  (desviación < 3) o ruido (rugosidad > 0,6) → la respuesta empieza por **AVISO** y el `.json` lleva `aviso`. No
  bloquea. `COMFY_MCP_REVISAR=0` lo quita. Motivo: el 2026-11-16 la GPU calculó mal (gris y ruido con todos los
  modelos) y `generar_video` respondió «Hecho» igualmente. Umbrales medidos en 16 imágenes del PC: buenas
  desviación 38-62 y rugosidad 0,11-0,34; grises 0; ruido 0,84-1,16 (las 16 bien clasificadas).
- Tiempo previsto del definitivo 25-30 min (medido 25,5 desde Claude Desktop). 42 pruebas pytest (+6).
- Corregido (visto al publicar en el PC): si un trabajo no tenía su fichero en `pendientes`, la imagen se guardaba como
  `HHMMSS_?_1.png`, nombre no válido en Windows (fallaba al guardar). Ahora el tipo se limpia y por defecto es `img`.

## 1.3.0 — 2026-11-16 (spec 005) · complemento imga_mcp 1.3.0
- Validado desde Claude Desktop tras reiniciar el PC: borrador 8,0 min (revisado entero) y definitivo 1920×1080
  a 32 fps 25,5 min (revisado el fotograma de muestra).
- Herramienta **`generar_video(prompt, imagen, calidad, segundos, semilla)`** (9 herramientas): imagen → vídeo con
  Wan 2.2 14B + LoRA lightx2v 4 pasos. `borrador` (por defecto) 832×576 a 16 fps; `definitivo` Wan 1280×720 →
  RelayVSR ×2 → 1920×1080 → FILM ×2 = 32 fps. Todo Apache-2.0. Vertical si la imagen es vertical; aviso si se estira.
- Devuelve el `prompt_id` al momento; los pasos se encadenan en un hilo de segundo plano y en `esperar_resultado`,
  con el estado en `C:\IA_Imagenes\videos_pendientes\` (cerrojo para que dos apps no lancen el mismo paso).
- Comprobación de memoria antes de un vídeo (≥ 45 GB, `COMFY_MCP_VIDEO_GB`): libera la de ComfyUI y, si no basta,
  explica que hay que cerrar «ComfyUI servidor» (caso del 2026-11-16: 0,7 GB libres tras un trabajo cortado).
- Flujos `video_wan.json` (exportado de la plantilla `video_wan2_2_14B_i2v`, LoRA activada, + fotograma de muestra)
  y `video_acabado.json` (RelayVSR + ImageScale + FILM + fotograma; probado en ComfyUI: 720p → 1080p32 en 165 s).
- Complemento 1.3.0: «Guardar como flujo» admite `video_wan` y `video_acabado`; lee sin caché del navegador.
- Corregido (visto al publicar en el PC): con `COMFY_MCP_AUTOARRANQUE=0`, si la segunda comprobación sí respondía,
  `_asegurar_comfy` seguía hacia la rama de arranque. La prueba `test_autoarranque_desactivado` dependía de que
  ComfyUI estuviera parado; ahora usa un puerto cerrado. 36 pruebas pytest (9 de vídeo + 1 de este caso).

## 1.2.0 — 2026-11-15 (spec 004) · complemento imga_mcp 1.2.1
- Complemento 1.2.1: la pestaña del trabajo del MCP se abre ya encuadrada (Comfy.Canvas.FitView).
- Validado en el PC (21:47-21:58): `03_instalar` TODO OK; complemento cargado; desde Bionic (modo por defecto) →
  Qwen-Image 2.1, licencia indicada, 1216×832 en 115 s (con carga); la pestaña «MCP 21:55 calidad» se abrió sola.
- **Qwen-Image 2.1 por defecto** (`modo="calidad"`) para generar, editar (1-10 referencias) y retocar; `modo="rapido"`
  (Z-Image / Qwen-Edit 2511 4 pasos) y `modo="texto"` (Qwen 2512) bajo petición. `COMFY_MCP_MODELO=clasico` = solo Apache-2.0.
- Modelo y licencia en cada respuesta y en el `.json` de cada imagen (Qwen 2.1: licencia de investigación, no comercial).
- Flujos `generar_qwen21.json` y `editar_qwen21.json` (de las plantillas oficiales, probados en el PC).
- Flujos editados por el usuario en `C:\ComfyUI\ComfyUI\user\default\imga_flujos\` con prioridad (validados).
- Visor: abre la interfaz de ComfyUI si no está abierta (`COMFY_MCP_VISOR`); complemento `imga_mcp` (menú IMGA,
  pestaña por trabajo del MCP, guardar como flujo del MCP, latido).
- `estado` informa del modelo por defecto, visor y flujos editados. 26 pruebas pytest.

## 1.1.0 — 2026-11-15
- Arranque automático de ComfyUI desde `estado`, `generar_imagen`, `editar_imagen` y `retocar_ultima`
  (ventana minimizada «ComfyUI servidor», desligada del cliente, entorno completo del registro; sin duplicados).
- Variables nuevas: `COMFY_MCP_AUTOARRANQUE`, `COMFY_MCP_ARRANQUE`, `COMFY_LANZADOR`.
- `liberar_memoria` no falla si ComfyUI está parado. `estado` informa de `autoarranque` y del arranque.
- Verificado en el PC: Bionic y Hermes con ComfyUI parado (≈ 17 s de arranque); Claude Desktop y LM Studio.
- Repositorio git con estructura SDD, pruebas pytest (17) y script de publicación en `C:\Notas_IA`.

## 1.0.1 — 2026-11-15
- 8 herramientas (`estado`, `generar_imagen`, `editar_imagen`, `retocar_ultima`, `esperar_resultado`,
  `ver_imagen`, `listar_resultados`, `liberar_memoria`). Flujos de las plantillas oficiales de ComfyUI v0.45.0.
- Fijado `mcp==1.30.0` (la 2.3.0 renombró FastMCP).
