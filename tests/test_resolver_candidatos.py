import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup
from actualizacion_segura import ETAPAS, proteger
from resolver_candidatos import (resolver, detalle, hechos_propios, fecha_hora,
                                url_publica, SIN_HORA)

HOY = date(2026, 10, 19)
IPS = 'Instituto Politécnico — Novedades'
BASE = 'https://www.ips.edu.ar'
OFICIAL = 'https://teatro.example'


def schema(url, nombre='Actividad nueva', fecha='2026-11-20T22:00:00-03:00', **kw):
    e = {'@type': 'Event', 'url': url, 'name': nombre, 'startDate': fecha,
         'location': {'name': 'Sala Abierta', 'address': {
             'addressLocality': 'Rosario', 'addressRegion': 'Santa Fe',
             'streetAddress': 'Calle 123'}}}
    e.update(kw)
    return '<h1>' + nombre + '</h1><script type="application/ld+json">' + json.dumps(e) + '</script>'


class Acceso:
    def __init__(self, paginas, cache=None):
        self.paginas = paginas
        self.cache = cache if cache is not None else {}
        self.calls = []
    def reloj(self):
        return 1800000000
    def leer_datos(self, url, parser, horas=2):
        self.calls.append(url)
        pagina = self.paginas[url]
        if isinstance(pagina, Exception):
            raise pagina
        return parser(pagina, url)


