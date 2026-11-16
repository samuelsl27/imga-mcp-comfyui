// imga_mcp.js - complemento de interfaz de IMGA para ComfyUI (MCP "comfyui", spec 004 del repositorio MCP_ConfyUI)
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const PREFIJO = "mcp-comfyui-";
const FLUJOS = ["generar_qwen21", "editar_qwen21", "generar_rapido", "generar_texto", "editar", "video_wan", "video_acabado"];
const REQUISITOS = {  // mismos que el servidor (REQUISITOS en servidor_comfyui_mcp.py)
  generar_qwen21: ["TextGenerate", "ComfySwitchNode", "EmptyLatentImage", "KSampler", "TextEncodeQwenImage21"],
  editar_qwen21: ["LoadImage", "TextEncodeQwenImage21", "KSampler", "TextGenerate", "ComfySwitchNode"],
  generar_rapido: ["CLIPTextEncode", "EmptySD3LatentImage", "KSampler", "SaveImage"],
  generar_texto: ["CLIPTextEncode", "EmptySD3LatentImage", "KSampler", "SaveImage"],
  editar: ["LoadImage", "FluxKontextImageScale", "TextEncodeQwenImageEditPlus", "KSampler", "SaveImage"],
  video_wan: ["LoadImage", "WanImageToVideo", "KSamplerAdvanced", "CLIPTextEncode", "CreateVideo", "SaveVideo"],
  video_acabado: ["LoadVideo", "VSRDecode", "ImageScale", "FrameInterpolate", "CreateVideo", "SaveVideo"],
};
const vistos = new Set();
let seguir = (localStorage.getItem("imga.mcp.seguir") ?? "1") === "1";

function aviso(sev, titulo, texto) {
  try { app.extensionManager.toast.add({ severity: sev, summary: titulo, detail: texto, life: 7000 }); }
  catch (e) { console.log("[IMGA]", titulo, texto); }
}

async function guardar(ruta, contenido) {
  const r = await api.fetchApi("/userdata/" + encodeURIComponent(ruta) + "?overwrite=true",
    { method: "POST", body: typeof contenido === "string" ? contenido : JSON.stringify(contenido, null, 1) });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
}

async function leer(ruta) {
  const r = await api.fetchApi("/userdata/" + encodeURIComponent(ruta), { cache: "no-store" });
  return r.ok ? await r.text() : null;
}

async function latido() {
  try { await guardar("imga_visor_latido.json", { t: new Date().toISOString(), seguir }); } catch (e) { /* sin importancia */ }
}

