import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from actualizacion_segura import proteger, ETAPAS
from fuentes_ampliadas import listado, ficha, fusionar, revisar, actualizar, ConsultaAmpliada
from fuentes_refi_folklore import Consulta

HOY = date(2026, 10, 17)
URL = 'https://cultura.example/evento/nueva/'
FUENTE = {'nombre': 'Santa Fe Cultura', 'habilitada': True, 'tipo': 'oficial',
          'adaptador': 'santafe', 'listado': 'https://cultura.example/agenda/',
          'patron_ficha': r'^/evento/[^/]+/?$'}
SCHEMA = {'@type': 'Event', 'name': 'Actividad nueva', 'url': URL,
          'startDate': '2026-11-10T00:30:00Z'}
DONDE = '<h4 class="block__title">¿Dónde?</h4><ul class="text-list"><li>Sala Prueba</li><li>Calle 12, Rosario</li><li>Rosario, Argentina</li></ul>'

def html(schema=None, donde=DONDE):
    return '<script type="application/ld+json">'+json.dumps(schema or SCHEMA)+'</script><div>'+donde+'</div>'

def evento(**kw):
    return dict(fecha='2026-11-09', hora='21:30', nombre='Actividad nueva',
                lugar='Sala Prueba', origen='Santa Fe Cultura', evento_url=URL, **kw)

class Fake:
    def __init__(self, paginas):
        self.paginas, self.cache, self.llamadas = paginas, {}, []
    def leer_datos(self, url, parser, horas=2):
        self.llamadas.append(url)
        dato = self.paginas[url]
        if isinstance(dato, Exception):
            raise dato
        return parser(dato, url)

