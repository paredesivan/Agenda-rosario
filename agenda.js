let events = [];
let activeFilters = [];
const categories = [
  ["todos", "Todo"], ["teatro", "Teatro"], ["musica", "Música"],
  ["cine", "Cine"], ["museos", "Museos y muestras"], ["ferias", "Ferias"],
  ["libros", "Libros y charlas"], ["danza", "Danza"],
  ["infancias", "Infancias"], ["otros", "Otros"], ["gratis", "Gratis"]
];
const normalize = value => String(value || "").normalize("NFD")
  .replace(/[\u0300-\u036f]/g, "").toLowerCase();

// Casos comprobados en la ficha de la fuente; evita clasificar sólo por el recinto.
const verifiedCategories = [
  ["rosario.gob.ar/inicio/medicine-como-el-arte-puede-ayudar-la-ciencia", ["cine"]],
  ["ccpe.org.ar/web/actividades/la-montana-una-obra-escultorica", ["teatro", "danza"]],
  ["d7entradas.com.ar/eventos/abuelas-e349", ["cine", "libros"]],
  ["d7entradas.com.ar/eventos/nico-ibarburu-en-d7-e348", ["musica"]],
  ["d7entradas.com.ar/eventos/murio-de-asco-alejandro-schanzenbach-e347", ["musica"]],
  ["d7entradas.com.ar/eventos/princesa-tetrabrick-el-espiritu-frenetico-de-la-noche-cicuta-e353", ["musica"]],
  ["plataformalavarden.gob.ar/actividades/pupina-plomer", ["teatro", "libros"]],
  ["plataformalavarden.gob.ar/actividades/julieta-laso", ["musica"]]
];

