# Spec 005 — Vídeo con Wan 2.2 14B desde el MCP

| Campo | Valor |
|---|---|
| Estado | **Cerrada** 2026-11-16 — implementada en 1.3.0, aviso de resultado gris/ruido en 1.3.1; validada desde Claude Desktop (borrador 8,0 min, definitivo 25,5 min, revisado por Andrés). Criterio 3: Andrés decide que el vídeo no hace falta en LM Studio ni en Hermes |
| Fecha | 2026-11-15 |
| Equipo | MS-S1 (desktop-3t6aul2) |
| Autor | Andrés (petición) / Claude (redacción) |

## Contexto
Andrés quiere generar vídeos cortos con IA local (sobrevuelos y presentaciones de canteras a partir de una imagen:
foto de dron, imagen de Qwen o render de topografía como el de un proyecto real).

Revisión de modelos del 2026-11-15 (detalle y fuentes en `C:\Notas_IA\apps\comfyui.md`):
- Wan 2.5, 2.6, 2.7 y 3.0 no tienen pesos descargables (solo API de pago). El último Wan local es **2.2 (Apache 2.0)**.
- MiniMax H3 y HunyuanVideo 1.5: sus licencias excluyen la UE → no se pueden usar en IMGA.
- LTX-2.5 (con audio, varias tomas): LTX-2.x Community License, gratis por debajo de 10 M$ → segunda opción, más adelante.
- Decisión de Andrés: **Wan 2.2 14B imagen → vídeo** primero.

Modelos (grupo `video14` de `C:\Notas_IA\scripts\comfyui\modelos_comfyui.py` rev. 4, ≈ 37 GB, SHA-256 de Hugging Face):
`wan2.2_i2v_high_noise_14B_fp8_scaled`, `wan2.2_i2v_low_noise_14B_fp8_scaled`, `umt5_xxl_fp8_e4m3fn_scaled`,
`wan_2.1_vae`, LoRA `wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise` / `_low_noise`. Plantillas oficiales:
`video_wan2_2_14B_i2v` y `video_wan2_2_14B_flf2v` (primer y último fotograma).

## Medida de referencia
Prueba a mano 2026-11-15 23:23-23:31 (plantilla oficial `video_wan2_2_14B_i2v`, LoRA 4 pasos activada, 832×576, 81 fotogramas = 5 s a 16 fps, semilla 515, imagen de partida = Qwen 2.1 de un proyecto de prueba 1216×832, ComfyUI recién arrancado y LM Studio sin modelo): **498,6 s (8 min 19 s)** → texto y VAE ≈ 40 s; modelo de alto ruido 8 s de carga + 2 pasos 98 s (≈ 49 s/paso); cambio al de bajo ruido ≈ 116 s; 2 pasos 99 s; decodificación del vídeo ≈ 138 s. Memoria: «VRAM» libre mínima 65,8 de 107 GB; RAM de Windows libre mínima **12,9 GB** (empezó en 54,6). Resultado `C:\ComfyUI\ComfyUI\output\video\IMGA_prueba_wan22_i2v_00001_.mp4` (H.264, 7,0 MB): movimiento de cámara suave hacia delante, terreno y pista coherentes, sin parpadeos visibles en 4 fotogramas revisados. Flujo guardado en la interfaz como `workflows\IMGA_prueba_wan22_i2v.json` y en formato API (borrador) en `imga_flujos\borradores\video_i2v_wan22_api.json`.

Consecuencia para el diseño: una herramienta de vídeo **no puede esperar** (≈ 8 min); debe devolver `prompt_id` al momento y `esperar_resultado` se llamará varias veces (≤ 60 s cada una).

## Borrador y definitivo (decisión de Andrés, 2026-11-15)
Decisión de Andrés (2026-11-15 23:37): **borradores a 832×576** (≈ 8 min); **definitivos en 1080p**. Wan 2.2 14B genera como máximo a 720p, así que el definitivo es: Wan 2.2 a 1280×720 → **SeedVR2 3B** (escalado ×1,5 a 1920×1080) → **FILM** ×2 (16 → 32 fps). Modelos: `02e_modelos_video_1080p.bat` (23:39, 3,75 GB, TODO OK, SHA-256 correcto).

