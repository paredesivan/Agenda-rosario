// Íconos diferenciados para las losetas. No modifica filtros ni extractores.
(() => {
  const originalRenderEvent = renderEvent;
  const sketches = {
    infancias: [
      ['M18 53L32 35L46 53L32 70Z','#e2b46c'],
      ['M48 23A11 11 0 1 0 48 45A11 11 0 1 0 48 23','#b7c6ab'],
      ['M16 20L25 10L34 20L31 31H19Z','#e2b0a5'],
      ['M47 34L54 27M21 48L17 43M32 42L32 25','none']
    ],
    museos: [
      ['M9 32L40 12L71 32Z','#e1c89d'],
      ['M13 69H67V76H13Z','#c8b59b'],
      ['M16 35H64V42H16Z','#bbccbb'],
      ['M21 42V68M30 42V68M40 42V68M50 42V68M59 42V68','none']
    ],
    charlas: [
      ['M9 21Q9 13 22 13H52Q65 13 65 27V47Q65 59 52 59H32L18 72V57Q9 54 9 43Z','#b9cbb9'],
      ['M28 32Q28 21 42 21H59Q72 21 72 35V52Q72 61 62 61H57L65 72L44 61','#e5be9d'],
      ['M18 33H47M18 43H37M43 43H54','none']
    ],
    muestras: [
      ['M12 17H68V70H12Z','#e5c79a'],
      ['M18 23H62V64H18Z','#f0e6d3'],
      ['M24 54L36 39L44 47L51 34L59 54Z','#b7c8a8'],
      ['M43 31A4 4 0 1 0 43 39A4 4 0 1 0 43 31','#dcaf87'],
      ['M7 75H73M40 70V79M20 79H60','none']
    ]
  };
  const normal = v => String(v || '').normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '').toLowerCase();
  function categoryForIcon(item) {
    const tags = [item.categoria, ...(Array.isArray(item.categorias) ? item.categorias : [])]
      .map(normal);
    const title = normal(item.nombre);
    const venue = normal(item.lugar);
    if (tags.includes('infancias') || tags.includes('infantil') ||
        /\b(infancias?|infantil(?:es)?|ninos?|ninas?|titeres?|para chicos|para ninos)\b/.test(title)) return 'infancias';
    if (tags.includes('charlas') || /\b(charlas?|conferencias?|conversatorios?|debates?|panel de debate)\b/.test(title)) return 'charlas';
    if (tags.includes('muestras') || tags.includes('exposiciones') ||
        /\b(muestras?|exposiciones?|exhibiciones?|galeria de arte)\b/.test(title)) return 'muestras';
    if (tags.includes('museos') || tags.includes('museo') ||
        /\b(museos?|macro|castagnino)\b/.test(venue) ||
        /\b(museos?|visita guiada al museo)\b/.test(title)) return 'museos';
    return null;
  }
  function draw(category) {
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 80 90');
    for (const [d, fill] of sketches[category]) {
      const path = document.createElementNS(ns, 'path');
      path.setAttribute('d', d);
      path.setAttribute('fill', fill);
      path.setAttribute('stroke', '#665442');
      path.setAttribute('stroke-width', '2');
      path.setAttribute('stroke-linejoin', 'round');
      path.setAttribute('stroke-linecap', 'round');
      svg.append(path);
    }
    return svg;
  }
  renderEvent = function(item) {
    originalRenderEvent(item);
    const category = categoryForIcon(item);
    if (!category) return;
    const card = document.getElementById('events').lastElementChild;
    const sketch = card && card.querySelector('.event-sketch');
    if (sketch) sketch.replaceChildren(draw(category));
  };
})();
