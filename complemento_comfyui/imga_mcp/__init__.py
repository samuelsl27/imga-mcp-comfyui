"""imga_mcp - complemento de interfaz de IMGA para ComfyUI (no anade nodos).

Solo carga web/imga_mcp.js en la interfaz web:
  - abre como pestana cada trabajo que lanza el MCP "comfyui" (client_id mcp-comfyui-*) para verlo,
  - menu IMGA: Abrir ultimo trabajo del MCP / Seguir al MCP (activar-desactivar) / Guardar como flujo del MCP,
  - escribe un latido en user/default/imga_visor_latido.json para que el MCP sepa que la interfaz esta abierta.
Repositorio: Z:\\cu\\SOFTWARE_APLIACIONES_IMGA\\Desarrollado_IMGA\\MCP_ConfyUI (complemento_comfyui/imga_mcp).
"""
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = "./web"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
