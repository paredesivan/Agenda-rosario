let events = [];
let visibleMonth = new Date(2026, 9, 1);
let selectedDate = "2026-10-17";
const $ = id => document.getElementById(id);
const pad = n => String(n).padStart(2, "0");
const dateKey = (y, m, d) => `${y}-${pad(m + 1)}-${pad(d)}`;

async function loadEvents() {
  const response = await fetch(`eventos.json?t=${Date.now()}`, {cache: "no-store"});
  if (!response.ok) throw Error("No se pudo cargar la agenda");
  const data = await response.json();
  events = data.eventos;
  $("updated").textContent = `Datos revisados: ${data.actualizado || "sin fecha"}`;
  render();
}

function renderCalendar() {
  const y = visibleMonth.getFullYear(), m = visibleMonth.getMonth();
  $("month").textContent = visibleMonth.toLocaleDateString("es-AR", {month:"long", year:"numeric"});
  const grid = $("days"); grid.replaceChildren();
  for (const label of ["Lu","Ma","Mi","Ju","Vi","Sá","Do"]) {
    const span = document.createElement("span"); span.className="label"; span.textContent=label; grid.append(span);
  }
  const offset = (new Date(y,m,1).getDay()+6)%7;
  for (let i=0;i<offset;i++) grid.append(document.createElement("span"));
  for (let d=1;d<=new Date(y,m+1,0).getDate();d++) addDay(grid,dateKey(y,m,d),d);
}

function addDay(grid, key, number) {
  const button = document.createElement("button"); button.textContent=number;
  if (events.some(e => e.fecha === key)) button.classList.add("has");
  if (key === selectedDate) button.classList.add("active");
  button.onclick = () => {selectedDate=key; render();};
  grid.append(button);
}

function addLink(parent, label, url, className="") {
  if (!url) return;
  const link = document.createElement("a"); link.textContent=label;
  link.href=url; link.className=className; link.target="_blank"; link.rel="noopener noreferrer";
  parent.append(link);
}

function renderEvent(item) {
  const card=document.createElement("article"); card.className="event";
  const title=document.createElement("h3"); title.textContent=item.nombre;
  const time=document.createElement("div"); time.className="time"; time.textContent=item.hora;
  const place=document.createElement("p"); place.textContent=item.lugar;
  const desc=document.createElement("p"); desc.textContent=item.descripcion;
  const actions=document.createElement("div"); actions.className="actions";
  addLink(actions,"🎟 Página oficial",item.evento_url);
  const maps=`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(item.direccion)}`;
  addLink(actions,"📍 Mapa",maps,"map");
  card.append(time,title,place,desc,actions); $("events").append(card);
}

function render() {
  renderCalendar();
  const date=new Date(`${selectedDate}T12:00:00`);
  $("selected").textContent=date.toLocaleDateString("es-AR",{weekday:"long",day:"numeric",month:"long"});
  $("events").replaceChildren();
  const list=events.filter(e=>e.fecha===selectedDate).sort((a,b)=>a.hora.localeCompare(b.hora));
  if (!list.length) $("events").textContent="Todavía no hay actividades cargadas para esta fecha.";
  list.forEach(renderEvent);
}

$("prev").onclick=()=>{visibleMonth.setMonth(visibleMonth.getMonth()-1);render();};
$("next").onclick=()=>{visibleMonth.setMonth(visibleMonth.getMonth()+1);render();};
loadEvents().catch(()=>{$("events").textContent="Error cargando eventos. Abrí la página desde un servidor web.";});
setInterval(()=>loadEvents().catch(console.error),60*60*1000);
