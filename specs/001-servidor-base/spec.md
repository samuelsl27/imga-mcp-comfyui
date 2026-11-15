# Spec 001 — Servidor MCP base (imagen con ComfyUI local)

| Campo | Valor |
|---|---|
| Estado | Hecha (1.0.1, 2026-11-15) |
| Origen | `C:\Notas_IA\specs\006-comfyui-imagen-video` (T6) |

## Contexto
ComfyUI instalado en el MS-S1 con Z-Image Turbo, Qwen-Image 2512 y Qwen-Image-Edit 2511. Andrés quiere que Claude
Desktop (y las apps locales) generen una imagen, partan de una imagen de referencia y la modifiquen por pasos.

## Requisitos (EARS)
- **RF-1** El servidor deberá ofrecer por stdio las herramientas `estado`, `generar_imagen`, `editar_imagen`,
  `retocar_ultima`, `esperar_resultado`, `ver_imagen`, `listar_resultados` y `liberar_memoria`.
- **RF-2** Cuando se genere o edite una imagen, el servidor deberá guardarla en `C:\IA_Imagenes\AAAA-MM-DD\` con un
  `.json` (prompt, semilla, flujo, referencias, tiempo) y devolverla al chat reducida a 1024 px.
- **RF-3** Cuando se pida un retoque, el servidor deberá usar la última imagen como imagen 1.
- **RF-4** Si un trabajo no termina en `COMFY_MCP_ESPERA`, el servidor deberá devolver su `prompt_id`.
- **RF-5** Si ComfyUI no responde, el servidor deberá devolver un error que diga cómo arrancarlo.

## Validación
| RF | Prueba | Resultado |
|---|---|---|
| RF-1 | `test_ocho_herramientas`; `03_instalar` en el PC | ✅ |
| RF-2/3 | Claude Desktop 2026-11-15 20:12 (`generar_imagen` + `retocar_ultima`) | ✅ |
| RF-4 | `retocar_ultima` 80,8 s → `esperar_resultado` | ✅ |
| RF-5 | Bionic con ComfyUI parado (1.0.1) | ✅ (sustituido por el arranque automático en 002) |
