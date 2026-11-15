// Utilidades compartidas por el portal y el panel de operadores
const C = window.CONFIG;

// Coordenadas aproximadas de cada zona (Lima) para dibujar el mapa
const ZONAS_GEO = {
  "Z-MIRAFLORES": [-12.1211, -77.0297],
  "Z-SURCO": [-12.1350, -76.9930],
  "Z-ATE": [-12.0450, -76.9300],
  "Z-BARRANCO": [-12.1450, -77.0210],
  "Z-JESUSMARIA": [-12.0720, -77.0450],
  "Z-SANISIDRO": [-12.0970, -77.0360]
};
const CENTRO_LIMA = [-12.095, -77.000];
const COLOR_ESTADO = { NORMAL: "#1E9E5A", SATURADA: "#D99A00", CAIDA: "#DD5F1A", INHABILITADA: "#C8102E" };
const COLOR_PRIORIDAD = { BAJA: "#1E9E5A", MEDIA: "#D99A00", ALTA: "#DD5F1A", CRITICA: "#C8102E" };

// Posicion de cada antena: alrededor del centro de su zona
function posicionAntena(antena) {
  const base = ZONAS_GEO[antena.zona_id] || CENTRO_LIMA;
  const n = Number((antena.antena_id || "").split("-").pop()) || 1;
  return [base[0] + (n === 1 ? 0.006 : -0.005), base[1] + (n === 1 ? -0.006 : 0.007)];
}

// Igual que el taller: integration lambda, el statusCode viene dentro del JSON
async function post(ruta, cuerpo = {}, token = null) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = token;
  const r = await fetch(`${C.API_URL}${ruta}`, { method: "POST", headers, body: JSON.stringify(cuerpo) });
  if (r.status === 401 || r.status === 403) throw Object.assign(new Error("Sesion expirada"), { sesion: true });
  const j = await r.json();
  if (j.statusCode >= 400 || j.message) throw new Error(j.error || j.message || "Error");
  return j;
}

// Crea elementos sin innerHTML (el texto de usuarios nunca se interpreta como HTML)
function el(tag, texto, clase, estilo) {
  const e = document.createElement(tag);
  if (texto !== undefined && texto !== null) e.textContent = texto;
  if (clase) e.className = clase;
  if (estilo) e.style.cssText = estilo;
  return e;
}
// Nombres legibles (con tildes) para los estados que vienen del backend
const NOMBRE_ESTADO = { EN_EVALUACION: "En evaluación", EN_REVISION: "En revisión", EN_ATENCION: "En atención", CAIDA: "Caída",
  CRITICA: "Crítica", IDENTIFICADO: "Falla identificada", RESTABLECIDO: "Restablecido", DESCARTADO: "Descartado", VENCIDO: "Vencido",
  NOTIFICACION: "Aviso enviado", VERIFICACION_INFRA: "Verificación de antenas", PRIORIZADO: "Prioridad calculada",
  ESPERANDO_VERIFICACION: "Esperando verificación", ESPERANDO_RESOLUCION: "Esperando resolución", ESPERA_COMPLETADA: "Decisión recibida",
  ANTENA_VINCULADA: "Antena vinculada", PROBLEMA_ESTRUCTURAL: "Falla recurrente", SIMULACION: "Simulación" };
function nombreEstado(valor) {
  if (!valor) return "Sin dato";
  if (NOMBRE_ESTADO[valor]) return NOMBRE_ESTADO[valor];
  const t = valor.replaceAll("_", " ").toLowerCase();
  return t.charAt(0).toUpperCase() + t.slice(1);
}
function badge(valor) { return el("span", nombreEstado(valor), "badge " + (valor || "")); }

function toast(texto, color = "#F2B705", ms = 4500) {
  let caja = document.getElementById("toasts");
  if (!caja) { caja = el("div"); caja.id = "toasts"; document.body.appendChild(caja); }
  const t = el("div", texto, "toast");
  t.style.setProperty("--c", color);
  caja.appendChild(t);
  setTimeout(() => { t.classList.add("salir"); setTimeout(() => t.remove(), 300); }, ms);
}

// Contador animado para los KPIs
function animarNumero(nodo, destino) {
  const inicio = Number(nodo.dataset.valor || 0);
  nodo.dataset.valor = destino;
  if (inicio === destino) { nodo.textContent = destino; return; }
  const t0 = performance.now(), dur = 700;
  const paso = (t) => {
    const p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 3);
    nodo.textContent = Math.round(inicio + (destino - inicio) * e);
    if (p < 1) requestAnimationFrame(paso);
  };
  requestAnimationFrame(paso);
}

function hora(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleString("es-PE", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

// Avance como barras de senal: cada etapa cumplida llena una barra
function etapas(lista, actual, etiquetas) {
  const fin = actual === lista[lista.length - 1];
  const idx = fin ? lista.length : Math.max(0, lista.indexOf(actual));
  const nombre = i => (etiquetas && etiquetas[i]) || lista[i].replaceAll("_", " ").toLowerCase();
  const cont = el("div", null, "senal");
  const barras = el("div", null, "barras");
  barras.setAttribute("role", "img");
  barras.setAttribute("aria-label", `Etapa ${Math.min(idx + 1, lista.length)} de ${lista.length}`);
  lista.forEach((_, i) => {
    const b = el("span", null, "barra" + (i < idx ? " llena" : i === idx ? " actual" : ""));
    b.style.height = (30 + i * 17.5) + "%";
    b.title = nombre(i);
    barras.appendChild(b);
  });
  const txt = el("div", null, "senal-txt");
  txt.appendChild(el("b", nombre(Math.min(idx, lista.length - 1))));
  txt.appendChild(el("span", fin ? "Atención completada" : `Etapa ${idx + 1} de ${lista.length}. Sigue: ${nombre(idx + 1 < lista.length ? idx + 1 : idx)}`));
  cont.append(barras, txt);
  return cont;
}

function lineaTiempo(historial) {
  const ul = el("ul", null, "linea");
  (historial || []).forEach(h => {
    const li = el("li");
    li.appendChild(el("span", hora(h.fecha), "hora"));
    li.appendChild(el("b", nombreEstado(h.estado)));
    if (h.detalle) li.appendChild(document.createTextNode(": " + h.detalle));
    ul.appendChild(li);
  });
  return ul;
}

// Mapa base oscuro (CARTO + OpenStreetMap)
function crearMapa(id, zoom = 12) {
  const mapa = L.map(id, { zoomControl: true, attributionControl: true }).setView(CENTRO_LIMA, zoom);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
    maxZoom: 19, attribution: "&copy; OpenStreetMap &copy; CARTO"
  }).addTo(mapa);
  return mapa;
}

// Zona mas cercana a un punto (para el portal)
function zonaCercana(lat, lon) {
  let mejor = null, dist = Infinity;
  for (const [id, [zl, zo]] of Object.entries(ZONAS_GEO)) {
    const d = (zl - lat) ** 2 + (zo - lon) ** 2;
    if (d < dist) { dist = d; mejor = id; }
  }
  return mejor;
}
