"""Extractor dinámico para eventos oficiales de Tickets Bravos.
Control conservador: robots verificado en vivo, sin bypass, sin JS ni APIs privadas.
Ante prohibición, error o ambigüedad, no consultar páginas y no borrar eventos.
"""
import re
import os
from datetime import date
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup

HOME='https://www.ticketsbravos.com/'
AGENTE='AgendaRosario/3.1 (+https://github.com/paredesivan/Agenda-rosario)'
MESES={'ENE':1,'FEB':2,'MAR':3,'ABR':4,'MAY':5,'JUN':6,'JUL':7,'AGO':8,'SEP':9,'OCT':10,'NOV':11,'DIC':12}
FECHA=re.compile(r'(?<!\d)(\d{1,2})\.([A-Z]{3})\.(20\d\d)\s+(\d{1,2}):(\d\d)hs',re.I)


def _permitido(session, url, cache):
    host=urlsplit(url).netloc
    if host not in cache:
        robots=f'https://{host}/robots.txt'
        try:
            res=session.get(robots,timeout=12,allow_redirects=False)
            if res.status_code!=200 or not res.text.lstrip().lower().startswith(('user-agent:', '#','sitemap:')):
                cache[host]=None
            elif '<html' in res.text[:500].lower(): cache[host]=None
            else:
                rp=RobotFileParser();rp.parse(res.text.splitlines());cache[host]=rp
        except requests.RequestException: cache[host]=None
    rp=cache[host]
    return rp is not None and rp.can_fetch(AGENTE,url)


def _ficha(html,url,hoy):
    doc=BeautifulSoup(html,'html.parser')
    # La fecha y el lugar se extraen de la ficha oficial, no del texto narrativo.
    titulo=doc.select_one('h2')
    if not titulo: return None
    titulo=titulo.get_text(' ',strip=True)
    if not titulo or len(titulo)>180: return None
    cabecera=doc.get_text(' ',strip=True)
    m=FECHA.search(cabecera)
    if not m: return None
    dia,mes,anio,hora,minuto=m.groups()
    mes=MESES.get(mes.upper())
    if not mes: return None
    try: fecha=date(int(anio),mes,int(dia))
    except ValueError: return None
    if not hoy <= fecha: return None
    # La plataforma también publica eventos en otras localidades: validación obligatoria.
    lm=re.search(r'\bLugar\b\s+(.{3,180}?)\s*,?\s*Rosario\s*,\s*Santa Fe',cabecera,re.I)
    if not lm: return None
    lugar_dir=lm.group(1).strip()
    # Requiere una dirección con número para evitar inventar geolocalización.
    d=re.search(r'(.+?)\s+((?:Av\.?\s+)?[\wÁÉÍÓÚÜÑáéíóúüñ. ]+\s+\d{1,5})$',lugar_dir)
    if not d: return None
    lugar=d.group(1).strip();direccion=d.group(2).strip()
    if lugar=='Casa' and direccion.startswith('Brava '):
        lugar='Casa Brava';direccion=direccion[len('Brava '):]
    if not lugar or len(lugar)>100: return None
    return {'fecha':fecha.isoformat(),'hora':f'{int(hora):02d}:{minuto}',
            'nombre':titulo,'lugar':lugar,'direccion':direccion+', Rosario, Santa Fe',
            'descripcion':'Espectáculo publicado por la ticketera oficial.',
            'evento_url':url,'precio':None,'precio_etiqueta':'Consultar precio en Tickets Bravos',
            'origen':'Tickets Bravos','fuente_verificada':True}


def revisar_ticketsbravos(hoy,estado):
    if os.environ.get('TICKETS_BRAVOS_TERMS_APPROVED') != '1':
        estado['Tickets Bravos']='pendiente: falta confirmar autorización y términos para extracción automatizada'
        return []
    s=requests.Session();s.headers.update({'User-Agent':AGENTE})
    robots={};salida=[];vistos=set()
    if not _permitido(s,HOME,robots):
        estado['Tickets Bravos']='no activada: robots.txt no verificable o acceso no autorizado'
        return salida
    try:
        resp=s.get(HOME,timeout=15,allow_redirects=False);resp.raise_for_status()
        soup=BeautifulSoup(resp.text,'html.parser')
        enlaces=[]
        for a in soup.select('a[href]'):
            u=urljoin(HOME,a['href']).split('#')[0]
            if urlsplit(u).netloc==urlsplit(HOME).netloc and re.fullmatch(r'/eventos/[a-zA-Z0-9_-]+',urlsplit(u).path) and u not in vistos:
                vistos.add(u);enlaces.append(u)
        for u in enlaces[:30]:
            if not _permitido(s,u,robots): continue
            try:
                r=s.get(u,timeout=12,allow_redirects=False);r.raise_for_status()
                e=_ficha(r.text,u,hoy)
                if e:salida.append(e)
            except requests.RequestException: continue
        estado['Tickets Bravos']=f'revisada: {len(enlaces)} fichas descubiertas; {len(salida)} eventos validos'
    except requests.RequestException as exc:
        estado['Tickets Bravos']=f'no accesible: {type(exc).__name__}'
    return salida