function eventCategories(item) {
  const explicit = Array.isArray(item.categorias) ? item.categorias : [item.categoria];
  const aliases = {"musica en vivo":"musica", "conciertos":"musica", "recitales":"musica",
    "muestras":"museos", "exposiciones":"museos", "literatura":"libros", "charlas":"libros",
    "infantil":"infancias", "teatral":"teatro", "peliculas":"cine"};
  const known = explicit.map(value => aliases[normalize(value)] || normalize(value))
    .filter(id => id !== "todos" && id !== "otros" && categories.some(([value]) => value === id));
  const content = normalize(`${item.nombre} ${item.descripcion || ""}`);
  const venue = normalize(`${item.lugar} ${item.origen || ""}`);
  const result = [...known];
  const match = (id, pattern) => { if (pattern.test(content)) result.push(id); };
  match("musica", /\b(musica|musical(?:es)?|recital(?:es)?|concierto(?:s)?|orquesta(?:s)?|banda(?:s)?|cantante(?:s)?|cantora?|cantautor(?:a)?|rock|jazz|opera|filarmonica|reggae|blues|cumbia|rap|hip hop|fol[ck]lore|fol[ck]loric[oa]|chamame\w*|tanguer[oa]s?|tango|karaoke|cantata|ensamble|sonido de cuerdas|tambor|heavy|punk|dj)\b/);
  match("teatro", /\b(teatro|teatral(?:es)?|comedia|dramaturgia|stand[ -]?up|monologo(?:s)?|unipersonal|humor|artes escenicas|en escena|actriz|actor)\b|\bobra(?:s)? (?:de teatro|teatral)/);
  match("cine", /\b(cine|pelicula(?:s)?|film(?:s)?|documental(?:es)?|proyecci[oó]n(?:es)?|cinematografic[oa]|fulldome|slasher)\b/);
  match("museos", /\b(museo(?:s)?|muestra(?:s)?|exposicion(?:es)?|artes visuales|fotografia|escultura(?:s)?)\b/);
  match("ferias", /\b(feria(?:s)?|artesan[oa]s?|artesanal(?:es)?|mercado)\b/);
  match("libros", /\b(libro(?:s)?|lectura(?:s)?|leer|literatura|literari[oa]|poesia|narracion|charla(?:s)?|conferencia(?:s)?|tertulia(?:s)?|conversa|cuento(?:s)?)\b/);
  match("danza", /\b(danza(?:s)?|ballet|baile|bailar|milonga(?:s)?)\b/);
  match("infancias", /\b(infancia(?:s)?|infantil(?:es)?|ninos|ninas|bebes|titere(?:s)?|nivel(?:es)? inicial|jugar|rompecabezas)\b|disfrutar en familia/);
  // Los nombres de artistas permiten ubicar conciertos con descripciones mínimas.
  match("musica", /\b(david bisbal|camilo|sergio dalma|ronnie wood|los nocheros|un poco de ruido|fiesta tnt)\b/);
  if (/\b(cine|cinema|cinemateca)\b/.test(venue)) result.push("cine");
  if (/\b(museo(?:s)?|macro|castagnino)\b/.test(venue)) result.push("museos");
  if (/biblioteca/.test(venue) && /biblioteca|lectura|libro|bullying/.test(content)) result.push("libros");
  if (!result.includes("musica") && !result.includes("cine") &&
      (/teatro|astengo|atir|comedia|orilla infinita|cultural de abajo|caras y caretas|espacio bravo|la morada|la escalera|la torneria/.test(venue) ||
       /\bfuncion (?:de|del)\b|\bgrandinetti\b/.test(content))) result.push("teatro");
  const link = normalize(item.evento_url).replace(/^https?:\/\/(?:www\.)?/, "").split(/[?#]/)[0].replace(/\/$/, "");
  const verified = verifiedCategories.find(([url]) => url === link);
  if (verified) result.push(...verified[1]);
  return result.length ? [...new Set(result)] : ["otros"];
}

function todayKey() {
  const now = new Date();
  return dateKey(now.getFullYear(), now.getMonth(), now.getDate());
}

function matchesFilter(item) {
  if (!activeFilters.length) return true;
  const gratis = activeFilters.includes("gratis");
  const categoriesSelected = activeFilters.filter(filter => filter !== "gratis");
  const matchesCategory = !categoriesSelected.length || categoriesSelected.some(filter => eventCategories(item).includes(filter));
  return matchesCategory && (!gratis || estadoPrecio(item).gratis);
}

// Evita mostrar varias fichas del mismo evento cuando distintas fuentes lo
// publican con títulos levemente diferentes. Solo une coincidencias de fecha,
// hora y recinto; los casos ambiguos se mantienen separados.
const genericTitleWords = new Set([
  "a", "al", "algunas", "algun", "con", "de", "del", "desde", "el", "en",
  "es", "espectaculo", "funcion", "la", "las", "los", "muestra", "obra",
  "para", "presenta", "presentacion", "que", "un", "una", "y"
]);

function titleTokens(value) {
  return normalize(value).replace(/[^a-z0-9]+/g, " ").trim().split(/\s+/)
    .filter(token => token.length > 1 && !genericTitleWords.has(token));
}

function titleSimilarity(a, b) {
  const left = new Set(titleTokens(a));
  const right = new Set(titleTokens(b));
  if (!left.size || !right.size) return false;
  const shared = [...left].filter(token => right.has(token)).length;
  const smaller = Math.min(left.size, right.size);
  const larger = Math.max(left.size, right.size);
  // Dos palabras distintivas compartidas y alta cobertura del título más corto
  // permiten variantes como “Mamá Mía” y “Función de Mamá Mía…”.
  return shared >= 2 && shared / smaller >= 0.75 && shared / larger >= 0.45;
}

function locationTokens(value) {
  let text = normalize(value).replace(/\bccpe\b/g, "centro cultural parque espana")
    .replace(/\bmacro\b/g, "museo arte contemporaneo rosario")
    .replace(/\b(sarmiento y el rio|rosario|santa fe|argentina)\b/g, "")
    .replace(/[^a-z0-9]+/g, " ").trim();
  return new Set(text.split(/\s+/).filter(token => token.length > 1 &&
    !["calle", "avenida", "av", "piso", "bis"].includes(token)));
}

function sameLocation(a, b) {
  const left = locationTokens(`${a.lugar || ""} ${a.direccion || ""}`);
  const right = locationTokens(`${b.lugar || ""} ${b.direccion || ""}`);
  if (!left.size || !right.size) return false;
  const shared = [...left].filter(token => right.has(token)).length;
  return shared / Math.min(left.size, right.size) >= 0.7;
}

function sourceReliability(item) {
  const origin = normalize(item.origen || "").replace(/[^a-z0-9]+/g, " ").trim();
  let host = "";
  try { host = new URL(item.evento_url || item.entradas_url).hostname.replace(/^www\./, ""); }
  catch (_) {}
  const place = locationTokens(item.lugar || "");
  const originTokens = locationTokens(origin);
  const directMatch = [...place].filter(token => originTokens.has(token)).length;
  const isAggregator = /rosario en cartel|rosario times|agenda|guia|cartelera|passline|entradafan|ticketek|entrada play|linke arte/.test(`${origin} ${host}`);
  let score = 100;
  if (directMatch >= 2) score = 500;
  else if (/\.gob\.ar$|\.edu\.ar$|\.gov\./.test(host) || /municipalidad|universidad|gobierno/.test(origin)) score = 400;
  else if (/passline|entradafan|ticketek|entradaplay/.test(host)) score = 300;
  else if (isAggregator) score = 150;
  return score + (item.evento_url ? 5 : 0) + (item.entradas_url ? 3 : 0) +
    (item.descripcion ? Math.min(String(item.descripcion).length, 250) / 1000 : 0);
}

function duplicateEvents(a, b) {
  const startA = String(a.hora || "").match(/\d{1,2}:\d{2}/)?.[0];
  const startB = String(b.hora || "").match(/\d{1,2}:\d{2}/)?.[0];
  return a.fecha === b.fecha && startA && startA === startB &&
    sameLocation(a, b) && titleSimilarity(a.nombre, b.nombre);
}

function deduplicatedEvents(items) {
  // Comparar sólo funciones del mismo día y horario.
  const buckets = new Map();
  for (const item of items) {
    const start = String(item.hora || "").match(/\d{1,2}:\d{2}/)?.[0];
    const key = `${item.fecha}|${start}`;
    if (!buckets.has(key)) buckets.set(key, []);
    const groups = buckets.get(key);
    const group = groups.find(candidate => candidate.every(existing => duplicateEvents(item, existing)));
    if (group) group.push(item);
    else groups.push([item]);
  }
  return [...buckets.values()].flatMap(groups => groups.map(group =>
    [...group].sort((a, b) => sourceReliability(b) - sourceReliability(a))[0]));
}

let futureCache = {source: null, day: null, items: []};
function futureEvents() {
  const day = todayKey();
  if (futureCache.source !== events || futureCache.day !== day) {
    futureCache = {source: events, day,
      items: deduplicatedEvents(events.filter(item => item.fecha >= day))};
  }
  return futureCache.items;
}

function availableDates() {
  return [...new Set(futureEvents().filter(matchesFilter).map(item => item.fecha))].sort();
}

function ensureSelection() {
  const dates = availableDates();
  if (dates.includes(selectedDate)) return;
  const next = dates.find(key => key >= (selectedDate || todayKey())) || dates.at(-1) || null;
  selectedDate = next;
  if (next) visibleMonth = new Date(`${next.slice(0, 7)}-01T12:00:00`);
}

function selectDate(key, scroll = false) {
  if (!availableDates().includes(key)) return;
  selectedDate = key;
  visibleMonth = new Date(`${key.slice(0, 7)}-01T12:00:00`);
  render();
  if (scroll) {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    $("day-heading").scrollIntoView({behavior: reduced ? "auto" : "smooth", block:"start"});
  }
}

function adjacentDate(direction) {
  const dates = availableDates();
  const index = dates.indexOf(selectedDate);
  return index < 0 ? null : dates[index + direction] || null;
}

function renderNavigation() {
  const previous = adjacentDate(-1), next = adjacentDate(1);
  $("previous-day").disabled = !previous;
  $("next-day").disabled = !next;
  $("previous-day").onclick = () => { if (previous) selectDate(previous, true); };
  $("next-day").onclick = () => { if (next) selectDate(next, true); };
  const dates = availableDates();
  const month = dateKey(visibleMonth.getFullYear(), visibleMonth.getMonth(), 1).slice(0, 7);
  $("prev").disabled = !dates.some(key => key.slice(0, 7) < month);
  $("next").disabled = !dates.some(key => key.slice(0, 7) > month);
  $("today").disabled = !dates.length;
  $("today").textContent = dates.includes(todayKey()) ? "Ir a hoy" : "Próximo día disponible";
}

function renderSummary() {
  const future = futureEvents();
  $("total-events").textContent = future.length.toLocaleString("es-AR");
  const last = future.reduce((value, item) => item.fecha > value ? item.fecha : value, "");
  $("coverage").textContent = last ? `Hasta el ${new Date(last + "T12:00:00").toLocaleDateString("es-AR", {day:"numeric", month:"long"})}` : "Esperando nuevas actividades";
  const filters = $("filters");
  // Mantener los botones preserva el foco del teclado al filtrar.
  if (!filters.children.length) {
    for (const [id, label] of categories) {
      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute("role", id === "todos" ? "button" : "checkbox");
      button.dataset.filter = id;
      button.onclick = () => {
        if (id === "todos") {
          activeFilters = [];
        } else if (activeFilters.includes(id)) {
          activeFilters = activeFilters.filter(value => value !== id);
        } else {
          activeFilters = [...activeFilters, id];
        }
        render();
      };
      filters.append(button);
    }
  }
  for (const button of filters.children) {
    const id = button.dataset.filter;
    const label = categories.find(([value]) => value === id)[1];
    const count = id === "todos" ? future.length : future.filter(item => id === "gratis" ? estadoPrecio(item).gratis : eventCategories(item).includes(id)).length;
    button.textContent = `${label} · ${count}`;
    const selected = id === "todos" ? activeFilters.length === 0 : activeFilters.includes(id);
    button.setAttribute("aria-checked", String(selected));
    button.setAttribute("aria-pressed", String(selected));
  }
}

const $ = id => document.getElementById(id);
const pad = n => String(n).padStart(2, "0");
const dateKey = (y, m, d) => `${y}-${pad(m + 1)}-${pad(d)}`;

// Al abrir, mostrar el mes y día actuales.
const hoy = new Date();
let visibleMonth = new Date(
  hoy.getFullYear(),
  hoy.getMonth(),
  1
);
let selectedDate = dateKey(
  hoy.getFullYear(),
  hoy.getMonth(),
  hoy.getDate()
);

function actualizarDia() {
  const ahora = new Date();
  const nueva = dateKey(ahora.getFullYear(), ahora.getMonth(), ahora.getDate());
  const anterior = dateKey(hoy.getFullYear(), hoy.getMonth(), hoy.getDate());
  if (nueva !== anterior) {
    if (selectedDate === anterior) {
      selectedDate = nueva;
      visibleMonth = new Date(ahora.getFullYear(), ahora.getMonth(), 1);
    }
    hoy.setTime(ahora.getTime());
    render();
  }
}
setInterval(actualizarDia, 60 * 1000);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) actualizarDia();
});