function tipoDe(prompt) {
  for (const n of Object.values(prompt || {}))
    if (n?.inputs?.filename_prefix) return String(n.inputs.filename_prefix).replace(/^IMGA\//, "");
  return "trabajo";
}

async function abrir(prompt, extra, etiqueta) {
  const t = new Date(extra?.create_time || Date.now());
  const nombre = `MCP ${t.toTimeString().slice(0, 5)} ${tipoDe(prompt)}`;
  await app.loadApiJson(prompt, nombre);
  await new Promise(r => setTimeout(r, 300));
  try { await app.extensionManager.command.execute("Comfy.Canvas.FitView"); } catch (e) { /* version sin el comando */ }
  aviso("info", "Trabajo del MCP", `${etiqueta}: ${nombre}`);
}

async function revisarCola() {
  if (!seguir) return;
  try {
    const q = await (await api.fetchApi("/queue")).json();
    const items = [...(q.queue_running || []).map(i => [i, "En marcha"]), ...(q.queue_pending || []).map(i => [i, "En cola"])];
    for (const [it, etiqueta] of items) {
      const extra = it[3] || {};
      if (!(extra.client_id || "").startsWith(PREFIJO) || vistos.has(it[1])) continue;
      vistos.add(it[1]);
      await abrir(it[2], extra, etiqueta);
    }
  } catch (e) { console.warn("[IMGA] revisarCola", e); }
}

async function ultimoTrabajo() {
  const h = await (await api.fetchApi("/history?max_items=50")).json();
  const del_mcp = Object.values(h).filter(x => ((x.prompt?.[3] || {}).client_id || "").startsWith(PREFIJO));
  if (!del_mcp.length) { aviso("warn", "IMGA", "No hay trabajos del MCP en el historial."); return; }
  del_mcp.sort((a, b) => ((a.prompt[3].create_time || 0) - (b.prompt[3].create_time || 0)));
  const x = del_mcp[del_mcp.length - 1];
  await abrir(x.prompt[2], x.prompt[3], "Último");
}

function sugerir(clases) {
  if (clases.has("WanImageToVideo")) return "video_wan";
  if (clases.has("VSRDecode") || clases.has("FrameInterpolate")) return "video_acabado";
  if (clases.has("TextEncodeQwenImage21")) return clases.has("LoadImage") ? "editar_qwen21" : "generar_qwen21";
  if (clases.has("TextEncodeQwenImageEditPlus")) return "editar";
  if (clases.has("LoraLoaderModelOnly")) return "generar_texto";
  return "generar_rapido";
}

async function guardarComoFlujo() {
  const p = await app.graphToPrompt();
  const clases = new Set(Object.values(p.output).map(n => n.class_type));
  const nombre = (window.prompt("Guardar el flujo abierto como flujo del MCP.\nEscribe uno de: " + FLUJOS.join(", "),
    sugerir(clases)) || "").trim();
  if (!nombre) return;
  if (!FLUJOS.includes(nombre)) { aviso("error", "IMGA", `«${nombre}» no es un flujo del MCP.`); return; }
  const faltan = REQUISITOS[nombre].filter(c => !clases.has(c));
  if (!nombre.startsWith("video_") && !clases.has("SaveImage") && !clases.has("SaveImageAdvanced")) faltan.push("SaveImage");
  if (faltan.length) { aviso("error", "IMGA: no se guarda", `A este flujo le falta: ${faltan.join(", ")}`); return; }
  const anterior = await leer(`imga_flujos/${nombre}.json`);
  if (anterior) {
    const ts = new Date().toISOString().replace(/[-:]/g, "").slice(0, 13).replace("T", "_");
    await guardar(`imga_flujos/copias/${nombre}_${ts}.json`, anterior);
  }
  await guardar(`imga_flujos/${nombre}.json`, p.output);
  await guardar(`imga_flujos/ui/${nombre}.json`, p.workflow);
  aviso("success", "IMGA", `Guardado: el MCP usará tu «${nombre}» desde el próximo trabajo` +
    (anterior ? " (copia del anterior en imga_flujos/copias)." : "."));
}

app.registerExtension({
  name: "IMGA.MCP",
  commands: [
    { id: "IMGA.ultimoTrabajo", label: "Abrir último trabajo del MCP", function: ultimoTrabajo },
    { id: "IMGA.seguir", label: "Seguir al MCP (activar / desactivar)", function: () => {
        seguir = !seguir; localStorage.setItem("imga.mcp.seguir", seguir ? "1" : "0"); latido();
        aviso("info", "IMGA", seguir ? "Se abrirá cada trabajo del MCP en una pestaña." : "Ya no se abren los trabajos del MCP.");
      } },
    { id: "IMGA.guardarFlujo", label: "Guardar como flujo del MCP", function: guardarComoFlujo },
  ],
  menuCommands: [{ path: ["IMGA"], commands: ["IMGA.ultimoTrabajo", "IMGA.seguir", "IMGA.guardarFlujo"] }],
  async setup() {
    api.addEventListener("status", revisarCola);
    setInterval(revisarCola, 4000);
    latido();
    setInterval(latido, 15000);
    window.IMGA_MCP = { revisarCola, ultimoTrabajo, guardarComoFlujo, version: "1.3.0" };
    console.log("[IMGA] complemento imga_mcp 1.2.1 cargado; seguir =", seguir);
  },
});
