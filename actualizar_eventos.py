"""Actualiza actividades culturales con fecha, hora y acceso verificados."""

import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from cobertura_fuentes import HORIZONTE_DIAS

ARCHIVO = Path(__file__).with_name("eventos.json")
BASE = "https://www.rosario.gob.ar"
FUENTES = (f"{BASE}/inicio/cultura-y-educacion", f"{BASE}/inicio/agenda")
ORIGEN = "Municipalidad de Rosario"
ZONA = ZoneInfo("America/Argentina/Cordoba")
DIAS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")
CATEGORIAS = ("cine", "teatro", "musica", "concierto", "feria", "muestra",
              "exposicion", "festival", "danza", "planetario", "arte",
              "visita guiada", "visitas guiadas", "literatura", "libro")
DIAGNOSTICO_MUNICIPAL = {}


def texto(elemento):
    return " ".join(elemento.get_text(" ", strip=True).split()) if elemento else ""


def normalizar(valor):
    return "".join(c for c in unicodedata.normalize("NFD", valor.lower())
                   if unicodedata.category(c) != "Mn")


def url_oficial(valor):
    partes = urlsplit(urljoin(BASE, valor))
    if partes.hostname not in ("www.rosario.gob.ar", "rosario.gob.ar"):
        return ""
    ruta = partes.path.replace("/inicio/index.php/", "/inicio/").rstrip("/")
    if not ruta.startswith("/inicio/"):
        return ""
    return urlunsplit(("https", "www.rosario.gob.ar", ruta, "", ""))


def descargar(url):
    with requests.Session() as sesion:
        reintentos = Retry(total=2, backoff_factor=0.5,
                           status_forcelist=(429, 500, 502, 503, 504))
        sesion.mount("https://", HTTPAdapter(max_retries=reintentos))
        respuesta = sesion.get(url, timeout=(10, 25),
                               headers={"User-Agent": "AgendaRosario/2.0"})
        respuesta.raise_for_status()
        respuesta.encoding = "utf-8"
        return BeautifulSoup(respuesta.text, "html.parser")


def obtener_enlaces():
    enlaces, errores = set(), []
    for fuente in FUENTES:
        try:
            html = descargar(fuente)
            tarjetas = html.select("actividad a[href]")
            if not tarjetas:
                raise ValueError("La fuente no contiene tarjetas de actividades")
            enlaces.update(url for a in tarjetas if (url := url_oficial(a["href"])))
        except (requests.RequestException, ValueError) as error:
            errores.append(f"{fuente}: {error}")
    if not enlaces:
        raise RuntimeError("No se pudo consultar la agenda oficial; se conservan los datos")
    return enlaces, errores


def es_cultural(contenido):
    etiquetas = " ".join(texto(e) for e in contenido.select(
        ".etiqueta-actividad, .etiquetas-secundarias-container"))
    descripcion = texto(contenido.select_one(".descripcion"))
    valor = normalizar(etiquetas + " " + texto(contenido.select_one("h1")) + " " + descripcion)
    titulo = normalizar(texto(contenido.select_one('h1')))
    # La cartelera también ofrece juego y recreación. Una mención a aprender
    # en la descripción no convierte una visita pública en un curso.
    if re.match(r'^(?:cursos?|taller(?:es)?|seminarios?|capacitacion(?:es)?|clases?|workshops?)\b', titulo):
        return False
    if re.search(r'\binfancias\b|\brecreacion\b', normalizar(etiquetas)):
        return True
    return any(re.search(r"\b" + re.escape(c) + r"s?\b", valor) for c in CATEGORIAS)


def es_gratuito(bloque, contenido):
    entrada = bloque.select_one(".entrada-actividad")
    if entrada:
        return bool(re.fullmatch(
            r"gratis|gratuit[ao]s?|entrada (?:libre(?: y gratuita)?|gratuita)|sin (?:costo|cargo)",
            normalizar(texto(entrada))))
    # Una mención general no reemplaza el precio de otra función del mismo evento.
    if contenido.select_one(".entrada-actividad"):
        return False
    descripcion = normalizar(texto(contenido.select_one(".descripcion")))
    return any(frase in descripcion for frase in (
        "entrada libre y gratuita", "entrada gratuita", "actividad gratuita", "acceso gratuito"))


def hora_regla(valor):
    encontrado = re.match(r"(?:de\s+|a las\s+)?(\d{1,2})(?:[:.](\d{2}))?\b",
                          normalizar(valor))
    if not encontrado:
        return None
    hora, minuto = int(encontrado[1]), int(encontrado[2] or 0)
    return f"{hora:02d}:{minuto:02d}" if hora < 24 and minuto < 60 else None


def fechas_regla(regla, hoy, hora_alternativa=None):
    valor = normalizar(texto(regla.select_one(".rule-fechas")))
    patron = r"del?\s+(\d{1,2})(?:\s+de\s+(\w+)(?:\s+(\d{4}))?)?\s+al\s+(\d{1,2})\s+de\s+(\w+)(?:\s+(\d{4}))?"
    partes = re.fullmatch(patron, valor)
    hora_publicada = texto(regla.select_one('.rule-hora'))
    hora = hora_regla(hora_publicada) if hora_publicada else hora_alternativa
    if not hora and hora_alternativa == 'Horario a confirmar' and normalizar(hora_publicada) in (
            'a confirmar', 'horario a confirmar', 'sin horario confirmado'):
        hora = hora_alternativa
    if not partes or not hora:
        return []
    dia1, mes1, anio1, dia2, mes2, anio2 = partes.groups()
    if mes1 is None:
        mes1, anio1 = mes2, anio2
    if mes1 not in MESES or mes2 not in MESES:
        return []
    m1, m2 = MESES.index(mes1) + 1, MESES.index(mes2) + 1
    anio = int(anio1) if anio1 else hoy.year
    if not anio1 and m2 < m1 and hoy.month <= m2:
        anio -= 1
    try:
        inicio = date(anio, m1, int(dia1))
        fin = date(int(anio2) if anio2 else anio + (m2 < m1), m2, int(dia2))
    except ValueError:
        return []
    dias = normalizar(texto(regla.select_one(".rule-dias")))
    if dias == "todos los dias":
        elegidos = set(range(7))
    else:
        elegidos = {i for i, d in enumerate(DIAS) if re.search(r"\b" + d + r"\b", dias)}
        intervalo = re.fullmatch(r"(?:de\s+)?(" + "|".join(DIAS) + r")\s+a\s+(" + "|".join(DIAS) + r")", dias)
        if intervalo:
            primero, ultimo = DIAS.index(intervalo[1]), DIAS.index(intervalo[2])
            elegidos = {(primero + i) % 7 for i in range((ultimo - primero) % 7 + 1)}
        elif re.search(r"excepto|cada|alternad", dias):
            return []
    resultados = []
    actual, limite = max(inicio, hoy), min(fin, hoy + timedelta(days=HORIZONTE_DIAS))
    while actual <= limite:
        if actual.weekday() in elegidos:
            resultados.append((actual.isoformat(), hora))
        actual += timedelta(days=1)
    return resultados


