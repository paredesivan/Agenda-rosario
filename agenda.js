let events = [];
let activeFilters = [];
let searchQuery = "";

function matchesSearch(item) {
  if (!searchQuery.trim()) return true;
  const terms = normalize(searchQuery).trim().split(/\s+/).filter(Boolean);
  const text = normalize([item.nombre, item.artista, item.artistas, item.lugar,
    item.direccion, item.descripcion].filter(Boolean).join(" "));
  return terms.every(term => text.includes(term));
}

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

// Las fichas se reemplazan al recargar; reutilizar su clasificación evita
// recalcularla para cada botón, día y filtro en teléfonos lentos.
const categoryCache = new WeakMap();
function eventCategories(item) {
  if (!categoryCache.has(item)) categoryCache.set(item, computeEventCategories(item));
  return categoryCache.get(item);
}

function computeEventCategories(item) {
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
  if (!matchesSearch(item)) return false;
  if (!activeFilters.length) return true;
  const gratis = activeFilters.includes("gratis");
  const categoriesSelected = activeFilters.filter(filter => filter !== "gratis");
  const matchesCategory = !categoriesSelected.length || categoriesSelected.some(filter => eventCategories(item).includes(filter));
  return matchesCategory && (!gratis || estadoPrecio(item).gratis);
}

// Evita mostrar varias fichas del mismo evento cuando distintas fuentes lo
// publican con títulos levemente diferentes. Solo une coincidencias de fecha,
// hora y recinto; los casos ambiguos se mantienen separados.
function locationTokens(value) {
  let text = normalize(value).replace(/\bccpe\b/g, "centro cultural parque espana")
    .replace(/\bmacro\b/g, "museo arte contemporaneo rosario")
    .replace(/\b(sarmiento y el rio|rosario|santa fe|argentina)\b/g, "")
    .replace(/[^a-z0-9]+/g, " ").trim();
  return new Set(text.split(/\s+/).filter(token => (token.length > 1 || /^\d+$/.test(token)) &&
    !["calle", "avenida", "av", "piso", "bis"].includes(token)));
}

