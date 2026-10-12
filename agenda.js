
let events = [];

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

async function loadEvents() {
  const response = await fetch(`eventos.json?t=${Date.now()}`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw Error("No se pudo cargar la agenda");
  }

  const data = await response.json();
  events = data.eventos;

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

  if (events.some(e => e.fecha === key)) {
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

  return "Pago";
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
    "🎟 Página oficial",
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
    .filter(e => e.fecha === selectedDate)
    .sort((a, b) => a.hora.localeCompare(b.hora));

  if (!list.length) {
    $("events").textContent =
      "Todavía no hay actividades cargadas para esta fecha.";
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
