"""Pruebas del circuito entero: sólo cambia el HTML, nunca el código ni los eventos."""
import hashlib
import html
import json
import subprocess
import tempfile
import unittest
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from bs4 import BeautifulSoup
import requests
import actualizar_eventos as a
import actualizacion_segura as segura
from descubrimiento_html import descubrir, seleccionar
from calendarios_recuperados import adaptar, funciones_vigil

FUENTE = 'Biblioteca Argentina Dr. Juan Álvarez'
INDICE = 'https://biblioargentina.gob.ar/web/agenda/'
sopa = lambda s: BeautifulSoup(s, 'html.parser')


class OrigenCambiante:
    def __init__(self, hoy):
        self.hoy, self.publicaciones, self.fallos, self.pedidas = hoy, {}, set(), []

    def agregar(self, hora='18:00', precio=17000):
        identificador = uuid.uuid4().hex
        url = 'https://biblioargentina.gob.ar/web/' + identificador + '/'
        self.publicaciones[url] = dict(titulo='Encuentro ' + identificador, hora=hora, precio=precio)
        return url

    def leer(self, url):
        self.pedidas.append(url)
        if url in self.fallos:
            raise requests.Timeout('Fallo de conexión simulado')
        if url == INDICE:
            return sopa(''.join('<article><h2 class="entry-title"><a href="'+u+'">'+html.escape(e['titulo'])+'</a></h2></article>'
                                for u,e in self.publicaciones.items()))
        e = self.publicaciones[url]
        dia = self.hoy + timedelta(days=12)
        fecha = f'{dia.day} de {a.MESES[dia.month-1]} de {dia.year}'
        return sopa('<span class="published">'+str(self.hoy.year)+'</span><article><div class="entry-content">'
                    '<p>El '+fecha+' a las '+e['hora']+' h se realizará el encuentro.</p>'
                    '<p>Entrada general $'+str(e['precio'])+'.</p></div></article>')