def hora_descripcion(contenido):
    """Sólo un horario de apertura inequívoco; no inferir varios turnos."""
    valor = normalizar(texto(contenido.select_one('.descripcion')))
    patron = (r'\b(?:de|desde(?:\s+las)?)\s+(\d{1,2}(?:[:.]\d{2})?)'
              r'\s+(?:a|hasta(?:\s+las)?)\s+\d{1,2}(?:[:.]\d{2})?\s*(?:h\b|hs\b|horas\b)')
    horas = {hora_regla(m[1]) for m in re.finditer(patron, valor)} - {None}
    return next(iter(horas)) if len(horas) == 1 else None


def precio_municipal(bloque, contenido):
    entrada = bloque.select_one('.entrada-actividad')
    valor = texto(entrada) if entrada else texto(contenido.select_one('.descripcion'))
    normal = normalizar(valor)
    # El precio general prevalece sobre una gratuidad por edad/condición.
    pagas = bool(re.search(r'\bpaga\b|\barancelad|\$\s*\d', normal))
    if not pagas and es_gratuito(bloque, contenido):
        return 0, ''
    precio, nota = acceso(valor, venta=True)
    # Sin precio general comprobado no marcar GRATIS por menores, socios o CUD.
    if precio == 0:
        precio = None
    return precio, nota or 'Consultar precio y condiciones en la fuente oficial'


def ubicacion(bloque):
    titulo = bloque.select_one(".title-lugar")
    nombre = " ".join(titulo.find_all(string=True, recursive=False)).strip() if titulo else ""
    direccion = texto(bloque.select_one(".direccion-lugar"))
    if not nombre:
        nombre = texto(bloque.select_one(".lugar-contenedor"))
    return nombre, (direccion or nombre) + ", Rosario, Santa Fe" if nombre else ""


def clave(evento):
    return (evento["fecha"], evento["hora"], evento.get("evento_url") or normalizar(evento["nombre"]),
            normalizar(evento.get("lugar", "")))


def extraer_eventos(html, url, hoy, diagnostico=None):
    contenido = html.select_one("main") or html
    titulo = texto(contenido.select_one("h1"))
    registro = diagnostico if diagnostico is not None else {}
    registro.update(url=url, nombre=titulo, bloques=0, funciones=0, motivos=[])
    if not titulo or not es_cultural(contenido):
        registro['motivos'].append('Sin título o fuera del alcance cultural/recreativo (se excluye formación)')
        return []
    parrafo = contenido.select_one(".descripcion p")
    resumen = " ".join(texto(parrafo).split()[:22])
    if len(texto(parrafo).split()) > 22:
        resumen = resumen.rstrip(".,:;") + "…"
    resultados = {}
    bloques = [b for grupo in contenido.select('.cuando-fechas')
               for b in (grupo.select('.rule') or [grupo])]
    # Una hora de la descripción sólo se aplica a una sede y calendario únicos.
    sedes = {ubicacion(b)[0] for b in bloques} - {''}
    calendarios = {texto(b.select_one('.rule-fechas')) for b in bloques
                   if b.select_one('.rule-fechas')}
    hora_comun = hora_descripcion(contenido) if len(sedes) == 1 and len(calendarios) <= 1 else None
    for bloque in bloques:
        registro['bloques'] += 1
        lugar, direccion = ubicacion(bloque)
        if not lugar:
            registro['motivos'].append('Bloque sin sede verificable')
            continue
        precio, etiqueta = precio_municipal(bloque, contenido)
        fechas = []
        if 'rule' in bloque.get('class', []):
            fechas.extend(fechas_regla(bloque, hoy, hora_comun or 'Horario a confirmar'))
        for instante in bloque.select("time[datetime]"):
            raw = instante['datetime']
            if 'T' in raw and not instante.select_one('.hora-desde'):
                continue  # La hora de cierre no es una segunda función.
            cuando = datetime.fromisoformat(raw)
            if cuando.tzinfo:
                cuando = cuando.astimezone(ZONA)
            if hoy <= cuando.date() <= hoy + timedelta(days=HORIZONTE_DIAS):
                hora = cuando.strftime('%H:%M') if 'T' in raw else (hora_comun or 'Horario a confirmar')
                fechas.append((cuando.date().isoformat(), hora))
        if not fechas:
            registro['motivos'].append('Sin fechas/horarios interpretables dentro del horizonte')
        for fecha, hora in fechas:
            evento = {"fecha": fecha, "hora": hora, "nombre": titulo,
                      "lugar": lugar, "direccion": direccion,
                      "descripcion": resumen or "Actividad de la agenda cultural municipal.",
                      "evento_url": url, "precio": precio, "origen": ORIGEN,
                      "horario_pendiente": hora == 'Horario a confirmar'}
            if etiqueta:
                evento['precio_etiqueta'] = etiqueta
            resultados[clave(evento)] = evento
    registro['funciones'] = len(resultados)
    registro['detalle_funciones'] = [{k: e.get(k, '') for k in
        ('fecha', 'hora', 'nombre', 'lugar', 'evento_url', 'origen')} for e in resultados.values()]
    registro['motivos'] = list(dict.fromkeys(registro['motivos']))
    return list(resultados.values())


