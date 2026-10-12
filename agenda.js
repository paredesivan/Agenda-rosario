let events = [];
let visibleMonth = new Date(2026, 9, 1);
let selectedDate = "2026-10-17";

const $ = id => document.getElementById(id);
const pad = n => String(n).padStart(2, "0");
const dateKey = (y, m, d) => `${y}-${pad(m + 1)}-${pad(d)}`;

async function loadEvents() {
  const response = await fetch(`eventos.json?t=${Date.now()}`, {
    cache: "no-store"
  });
  if (!response.ok) throw Error("No se pudo cargar la agenda");

  const data = await response.json();
  events = data.eventos;
  $("updated").textContent =
    `Datos revisados: ${data.actualizado || "sin fecha"}`;
  render();
}

function renderCalendar() {
  const y = visibleMonth.getFullYear();
  const m = visibleMonth.getMonth();

  $("month").textContent = visibleMonth.toLocaleDateString("es-AR", {
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

  for (let d = 1; d <= new Date(y, m + 1, 0
