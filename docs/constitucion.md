# Constitución — principios no negociables del MCP `comfyui`

Si un cambio necesita romper alguno, se cambia primero este documento (con motivo y fecha en `CHANGELOG.md`).

1. **Local.** El servidor solo habla con ComfyUI en `127.0.0.1`; no abre puertos ni usa servicios en la nube.
   Las imágenes que devuelve a una app en la nube (Claude Desktop) sí salen del equipo: se documenta.
2. **Una sola fuente de verdad.** El código se desarrolla aquí; `C:\Notas_IA\mcp\comfyui` es la copia publicada
   (con SHA-256) desde la que se instala; `C:\ComfyUI_MCP` es lo instalado. No se edita en ninguno de los otros dos.
3. **Versiones fijadas.** `mcp==1.30.0`, `pillow==13.0.0`. Cambiarlas exige spec y pruebas en las 4 apps.
4. **No romper lo que funciona.** Las 8 herramientas mantienen nombre y parámetros; lo nuevo se añade.
   Las apps conservan sus otros MCP (copia de seguridad antes de tocar sus configuraciones).
5. **Respuestas acotadas.** Ninguna herramienta bloquea más de ~60 s; lo largo se recoge con `esperar_resultado`.
6. **Flujos exportados, no escritos.** Los `.json` de `flujos\` salen de la interfaz de ComfyUI (formato API).
7. **Modelos con licencia comprobada** para uso profesional antes de entrar en un flujo.
8. **Probado antes de publicar.** `pytest` aquí y `03_instalar_mcp_comfyui.bat` (prueba real) en el PC.
9. **No inventar.** Lo no comprobado es `PENDIENTE` o hipótesis con su efecto.