class Ampliadas(unittest.TestCase):
    def test_listado_dinamico_sin_externos(self):
        salida = listado('<a href="/evento/nuevo/">X</a><a href="https://externo.test/evento/x/">Y</a><a href="/evento/nuevo/">X</a>', FUENTE['listado'], FUENTE)
        self.assertEqual(salida, [{'url': 'https://cultura.example/evento/nuevo/', 'referencia': ''}])

    def test_vacio_es_error_no_borrado(self):
        with self.assertRaises(ValueError):
            listado('<div>Cargando</div>', URL, FUENTE)

    def test_fecha_zona_y_ubicacion_visible(self):
        e = ficha(html(), URL, FUENTE)[0]
        self.assertEqual((e['fecha'], e['hora'], e['lugar']), ('2026-11-09', '21:30', 'Sala Prueba'))
        self.assertNotIn('description', e)
        self.assertNotIn('image', e)

    def test_fin_explicito_y_fin_invalido(self):
        e = ficha(html({**SCHEMA, 'endDate': '2026-11-10T02:00:00Z'}), URL, FUENTE)[0]
        self.assertEqual((e['fecha_fin'], e['hora_fin']), ('2026-11-09', '23:00'))
        with self.assertRaises(ValueError):
            ficha(html({**SCHEMA, 'endDate': '2026-11-09T02:00:00Z'}), URL, FUENTE)

    def test_otra_ciudad_rechazada(self):
        with self.assertRaises(ValueError):
            ficha(html(donde=DONDE.replace('Rosario', 'Santa Fe')), URL, FUENTE)

    def test_sin_sede_rechazado(self):
        with self.assertRaises(ValueError):
            ficha(html(donde=''), URL, FUENTE)

    def test_sin_hora_o_ano_invalido(self):
        for v in ['2026-11-09', '10 de noviembre', '2026-02-30T21:00']:
            with self.subTest(v=v), self.assertRaises(ValueError):
                ficha(html({**SCHEMA, 'startDate': v}), URL, FUENTE)

    def test_ignora_recomendaciones(self):
        self.assertEqual(len(ficha(html([SCHEMA, {**SCHEMA, 'url': 'https://externo.test/otro/'}]), URL, FUENTE)), 1)

    def test_cancelada_sin_importar(self):
        self.assertEqual(ficha(html({**SCHEMA, 'eventStatus': 'https://schema.org/EventCancelled'}), URL, FUENTE), [{'cancelado': True}])

    def test_error_conserva_anterior(self):
        self.assertEqual(fusionar([evento()], [], set(), HOY), [evento()])

    def test_cambio_horario_reemplaza_url(self):
        nuevo = {**evento(), 'hora': '22:00'}
        self.assertEqual(fusionar([evento()], [nuevo], {('Santa Fe Cultura', URL)}, HOY), [nuevo])

    def test_oficial_reemplaza_acr_sin_duplicado(self):
        acr = {**evento(), 'origen': 'Agenda Cultural Rosario'}
        self.assertEqual(fusionar([acr], [evento()], set(), HOY), [evento()])

    def test_primaria_existente_conserva_precio(self):
        primaria = {**evento(), 'origen': 'Sala oficial', 'precio': 15000}
        self.assertEqual(fusionar([primaria], [evento()], set(), HOY), [primaria])

    def test_medios_solo_candidatos(self):
        f = {**FUENTE, 'tipo': 'descubrimiento'}
        acceso = Fake({f['listado']: '<a href="/evento/nueva/">N</a>'})
        nuevos, candidatos, estados, revisadas = revisar({'fuentes': [f]}, acceso, HOY)
        self.assertFalse(nuevos)
        self.assertEqual(len(candidatos), 1)
        self.assertEqual(len(acceso.llamadas), 1)

    def test_deshabilitada_no_hace_red(self):
        acceso = Fake({})
        revisar({'fuentes': [{**FUENTE, 'habilitada': False, 'motivo': '403'}]}, acceso, HOY)
        self.assertFalse(acceso.llamadas)

    def test_limite_errores_por_ficha_y_fuente(self):
        links = ''.join(f'<a href="/evento/n{i}/">X</a>' for i in range(6))
        acceso = Fake({FUENTE['listado']: links, **{f'https://cultura.example/evento/n{i}/': ValueError('falló') for i in range(6)}})
        _, _, estados, urls = revisar({'fuentes': [FUENTE], 'max_fichas_por_fuente': 2}, acceso, HOY)
        self.assertEqual(len(acceso.llamadas), 3)
        self.assertFalse(urls)
        self.assertEqual(estados[FUENTE['nombre']]['diferidas_por_limite'], 4)

    def test_cancelacion_no_restaurada_por_proteccion_global(self):
        anterior = {'eventos': [evento()]}
        posterior = {'eventos': [], 'revision_ampliadas': {'id': 'nuevo', 'fichas_revisadas': [['Santa Fe Cultura', URL]]}}
        salida, _ = proteger(anterior, posterior, HOY)
        self.assertTrue(salida['eventos'][0]['revision_pendiente'])
        repetido, _ = proteger({**anterior, 'revision_ampliadas': posterior['revision_ampliadas']}, copy.deepcopy(posterior), HOY)
        self.assertEqual(len(repetido['eventos']), 1)

    def test_crawl_delay_con_comentario(self):
        class Response:
            status_code=200
            text='User-agent: *\nDisallow:\nCrawl-delay: 60 # segundos\n'
            headers={}
            def raise_for_status(self): pass
        class Session:
            def get(self, *args, **kw): return Response()
        acceso = ConsultaAmpliada({},session=Session(),dormir=lambda t:None)
        self.assertEqual(acceso.robots(URL),60)

    def test_fuera_ventana_no_consulta(self):
        acceso=Fake({})
        _, _, estados, _=revisar({'fuentes':[{**FUENTE,'ventana_utc':[0,0]}]},acceso,HOY)
        self.assertFalse(acceso.llamadas)
        self.assertEqual(estados[FUENTE['nombre']]['estado'],'fuera de horario')

    def test_etapa_integrada(self):
        self.assertIn('fuentes_ampliadas.py', [e[0] for e in ETAPAS])

    def test_actualizacion_completa_datos_y_diagnostico(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p/'fuentes_ampliadas.json').write_text(json.dumps({'fuentes': [FUENTE]}))
            (p/'eventos.json').write_text(json.dumps({'eventos': []}))
            acceso = Fake({FUENTE['listado']: '<a href="/evento/nueva/">N</a>', URL: html()})
            actualizar(p, acceso, HOY)
            datos = json.loads((p/'eventos.json').read_text())
            self.assertEqual(len(datos['eventos']), 1)
            self.assertTrue((p/'revision_fuentes_ampliadas.json').exists())
            self.assertTrue(datos['eventos'][0]['fuente_verificada'])

    def test_robots_html_se_detiene(self):
        class Response:
            status_code=200
            text='<html>Portada</html>'
            headers={}
            def raise_for_status(self): pass
        class Session:
            def get(self, *args, **kw): return Response()
        acceso=Consulta({},session=Session(),dormir=lambda t:None)
        with self.assertRaisesRegex(ValueError,'robots no interpretable'):
            acceso.leer_datos(URL, lambda h,u: [])

if __name__ == '__main__':
    unittest.main()
