import json
import tempfile
import unittest
from pathlib import Path
from datetime import date
from bs4 import BeautifulSoup
from unittest.mock import Mock, patch
import actualizar_eventos as a
from calendarios_recuperados import adaptar, funciones_vigil, argentina, ccpe
from fuente_aec import ficha_aec
from descubrimiento_html import huella_html

HOY = date(2026, 10, 31)
sopa = lambda t: BeautifulSoup(t, 'html.parser')


class CalendariosRecuperados(unittest.TestCase):
    def test_vigil_separa_funciones_y_tarifas_de_socios(self):
        h = sopa('''<meta property="article:published_time" content="2026-10-23T10:00:00Z">
        <article><h1>Teatro Vigil</h1><div class="entry-content"><p>Temporada 2026</p>
        <p>Viernes 6 de noviembre 20:30h<br><strong>Una historia de museo</strong></p>
        <p>Socixs gratis.<br>Anticipadas <a href="/venta">acá</a> $15.000. En puerta $20.000</p>
        <p>Sábado 7 noviembre 20:30 h<br><strong>Una comedia diferente.</strong></p>
        <p>Socixs gratis.<br>Generales $35.000</p></div></article>''')
        e = funciones_vigil(h, 'https://bibliotecavigil.org.ar/inicio/nueva/', HOY,
                            a.actividad_ampliada, a.fechas_publicadas)
        self.assertEqual([x['fecha'] for x in e], ['2026-11-06','2026-11-07'])
        self.assertEqual(e[1]['precio'], 35000)
        self.assertIsNone(e[0]['precio'])
        self.assertNotIn(0, [x['precio'] for x in e])
        h.select_one('.entry-content p').string = 'Temporada 2020'
        self.assertEqual(funciones_vigil(h, '', HOY, a.actividad_ampliada, a.fechas_publicadas), [])

    def test_argentina_lee_anuncio_y_no_biografia(self):
        index = sopa('<article><h2 class="entry-title"><a href="/web/nueva/">Presentación de un libro</a></h2></article>')
        detalle = sopa('''<span class="published">19 septiembre, 2026</span><article><div class="entry-content">
        <p>El miércoles 11 de noviembre a las 18 h se presentará el libro.</p>
        <blockquote><p>El sábado 7 de noviembre a las 23 h, decía la novela.</p></blockquote>
        <p>El autor nació el 19 de marzo de 1986.</p><p>Entrada libre y gratuita.</p></div></article>''')
        e, fallas = argentina(index, 'Biblioteca Argentina Dr. Juan Álvarez',
            'https://biblioargentina.gob.ar/web/agenda/', 'Presidente Roca 731', HOY,
            lambda u: detalle, a.actividad_ampliada, a.fechas_publicadas)
        self.assertFalse(fallas)
        self.assertEqual([(x['fecha'],x['hora']) for x in e], [('2026-11-11','18:00')])
        self.assertEqual(e[0]['precio'], 0)

    def test_ccpe_usa_fecha_visible_con_anio_y_no_horario_boleteria(self):
        index = sopa('<h4 class="mec-event-title"><a href="/web/actividades/nueva/">Concierto nuevo</a></h4>')
        detalle = sopa('''<div class="mec-single-event-date"><span class="mec-start-date-label">Jue. 5/11/26</span></div>
        <div class="mec-single-event-time"><abbr class="mec-events-abbr">20:00</abbr></div>
        <div class="mec-single-event-description">Concierto. Entradas $20.000. Boletería de 9 a 15.</div>''')
        e, fallas = ccpe(index, 'Centro Cultural Parque de España', 'https://ccpe.org.ar/web/agenda/',
                        'Sarmiento y el río', HOY, lambda u: detalle, a.actividad_ampliada, a.fechas_publicadas)
        self.assertFalse(fallas)
        self.assertEqual([(x['fecha'],x['hora']) for x in e], [('2026-11-05','20:00')])
        detalle.select_one('.mec-start-date-label').string = 'Jue. 5/11'
        self.assertTrue(ccpe(index, 'CCPE', 'https://ccpe.org.ar/web/agenda/', '', HOY,
                             lambda u: detalle, a.actividad_ampliada, a.fechas_publicadas)[1])

    def test_atir_calendario_vacio_explicito_no_es_error_de_parser(self):
        with tempfile.TemporaryDirectory() as d:
            h = sopa('<div class="mec-calendar"><h4 class="mec-event-title">No Events</h4></div>')
            self.assertEqual(adaptar(h, 'ATIR', 'https://www.teatrosatir.ar/cartelera/', '', HOY,
                Mock(), a.actividad_ampliada, a.fechas_publicadas, Path(d)/'cache.json'), ([],set()))
            self.assertIsNone(adaptar(sopa('<h1>Error</h1>'), 'ATIR', '', '', HOY,
                Mock(), a.actividad_ampliada, a.fechas_publicadas, Path(d)/'cache.json'))

    def test_cache_no_repite_consultas_y_filtra_eventos_vencidos(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'cache.json'
            evento={'fecha':'2026-11-05','hora':'20:00'}
            p.write_text(json.dumps({'Centro Cultural Parque de España':{'consultado':1000,'huella':huella_html(sopa(''), 'https://ccpe.org.ar'),'eventos':[evento]}}))
            descarga=Mock()
            with patch('calendarios_recuperados.time.time', return_value=1100):
                e,_=adaptar(sopa(''), 'Centro Cultural Parque de España','https://ccpe.org.ar','',date(2026,11,6),
                    descarga,a.actividad_ampliada,a.fechas_publicadas,p)
            self.assertEqual(e,[])
            descarga.assert_not_called()

    def test_aec_titulo_pieza_con_coma(self):
        h='''<meta property="article:published_time" content="2026-10-20T10:00:00Z">
        <article class="category-teatro"><h1>Unipersonal</h1><div class="bs-desc">
        <p>La pieza, “Marta”, subirá al escenario de nuestro Teatro el sábado 7 de noviembre, a las 21.</p>
        <p>Sin cargo para afiliados. Consultar precio general.</p></div></article>'''
        e=ficha_aec(h,'',{})
        self.assertEqual((e[0]['nombre'],e[0]['fecha'],e[0]['hora']),('Marta','2026-11-07','21:00'))
        self.assertIsNone(e[0]['precio'])

    def test_aec_fecha_relativa_validada_con_publicacion_y_dia_semana(self):
        h='''<meta property="article:published_time" content="2026-10-22T10:00:00Z">
        <article class="category-teatro"><h1>Vuelve a nuestro Teatro</h1><div class="bs-desc">
        <p>El viernes 30 de este mes, a las 21.30, presentamos el espectáculo “Tango vivo”.</p>
        </div></article>'''
        e=ficha_aec(h,'',{})
        self.assertEqual((e[0]['fecha'],e[0]['hora']),('2026-10-30','21:30'))
        with self.assertRaises(ValueError):ficha_aec(h.replace('viernes 30','jueves 30'),'',{})

    def test_feria_finalizada_no_se_reporta_como_inaccesible(self):
        import fuentes_nuevas as f
        estado={}
        with patch.object(f,'descargar',return_value=sopa('<main>Del 8 al 18 de octubre de 2026</main>')):
            self.assertEqual(f.leer_feria_libro(HOY,estado),[])
        self.assertIn('edición finalizada',estado['Feria Internacional del Libro de Rosario'])