class ResolverTests(unittest.TestCase):
    def preparar(self, root, entradas, existentes=()):
        (root / 'eventos.json').write_text(json.dumps({'eventos': list(existentes)}))
        (root / 'fuentes_adicionales.json').write_text(json.dumps({
            'dominios_oficiales_existentes': ['teatro.example'],
            'fuentes': [{'nombre': 'Rosario Times', 'url': 'https://rosariotimes.com/', 'consulta_automatica': True},
                        {'nombre': 'SalePlan', 'url': 'https://saleplan.ar/rosario/eventos', 'consulta_automatica': True},
                        {'nombre': 'EntradaFan', 'url': 'https://www.entradafan.com.ar/', 'consulta_automatica': True}]}))
        (root / 'fuentes_ampliadas.json').write_text(json.dumps({'fuentes': [
            {'nombre': IPS, 'listado': BASE + '/category/noticias/', 'habilitada': True, 'tipo': 'descubrimiento'},
            {'nombre': 'Planaxia', 'listado': 'https://planaxia.com/categoria/agenda/', 'habilitada': True, 'tipo': 'descubrimiento'}]}))
        (root / 'candidatos_fuentes_adicionales.json').write_text(json.dumps({'candidatos': entradas}))

    def test_fecha_sin_hora_y_conversion_utc(self):
        self.assertEqual(fecha_hora('2026-11-21'), ('2026-11-21', SIN_HORA))
        self.assertEqual(fecha_hora('2026-11-21T01:00:00Z'), ('2026-11-20', '22:00'))
        with self.assertRaises(ValueError):
            fecha_hora('21 de noviembre')

    def test_schema_descarta_recomendaciones_sin_copiar_textos(self):
        url = OFICIAL + '/evento/a'
        h = schema(url) + schema(OFICIAL + '/evento/b', 'Otra recomendación')
        d = detalle(h, url)
        self.assertEqual(len(d['hechos']), 1)
        self.assertFalse({'precio', 'description', 'image', 'offers'} & d['hechos'][0].keys())

    def test_no_acepta_schema_sin_url_ni_titulo_propio(self):
        h = schema(OFICIAL + '/a').replace('<h1>Actividad nueva</h1>', '<h1>Noticia general</h1>').replace('"url": "https://teatro.example/a", ', '')
        self.assertFalse(detalle(h, OFICIAL + '/a')['hechos'])

    def test_cancela_cursos_otra_ciudad(self):
        url = OFICIAL + '/a'
        for kwargs in ({'eventStatus': 'https://schema.org/EventCancelled'},
                       {'location': {'name': 'Sala', 'address': {'addressLocality': 'Rosario del Tala'}}}):
            self.assertFalse(detalle(schema(url, **kwargs), url)['hechos'])
        self.assertFalse(detalle(schema(url, nombre='Curso de dibujo'), url)['hechos'])

    def test_no_consulta_dominios_arbitrarios_y_rutas_privadas(self):
        for u in ('http://teatro.example/a', 'https://teatro.example.evil/a',
                  'https://user:pass@teatro.example/a', 'https://teatro.example:444/a',
                  'https://teatro.example/api/a', 'https://127.0.0.1/a', 'https://saleplan.ar/go/a'):
            self.assertFalse(url_publica(u, {'teatro.example', 'saleplan.ar'}))

    def test_publica_oficial_enlazado_sin_evento_fijo(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            noticia, oficial = 'https://rosariotimes.com/nueva/', OFICIAL + '/funcion/1'
            self.preparar(p, [{'fuente': 'Rosario Times', 'referencia': noticia}])
            a = Acceso({noticia: '<article><a href="' + oficial + '">Entradas</a></article>', oficial: schema(oficial)})
            r = resolver(p, a, HOY)
            e = json.loads((p / 'eventos.json').read_text())['eventos'][0]
            self.assertEqual(e['evento_url'], oficial)
            self.assertEqual(r[0]['estado'], 'publicado')
            self.assertIsNone(e['precio'])

    def test_manana_publicacion_nueva_sin_modificar_codigo(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            n1, n2 = 'https://rosariotimes.com/a/', 'https://rosariotimes.com/b/'
            u1, u2 = OFICIAL + '/a/', OFICIAL + '/b/'
            self.preparar(p, [{'fuente': 'Rosario Times', 'referencia': n1}])
            a = Acceso({n1: f'<article><a href="{u1}">Entrada</a></article>', u1: schema(u1)})
            resolver(p, a, HOY)
            (p / 'candidatos_fuentes_adicionales.json').write_text(json.dumps({'candidatos': [{'fuente': 'Rosario Times', 'referencia': n2}]}))
            b = Acceso({**a.paginas, n2: f'<article><a href="{u2}">Entrada</a></article>', u2: schema(u2, 'Otra función inesperada')}, copy.deepcopy(a.cache))
            resolver(p, b, date(2026, 10, 20))
            eventos = json.loads((p / 'eventos.json').read_text())['eventos']
            self.assertEqual({e['nombre'] for e in eventos}, {'Actividad nueva', 'Otra función inesperada'})
            self.assertIn(n2, b.calls)

    def test_rotacion_y_cuota_persistente_no_repite_las_primeras(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            urls = ['https://rosariotimes.com/' + str(i) for i in range(6)]
            self.preparar(p, [{'fuente': 'Rosario Times', 'referencia': u} for u in urls])
            a = Acceso({u: '<article>Sin evento fechado</article>' for u in urls})
            resolver(p, a, HOY)
            self.assertEqual(len(a.calls), 4)
            b = Acceso(a.paginas, copy.deepcopy(a.cache))
            resolver(p, b, HOY)
            self.assertEqual(b.calls, [])
            c = Acceso(a.paginas, copy.deepcopy(b.cache))
            resolver(p, c, date(2026, 10, 20))
            self.assertTrue(set(urls[4:]) <= set(c.calls))

    def test_no_borra_evento_por_fallo_403(self):
        url = OFICIAL + '/e'
        viejo = {'fecha': '2026-11-20', 'hora': '22:00', 'nombre': 'Actividad nueva',
                 'lugar': 'Sala Abierta', 'evento_url': url, 'origen': 'Fuente oficial — Rosario Times'}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            noticia = 'https://rosariotimes.com/n/'
            self.preparar(p, [{'fuente': 'Rosario Times', 'referencia': noticia}], [viejo])
            r = resolver(p, Acceso({noticia: ValueError('HTTP 403; dominio pausado')}), HOY)
            self.assertEqual(r[0]['estado'], 'reintentar')
            self.assertEqual(json.loads((p / 'eventos.json').read_text())['eventos'], [viejo])

    def test_nota_con_url_oficial_ya_publicada_no_consulta_otra_vez(self):
        url, noticia = OFICIAL + '/e', 'https://rosariotimes.com/n/'
        viejo = {'fecha': '2026-11-20', 'hora': '22:00', 'nombre': 'Actividad nueva', 'lugar': 'Sala Abierta',
                 'evento_url': url, 'origen': 'Teatro oficial', 'precio': 1234}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            self.preparar(p, [{'fuente': 'Rosario Times', 'referencia': noticia}], [viejo])
            a = Acceso({noticia: f'<article><a href="{url}">Entradas</a></article>'})
            r = resolver(p, a, HOY)
            self.assertEqual(r[0]['estado'], 'corroborado')
            self.assertEqual(a.calls, [noticia])
            self.assertEqual(json.loads((p / 'eventos.json').read_text())['eventos'][0]['precio'], 1234)

    def test_ips_nuevo_publico_sin_hora_y_privado_no(self):
        url = BASE + '/actividad-nueva.html'
        for acceso in ('Actividad abierta a toda la comunidad', 'Actividad interna solo para estudiantes'):
            with self.subTest(acceso=acceso), tempfile.TemporaryDirectory() as d:
                p = Path(d)
                self.preparar(p, [{'fuente': IPS, 'url': url}])
                h = '<article><h1>Encuentro de poesía</h1><div class="entry-content"><p>' + acceso + '</p><p>¿Cuándo? 20 de noviembre de 2026</p><p>¿Dónde? Auditorio (Calle 123, Rosario)</p></div></article>'
                resolver(p, Acceso({url: h}), HOY)
                eventos = json.loads((p / 'eventos.json').read_text())['eventos']
                if 'abierta' in acceso:
                    self.assertEqual(eventos[0]['hora'], SIN_HORA)
                else:
                    self.assertFalse(eventos)

    def test_planaxia_extrae_funciones_no_el_titular_y_no_infiere_ano(self):
        h = '<meta property="article:published_time" content="2026-11-01T10:00:00-03:00"><article><h1>Agenda del finde</h1><h3>VIERNES 20 de NOVIEMBRE</h3><ul><li>Concierto singular en Sala Abierta a las 22 hs.</li><li>Curso de fotografía en Sala a las 18 hs.</li></ul></article>'
        d = detalle(h, 'https://planaxia.com/agenda/nueva/', 'Planaxia')
        self.assertEqual(d['hechos'][0]['nombre'], 'concierto singular')
        self.assertEqual(len(d['hechos']), 1)
        sin_ano = h[h.index('<article>'):]
        self.assertFalse(detalle(sin_ano, 'https://planaxia.com/agenda/nueva/', 'Planaxia')['hechos'])

    def test_saleplan_calendario_no_es_confirmacion_oficial(self):
        from urllib.parse import urlencode
        q = urlencode({'text': 'Concierto', 'dates': '20261121T010000Z/20261121T020000Z',
                       'location': 'Sala Abierta · Calle 123, Rosario, Santa Fe, Argentina'})
        h = '<main><h1>Concierto</h1><a href="https://calendar.google.com/calendar/render?' + q + '">Calendar</a></main>'
        d = detalle(h, 'https://saleplan.ar/santa-fe/rosario/planes/abc/nuevo', 'SalePlan')
        self.assertEqual(d['hechos'][0]['hora'], '22:00')
        self.assertEqual(d['hechos'][0]['fecha'], '2026-11-20')

    def test_etapa_y_cancelacion_no_restaurada_por_protector(self):
        self.assertIn('resolver_candidatos.py', [e[0] for e in ETAPAS])
        e = {'nombre': 'Evento', 'lugar': 'Sala', 'fecha': '2026-11-20', 'hora': '22:00', 'origen': IPS, 'evento_url': BASE + '/a'}
        despues = {'eventos': [], 'revision_resolucion': {'id': 'nuevo', 'fichas_revisadas': [[IPS, e['evento_url']]]}}
        self.assertTrue(proteger({'eventos': [e]}, despues, HOY)[0]['eventos'][0]['revision_pendiente'])


    def test_cancelacion_oficial_se_reconsulta_y_retira_sin_restaurar(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            noticia, oficial = 'https://rosariotimes.com/n/', OFICIAL + '/funcion/c'
            self.preparar(p, [{'fuente': 'Rosario Times', 'referencia': noticia}])
            paginas = {noticia: f'<article><a href="{oficial}">Entradas</a></article>', oficial: schema(oficial)}
            a = Acceso(paginas)
            resolver(p, a, HOY)
            antes = json.loads((p / 'eventos.json').read_text())
            b = Acceso({**paginas, oficial: schema(oficial, eventStatus='https://schema.org/EventCancelled')}, copy.deepcopy(a.cache))
            resolver(p, b, date(2026, 10, 20))
            despues = json.loads((p / 'eventos.json').read_text())
            self.assertIn(oficial, b.calls)
            self.assertFalse(despues['eventos'])
            self.assertTrue(proteger(antes, despues, HOY)[0]['eventos'][0]['revision_pendiente'])

    def test_actualizar_articulo_misma_url_descubre_otra_ficha(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            noticia, u1, u2 = 'https://rosariotimes.com/n/', OFICIAL + '/a', OFICIAL + '/b'
            self.preparar(p, [{'fuente': 'Rosario Times', 'referencia': noticia}])
            paginas = {noticia: f'<article><a href="{u1}">Entradas</a></article>', u1: schema(u1)}
            a = Acceso(paginas)
            resolver(p, a, HOY)
            b = Acceso({**paginas, noticia: f'<article><a href="{u1}">A</a><a href="{u2}">B</a></article>',
                        u2: schema(u2, 'Otra fecha añadida')}, copy.deepcopy(a.cache))
            resolver(p, b, date(2026, 10, 20))
            self.assertEqual(len(json.loads((p / 'eventos.json').read_text())['eventos']), 2)

    def test_parametros_de_evento_diferentes_no_son_misma_ficha(self):
        from resolver_candidatos import canonica
        self.assertNotEqual(canonica(OFICIAL + '/evento?id=1'), canonica(OFICIAL + '/evento?id=2'))
        self.assertEqual(canonica(OFICIAL + '/evento?id=1&utm_source=x'), canonica(OFICIAL + '/evento?id=1'))

    def test_ips_fecha_del_acto_no_fecha_de_historia_o_noticia(self):
        url = BASE + '/nueva.html'
        h = '<article><h1>Celebración abierta</h1><div class="entry-content"><h2>Festejo institucional</h2><p>Desde 1906, cuando Rosario cambiaba.</p><p>Te invitamos junto a toda la comunidad.</p><p>¿Cuándo? 20 de noviembre de 2026</p><p>¿Dónde? Salón (Calle 123, Rosario)</p><p>Cena 20 hs. Brindis 23 hs.</p></div></article>'
        d = detalle(h, url, IPS)
        self.assertEqual({h['hora'] for h in d['hechos']}, {'20:00', '23:00'})
        self.assertEqual({h['fecha'] for h in d['hechos']}, {'2026-11-20'})
        self.assertTrue(d['acceso_publico'])

    def test_fuente_deshabilitada_no_reactiva_cola_vieja(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            noticia = 'https://rosariotimes.com/n/'
            self.preparar(p, [{'fuente': 'Rosario Times', 'referencia': noticia}])
            cfg = json.loads((p / 'fuentes_adicionales.json').read_text())
            cfg['fuentes'][0]['consulta_automatica'] = False
            (p / 'fuentes_adicionales.json').write_text(json.dumps(cfg))
            a = Acceso({})
            resolver(p, a, HOY)
            self.assertFalse(a.calls)


if __name__ == '__main__':
    unittest.main()