class CircuitoAutomatico(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.hoy = date(2032, 3, 2)
        self.origen = OrigenCambiante(self.hoy)
        self.reloj = 10000
        (self.root/'eventos.json').write_text(json.dumps({'eventos':[]}))

    def ejecutar(self):
        def proceso(args, cwd, **kwargs):
            with patch.object(a,'ARCHIVO',Path(cwd)/'eventos.json'), \
                 patch.object(a,'EXTRAS',((FUENTE,INDICE,'Presidente Roca 731'),)), \
                 patch.object(a,'obtener_enlaces',return_value=(set(),[])), \
                 patch.object(a,'descargar',side_effect=self.origen.leer), \
                 patch.object(a,'datetime') as reloj, \
                 patch('calendarios_recuperados.time.time',return_value=self.reloj):
                reloj.now.return_value = datetime(2032,3,2,10,tzinfo=a.ZONA)
                a.actualizar()
        def como_subproceso(args, **kwargs):
            try:
                return proceso(args, **kwargs)
            except RuntimeError as exc:
                raise subprocess.CalledProcessError(1,args) from exc
        return segura.ejecutar_etapa(self.root,'actualizar_eventos.py',30,ejecutar=como_subproceso,hoy=self.hoy)

    def eventos(self):
        return json.loads((self.root/'eventos.json').read_text())['eventos']

    def test_nuevo_evento_cambio_hora_precio_y_fallo_sin_tocar_codigo(self):
        modulos = [Path(a.__file__),Path(segura.__file__),Path(a.__file__).with_name('calendarios_recuperados.py')]
        firmas = [hashlib.sha256(p.read_bytes()).hexdigest() for p in modulos]
        primero = self.origen.agregar()
        self.ejecutar()
        self.assertEqual(len(self.eventos()),1)
        self.assertEqual(self.eventos()[0]['evento_url'],primero)
        segundo = self.origen.agregar(hora='21:00',precio=23000)
        self.origen.publicaciones[primero].update(hora='19:30',precio=41000)
        self.reloj += 1  # El nuevo enlace debe invalidar una caché todavía vigente.
        self.ejecutar()
        eventos = {e['evento_url']:e for e in self.eventos()}
        self.assertEqual(set(eventos),{primero,segundo})
        self.assertEqual((eventos[primero]['hora'],eventos[primero]['precio']),('19:30',41000))
        self.assertEqual(len(self.eventos()),2)
        self.origen.publicaciones[primero]['precio'] = 47000
        self.reloj += 7201  # Cambio en la ficha, sin cambiar el índice.
        self.ejecutar()
        self.assertEqual(next(e for e in self.eventos() if e['evento_url']==primero)['precio'],47000)
        self.origen.fallos.add(segundo)
        self.reloj += 7201
        self.ejecutar()
        self.assertEqual(len(self.eventos()),2)
        self.assertTrue(next(e for e in self.eventos() if e['evento_url']==segundo)['revision_pendiente'])
        anterior = (self.root/'eventos.json').read_bytes()
        self.origen.fallos.add(INDICE)
        self.assertEqual(self.ejecutar()['estado'],'fallida')
        self.assertEqual((self.root/'eventos.json').read_bytes(),anterior)
        self.assertEqual(firmas,[hashlib.sha256(p.read_bytes()).hexdigest() for p in modulos])

    def test_repeticion_no_duplica(self):
        self.origen.agregar()
        self.ejecutar()
        self.ejecutar()
        self.assertEqual(len(self.eventos()),1)


class Descubrimiento(unittest.TestCase):
    def test_vigil_respeta_anio_publicado_y_formato_inline(self):
        token=uuid.uuid4().hex
        h=sopa('<h1>Teatro Vigil</h1><div class="entry-content"><p>Temporada 2032</p>'
               '<p>📆 <strong>Jueves 8 de enero 21h</strong><br>'+token+'</p><p>Generales $17000</p></div>')
        es=funciones_vigil(h,'https://bibliotecavigil.org.ar/inicio/'+token+'/',date(2031,12,20),
                           a.actividad_ampliada,a.fechas_publicadas)
        self.assertEqual([(e['nombre'],e['fecha']) for e in es],[(token,'2032-01-08')])

    def test_ccpe_y_vigil_descubren_nombres_y_enlaces_desconocidos(self):
        for fuente, indice in [('Centro Cultural Parque de España','https://ccpe.org.ar/web/agenda/'),
                               ('Biblioteca Vigil','https://bibliotecavigil.org.ar/inicio/eventos/')]:
            with self.subTest(fuente=fuente), tempfile.TemporaryDirectory() as d:
                cache=Path(d)/'cache.json';datos={}
                def pagina():
                    selector='mec-event-title' if fuente.startswith('Centro') else 'entry-title'
                    return sopa(''.join('<article><h2 class="'+selector+'"><a href="'+u+'">'+t+'</a></h2></article>'
                                        for u,t in datos.items()))
                def leer(u):
                    if u.endswith('/inicio/'):
                        return pagina()
                    titulo=datos[u]
                    if fuente.startswith('Centro'):
                        return sopa('<div class="mec-single-event-date"><span class="mec-start-date-label">5/11/26</span></div>'
                            '<div class="mec-single-event-time"><abbr class="mec-events-abbr">20:00</abbr></div>'
                            '<div class="mec-single-event-description">Concierto. Entrada general $17000.</div>')
                    return sopa('<h1>'+titulo+'</h1><div class="entry-content"><p>Temporada 2026 en el Teatro Vigil</p>'
                        '<p>Jueves 5 de noviembre 20h<br><strong>'+titulo+'</strong></p><p>Generales $17000</p></div>')
                for cantidad in (1,2):
                    token=uuid.uuid4().hex
                    host='https://ccpe.org.ar' if fuente.startswith('Centro') else 'https://bibliotecavigil.org.ar'
                    datos[host+'/publicacion/'+token+'/']='Actividad '+token
                    eventos,fallos=adaptar(pagina(),fuente,indice,'Rosario',date(2026,10,31),leer,
                                          a.actividad_ampliada,a.fechas_publicadas,cache)
                    self.assertFalse(fallos)
                    self.assertEqual({e['nombre'] for e in eventos},set(datos.values()))
                    self.assertEqual(len(eventos),cantidad)

    def test_paginacion_local_y_limite_sin_seguir_enlaces_externos(self):
        base='https://example.org/agenda/'
        h=sopa('<article><h2><a href="/primero/">Primero</a></h2></article>'
               '<a class="next" href="/agenda/page/2/">Más</a><a rel="next" href="https://otro.example/">Otro</a>')
        llamadas=[]
        def leer(u):
            llamadas.append(u)
            return sopa('<article><h2><a href="/segundo/">Segundo</a></h2></article><a class="next" href="/agenda/page/3/">Más</a>')
        enlaces=descubrir(h,base,'h2 a[href]',leer)
        self.assertEqual(set(enlaces),{'https://example.org/primero/','https://example.org/segundo/'})
        self.assertEqual(llamadas,['https://example.org/agenda/page/2/'])

    def test_rotacion_alcanza_todas_las_fichas_y_prioriza_nuevas(self):
        estado={};links={f'https://example.org/{i}':str(i) for i in range(29)}
        vistas=set()
        for tiempo in range(1,5):
            vistas.update(u for u,t in seleccionar(links,8,estado,tiempo))
        self.assertEqual(vistas,set(links))
        nueva='https://example.org/nueva'
        self.assertEqual(seleccionar({**links,nueva:'Nueva'},1,estado,5)[0][0],nueva)

    def test_produccion_no_contiene_semilla_de_evento_municipal(self):
        source=Path(a.__file__).with_name('fuentes_nuevas.py').read_text()
        self.assertNotIn('SEMILLAS_ESPACIOS',source)
        self.assertNotIn('festival-gualicho-cofradia-encuentro-y-fiesta-ricotera',source)
