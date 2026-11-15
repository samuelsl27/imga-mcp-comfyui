# Flujo SDD para el desarrollo del MCP

Adaptado de [mouredev/hello-sdd](https://github.com/mouredev/hello-sdd), igual que `C:\Notas_IA`, pero aplicado
a **programar** el servidor (no a administrar el equipo).

| hello-sdd | Aquí |
|---|---|
| `docs/constitution.md` | `docs/constitucion.md` |
| `AGENTS.md` + `CLAUDE.md` | raíz |
| `specs/NNN-x/spec.md` (RF en EARS) | qué debe hacer el servidor y por qué |
| `plan.md` | ficheros, funciones, flujos de ComfyUI, decisiones |
| `tasks.md` (T1…Tn, «Hecho cuando») | pasos verificables |
| Implementación + tests | `servidor/`, `flujos/`, `tests/` |
| Validación RF a RF | tabla al final de `tasks.md` (prueba en pytest o en el PC) |

## Fases
1. **Constitución** — ¿respeta `docs/constitucion.md`?
2. **Spec** — copiar `docs/plantillas_sdd/spec.md` a `specs/NNN-nombre/spec.md`; RF en EARS
   (*Ubicuo* «El servidor deberá…», *Evento* «Cuando…», *Estado* «Mientras…», *No deseado* «Si…», *Opcional* «Donde…»).
3. **Clarificación** — huecos, licencias de modelos, tiempos, memoria; no se planifica con preguntas abiertas de diseño.
4. **Plan** — `plan.md`: funciones, flujos, parámetros, decisiones y alternativas descartadas.
5. **Tareas** — `tasks.md`: T1…Tn con «Hecho cuando:».
6. **Ejecución** — una tarea cada vez; pruebas primero cuando se pueda.
7. **Validación** — cada RF con su prueba y su resultado real (pytest o prueba en el PC con fecha).
8. **Publicación** — versión, CHANGELOG, commit, `scripts\publicar_en_notas.bat`, instalar (03), documentar en `C:\Notas_IA`.
