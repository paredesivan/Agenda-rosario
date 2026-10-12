
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

function futureEvents() {
  return events.filter(item => item.fecha >= todayKey());
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

async function loadEvents() {
  const response = await fetch(`eventos.json?t=${Date.now()}`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw Error("No se pudo cargar la agenda");
  }

  const data = await response.json();
  events = Array.isArray(data.eventos) ? data.eventos : [];

  $("updated").textContent =
    `Datos revisados: ${data.actualizado || "sin fecha"}`;

  render();
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

function renderEvent(item) {
  const card = document.createElement("article");
  card.className = "event";

  const title = document.createElement("h3");
  title.textContent = item.nombre;

  const time = document.createElement("div");
  time.className = "time";
  time.textContent =
    `${item.hora} · ${etiquetaPrecio(item)}`;

  const place = document.createElement("p");
  place.textContent = item.lugar;

  const desc = document.createElement("p");
  desc.textContent = item.descripcion;

  const actions = document.createElement("div");
  actions.className = "actions";

  // Página del espectáculo.
  addLink(
    actions,
    "↗ Ver información",
    item.evento_url
  );

  // Enlace directo a Ticketek si está disponible.
  addLink(
    actions,
    "🎫 Comprar tickets",
    item.entradas_url
  );

  // Ubicación en Google Maps.
  const maps =
    `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(item.direccion)}`;

  addLink(actions, "📍 Mapa", maps, "map");

  card.append(time, title, place, desc);
  card.append(actions);

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

  const list = events
    .filter(e => e.fecha === selectedDate && matchesFilter(e))
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
    "Error cargando eventos. Abrí la página desde un servidor web.";
});

// Revisar el archivo de eventos cada hora.
setInterval(() => {
  loadEvents().catch(console.error);
}, 60 * 60 * 1000);