let loadingEvents = false;
async function loadEvents() {
  if (loadingEvents) return;
  loadingEvents = true;
  const started = performance.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch("eventos.json", {
      cache: "no-cache", signal: controller.signal
    });
    if (!response.ok) throw Error("No se pudo cargar la agenda");
    const text = await response.text();
    const data = JSON.parse(text);
    if (!Array.isArray(data.eventos) || data.eventos.some(item =>
      !item || typeof item.fecha !== "string" || typeof item.hora !== "string" ||
      typeof item.nombre !== "string" || typeof item.lugar !== "string")) {
      throw Error("Datos inválidos; se conserva la agenda visible");
    }
    events = data.eventos;
    $("updated").textContent = `Datos revisados: ${data.actualizado || "sin fecha"}` +
      (data.estado === "parcial" ? " · Algunas fuentes están pendientes de revisión" : "");
    const renderStarted = performance.now();
    render();
    window.agendaMetrics = {
      jsonBytes: new TextEncoder().encode(text).length,
      events: events.length,
      renderMs: performance.now() - renderStarted,
      loadMs: performance.now() - started
    };
    requestAnimationFrame(() => requestAnimationFrame(() => {
      window.agendaMetrics.visibleMs = performance.now() - started;
      window.agendaMetrics.navigationVisibleMs = performance.now();
      window.dispatchEvent(new CustomEvent("agenda:ready", {detail: window.agendaMetrics}));
    }));
  } finally {
    clearTimeout(timer);
    loadingEvents = false;
  }
}

