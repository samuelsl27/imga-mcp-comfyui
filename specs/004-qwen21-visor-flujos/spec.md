# Spec 004 — Qwen-Image 2.1 por defecto, visor en ComfyUI y flujos editables

| Campo | Valor |
|---|---|
| Estado | Implementada y validada en Bionic (1.2.0, 2026-11-15); Claude Desktop, LM Studio y Hermes PENDIENTES de reiniciar |
| Origen | Peticiones de Andrés del 2026-11-15 (20:34, 20:40, 20:54) |

## Contexto
- Prueba con un proyecto real (render MDT + ortofoto): Qwen-Image 2.1 respeta mejor el terreno y da más detalle que
  Qwen-Edit 2511 con 4 pasos (169 s con carga frente a 82 s). Generar con 2.1: 63 s (modelo cargado), el mejor de los 4.
- Andrés: «Vamos a usar qwen image 2.1 como modelo por defecto, a no ser que pida explicitamente algo rapido».
- Andrés: quiere ver en ComfyUI (127.0.0.1:8188) lo que hace el MCP, los nodos, editarlo y guardarlo; «por
  defecto el mcp funcione solo, pero que abra en una pestaña del navegador comfyui y yo ver que hace».

## Requisitos (EARS)
- **RF-1** El servidor deberá usar Qwen-Image 2.1 (`generar_qwen21`, `editar_qwen21`) en el modo por defecto
  `calidad` de `generar_imagen`, `editar_imagen` y `retocar_ultima`.
- **RF-2** Cuando se pida `modo="rapido"`, deberá usar Z-Image Turbo (generar) o Qwen-Edit 2511 + 4 pasos (editar);
  con `modo="texto"`, Qwen 2512.
- **RF-3** Donde `COMFY_MCP_MODELO=clasico`, el modo `calidad` deberá usar solo modelos Apache-2.0 (2512 / 2511).
- **RF-4** El servidor deberá guardar en el `.json` de cada imagen y decir en la respuesta el modelo y su licencia.
- **RF-5** Con Qwen 2.1 la edición deberá admitir de 1 a 10 imágenes de referencia (3 en modo rápido).
- **RF-6** Mientras la interfaz de ComfyUI esté abierta con el complemento `imga_mcp`, cada trabajo del MCP deberá
  abrirse en una pestaña con su esquema de nodos.
- **RF-7** Si no hay interfaz abierta (sin latido en 45 s), el servidor deberá abrirla (Edge en modo aplicación),
  como mucho una vez cada 10 min. `COMFY_MCP_VISOR=0` lo desactiva.
- **RF-8** Cuando Andrés guarde un flujo desde el menú IMGA, el servidor deberá usarlo en el siguiente trabajo si
  tiene los nodos imprescindibles; si no, deberá usar el instalado y avisar. El anterior se copia en `imga_flujos/copias/`.

## Licencia (decisión de Andrés, riesgo anotado)
Qwen-Image 2.1 = Qwen Research License: investigación/evaluación, **no comercial** sin licencia de Qwen. Andrés
decide usarlo por defecto; el riesgo queda anotado y el cambio a `clasico` es una variable de entorno.

## Validación
| RF | Prueba | Resultado |
|---|---|---|
| RF-1..5, RF-8 (lógica) | pytest (26 pruebas) | ✅ |
| RF-1, RF-5 en el PC | flujos exportados de las plantillas y ejecutados: editar 169 s, generar 63 s | ✅ (2026-11-15) |
| RF-1, RF-4, RF-6 en el PC | Bionic 21:55: modo por defecto → Qwen 2.1, licencia en la respuesta, pestaña «MCP 21:55 calidad» abierta sola | ✅ |
| RF-7 (abrir la interfaz si no hay) | no probado a propósito (la interfaz estaba abierta) | PENDIENTE |
| RF-8 (guardar flujo desde el menú IMGA) | pytest ✅; en la interfaz PENDIENTE (lo hará Andrés) | 🟡 |