function nearText(a, b) {
  if (!a || !b) return false;
  let row = Array.from({length: b.length + 1}, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const next = [i];
    for (let j = 1; j <= b.length; j++) next[j] = Math.min(
      next[j - 1] + 1, row[j] + 1, row[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    row = next;
  }
  return 1 - row[b.length] / Math.max(a.length, b.length) >= 0.85;
}

const contentStopWords = new Set("a al con de del desde el en es la las los para por que un una y muestra muestras exposicion exposiciones actividad cultural informacion publicada agenda rosario funcion obra presenta presentacion".split(" "));
function contentTokens(value) {
  return new Set((normalize(value).match(/[a-z0-9]+/g) || []).filter(w => !contentStopWords.has(w)));
}
function commonCount(a, b) { return [...a].filter(w => b.has(w)).length; }
function eventStart(item) {
  const m = String(item.hora || "").match(/(?<![0-9])([01]?[0-9]|2[0-3]):([0-5][0-9])(?![0-9])/);
  return m ? `${m[1].padStart(2, "0")}:${m[2]}` : null;
}
function sameLocation(a, b) {
  const room = e => {
    const m = normalize(e.lugar).match(/\b(?:sala|auditorio)\s+(.+)/);
    return m ? [...contentTokens(m[1])].sort().join(" ") : "";
  };
  const ra = room(a), rb = room(b);
  if (ra && rb && ra !== rb) return false;
  const signature = e => new Set([...contentTokens(normalize(e.lugar)
    .replace(/\bccpe\b/g, "centro cultural parque espana"))]
    .filter(w => !["centro", "cultural", "galeria", "arte", "teatro", "municipal", "fundacion"].includes(w)));
  const x = signature(a), y = signature(b);
  if (!x.size || !y.size) return false;
  const numbers = set => [...set].filter(w => /^\d+$/.test(w)).sort().join(" ");
  if (numbers(x) !== numbers(y)) return false;
  const shared = commonCount(x, y);
  const sx = [...x].sort().join(" "), sy = [...y].sort().join(" ");
  return sx === sy || (shared >= 2 && shared / Math.min(x.size, y.size) >= .8 &&
    shared / Math.max(x.size, y.size) >= .6) || nearText(sx, sy);
}

function sameContent(a, b) {
  const clean = v => (normalize(v).match(/[a-z0-9]+/g) || []).join(" ");
  const na = clean(a.nombre), nb = clean(b.nombre);
  if (na && nb && (na === nb || (Math.min(na.length, nb.length) >= 8 &&
      (na.includes(nb) || nb.includes(na))))) return true;
  const ta = contentTokens(na), tb = contentTokens(nb), shared = commonCount(ta, tb);
  if (ta.size && tb.size && shared >= 2 && shared / Math.min(ta.size, tb.size) >= .75 &&
      shared / Math.max(ta.size, tb.size) >= .45) return true;
  const description = e => {
    const words = contentTokens(normalize(e.descripcion).replace(/informacion publicada por[^.]*\.?/g, " "));
    for (const word of [...contentTokens(e.lugar), ...contentTokens(e.direccion)]) words.delete(word);
    return words;
  };
  const da = description(a), db = description(b), common = commonCount(da, db);
  return da.size > 0 && db.size > 0 && common >= 6 &&
    common / Math.min(da.size, db.size) >= .85 && common / Math.max(da.size, db.size) >= .7 &&
    (shared >= 1 && shared / Math.min(ta.size, tb.size) >= .5);
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
  const start = eventStart(a);
  return Boolean(a.fecha && a.fecha === b.fecha && start && start === eventStart(b) &&
    sameLocation(a, b) && sameContent(a, b));
}

function deduplicatedEvents(items) {
  // Comparar sólo funciones del mismo día y horario.
  const buckets = new Map();
  for (const item of items) {
    const start = eventStart(item);
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

function acrAvailable(item, now = Date.now()) {
 // if (item.origen !== "Agenda Cultural Rosario") return true;
 // if (horaPendiente(item)) return item.fecha >= todayKey();
 // const ended = item.fecha_fin && item.hora_fin;
 // const cutoff = Date.parse(`${ended ? item.fecha_fin : item.fecha}T${ended ? item.hora_fin : item.hora}:00-03:00`);
 // return Number.isFinite(cutoff) && (ended ? cutoff > now : cutoff >= now);
    return true;
}

let futureCache = {source: null, day: null, minute: null, items: []};
function futureEvents() {
  const day = todayKey();
  const minute = Math.floor(Date.now() / 60000);
  if (futureCache.source !== events || futureCache.day !== day || futureCache.minute !== minute) {
    futureCache = {source: events, day, minute,
      items: deduplicatedEvents(events.filter(item => item.fecha >= day && acrAvailable(item)))};
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
  } else if (events.some(item => item.origen === "Agenda Cultural Rosario")) {
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
    const staticAgenda = document.getElementById('static-agenda');
    if (staticAgenda) staticAgenda.hidden = true;
    document.documentElement.classList.remove('agenda-load-failed');
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

function horaPendiente(item) {
  return !/^\d{1,2}:\d{2}/.test(String(item.hora || "").trim());
}

function horarioEvento(item) {
  const inicio = String(item.hora || "").trim();
  if (horaPendiente(item)) return "Horario a confirmar";
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

function categorySketch(category) {
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', '0 0 80 90');
  const drawings = {
    musica: [['M45 9L58 16L51 29L43 25L28 63Q20 78 12 70Q7 61 18 56L29 59L43 22L37 19Z','#d1a34f'], ['M29 60L38 32M22 56L31 30M40 37L48 40M37 45L45 48M34 53L42 56','none']],
    teatro: [['M9 20Q26 26 43 20L40 48Q27 67 13 48Z','#e4b5a3'],['M35 34Q53 41 70 31L69 62Q55 81 40 64Z','#b8c7a5'],['M18 35L24 36M30 36L36 34M19 45Q27 54 34 45M44 49L50 48M57 47L63 46M46 64Q53 54 62 61','none']],
    ferias: [['M12 39H69V74H12Z','#d5b286'], ['M7 38L19 18H62L75 38Z','#b5c8aa'], ['M19 18L18 38M34 18L33 38M49 18L49 38M62 18L65 38M23 74V54H42V74M50 53H61V64H50Z','none']],
    libros: [['M10 22Q27 17 40 27Q55 18 70 23V70Q53 65 40 74Q25 65 10 69Z','#e7d4a4'],['M40 27V73M17 33L32 34M17 42L32 43M49 34L63 32M49 43L63 41','none']],
    cine: [['M9 32H71V72H9Z','#c0cbb7'],['M8 22L67 12L71 29L11 39Z','#e3c595'],['M33 43L52 53L33 63Z','#b97962'],['M20 20L29 35M38 17L47 32M56 14L65 29','none']]
  };
  for (const [d, fill] of drawings[category] || drawings.libros) {
    const p = document.createElementNS(ns, 'path');
    p.setAttribute('d', d); p.setAttribute('fill', fill);
    p.setAttribute('stroke', '#665442'); p.setAttribute('stroke-width', '2');
    p.setAttribute('stroke-linecap', 'round'); p.setAttribute('stroke-linejoin', 'round');
    svg.append(p);
  }
  return svg;
}

function renderEvent(item) {
  const card = document.createElement("article");
  card.className = "event";
  const category = eventCategories(item).find(id => id !== 'gratis') || 'otros';
  card.dataset.category = category;
  const marker = document.createElement('span');
  marker.className = 'timeline-time';
  marker.textContent = horaPendiente(item) ? 'A confirmar' : eventStart(item);
  marker.setAttribute('aria-hidden', 'true');
  const sketch = document.createElement('span');
  sketch.className = 'event-sketch';
  sketch.setAttribute('aria-hidden', 'true');
  sketch.append(categorySketch(category));

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
  const address = String(item.direccion || "").trim();
  const venue = String(item.lugar || "").trim();
  const destination = address || (venue ? `${venue}, Rosario, Santa Fe, Argentina` : "");
  const maps = destination
    ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(destination)}`
    : "";
  addLink(actions, "📍 Mapa", maps, "map");

  // Enlace directo a Ticketek si está disponible.
  addLink(actions, "🎫 Comprar tickets", item.entradas_url);

  card.append(marker, info, sketch, actions);
  $("events").append(card);
}

function render() {
  ensureSelection();
  renderSummary();
  renderNavigation();
  renderCalendar();
  renderWeekStrip();
  const resultCount = futureEvents().filter(matchesFilter).length;
  $("search-status").textContent = searchQuery ? `${resultCount} ${resultCount === 1 ? "función encontrada" : "funciones encontradas"} en todas las fechas${activeFilters.length ? " con estos filtros" : ""}` : "";
  $("clear-search").hidden = !searchQuery;

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
    .sort((a, b) => Number(horaPendiente(a)) - Number(horaPendiente(b)) || a.hora.localeCompare(b.hora));

  $("day-count").textContent = `${list.length} ${list.length === 1 ? "actividad" : "actividades"}${activeFilters.length || searchQuery ? " con estos filtros" : ""}`;

  if (!list.length) {
    $("events").textContent =
      !searchQuery && activeFilters.length === 0 ? "Todavía no hay actividades cargadas para esta fecha." : "No hay actividades que coincidan con la búsqueda y los filtros. Probá otra palabra o quitá un filtro.";
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

// Buscar en todas las fechas; las categorías se combinan con la búsqueda.
$("event-search-form").addEventListener("submit", event => {
  event.preventDefault();
  searchQuery = $("event-search").value.trim();
  render();
});
function clearEventSearch() {
  searchQuery = "";
  $("event-search").value = "";
  render();
}
$("clear-search").addEventListener("click", () => {
  clearEventSearch();
  $("event-search").focus();
});
$("event-search").addEventListener("input", event => {
  if (!event.target.value && searchQuery) clearEventSearch();
});


// Ambas presentaciones usan la misma selección, filtros y fichas.
function renderWeekStrip() {
  const strip = $('week-strip');
  strip.replaceChildren();
  const anchor = new Date(`${selectedDate || todayKey()}T12:00:00`);
  anchor.setDate(anchor.getDate() - (anchor.getDay() + 6) % 7);
  const dates = new Set(availableDates());
  for (let i = 0; i < 7; i++) {
    const date = new Date(anchor);
    date.setDate(anchor.getDate() + i);
    const key = dateKey(date.getFullYear(), date.getMonth(), date.getDate());
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.date = key;
    button.disabled = !dates.has(key);
    button.setAttribute('aria-pressed', String(key === selectedDate));
    button.setAttribute('aria-label', date.toLocaleDateString('es-AR', {weekday:'long', day:'numeric', month:'long'}) + (dates.has(key) ? ', con actividades' : ', sin actividades'));
    const label = document.createElement('span');
    label.textContent = date.toLocaleDateString('es-AR', {weekday:'short'}).replace('.', '');
    const number = document.createElement('strong');
    number.textContent = date.getDate();
    button.append(label, number);
    button.onclick = () => selectDate(key);
    strip.append(button);
  }
}
function setAgendaView(view, persist = true) {
  const value = view === 'calendario' ? 'calendario' : 'cuaderno';
  document.documentElement.dataset.agendaView = value;
  for (const button of document.querySelectorAll('button[data-agenda-view]')) {
    button.setAttribute('aria-pressed', String(button.dataset.agendaView === value));
  }
  $('week-strip').hidden = value !== 'calendario';
  if (persist) { try { localStorage.setItem('salidasrosario.vista', value); } catch (_) {} }
}
for (const button of document.querySelectorAll('button[data-agenda-view]')) {
  button.addEventListener('click', () => setAgendaView(button.dataset.agendaView));
}
setAgendaView(document.documentElement.dataset.agendaView, false);

// Cargar eventos al abrir.
loadEvents().catch(() => {
  document.documentElement.classList.add('agenda-load-failed');
  const staticAgenda = $('static-agenda');
  if (staticAgenda) staticAgenda.hidden = false;
  $("events").textContent =
    "Error cargando eventos. Intentá recargar la página en unos instantes.";
});

// Revisar el archivo de eventos cada hora.
setInterval(() => {
  loadEvents().catch(console.error);
}, 60 * 60 * 1000);



