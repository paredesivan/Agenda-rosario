"""Descubrimiento acotado desde índices públicos; sin datos de eventos fijos."""
import hashlib
from urllib.parse import urljoin, urlsplit


def enlace_local(href, base):
    url = urljoin(base, href).split('#', 1)[0]
    p, b = urlsplit(url), urlsplit(base)
    if p.scheme != 'https' or p.hostname != b.hostname or p.username or p.password:
        return ''
    try:
        if p.port:
            return ''
    except ValueError:
        return ''
    return url


def huella_html(html, base):
    # Ignora scripts, contadores y estilos; incluye texto del índice y sus URLs.
    elementos = html.select('article, .mec-event-article') or [html]
    contenido = []
    for elemento in elementos:
        contenido.append(elemento.get_text(' ', strip=True))
        contenido.extend(enlace_local(a['href'], base) for a in elemento.select('a[href]'))
    return hashlib.sha256('\n'.join(contenido).encode()).hexdigest()


def descubrir(html, base, selector, descargar, paginas=2, admitir=None):
    cola, vistas, enlaces = [(base, html)], set(), {}
    while cola and len(vistas) < paginas:
        url, pagina = cola.pop(0)
        if url in vistas:
            continue
        vistas.add(url)
        if pagina is None:
            pagina = descargar(url)
        for a in pagina.select(selector):
            if admitir is not None and not admitir(a):
                continue
            link = enlace_local(a.get('href', ''), base)
            if link and link != base:
                enlaces.setdefault(link, a.get_text(' ', strip=True))
        for a in pagina.select('a.next[href], a[rel~="next"][href], .pagination a.next[href]'):
            link = enlace_local(a['href'], base)
            if link and link not in vistas and all(link != p[0] for p in cola):
                cola.append((link, None))
    return enlaces


def seleccionar(enlaces, limite, anterior, reloj):
    intentos = anterior.setdefault('intentos', {})
    conocidos = anterior.setdefault('enlaces', {})
    conocidos.update(enlaces)
    posiciones = {url: i for i, url in enumerate(enlaces)}
    ordenados = sorted(conocidos.items(), key=lambda par: (
        intentos.get(par[0], 0), posiciones.get(par[0], len(posiciones))))
    seleccion = ordenados[:limite]
    for url, _ in seleccion:
        intentos[url] = reloj
    return seleccion


def combinar(anteriores, nuevos, consultadas, fallidos, hoy):
    actuales = {(e['evento_url'], e['fecha'], e['hora'], e['nombre']): e for e in nuevos}
    for e in anteriores:
        if e.get('fecha', '') < hoy.isoformat():
            continue
        url = e.get('evento_url')
        if url not in consultadas or url in fallidos:
            conservado = {**e, 'revision_pendiente': True} if url in fallidos else e
            actuales.setdefault((url, e['fecha'], e['hora'], e['nombre']), conservado)
    return sorted(actuales.values(), key=lambda e: (e['fecha'], e['hora'], e['nombre']))