function renderCalendar() {
  const y = visibleMonth.getFullYear();
  const m = visibleMonth.getMonth();

  $("month").textContent =
    visibleMonth.toLocaleDateString("es-AR", {
      month: "long",
      year: "numeric"
    });

  const grid = $("days");
  grid.replaceChildren();

  for (const label of ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"]) {
    const span = document.createElement("span");
    span.className = "label";
    span.textContent = label;
    grid.append(span);
  }

  const offset = (new Date(y, m, 1).getDay() + 6) % 7;

  for (let i = 0; i < offset; i++) {
    grid.append(document.createElement("span"));
  }

  for (let d = 1; d <= new Date(y, m + 1, 0).getDate(); d++) {
    addDay(grid, dateKey(y, m, d), d);
  }
}

function addDay(grid, key, number) {
  const button = document.createElement("button");

  button.textContent = number;

  const available = availableDates().includes(key);
  button.disabled = !available;
  button.setAttribute("aria-label", `${number}${available ? ", con actividades" : ", sin actividades"}`);
  if (available) {
    button.classList.add("has");
  }

  if (key === selectedDate) {
    button.classList.add("active");
  }

  button.onclick = () => {
    selectDate(key);
  };

  grid.append(button);
}

function addLink(parent, label, url, className = "") {
  if (!url) return;

  const link = document.createElement("a");

  link.textContent = label;
  link.href = url;
  link.className = className;
  link.target = "_blank";
  link.rel = "noopener noreferrer";

  parent.append(link);
}

