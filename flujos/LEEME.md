# Flujos de ComfyUI para el MCP `comfyui` (spec 006)

Flujos en **formato API** exportados por Andrés desde la interfaz de ComfyUI
(menú *Flujo de trabajo → Exportar (API)*), después de comprobar que funcionan a mano.
Son la **referencia**: el instalador del MCP los copia (con SHA-256) a la carpeta del servidor.

| Fichero | Plantilla de origen | Uso en el MCP |
|---|---|---|
| `generar_rapido.json` | Z-Image Turbo (`image_z_image_turbo`) | imagen desde texto, rápida |
| `generar_texto.json` | Qwen-Image 2512 (`image_qwen_Image_2512`), con la LoRA Lightning activada | imagen con rótulos/texto legible |
| `editar.json` | Qwen-Image-Edit 2511 (`image_qwen_image_edit_2511`), con la LoRA Lightning activada | editar con 1–3 imágenes de referencia |
| `video.json` (fase posterior) | Wan 2.2 | vídeo desde imagen |

No editar a mano: si cambia un flujo, se vuelve a exportar desde ComfyUI.