def consultar_evento(url, hoy):
    registro = DIAGNOSTICO_MUNICIPAL.setdefault(url, {})
    try:
        return url, extraer_eventos(descargar(url), url, hoy, registro), None, False
    except requests.HTTPError as error:
        registro.update(url=url, error=str(error), funciones=0)
        eliminado = error.response is not None and error.response.status_code in (404, 410)
        return url, [], str(error), eliminado
    except (requests.RequestException, ValueError) as error:
        registro.update(url=url, error=str(error), funciones=0)
        return url, [], str(error), False


def combinar_eventos(nuevos, anteriores, fallidos, hoy):
    resultados = {clave(e): e for e in nuevos}
    for evento in anteriores:
        if evento["fecha"] < hoy.isoformat():
            continue
        if evento.get("origen") != ORIGEN or url_oficial(evento.get("evento_url", "")) in fallidos:
            resultados.setdefault(clave(evento), evento)
    return sorted(resultados.values(), key=lambda e: (e["fecha"], e["hora"], e["nombre"]))


def actualizar():
    ahora = datetime.now(ZONA)
    hoy = ahora.date()
    anteriores = json.loads(ARCHIVO.read_text(encoding="utf-8")) if ARCHIVO.exists() else {"eventos": []}
    conocidos = anteriores.get("eventos", [])
    enlaces, errores = obtener_enlaces()
    print(f"Municipal: {len(enlaces)} enlaces del índice; {sum(e.get('origen') == ORIGEN and e.get('fecha', '') >= hoy.isoformat() for e in conocidos)} fichas futuras conservadas como respaldo", flush=True)
    enlaces.update(url for e in conocidos if e.get("origen") == ORIGEN
                   and e["fecha"] >= hoy.isoformat() and (url := url_oficial(e.get("evento_url", ""))))
    eventos, fallidos = [], set()
    print(f"Consultando {len(enlaces)} fichas oficiales", flush=True)
    with ThreadPoolExecutor(max_workers=4) as grupo:
        for indice, (url, nuevos, error, eliminado) in enumerate(
                grupo.map(lambda u: consultar_evento(u, hoy), sorted(enlaces)), 1):
            eventos.extend(nuevos)
            if error and not eliminado:
                errores.append(f"{url}: {error}")
                fallidos.add(url)
            if indice % 20 == 0:
                print(f"Revisadas {indice}/{len(enlaces)} fichas", flush=True)
    if not eventos:
        raise RuntimeError("No se extrajeron actividades verificables; no se reemplaza la agenda")
    datos = {"actualizado": ahora.strftime("%Y-%m-%d %H:%M"),
             "estado": "parcial" if errores else "completo",
        "avisos_fuentes": errores,
             "eventos": combinar_eventos(eventos, conocidos, fallidos, hoy)}
    temporal = ARCHIVO.with_suffix(".json.tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporal.replace(ARCHIVO)
    print(f"Agenda actualizada: {len(datos['eventos'])} actividades, {len(errores)} consultas fallidas")
    for error in errores:
        print(f"Aviso: {error}")

# Fuentes adicionales y consultas moderadas.
from html import unescape
from time import monotonic, sleep

EXTRAS = (
    (
        "Plataforma Lavardén",
        "https://plataformalavarden.gob.ar/agenda/",
        "Mendoza 1085",
    ),
    (
        "Centro Cultural Parque de España",
        "https://ccpe.org.ar/web/agenda/",
        "Sarmiento y el río",
    ),
    (
        "Teatro Municipal La Comedia",
        "https://teatrolacomedia.gob.ar/espectaculos/programacion/",
        "Mitre 958",
    ),
)

from control_http import SesionControlada
SESION = SesionControlada()
SESION.headers.update({
    "User-Agent": "AgendaRosario/3.0 (+https://paredesivan.github.io/Agenda-rosario/)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "es-AR,es;q=0.9",
})
# Pausas solicitadas en robots.txt, revisadas el 14/10/2026.
# La pausa general mínima sigue siendo 1,5 segundos.
PAUSAS_POR_HOST = {
    "bibliotecavigil.org.ar": 60.0,
    "www.metropolitano.ar": 10.0,
    "www.teatrosatir.ar": 10.0,
}

ULTIMA, BLOQUEADOS, FALLAS = {}, set(), {}


def descargar(url):
    host = urlsplit(url).hostname
    if host in BLOQUEADOS:
        raise requests.RequestException(
            f"Fuente pausada: {host}; se conservan sus datos"
        )

    espera = max(1.5, PAUSAS_POR_HOST.get(host, 1.5)) - (monotonic() - ULTIMA.get(host, 0))
    if espera > 0:
        sleep(espera)

    try:
        respuesta = SESION.get(url, timeout=(10, 25))
        if respuesta.status_code in (403, 429):
            BLOQUEADOS.add(host)
            raise requests.HTTPError(
                f"HTTP {respuesta.status_code}: fuente pausada hasta la próxima revisión",
                response=respuesta,
            )
        respuesta.raise_for_status()
        FALLAS[host] = 0
        respuesta.encoding = "utf-8"
        return BeautifulSoup(respuesta.text, "html.parser")
    except (requests.ConnectionError, requests.Timeout):
        FALLAS[host] = FALLAS.get(host, 0) + 1
        if FALLAS[host] >= 3:
            BLOQUEADOS.add(host)
        raise
    finally:
        ULTIMA[host] = monotonic()


def acceso(valor, venta=False):
    valor = normalizar(valor)
    patron = r"\$\s*(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?)"
    importes = [
        float(n.replace(".", "").replace(",", "."))
        for n in re.findall(patron, valor)
    ]
    importes = sorted(set(n for n in importes if n > 0))

    if len(importes) == 1:
        return importes[0], ""
    if importes:
        nota = (
            f"Entradas entre ${importes[0]:,.0f} "
            f"y ${importes[-1]:,.0f}. "
        ).replace(",", ".")
        return None, nota

    if re.search(
        r"\bgratis\b|\bgratuit[ao]s?\b|entrada libre|sin (?:costo|cargo)",
        valor,
    ):
        return 0, ""

    if venta or re.search(
        r"entradas? (?:a la venta|anticipadas|en venta)|arancelad|boleteria|tickets",
        valor,
    ):
        return None, ""

    return None, None


def resumen(valor):
    palabras = valor.split()
    return " ".join(palabras[:22]) + ("…" if len(palabras) > 22 else "")


def evento_extra(fecha, hora, nombre, url, fuente, direccion,
                 descripcion, precio, nota):
    return {
        "fecha": fecha,
        "hora": hora,
        "nombre": unescape(nombre),
        "lugar": fuente,
        "direccion": (direccion if "rosario" in normalizar(direccion) else direccion + ", Rosario, Santa Fe"),
        "descripcion": nota + resumen(descripcion),
        "evento_url": url,
        "precio": precio,
        "origen": fuente,
    }


# Comparación factual: nunca unir fechas, funciones o salas distintas.
_PALABRAS_GENERICAS = set("a al con de del desde el en es la las los para por que un una y muestra muestras exposicion exposiciones actividad cultural informacion publicada agenda rosario funcion obra presenta presentacion".split())


def _tokens_evento(valor):
    return set(re.findall(r"[a-z0-9]+", normalizar(str(valor or "")))) - _PALABRAS_GENERICAS


def _hora_evento(evento):
    m = re.search(r"(?<![0-9])([01]?[0-9]|2[0-3]):([0-5][0-9])(?![0-9])", str(evento.get("hora", "")))
    return f"{int(m[1]):02d}:{m[2]}" if m else None


def _texto_cercano(a, b):
    if not a or not b:
        return False
    fila = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        siguiente = [i]
        for j, cb in enumerate(b, 1):
            siguiente.append(min(siguiente[-1] + 1, fila[j] + 1, fila[j - 1] + (ca != cb)))
        fila = siguiente
    return 1 - fila[-1] / max(len(a), len(b)) >= .85


def _mismo_lugar(a, b):
    def firma(e):
        valor = normalizar(e.get("lugar", ""))
        valor = re.sub(r"\bccpe\b", "centro cultural parque espana", valor)
        return _tokens_evento(valor) - {"centro", "cultural", "galeria", "arte", "teatro", "municipal", "fundacion"}
    def sala(e):
        valor = normalizar(e.get("lugar", ""))
        m = re.search(r"\b(?:sala|auditorio)\s+(.+)", valor)
        return " ".join(sorted(_tokens_evento(m[1]))) if m else ""
    sa, sb = sala(a), sala(b)
    if sa and sb and sa != sb:
        return False
    x, y = firma(a), firma(b)
    if not x or not y:
        return False
    # Números de sede y sala son significativos, aunque el nombre sea parecido.
    if {w for w in x if w.isdigit()} != {w for w in y if w.isdigit()}:
        return False
    shared = len(x & y)
    return (x == y or (shared >= 2 and shared / min(len(x), len(y)) >= .8
                       and shared / max(len(x), len(y)) >= .6)
            or _texto_cercano(" ".join(sorted(x)), " ".join(sorted(y))))


def _mismo_contenido(a, b):
    def limpio(valor):
        return " ".join(re.findall(r"[a-z0-9]+", normalizar(str(valor or ""))))
    na, nb = limpio(a.get("nombre")), limpio(b.get("nombre"))
    if na and nb and (na == nb or (min(len(na), len(nb)) >= 8 and (na in nb or nb in na))):
        return True
    ta, tb = _tokens_evento(na), _tokens_evento(nb)
    shared = len(ta & tb)
    if ta and tb and shared >= 2 and shared / min(len(ta), len(tb)) >= .75 and shared / max(len(ta), len(tb)) >= .45:
        return True
    def descripcion(e):
        valor = normalizar(e.get("descripcion") or "")
        valor = re.sub(r"informacion publicada por[^.]*\.?", " ", valor)
        return _tokens_evento(valor) - _tokens_evento(e.get("lugar")) - _tokens_evento(e.get("direccion"))
    da, db = descripcion(a), descripcion(b)
    if not da or not db:
        return False
    comunes = len(da & db)
    # Se exige contenido propio, no una plantilla con categoría, sede y fuente.
    return comunes >= 6 and comunes / min(len(da), len(db)) >= .85 and comunes / max(len(da), len(db)) >= .7 and (
        shared >= 1 and shared / min(len(ta), len(tb)) >= .5)


def eventos_duplicados(a, b):
    hora = _hora_evento(a)
    return bool(a.get("fecha") and a.get("fecha") == b.get("fecha") and hora
                and hora == _hora_evento(b) and _mismo_lugar(a, b) and _mismo_contenido(a, b))


def sin_repetidos(eventos):
    def confianza(e):
        dominio = (urlsplit(e.get("evento_url", "")).hostname or "").removeprefix("www.")
        origen, sede = _tokens_evento(e.get("origen")), _tokens_evento(e.get("lugar"))
        if len(origen & sede) >= 2:
            return 500
        if dominio.endswith((".gob.ar", ".edu.ar")):
            return 400
        if any(t in dominio for t in ("ticketek", "passline", "turboentrada")):
            return 300
        return 100
    grupos = {}
    for evento in sorted(eventos, key=confianza, reverse=True):
        turno = (evento.get("fecha"), _hora_evento(evento))
        funciones = grupos.setdefault(turno, [])
        grupo = next((g for g in funciones if all(eventos_duplicados(evento, e) for e in g)), None)
        if grupo is None:
            funciones.append([evento])
        else:
            grupo.append(evento)
    return [grupo[0] for funciones in grupos.values() for grupo in funciones]


def lavarden(html, fuente, url, direccion, hoy):
    tarjetas = html.select(".jet-listing-grid__item")
    if not tarjetas:
        raise ValueError("Cambió el formato de la agenda Lavardén")

    eventos = []
    for tarjeta in tarjetas:
        enlace = tarjeta.select_one("h2 a[href]")
        valores = [
            texto(v)
            for v in tarjeta.select(".jet-listing-dynamic-field__content")
        ]
        fecha = next(
            (v for v in valores if re.search(r"\d{1,2}:\d{2}\s*hs", v)),
            "",
        )
        partes = re.search(
            r"(\d{1,2})\s+(\w+)(?:\s+(\d{4}))?,\s*(\d{1,2}):(\d{2})",
            normalizar(fecha),
        )
        if not enlace or not partes or partes[2] not in MESES:
            continue

        mes = MESES.index(partes[2]) + 1
        anio = (
            int(partes[3]) if partes[3]
            else hoy.year + (hoy.month == 12 and mes == 1)
        )
        dia = date(anio, mes, int(partes[1]))
        if not hoy <= dia <= hoy + timedelta(days=HORIZONTE_DIAS):
            continue

        venta = any(
            "entradaslavarden.com" in a["href"]
            for a in tarjeta.select("a[href]")
        )
        precio, nota = acceso(texto(tarjeta), venta)
        if nota is None:
            continue

        descripcion = texto(
            tarjeta.select_one(".elementor-widget-text-editor")
        )
        eventos.append(evento_extra(
            dia.isoformat(),
            f"{int(partes[4]):02d}:{partes[5]}",
            texto(enlace),
            enlace["href"],
            fuente,
            direccion,
            descripcion,
            precio,
            nota,
        ))
    return eventos, set()


def eventos_schema(valor):
    if isinstance(valor, list):
        for v in valor:
            yield from eventos_schema(v)
    elif isinstance(valor, dict):
        tipos = valor.get("@type", [])
        if tipos == "Event" or isinstance(tipos, list) and "Event" in tipos:
            yield valor
        for v in valor.values():
            if isinstance(v, (list, dict)):
                yield from eventos_schema(v)


def calendario(html, fuente, url, direccion, hoy):
    fichas = []
    for tag in html.select('script[type="application/ld+json"]'):
        try:
            fichas.extend(eventos_schema(json.loads(tag.get_text())))
        except ValueError:
            continue
    if not fichas:
        raise ValueError("Cambió el formato del calendario")

    eventos, fallidos, vistos = [], set(), set()
    for ficha in fichas:
        fecha = ficha.get("startDate", "")[:10]
        enlace = (
            ficha.get("url")
            or ficha.get("offers", {}).get("url", "")
        )
        if not enlace or enlace in vistos:
            continue
        if urlsplit(enlace).hostname != urlsplit(url).hostname:
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
            continue
        if not hoy <= date.fromisoformat(fecha) <= hoy + timedelta(days=HORIZONTE_DIAS):
            continue

        vistos.add(enlace)
        try:
            detalle = descargar(enlace)
            cuerpo = detalle.select_one(".mec-single-event-description")
            if not cuerpo:
                raise ValueError("La ficha no tiene descripción verificable")
            descripcion = texto(cuerpo)

            if re.search(
                r"\bsuspendid[ao]\b|\bcancelad[ao]\b|\breprogramad[ao]\b",
                normalizar(descripcion),
            ):
                continue

            hora = texto(detalle.select_one(
                ".mec-single-event-time .mec-events-abbr"
            ))
            coincidencia = re.match(r"(\d{1,2}):(\d{2})", hora)
            if not coincidencia:
                continue
            hora = f"{int(coincidencia[1]):02d}:{coincidencia[2]}"

            precio, nota = acceso(descripcion)
            if nota is None:
                continue

            eventos.append(evento_extra(
                fecha, hora, ficha.get("name", ""), enlace,
                fuente, direccion, descripcion, precio, nota,
            ))
        except (requests.RequestException, ValueError) as error:
            fallidos.add(enlace)
            print(
                f"Aviso: {fuente}: {type(error).__name__}; "
                "se conserva la ficha anterior",
                flush=True,
            )
    return eventos, fallidos


def actualizar():
    ahora = datetime.now(ZONA)
    hoy = ahora.date()
    anteriores = (
        json.loads(ARCHIVO.read_text(encoding="utf-8"))
        if ARCHIVO.exists() else {"eventos": []}
    )
    conocidos = anteriores.get("eventos", [])
    eventos, fallidos, errores, correctas = [], set(), [], set()
    BLOQUEADOS.clear()
    FALLAS.clear()
    DIAGNOSTICO_MUNICIPAL.clear()

    for fuente, url, direccion in EXTRAS:
        try:
            html = descargar(url)
            parser = lavarden if fuente == "Plataforma Lavardén" else calendario
            nuevos, fallas = parser(html, fuente, url, direccion, hoy)
            eventos.extend(nuevos)
            fallidos.update(fallas)
            if not nuevos and any(e.get("origen") == fuente and e.get("fecha", "") >= hoy.isoformat() for e in conocidos):
                errores.append(f"{fuente}: extracción vacía; se conservan datos anteriores")
            else:
                correctas.add(fuente)
            if fallas:
                errores.append(f"{fuente}: {len(fallas)} fichas pendientes")
            print(f"{fuente}: {len(nuevos)} actividades", flush=True)
        except (requests.RequestException, ValueError) as error:
            errores.append(
                f"{fuente}: {type(error).__name__}: {error}; "
                "se conservan datos anteriores"
            )

    enlaces = set()
    try:
        enlaces, avisos = obtener_enlaces()
        errores.extend(avisos)
    except (requests.RequestException, ValueError, RuntimeError) as error:
        errores.append(f"Municipalidad: índice inaccesible ({type(error).__name__}: {error}); se reintentan fichas conocidas")
    enlaces = {url_oficial(url) for url in enlaces if url_oficial(url)}
    enlaces.update(
        url for e in conocidos
        if e.get("origen") == ORIGEN and e.get("fecha", "") >= hoy.isoformat()
        if (url := url_oficial(e.get("evento_url", "")))
    )
    print(f"Municipalidad: índice y respaldo reúnen {len(enlaces)} fichas para consultar", flush=True)
    try:
        from cobertura_fuentes import ordenar_consultas
        revision_anterior = ARCHIVO.with_name('revision_cobertura_municipal.json')
        ordenados = ordenar_consultas(enlaces, revision_anterior)
        lote = 40
        inicio_lote = ((ahora.toordinal() * 12 + ahora.hour // 2) * lote) % max(1, len(ordenados))
        seleccion = (ordenados[inicio_lote:] + ordenados[:inicio_lote])[:lote]
        if len(ordenados) > len(seleccion):
            errores.append(f'Municipalidad: revisión rotativa {len(seleccion)}/{len(ordenados)} fichas; el resto se conserva')
        for indice, url in enumerate(seleccion, 1):
            _, nuevos, error, eliminado = consultar_evento(url, hoy)
            eventos.extend(nuevos)
            if error and not eliminado:
                fallidos.add(url)
            if indice % 20 == 0:
                print(
                    f"Municipalidad: {indice}/{len(enlaces)} fichas",
                    flush=True,
                )
        if len(seleccion) == len(ordenados) and not fallidos:
            correctas.add(ORIGEN)
    except (requests.RequestException, ValueError, RuntimeError) as error:
        errores.append(
            f"Municipalidad: {type(error).__name__}; "
            "se conservan datos anteriores"
        )

    if fallidos:
        errores.append(f"{len(fallidos)} fichas pendientes de consulta")
    if not eventos:
        raise RuntimeError(
            "No se obtuvieron actividades; se conserva la agenda anterior"
        )

    resultados = {clave(e): e for e in eventos}
    for e in conocidos:
        conservar = (
            e.get("origen") not in correctas
            or e.get("evento_url") in fallidos
        )
        if e["fecha"] >= hoy.isoformat() and conservar:
            resultados.setdefault(clave(e), e)

    datos = {
        "actualizado": ahora.strftime("%Y-%m-%d %H:%M"),
        "estado": "parcial" if errores else "completo",
        "avisos_fuentes": errores,
        "eventos": sorted(
            sin_repetidos(resultados.values()),
            key=lambda e: (e["fecha"], e["hora"], e["nombre"]),
        ),
    }
    temporal = ARCHIVO.with_suffix(".json.tmp")
    temporal.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporal.replace(ARCHIVO)
    print(
        f"Agenda actualizada: {len(datos['eventos'])} actividades",
        flush=True,
    )
    for error in errores:
        print(f"Aviso: {error}", flush=True)
    revision = {'revision': ahora.isoformat(), 'horizonte_dias': HORIZONTE_DIAS,
                'fuente': ORIGEN, 'fichas_consultadas': len(DIAGNOSTICO_MUNICIPAL),
                'fichas_leidas': sum(not v.get('error') for v in DIAGNOSTICO_MUNICIPAL.values()),
                'fichas_con_error': sum(bool(v.get('error')) for v in DIAGNOSTICO_MUNICIPAL.values()),
                'funciones_extraidas': sum(v.get('funciones', 0) for v in DIAGNOSTICO_MUNICIPAL.values()),
                'fichas_sin_funciones': sum(not v.get('funciones') for v in DIAGNOSTICO_MUNICIPAL.values()),
                'fichas': list(DIAGNOSTICO_MUNICIPAL.values())}
    ARCHIVO.with_name('revision_cobertura_municipal.json').write_text(
        json.dumps(revision, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


# Ampliación: teatros, música y bibliotecas.
EXTRAS += (
    ("Teatro Astengo", "https://teatroastengo.ar/events/", "Mitre 754"),
    ("ATIR", "https://www.teatrosatir.ar/cartelera/", ""),
    ("Teatro Broadway", "https://teatrobroadwayrosario.com/", "San Lorenzo 1223"),
    ("Distrito Siete", "https://www.d7entradas.com.ar/", "Ovidio Lagos 790"),
    ("Metropolitano", "https://www.metropolitano.ar/espectaculos/", "Junín 501"),
    ("Biblioteca Argentina Dr. Juan Álvarez", "https://biblioargentina.gob.ar/web/agenda/", "Presidente Roca 731"),
    ("Biblioteca Vigil", "https://bibliotecavigil.org.ar/inicio/eventos/", "Biblioteca Vigil"),
)
FUENTES += (f"{BASE}/inicio/agenda/buscar",)
CATEGORIAS += ("biblioteca", "lectura", "poesia", "narracion", "charla", "boxeo")
_calendario_anterior = calendario


def hora_visible(valor):
    m = re.match(r"\s*(\d{1,2})(?::|\.)(\d{2})(?:\s*([ap])\.?m\.?)?", normalizar(valor))
    if not m:
        return None
    h = int(m[1])
    if m[3]:
        h = h % 12 + (12 if m[3] == "p" else 0)
    return f"{h:02d}:{m[2]}" if h < 24 and int(m[2]) < 60 else None


def fechas_publicadas(valor, hoy, anio_confirmado=False):
    valor = normalizar(valor)
    patron = (r"(?:(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+)?"
              r"(\d{1,2})\s+(?:de\s+)?(" + "|".join(MESES) + r")"
              r"(?:\s+(?:de\s+)?(20\d{2}))?\s*(?:,\s*)?"
              r"(?:a las?\s+|de\s+)?(\d{1,2})(?::|\.)?(\d{2})?"
              r"(?:\s+a\s+\d{1,2}(?::\d{2})?)?\s*(?:hs?\.?|horas)\b")
    resultado = []
    for m in re.finditer(patron, valor):
        if not m[1] and not m[4] and not anio_confirmado:
            continue
        mes = MESES.index(m[3]) + 1
        anio = int(m[4]) if m[4] else hoy.year + (hoy.month == 12 and mes == 1)
        try:
            dia = date(anio, mes, int(m[2]))
        except ValueError:
            continue
        if m[1] and DIAS[dia.weekday()] != m[1]:
            continue
        hora = hora_visible(f"{m[5]}:{m[6] or '00'}")
        if hora and hoy <= dia <= hoy + timedelta(days=HORIZONTE_DIAS):
            resultado.append((dia.isoformat(), hora))
    return list(dict.fromkeys(resultado))


def actividad_ampliada(fecha, hora, titulo, enlace, fuente, direccion,
                       descripcion, lugar=None, desde=False):
    venta = fuente in ("Teatro Broadway", "Distrito Siete", "Metropolitano")
    precio, nota = acceso(descripcion, venta)
    e = evento_extra(fecha, hora, titulo, enlace, fuente, direccion,
                     descripcion, precio, nota or "")
    e["lugar"] = lugar or fuente
    if nota is None:
        e["precio_etiqueta"] = "Precio a confirmar"
    elif nota:
        valores = re.findall(r"\$[\d.]+", nota)
        e["precio_etiqueta"] = " – ".join(v.rstrip(".") for v in valores)
    elif precio is None:
        e["entrada_paga"] = True
    elif desde and precio:
        e["precio_etiqueta"] = f"Desde ${precio:,.0f}".replace(",", ".")
    return e


def calendario_mec(html, fuente, url, direccion, hoy):
    fichas = []
    for s in html.select('script[type="application/ld+json"]'):
        try:
            contenido = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', s.get_text())
            fichas.extend(eventos_schema(json.loads(contenido)))
        except ValueError:
            continue
    if not fichas:
        raise ValueError("No se encontró el calendario de la sala")

    eventos, fallidos, cache, vistos = [], set(), {}, set()
    for f in fichas:
        fecha, enlace = f.get("startDate", "")[:10], f.get("url", "")
        if not enlace or urlsplit(enlace).hostname != urlsplit(url).hostname:
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha) or (enlace, fecha) in vistos:
            continue
        if not hoy <= date.fromisoformat(fecha) <= hoy + timedelta(days=HORIZONTE_DIAS):
            continue
        vistos.add((enlace, fecha))
        try:
            if enlace not in cache:
                cache[enlace] = descargar(enlace)
            detalle = cache[enlace]
            cuerpo = detalle.select_one(".mec-single-event-description")
            if not cuerpo:
                raise ValueError("Ficha incompleta")
            descripcion = texto(cuerpo)
            if re.search(
                r"\bsuspendid[ao]\b|\bcancelad[ao]\b|\breprogramad[ao]\b",
                normalizar(descripcion),
            ):
                continue
            hora = hora_visible(texto(detalle.select_one(
                ".mec-single-event-time .mec-events-abbr"
            )))
            if not hora:
                continue

            loc = f.get("location", {})
            lugar = loc.get("name") or fuente
            domicilio = loc.get("address") or direccion
            if isinstance(domicilio, dict):
                domicilio = domicilio.get("streetAddress", direccion)

            if fuente == "Teatro Astengo" and not re.search(r"\d", str(domicilio)):
                domicilio = direccion

            if fuente == "Biblioteca Vigil":
                calle = re.search(r"\b(Alem|Gaboto)\s+(\d{3,4})\b", descripcion, re.I)
                if calle:
                    domicilio = calle[0]
                if "astronom" in normalizar(f.get("name", "")):
                    lugar = "Observatorio de la Biblioteca Vigil"
                elif "teatro vigil" in normalizar(f.get("name", "")):
                    lugar, domicilio = "Teatro Vigil", "Alem 3086"

            precio_visible = texto(detalle.select_one(".mec-single-event-cost"))
            eventos.append(actividad_ampliada(
                fecha, hora, f.get("name", ""), enlace, fuente, domicilio,
                precio_visible + " " + descripcion, lugar,
            ))
        except (requests.RequestException, ValueError):
            fallidos.add(enlace)
    return eventos, fallidos


def calendario_paginas(html, fuente, url, direccion, hoy):
    selectores = {
        "Teatro Broadway": "a[href*='/cartelera/']",
        "Distrito Siete": "a[href^='/eventos/']",
        "Metropolitano": "a[href*='/espectaculo/']",
        "Biblioteca Argentina Dr. Juan Álvarez": "h2 a[href], h3 a[href]",
    }
    tarjetas = html.select(selectores[fuente])
    if not tarjetas:
        raise ValueError("No se encontró la programación de la fuente")

    eventos, fallidos, vistos = [], set(), set()
    for a in tarjetas:
        enlace = urljoin(url, a["href"])
        if enlace in vistos or urlsplit(enlace).hostname != urlsplit(url).hostname:
            continue
        vistos.add(enlace)
        if fuente == "Distrito Siete" and "venta finalizada" in normalizar(texto(a)):
            continue
        try:
            detalle = descargar(enlace)
            if fuente == "Distrito Siete":
                titulo = texto(a.select_one("h2")) or texto(detalle.select_one("h2"))
            elif fuente == "Teatro Broadway":
                titulo = (
                    texto(a.select_one(".tbr-show-card-title"))
                    or texto(detalle.select_one("h1"))
                )
            else:
                titulo = texto(detalle.select_one("h1")) or texto(a)

            cuerpo = detalle.select_one(
                ".entry-content, .tbr-detail-text, main, #main"
            ) or detalle
            descripcion = texto(cuerpo)
            if re.search(
                r"funcion\s+(?:se encuentra\s+)?suspendida|evento cancelado|show cancelado",
                normalizar(descripcion),
            ):
                continue

            if fuente == "Distrito Siete":
                m = re.search(
                    r"(\d{1,2})\.([A-Z]{3})\.(20\d{2})\s+(\d{1,2}:\d{2})hs",
                    descripcion,
                )
                abreviaturas = (
                    "ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
                    "JUL", "AGO", "SEP", "OCT", "NOV", "DIC",
                )
                fechas = []
                if m and m[2] in abreviaturas:
                    dia = date(int(m[3]), abreviaturas.index(m[2]) + 1, int(m[1]))
                    if hoy <= dia <= hoy + timedelta(days=HORIZONTE_DIAS):
                        fechas = [(dia.isoformat(), m[4])]
                precio = re.search(
                    r"Precios desde\s+ARS\s*(\$\s*[\d.,]+)", descripcion
                )
                descripcion_precio = (precio[1] if precio else "") + " " + titulo
            else:
                if fuente == "Teatro Broadway":
                    fechas_texto = " ".join(
                        texto(x) for x in detalle.select(".tbr-detail-text")
                    )
                    descripcion = texto(detalle.select_one("main")) or texto(detalle)
                else:
                    fechas_texto = descripcion
                anio_confirmado = fuente == "Metropolitano" and bool(re.search(
                    rf'(?:datePublished|dateModified)[^\n]{{0,40}}{hoy.year}-',
                    str(detalle),
                ))
                fechas = fechas_publicadas(fechas_texto, hoy, anio_confirmado)
                descripcion_precio = descripcion

            for fecha, hora in fechas:
                e = actividad_ampliada(
                    fecha, hora, titulo, enlace, fuente, direccion,
                    descripcion_precio, desde=fuente == "Distrito Siete",
                )
                if fuente == "Distrito Siete":
                    e["descripcion"] = resumen(titulo)
                eventos.append(e)
        except (requests.RequestException, ValueError):
            fallidos.add(enlace)
    return eventos, fallidos



def calendario_comedia(html, fuente, url, direccion, hoy):
    """Descubre obras Kalendo y verifica fechas en cada ficha oficial."""
    host = urlsplit(url).hostname
    enlaces, paginas = set(), set()
    pagina, listado = url, html
    while pagina not in paginas:
        paginas.add(pagina)
        for a in listado.select("article.kalendo_event .entry-title a[href], .kalendo-compact__title[href]"):
            enlace = urljoin(pagina, a["href"])
            if urlsplit(enlace).hostname == host and urlsplit(enlace).path.startswith("/espectaculo/"):
                enlaces.add(enlace)
        siguiente = listado.select_one(".pagination .alignleft a[href], a.next.page-numbers[href]")
        if not siguiente:
            break
        pagina = urljoin(pagina, siguiente["href"])
        if pagina in paginas:
            break
        if urlsplit(pagina).hostname != host or len(paginas) >= 10:
            raise ValueError("Programación de La Comedia incompleta: paginación no verificable")
        listado = descargar(pagina)
    if not enlaces:
        raise ValueError("No se encontraron fichas Kalendo en la programación de La Comedia")

    eventos, fallidos = {}, set()
    for enlace in sorted(enlaces):
        try:
            detalle = descargar(enlace)
            cuerpo = detalle.select_one("article.kalendo_event .entry-content")
            if not cuerpo:
                raise ValueError("La ficha de La Comedia no contiene descripción verificable")
            descripcion = texto(cuerpo)
            fichas = []
            for tag in detalle.select('script[type="application/ld+json"]'):
                try:
                    fichas.extend(eventos_schema(json.loads(tag.get_text())))
                except ValueError:
                    continue
            propias = [f for f in fichas if (f.get("url") or "").rstrip("/") == enlace.rstrip("/")]
            if not propias:
                raise ValueError("La ficha de La Comedia no contiene fechas Event verificables")
            for ficha in propias:
                estado = ficha.get("eventStatus", "").rsplit("/", 1)[-1]
                if estado in ("EventCancelled", "EventPostponed", "EventRescheduled") or re.search(
                    r"\b(?:suspendid[ao]|cancelad[ao]|reprogramad[ao])\b", normalizar(descripcion)
                ):
                    continue
                valor = ficha.get("startDate", "")
                if not isinstance(valor, str) or not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", valor):
                    raise ValueError("Fecha u hora incompleta en la ficha de La Comedia")
                cuando = datetime.fromisoformat(valor)
                if cuando.tzinfo:
                    cuando = cuando.astimezone(ZONA)
                if not hoy <= cuando.date() <= hoy + timedelta(days=HORIZONTE_DIAS):
                    continue
                titulo = texto(detalle.select_one("article.kalendo_event h1")) or ficha.get("name", "")
                if not titulo:
                    raise ValueError("Ficha de La Comedia sin título")
                evento = actividad_ampliada(
                    cuando.date().isoformat(), cuando.strftime("%H:%M"), titulo,
                    enlace, fuente, direccion, descripcion,
                )
                eventos[clave(evento)] = evento
        except (requests.RequestException, ValueError, TypeError) as error:
            # Si una ficha falla a mitad de lectura, no publicar un resultado parcial.
            eventos = {k: e for k, e in eventos.items() if e["evento_url"] != enlace}
            fallidos.add(enlace)
            print(f"Aviso: {fuente}: {enlace}: {type(error).__name__}: {error}; se conserva la ficha anterior", flush=True)
    return list(eventos.values()), fallidos


def calendario(html, fuente, url, direccion, hoy):
    if fuente == "Teatro Municipal La Comedia":
        return calendario_comedia(html, fuente, url, direccion, hoy)
    if fuente in ("Teatro Astengo", "ATIR", "Biblioteca Vigil"):
        return calendario_mec(html, fuente, url, direccion, hoy)
    if fuente in (
        "Teatro Broadway", "Distrito Siete", "Metropolitano",
        "Biblioteca Argentina Dr. Juan Álvarez",
    ):
        return calendario_paginas(html, fuente, url, direccion, hoy)
    return _calendario_anterior(html, fuente, url, direccion, hoy)


if __name__ == "__main__":
    actualizar()



