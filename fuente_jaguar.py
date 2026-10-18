"""Descubrimiento conservador de eventos de Jaguar Haüs.

El perfil oficial se consulta con robots.txt, un único GET, timeout, y frecuencia
máxima de 24 horas. Solo se recopilan hechos mínimos y enlaces oficiales.
No se accede automáticamente a dominios de las ticketeras.
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo

URL = 'https://linktr.ee/jaguarhaus'
ROBOTS = 'https://linktr.ee/robots.txt'
USER_AGENT = 'AgendaRosario/3.1 (+https://github.com/paredesivan/Agenda-rosario)'
ZONA = ZoneInfo('America/Argentina/Buenos_Aires')
DOMINIOS = {'damemiticket.com', 'www.damemiticket.com', 'www.passline.com',
            'passline.com', 'eventos.tqr.la'}
FECHA = re.compile(r'(?<!\d)(\d{1,2})[./-](\d{1,2})(?!\d)')
CACHE = Path(__file__).with_name('cache_jaguar.json')
CANDIDATOS = Path(__file__).with_name('candidatos_jaguar.json')


def extraer(html, hoy):
    """Listar anuncios futuros enlazados a vendedores; no suponer el horario."""
    soup = BeautifulSoup(html, 'html.parser')
    encontrados, vistos = [], set()
    for a in soup.select('a[href]'):
        enlace = a.get('href', '')
        host = urlsplit(enlace).hostname
        if host not in DOMINIOS:
            continue
        titulo = a.get_text(' ', strip=True)
        coincidencias = list(FECHA.finditer(titulo))
        if len(coincidencias) != 1:
            continue
        m = coincidencias[0]
        try:
            dia, mes = int(m[1]), int(m[2])
            fecha = hoy.replace(month=mes, day=dia)
            if fecha < hoy:
                fecha = fecha.replace(year=hoy.year + 1)
        except ValueError:
            continue
        if fecha > hoy + timedelta(days=180):
            continue
        nombre = (titulo[:m.start()] + titulo[m.end():]).strip(' -–:|')
        if len(nombre) < 3 or len(nombre) > 140:
            continue
        clave = (fecha.isoformat(), nombre.casefold())
        if clave in vistos:
            continue
        vistos.add(clave)
        encontrados.append({'fecha':fecha.isoformat(), 'nombre':nombre,
                            'lugar':'Jaguar Haüs',
                            'direccion':'Rodríguez 198 bis, Rosario, Santa Fe',
                            'evento_url':enlace,'origen':'Jaguar Haüs (perfil oficial)',
                            'estado':'pendiente_hora', 'hora':None})
    return sorted(encontrados, key=lambda c:(c['fecha'],c['nombre']))


def ejecutar(hoy=None, session=requests, cache=CACHE, salida=CANDIDATOS):
    hoy = hoy or datetime.now(ZONA).date()
    ahora = datetime.now(ZONA)
    try:
        previo = json.loads(cache.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        previo = {}
    if previo.get('consultado'):
        try:
            ultima = datetime.fromisoformat(previo['consultado'])
            if ahora - ultima < timedelta(hours=24):
                return {'estado':'diferida_por_frecuencia', 'candidatos':len(previo.get('candidatos', []))}
        except ValueError:
            pass
    robot = session.get(ROBOTS, headers={'User-Agent':USER_AGENT}, timeout=12)
    robot.raise_for_status()
    if not robot.text.lstrip().startswith(('User-agent:', '#')):
        return {'estado':'robots_no_interpretable','candidatos':0}
    parser = RobotFileParser()
    parser.parse(robot.text.splitlines())
    if not parser.can_fetch(USER_AGENT, URL):
        return {'estado':'bloqueada_robots', 'candidatos':0}
    respuesta = session.get(URL, headers={'User-Agent':USER_AGENT}, timeout=15,
                           allow_redirects=False)
    if respuesta.status_code != 200:
        return {'estado':f'http_{respuesta.status_code}', 'candidatos':0}
    anuncios = extraer(respuesta.text, hoy)
    salida.write_text(json.dumps({'fuente':URL,'candidatos':anuncios},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    cache.write_text(json.dumps({'consultado':ahora.isoformat(),'candidatos':anuncios},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {'estado':'descubrimiento_sin_horarios_verificados', 'candidatos':len(anuncios)}


if __name__ == '__main__':
    print(json.dumps(ejecutar(),ensure_ascii=False))
