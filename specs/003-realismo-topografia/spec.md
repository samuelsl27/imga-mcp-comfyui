# Spec 003 — Imagen realista a partir de topografía, foto aérea y descripción

| Campo | Valor |
|---|---|
| Estado | **Borrador** (preguntas abiertas) |
| Fecha | 2026-11-15 |
| Equipo | MS-S1 (desktop-3t6aul2) |

## Contexto
Prueba del 2026-11-15 en Claude Desktop: Z-Image Turbo genera fotos verosímiles pero **no respeta la geometría**
de una cantera («bancos» → escalera; dúmper → excavadora) y la edición arregla parte y mete artefactos.
Idea de Andrés: dar **topografía (curvas, MDT), una foto aérea y una descripción** y obtener una imagen realista
fiel al terreno real (proyectos de cantera, restauración, presentaciones).

## Historias
- Como Andrés, quiero pasar la ortofoto y el MDT/curvas de una cantera y una descripción («frente con bancos de
  10 m, pista de acceso, balsa al pie…») y obtener una vista realista que respete la forma real del terreno.
- Como Andrés, quiero repetir la vista con otro estado (avance de labores, restauración) manteniendo el encuadre.

## Requisitos (EARS) — propuesta
- **RF-1** Cuando se le pase una imagen de control (profundidad/relieve, bordes o la propia ortofoto) y un texto,
  el servidor deberá generar una imagen que siga la estructura de esa imagen (ControlNet / model patch).
- **RF-2** El servidor deberá aceptar la fuerza del control (0–1) para equilibrar fidelidad y realismo.
- **RF-3** Donde haya ortofoto y relieve a la vez, el servidor deberá poder usar los dos (relieve = forma,
  ortofoto = colores y texturas).
- **RF-4** Si el modelo de control no está instalado, el servidor deberá decir qué falta y cómo instalarlo.
- **RF-5** El servidor deberá guardar con la imagen las entradas de control usadas (rutas y fuerza).

## Opciones estudiadas (2026-11-15, por comprobar en el PC)
| Opción | Modelos | Licencia | Encaje |
|---|---|---|---|
| A. Z-Image Turbo + **Fun ControlNet Union 2.1** (alibaba-pai) | patch `model_patches/` (hay versión *lite* de 1,9 GB); control Canny, Depth, HED, MLSD, Scribble, Gray, Pose + Tile | Apache-2.0 | Rápido (8 pasos), muy realista; plantilla oficial de ComfyUI |
| B. Qwen-Image 2512 + DiffSynth model patches / InstantX Union | canny, depth, inpaint (patch) o canny/softedge/depth/pose (InstantX) | Apache-2.0 | Más lento; mejor siguiendo instrucciones |
| C. Qwen-Image-Edit 2511 (ya instalado) con la imagen de control como imagen 1/2 | — | Apache-2.0 | Sin descargas; probar primero |
| D. Krea 2 Turbo (12,9 B, jun-2026), el más realista según comparativas | ~13 GB FP8 | **Krea 2 Community License**: fuentes contradictorias (no comercial / comercial < 1 M$ y < 50 puestos, con filtrado obligatorio) | PENDIENTE leer la licencia oficial antes de nada |

## Cadena propuesta para la topografía (hipótesis a validar)
QGIS (MDT de las curvas + ortofoto, MCP `qgis`) → Blender (terreno 3D con la ortofoto, cámara oblicua; MCP `blender`)
→ render de **profundidad** + render de color → ComfyUI: control *Depth* (forma) + *Tile/Gray* o img2img (colores) +
descripción → foto realista. Las curvas dibujadas como líneas **no** sirven bien como control (el modelo dibuja
líneas); hay que pasarlas a MDT/profundidad.

## Fuera de alcance
Vídeo (va en la spec de vídeo). Medidas: la imagen es ilustrativa, no sirve para medir.

## Preguntas abiertas
1. ¿Vista cenital (como la ortofoto) u oblicua/perspectiva (como una foto de dron)? Cambia la cadena (con oblicua hace falta Blender).
2. ¿Qué proyecto de prueba? (ortofoto + MDT o curvas en QGIS: p. ej. proyecto A o proyecto B).
3. ¿Se descarga Fun ControlNet Union 2.1 (opción A)? Tamaño exacto PENDIENTE (lite 1,9 GB).
4. Krea 2: ¿se revisa su licencia para uso en IMGA?