function precioDesdeTexto(texto) {
  const text = normalize(texto);
  if (/\b(gratis|gratuita|gratuito|sin cargo|entrada libre|acceso libre)\b/.test(text)) {
    return {gratis: true, etiqueta: "Gratis"};
  }
  const matches = [...String(texto || "").matchAll(/(?:\$|ars\s*)\s*([\d.]+(?:,[\d]{1,2})?)/gi)]
    .map(match => Number(match[1].replace(/\./g, "").replace(",", ".")))
    .filter(value => Number.isFinite(value) && value > 0 && value < 50000000);
  if (!matches.length) return null;
  const amount = Math.min(...matches);
  const formatted = new Intl.NumberFormat("es-AR", {style: "currency", currency: "ARS", maximumFractionDigits: 2}).format(amount);
  return {gratis: false, etiqueta: matches.length > 1 || /\bdesde\b/i.test(texto) ? `Desde ${formatted}` : formatted};
}

function estadoPrecio(item) {
  if (item.precio === 0) return {gratis: true, etiqueta: "Gratis"};
  if (item.precio_etiqueta && /\b(gratis|gratuita|gratuito|sin cargo|libre)\b/i.test(item.precio_etiqueta)) {
    return {gratis: true, etiqueta: "Gratis"};
  }
  if (typeof item.precio === "number" && Number.isFinite(item.precio) && item.precio > 0) {
    return {gratis: false, etiqueta: new Intl.NumberFormat("es-AR", {style: "currency", currency: "ARS", maximumFractionDigits: 2}).format(item.precio)};
  }
  const desdeDescripcion = precioDesdeTexto(item.descripcion);
  if (desdeDescripcion) return desdeDescripcion;
  if (item.precio_etiqueta) return {gratis: false, etiqueta: item.precio_etiqueta};
  return {gratis: false, etiqueta: item.entrada_paga === true || item.entradas_url ? "Pago" : "Precio a confirmar"};
}

function etiquetaPrecio(item) {
  return estadoPrecio(item).etiqueta;
}

function horarioEvento(item) {
  const inicio = String(item.hora || "").trim();
  const finDirecto = item.hora_fin || item.hora_hasta || item.hasta || item.fin || item.endTime;
  if (finDirecto) {
    const fin = String(finDirecto).match(/(?:T|\b)(\d{1,2}):([0-5]\d)/);
    if (fin) return `${inicio}–${fin[1].padStart(2, "0")}:${fin[2]}`;
  }

  // Algunas fuentes publican el rango en la descripción (por ejemplo, la Feria
  // del Libro); mostrarlo junto a la hora evita que quede escondido en el texto.
  const texto = String(item.descripcion || "");
  const rango = texto.match(/(?:horario(?:\s+oficial)?\s*[:：]?\s*(?:de\s*)?|\bde)\s*(\d{1,2}(?::[0-5]\d)?)\s*(?:a|hasta|[-–])\s*(\d{1,2}(?::[0-5]\d)?)(?:\s*(?:hs?|horas))?/i);
  if (rango) {
    const formatear = valor => {
      const [h, m = "00"] = valor.split(":");
      return `${h.padStart(2, "0")}:${m}`;
    };
    const desde = formatear(rango[1]);
    const hasta = formatear(rango[2]);
    return inicio && inicio !== desde ? `${desde}–${hasta}` : `${inicio || desde}–${hasta}`;
  }

  // También aceptar rangos ya normalizados en el propio campo hora.
  const horaConRango = inicio.match(/^(\d{1,2}:\d{2})\s*(?:a|hasta|[-–])\s*(\d{1,2}:\d{2})$/i);
  if (horaConRango) return `${horaConRango[1]}–${horaConRango[2]}`;
  return inicio;
}