Prueba 720p 2026-11-15 23:38-00:01 (misma plantilla, imagen, prompt y semilla; 1280×720, 81 fotogramas, LoRA 4 pasos; modelos ya cargados de la prueba anterior): **1384,9 s (23 min 05 s)**, ≈ 2,8 veces más que a 832×576. Cada fase de muestreo de 2 pasos ≈ 5 min 15 s (frente a 98 s). «VRAM» libre mínima 47,7 GB; RAM de Windows libre mínima 13,1 GB. Resultado `output\video\IMGA_prueba_wan22_i2v_720p_00001_.mp4` (1280×720, 16 fps, 9,6 MB).

SeedVR2: **Terminó a las 00:55: 39 min 01 s** (decodificación ≈ 29 min) → `IMGA_prueba_wan22_1080p_seedvr2_00001_.mp4`. Calidad: el que más detalle añade (gradiente medio 20,0 frente a 10,1 del 720p ampliado), pero sobreafilado y más cálido; sin desplazamiento de encuadre (correlación de fase 0,0). **Descartado por tiempo.** Tras la prueba cortada, ComfyUI retuvo ≈ 106 GB de la GPU hasta reiniciarlo (ni «liberar memoria» ni `/free` los devolvieron). Detalle del intento: Plantilla oficial `utility_seedvr2_3b_int8_upscale_video` sobre el vídeo de 720p (×1,5 → 1920×1080, 81 fotogramas). 1.er intento (mosaicos 512/128, los de la plantilla): codificación 8 min 30 s, muestreo 41 s, decodificación al 13 % a los 5 min → cortado por Claude a los 14 min 40 s. 2.º intento (mosaicos 2048/64, 00:16): codificación ≈ 9 min (no mejora), «VRAM» libre bajó a 2,3 GB y el modelo se cargó en CPU, muestreo ≈ 43 s, decodificación sin terminar a los 15 min (00:42; seguía en marcha en ComfyUI). Conclusión provisional: en este chip SeedVR2 3B a 1080p tarda > 25 min por cada 5 s; hay que probar RelayVSR ×2 (`--grupos video_relayvsr`, pensado para vídeo generado) o un escalado clásico, y FILM aún no se ha probado

**RelayVSR ×2 (2026-11-16, plantilla `utility_relayvsr_video_x2_upscale`, `02f_modelos_video_relayvsr.bat`, 4,93 GB, TODO OK):** 720p → 2560×1440 en **66,6 s** (decodificación 4,1 fotogramas/s); memoria GPU libre mínima 93,9 GB. Detalle intermedio (gradiente 14,5), colores fieles, sin desplazamiento. **FILM ×2** (plantilla `utility_video_frame_interpolation`) sobre ese vídeo: **3 min 01 s** (2 s/fotograma a 1440p; 161 fotogramas a 32 fps); fotograma intermedio revisado sin fantasmas. Reducción a 1920×1080 con ffmpeg (lanczos, H.264 CRF 18): 7 s → `output\video\IMGA_prueba_definitivo_1080p32.mp4`. **Cadena definitiva elegida:** Wan 2.2 a 1280×720 (≈ 23 min) → RelayVSR ×2 (≈ 1 min) → FILM ×2 (≈ 3 min; hipótesis ≈ 1,5 min si se hace tras bajar a 1080p) → 1920×1080 ≈ **27-28 min por cada 5 s**. PENDIENTE: el paso a 1080p dentro del propio flujo de ComfyUI (nodo de redimensionado) y medir el parpadeo.

## Historias
- Como Andrés, quiero pedir a Claude (o a LM Studio, Bionic, Hermes) «haz un vídeo de 5 s de esta imagen con la cámara
  avanzando sobre el frente» y recibir el vídeo en `C:\IA_Imagenes\AAAA-MM-DD`.
