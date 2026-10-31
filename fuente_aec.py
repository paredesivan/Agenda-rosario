"""Programación factual del Teatro AEC, sin eventos fijos ni reproducción de notas."""
import re
from datetime import date,datetime
from bs4 import BeautifulSoup
from fuentes_refi_folklore import norm,categorias_factuales

MESES={m:i for i,m in enumerate('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split(),1)}


def ficha_aec(html,url,fuente):
    s=BeautifulSoup(html,'html.parser');a=s.select_one('article.category-teatro')
    if not a: return []
    cuerpo=a.select_one('.bs-desc')
    if not cuerpo: raise ValueError('AEC: cambió el cuerpo de la ficha')
    parrafos=[p.get_text(' ',strip=True) for p in cuerpo.select('p') if p.get_text(strip=True)]
    t=' '.join(parrafos);n=norm(t)
    encabezado=s.select_one('h1')
    sede=norm((encabezado.get_text(' ',strip=True) if encabezado else '')+' '+t)
    if re.search(r'\b(curso|taller|capacitacion|seminario|workshop|clases)\b',norm(parrafos[0] if parrafos else '')):return []
    if re.search(r'(?:exclusiv[oa]|solo|unicamente)\s+(?:para\s+)?(?:afiliados|socios)',n):return []
    if not re.search(r'nuestro teatro|nuestro escenario|corrientes\s+450',sede):
        raise ValueError('AEC: falta sede teatral verificada')
    if re.search(r'\b(zavalla|general lagos|los cocos|san lorenzo)\b',n) and 'nuestro teatro' not in n:
        raise ValueError('AEC: sede fuera de Rosario')
    if re.search(r'\b(suspendid[oa]|cancelad[oa]|postergad[oa])\b',norm(parrafos[0])):return [{'cancelado':True}]
    # Usar únicamente el párrafo del anuncio: no horarios de boletería ni
    # aniversarios o referencias históricas del resto de la nota.
    anuncio=next((p for p in parrafos if re.search(r'\b\d{1,2}(?:\s*(?:y|,)\s*\d{1,2})*\s+de\s+(?:'+ '|'.join(MESES)+')',norm(p))),None)
    if not anuncio:
        pub=s.select_one('meta[property="article:published_time"]')
        publicado=date.fromisoformat(pub['content'][:10]) if pub else None
        dias='lunes martes miercoles jueves viernes sabado domingo'.split()
        for parrafo in parrafos:
            relativo=re.search(r'\b('+ '|'.join(dias) +r')\s+(\d{1,2})\s+(?:de este mes|,)',norm(parrafo))
            if not relativo or not publicado: continue
            candidato=date(publicado.year,publicado.month,int(relativo[2]))
            if not 0 <= (candidato-publicado).days <= 31 or dias[candidato.weekday()]!=relativo[1]:
                raise ValueError('AEC: fecha relativa ambigua')
            anuncio=norm(parrafo).replace(relativo[0],f'{relativo[1]} {relativo[2]} de {list(MESES)[publicado.month-1]} de {publicado.year} ',1)
            break
    if not anuncio: raise ValueError('AEC: fecha de función no interpretable')
    an=norm(anuncio)
    patron=r'\b(\d{1,2}(?:\s*(?:y|,)\s*\d{1,2})*)\s+de\s+('+ '|'.join(MESES)+r')(?:\s+(?:de\s+)?(20\d{2}))?'
    matches=list(re.finditer(patron,an))
    pub=s.select_one('meta[property="article:published_time"]')
    publicado=date.fromisoformat(pub['content'][:10]) if pub else None
    fechas=[];inferido=False
    for m in matches:
        if m[3]: anio=int(m[3])
        elif publicado:anio=publicado.year;inferido=True
        else:raise ValueError('AEC: falta año del anuncio')
        for dia in re.findall(r'\d+',m[1]):
            f=date(anio,MESES[m[2]],int(dia))
            # Sin año explícito, sólo anuncios contemporáneos del mismo año.
            if not m[3] and not 0 <= (f-publicado).days <= 90:
                raise ValueError('AEC: año de función ambiguo')
            fechas.append(f)
    hm=re.search(r'(?:desde las|a las)\s+(\d{1,2})(?:[.:](\d{2}))?',an)
    hora=f'{int(hm[1]):02d}:{hm[2] or "00"}' if hm else 'Horario a confirmar'
    if hm:datetime.strptime(hora,'%H:%M')
    # Preferir nombre entre comillas del espectáculo, nunca el titular periodístico.
    titulo=re.search(r'(?:obra|pieza|espectáculo|unipersonal|show)\s*[,.:]?\s*[«“"]([^»”"]+)',t,re.I)
    if titulo:nombre=titulo[1].strip()
    else:
        base=re.search(r'show coreográfico con base de\s+([^,.]+)',t,re.I)
        if base:nombre='Show coreográfico de '+base[1].strip()
        else:raise ValueError('AEC: nombre del espectáculo no verificable en el texto')
    beneficio=bool(re.search(r'sin cargo para afiliados|sin cargo.*socios',n))
    gratis=bool(re.search(r'(?:entrada|entradas) (?:libre y gratuita|gratuitas?)(?: para todo publico| para publico general| para toda la comunidad)',n))
    etiqueta='Gratis' if gratis else ('Sin cargo para afiliados AEC y socios de Amecro; consultar precio para público general' if beneficio else 'Consultar precio y condiciones en AEC')
    descripcion=''
    if 'cupos limitados' in n:descripcion+='Cupos limitados. '
    if 'boleteria' in n and ('retir' in n):descripcion+='Retiro de entradas en boletería; consultar disponibilidad y condiciones de acceso en AEC.'
    categorias=['danza'] if 'coreograf' in n else categorias_factuales(nombre,'','TheaterEvent')
    return [{'cancelado':False,'nombre':nombre,'fecha':f.isoformat(),'hora':hora,
             'lugar':'Teatro AEC - Asociación Empleados de Comercio','direccion':'Corrientes 450, Rosario, Santa Fe',
             'precio':0 if gratis else None,'precio_etiqueta':etiqueta,'descripcion':descripcion.strip(),
             'categorias':categorias,'anio_contextual_publicacion':inferido} for f in sorted(set(fechas))]


def misma_sala_aec(a,b):
    if not any(e.get('origen')=='Empleados de Comercio Rosario — Teatro AEC' for e in (a,b)):return False
    def sede(e):
        n=norm(e.get('lugar',''));return ('aec' in n or 'empleados de comercio' in n) and 'teatro' in n
    return sede(a) and sede(b) and a.get('fecha')==b.get('fecha') and a.get('hora')==b.get('hora') and a.get('hora')!='Horario a confirmar'
