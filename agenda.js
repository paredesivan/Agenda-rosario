
let events = [];
let activeFilter = "todos";
const categories = [
  ["todos", "Todo"], ["teatro", "Teatro"], ["musica", "Música"],
  ["cine", "Cine"], ["museos", "Museos y muestras"], ["ferias", "Ferias"],
  ["libros", "Libros y charlas"], ["danza", "Danza"],
  ["infancias", "Infancias"], ["otros", "Otros"]
];
const normalize = value => String(value || "").normalize("NFD")
  .replace(/[\u0300-\u036f]/g, "").toLowerCase();

function eventCategories(item) {
  const explicit = Array.isArray(item.categorias) ? item.categorias : [item.categoria];
  const known = explicit.map(normalize).filter(c => categories.some(([id]) => id !== "todos" && id === c));
  if (known.length) return [...new Set(known)];
  const content = normalize(`${item.nombre} ${item.descripcion || ""}`);
  const venue = normalize(`${item.lugar} ${item.origen || ""}`);
  const result = [];
  const match = (id, pattern) => { if (pattern.test(content)) result.push(id); };
  match("musica", /\b(musica|musical|recital|concierto|orquesta|banda|cantante|rock|jazz|opera|filarmonica|reggae|blues|cumbia|rap|folklore|tango|cantautor)\b/);
  match("teatro", /\b(teatro|teatral|obra|comedia|dramaturgia|stand[ -]?up|monologo)\b/);
  match("cine", /\b(cine|pelicula|film|documental|proyeccion|cinematografico)\b/);
  match("museos", /\b(museo|museos|muestra|exposicion|artes visuales|fotografia|escultura)\b/);
  match("ferias", /\b(feria|ferias|artesanos|artesanal|mercado)\b/);
  match("libros", /\b(libro|libros|lectura|literatura|literario|poesia|narracion|charla|conferencia)\b/);
  match("danza", /\b(danza|ballet|baile|milonga)\b/);
  match("infancias", /\b(infancias|infantil|ninos|ninas|bebes|titeres)\b/);
  if (/\b(museo|museos|macro|castagnino)\b/.test(venue) && !result.includes("museos")) result.push("museos");
  if (!result.length && /teatro|astengo|atir|comedia/.test(venue)) result.push("teatro");
  return result.length ? result : ["otros"];
}

function todayKey() {
  const now = new Date();
  return dateKey(now.getFullYear(), now.getMonth(), now.getDate());
}

function matchesFilter(item) {
  return activeFilter === "todos" || eventCategories(item).includes(activeFilter);
}

function futureEvents() {
  return events.filter(item => item.fecha >= todayKey());
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
      button.dataset.filter = id;
      button.onclick = () => { activeFilter = id; render(); };
      filters.append(button);
    }
  }
  for (const button of filters.children) {
    const id = button.dataset.filter;
    const label = categories.find(([value]) => value === id)[1];
    const count = id === "todos" ? future.length : future.filter(item => eventCategories(item).includes(id)).length;
    button.textContent = `${label} · ${count}`;
    button.setAttribute("aria-pressed", String(activeFilter === id));
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

  if (events.some(e => e.fecha === key && matchesFilter(e))) {
    button.classList.add("has");
  }

  if (key === selectedDate) {
    button.classList.add("active");
  }

  button.onclick = () => {
    selectedDate = key;
    render();
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

function etiquetaPrecio(item) {
  if (item.precio_etiqueta) {
    return item.precio_etiqueta;
  }

  if (item.precio === 0) {
    return "Gratis";
  }

  if (
    typeof item.precio === "number" &&
    Number.isFinite(item.precio) &&
    item.precio > 0
  ) {
    return new Intl.NumberFormat("es-AR", {
      style: "currency",
      currency: "ARS",
      maximumFractionDigits: 2
    }).format(item.precio);
  }

  return item.entrada_paga === true || item.entradas_url ? "Pago" : "Precio a confirmar";
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

  card.append(time, title, place, desc, actions);

  $("events").append(card);
}

function render() {
  renderSummary();
  renderCalendar();

  const date = new Date(`${selectedDate}T12:00:00`);

  $("selected").textContent =
    date.toLocaleDateString("es-AR", {
      weekday: "long",
      day: "numeric",
      month: "long"
    });

  $("events").replaceChildren();

  const list = events
    .filter(e => e.fecha === selectedDate && matchesFilter(e))
    .sort((a, b) => a.hora.localeCompare(b.hora));

  $("day-count").textContent = `${list.length} ${list.length === 1 ? "actividad" : "actividades"}${activeFilter === "todos" ? "" : " con este filtro"}`;

  if (!list.length) {
    $("events").textContent =
      activeFilter === "todos" ? "Todavía no hay actividades cargadas para esta fecha." : "No hay actividades de esta categoría para este día. Probá otra categoría o elegí un día marcado en el calendario.";
  }

  list.forEach(renderEvent);
}

// Navegar entre meses, actualizando la fecha seleccionada.
function cambiarMes(desplazamiento) {
  const diaSeleccionado =
    Number(selectedDate.slice(-2));

  visibleMonth = new Date(
    visibleMonth.getFullYear(),
    visibleMonth.getMonth() + desplazamiento,
    1
  );

  const ultimoDia = new Date(
    visibleMonth.getFullYear(),
    visibleMonth.getMonth() + 1,
    0
  ).getDate();

  selectedDate = dateKey(
    visibleMonth.getFullYear(),
    visibleMonth.getMonth(),
    Math.min(diaSeleccionado, ultimoDia)
  );

  render();
}

$("today").onclick = () => {
  const now = new Date();
  selectedDate = todayKey();
  visibleMonth = new Date(now.getFullYear(), now.getMonth(), 1);
  render();
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