- Como Andrés, quiero ver el trabajo en la pestaña de ComfyUI (visor) y poder ajustar el flujo y guardarlo
  («IMGA → Guardar como flujo del MCP»), igual que con las imágenes.

## Requisitos (EARS) — propuesta
- **RF-1** Cuando se pida un vídeo con una imagen de partida y un texto, el servidor deberá lanzarlo con el flujo
  `video_i2v` (de la plantilla oficial, exportado en formato API) y devolver enseguida un `prompt_id`.
- **RF-2** `esperar_resultado` deberá devolver la ruta del vídeo (MP4) y un fotograma de muestra, no el vídeo en el chat.
- **RF-3** El servidor deberá aceptar `calidad="borrador"` (por defecto: 832×576, 16 fps) o `calidad="definitivo"` (1280×720 → RelayVSR ×2 → FILM ×2 = 32 fps → 1920×1080; ≈ 27-28 min por 5 s), además de duración y semilla.
- **RF-4** Opcional: último fotograma (`flf2v`) para ir de una imagen a otra (p. ej. estado actual → restauración).
- **RF-5** Si faltan los modelos, el servidor deberá decir qué falta y qué `.bat` ejecutar (`02d_modelos_video_wan22_14b.bat`).
- **RF-7** Antes de un vídeo definitivo el servidor deberá comprobar la memoria libre de la GPU y avisar si ComfyUI retiene memoria (caso del 2026-11-16: 0,7 GB libres tras un trabajo cortado → hay que reiniciar ComfyUI).
- **RF-6** Cada vídeo deberá guardar su `.json` con modelo, licencia (Apache 2.0), parámetros y tiempo.
- **RF-8** (1.3.1) Si el fotograma de muestra de un vídeo, o una imagen, sale gris uniforme o ruido de colores, el
  servidor deberá avisar en la respuesta (no bloquear). Caso del 2026-11-16: la GPU calculaba mal y el MCP dijo «Hecho».

## Criterios de aceptación
1. Prueba a mano en ComfyUI con la plantilla `video_wan2_2_14B_i2v`: tiempo y pico de memoria medidos y anotados.
2. Flujo exportado en formato API desde la interfaz (no escrito a mano) y probado.
3. Un vídeo generado desde Claude Desktop y desde una app local (LM Studio o Hermes).

## Validación (2026-11-16, Claude Desktop, imagen de partida Qwen 2.1 de un proyecto de prueba 1216×832, semilla 515)
- 11:18-11:25: borrador «Hecho» pero **gris**; luego ruido de colores en vídeos cortos y en Z-Image → GPU calculando
  mal; arreglado reiniciando el PC (12:50). Causa no comprobada. Dio lugar a RF-8.
- 12:53-13:01: **borrador** 832×576, 81 fotogramas, **8,0 min**; revisados 6 fotogramas: avance suave, escena coherente.
- 13:02-13:28: **definitivo** 1920×1080 a 32 fps, **25,5 min**; revisado el fotograma de muestra (correcto, algo
  estirado: la imagen no es 16:9 y el MCP lo avisó). Andrés lo revisó (17:42): está bien.
- 17:30: 1.3.1 instalada; imagen normal sin aviso. 17:42: Andrés decide que el vídeo no hace falta en las apps locales.

## Fuera de alcance (por ahora)
Audio, texto → vídeo, control de cámara (`video_camara`) y vídeo guiado (`video_control`): grupos de modelos ya
preparados en el script, se decidirán tras medir el i2v.

## Preguntas abiertas
1. ~~Resolución por defecto~~ Resuelta: borrador 832×576, definitivo 1080p.
2. ¿Hace falta liberar LM Studio antes de un vídeo? Medido sin LM Studio: la RAM de Windows bajó hasta 12,9 GB libres; con Qwen3.6 (≈ 22 GB) cargado no cabría holgado → hipótesis: liberar antes.
3. ¿Se añade después el control de cámara (`video_camara`, ≈ 31 GB más) para sobrevuelos?
