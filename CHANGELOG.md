# CHANGELOG — MCP `comfyui`

Formato: versión — fecha — cambios. Lo más reciente arriba.

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