function renderEvent(item) {
  const card = document.createElement("article");
  card.className = "event";

  // Toda la información del evento abre la misma ficha que antes abría el botón.
  const infoUrl = item.evento_url || item.entradas_url;
  const info = document.createElement(infoUrl ? "a" : "div");
  info.className = "event-info";
  if (infoUrl) {
    info.href = infoUrl;
    info.target = "_blank";
    info.rel = "noopener noreferrer";
    info.setAttribute("aria-label", `Ver información de ${item.nombre}`);
  }

  const title = document.createElement("h3");
  title.textContent = item.nombre;

  const time = document.createElement("div");
  time.className = "time";
  time.textContent = `${horarioEvento(item)} · ${etiquetaPrecio(item)}`;

  const place = document.createElement("p");
  place.textContent = item.lugar;

  const desc = document.createElement("p");
  desc.textContent = item.descripcion || "";
  if (item.revision_pendiente) desc.textContent += " · Información anterior: pendiente de revisión";

  info.append(time, title, place, desc);

  const actions = document.createElement("div");
  actions.className = "actions";

  // El mapa ocupa el lugar que tenía “Ver información”.
  const maps =
    `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(item.direccion)}`;
  addLink(actions, "📍 Mapa", maps, "map");

  // Enlace directo a Ticketek si está disponible.
  addLink(actions, "🎫 Comprar tickets", item.entradas_url);

  card.append(info, actions);
  $("events").append(card);
}

function render() {
  ensureSelection();
  renderSummary();
  renderNavigation();
  renderCalendar();

  const date = selectedDate ? new Date(`${selectedDate}T12:00:00`) : null;

  $("selected").textContent =
    date ? date.toLocaleDateString("es-AR", {
      weekday: "long",
      day: "numeric",
      month: "long"
    }) : "Sin días disponibles";

  $("events").replaceChildren();

  const list = futureEvents().filter(e => e.fecha === selectedDate)
    .filter(matchesFilter)
    .sort((a, b) => a.hora.localeCompare(b.hora));

  $("day-count").textContent = `${list.length} ${list.length === 1 ? "actividad" : "actividades"}${activeFilters.length ? " con estos filtros" : ""}`;

  if (!list.length) {
    $("events").textContent =
      activeFilters.length === 0 ? "Todavía no hay actividades cargadas para esta fecha." : "No hay actividades que coincidan con todos los filtros elegidos. Probá quitar uno.";
  }

  list.forEach(renderEvent);
}

// Navegar entre meses, actualizando la fecha seleccionada.
function cambiarMes(direction) {
  const months = [...new Set(availableDates().map(key => key.slice(0, 7)))];
  const current = dateKey(visibleMonth.getFullYear(), visibleMonth.getMonth(), 1).slice(0, 7);
  const target = direction > 0 ? months.find(month => month > current) : months.filter(month => month < current).at(-1);
  if (!target) return;
  selectDate(availableDates().find(key => key.startsWith(target)));
}

$("today").onclick = () => {
  const key = availableDates().find(date => date >= todayKey());
  if (key) selectDate(key);
};

$("prev").onclick = () => cambiarMes(-1);
$("next").onclick = () => cambiarMes(1);

// Cargar eventos al abrir.
loadEvents().catch(() => {
  $("events").textContent =
    "Error cargando eventos. Intentá recargar la página en unos instantes.";
});

// Revisar el archivo de eventos cada hora.
setInterval(() => {
  loadEvents().catch(console.error);
}, 60 * 60 * 1000);
