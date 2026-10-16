"""Pruebas offline: funciones nuevas, fechas, fuentes caídas y duplicados."""
import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import requests
import fuentes_refi_folklore as m

HOY = date(2031, 4, 12)
URL = 'https://refiticket.ar/OTRA-PROPUESTA/'


def fila(**cambios):
    valor = {'nombre': 'Concierto de prueba', 'slug': 'OTRA-PROPUESTA',
             'unica_fecha': True, 'desde_fecha': '12/04/2031, 20:00',
             'moneda': 'ARS', 'entradas_online_desde': '2500.00',
             'lugar': 'Sala Nueva, Rosario, Santa Fe'}
    valor.update(cambios)
    return valor


def html_ficha(opciones='<option value="1">12-04-2031, 20:00</option>', estado='EventScheduled'):
    schema = {'@type': 'Event', 'name': 'Concierto de prueba',
              'startDate': '2031-04-12T20:00:00-03:00', 'eventStatus': estado,
              'offers': {'url': URL, 'price': '0.00'},
              'location': {'name': 'Sala Nueva', 'address': {'streetAddress': 'Calle 123'}}}
    selector = '<select id="idFechasEventos">' + opciones + '</select>' if opciones is not None else ''
    return '<script type="application/ld+json">' + json.dumps(schema) + '</script>' + selector


def ficha(**cambios):
    valor = m.datos_ficha_refi(html_ficha(), URL)
    valor.update(cambios)
    return valor


class RefiTests(unittest.TestCase):
    def test_evento_desconocido_y_fecha_futura_sin_catalogo_fijo(self):
        e = m.convertir_refi(fila(nombre='Otra obra jamás cargada'), ficha(), URL, HOY)[0]
        self.assertEqual(e['nombre'], 'Otra obra jamás cargada')
        self.assertEqual(e['fecha'], '2031-04-12')
        self.assertEqual(e['direccion'], 'Calle 123, Rosario, Santa Fe')
        self.assertEqual(e['precio'], 2500)
        self.assertEqual(e['descripcion'], '')

    def test_toma_todas_las_funciones_reales_sin_expandir(self):
        opciones = '<option value="1">12-04-2031, 20:00</option><option value="2">14-04-2031, 22:30</option><option disabled value="3">15-04-2031, 21:00</option>'
        f = m.datos_ficha_refi(html_ficha(opciones), URL)
        eventos = m.convertir_refi(fila(unica_fecha=False), f, URL, HOY)
        self.assertEqual([(e['fecha'], e['hora']) for e in eventos], [('2031-04-12', '20:00'), ('2031-04-14', '22:30')])
        self.assertIsNone(eventos[0]['precio'])

    def test_no_publica_fecha_resumida_como_unica_de_varias(self):
        with self.assertRaises(ValueError):
            m.convertir_refi(fila(unica_fecha=False), m.datos_ficha_refi(html_ficha(None), URL), URL, HOY)

    def test_selector_vacio_no_revivir_fecha_de_json_ld(self):
        f = m.datos_ficha_refi(html_ficha(''), URL)
        self.assertEqual(m.convertir_refi(fila(), f, URL, HOY), [])

    def test_cero_no_es_gratis(self):
        for precio in ('0.00', None, 'NaN', '-1', 'infinito'):
            e = m.convertir_refi(fila(entradas_online_desde=precio), ficha(), URL, HOY)[0]
            self.assertIsNone(e['precio'])
            self.assertNotIn('gratis', e['precio_etiqueta'].lower())

    def test_no_mezcla_monedas(self):
        self.assertIsNone(m.convertir_refi(fila(moneda='USD'), ficha(), URL, HOY)[0]['precio'])

    def test_categoria_de_concierto_sin_copiar_descripcion(self):
        self.assertEqual(m.categorias_factuales('Artista desconocido', '<p>Presenta su nuevo disco</p>'), ['musica'])
        evento = m.convertir_refi(fila(), ficha(categorias=['musica']), URL, HOY)[0]
        self.assertEqual(evento['categorias'], ['musica'])
        self.assertEqual(evento['descripcion'], '')

    def test_excluye_otras_ciudades_y_provincias(self):
        for lugar in ('Sala, Granadero Baigorria, Santa Fe', 'Sala, Rosario del Tala, Entre Ríos', 'Sala, Rosario, Córdoba'):
            self.assertEqual(m.convertir_refi(fila(lugar=lugar), ficha(), URL, HOY), [])
        self.assertEqual(m.convertir_refi(fila(), ficha(ciudad='Funes'), URL, HOY), [])

    def test_cancela_y_reprograma(self):
        for estado in ('EventCancelled', 'EventPostponed', 'EventRescheduled'):
            f = m.datos_ficha_refi(html_ficha(estado=estado), URL)
            self.assertEqual(m.convertir_refi(fila(), f, URL, HOY), [])

    def test_filtra_pasado_y_horizonte(self):
        for fecha in ('2031-04-11T20:00', '2031-06-30T20:00'):
            self.assertEqual(m.convertir_refi(fila(), ficha(fechas=[fecha]), URL, HOY), [])

    def test_catalogo_valida_formato_y_truncamiento(self):
        for obj in ({}, {'eventos': [fila()], 'cantidad_total_fechas_activas': 8}):
            with self.assertRaises(ValueError):
                m.catalogo_refi(json.dumps(obj), URL)

    def test_solo_guarda_campos_factuales(self):
        f = fila(imagen_home='afiche.jpg', descripcion_evento='Texto protegido')
        resultado = m.catalogo_refi(json.dumps({'eventos': [f]}), URL)
        self.assertNotIn('imagen_home', resultado[0])
        self.assertNotIn('descripcion_evento', resultado[0])


class IntegracionTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((Path(m.__file__).parent / 'fuentes_refi_folklore.json').read_text())
        self.a = Mock()
        self.a.cache = {}

    def test_descubre_eventos_cargados_despues(self):
        self.a.leer_datos.side_effect = [[fila()], ficha()]
        eventos, _, exitosas, _ = m.revisar(self.config, HOY, self.a)
        self.assertEqual(len(eventos), 1)
        self.assertIn(m.ORIGEN_REFI, exitosas)
        nueva = fila(nombre='Estreno futuro', slug='UN-NUEVO-SLUG', desde_fecha='13/04/2031, 22:00')
        self.a.leer_datos.side_effect = [[fila(), nueva], ficha(), ficha(fechas=['2031-04-13T22:00'])]
        eventos, _, _, _ = m.revisar(self.config, HOY, self.a)
        self.assertEqual(len(eventos), 2)
        self.assertTrue(any(e['nombre'] == 'Estreno futuro' for e in eventos))

    def test_folklore_no_se_consulta_sin_permiso(self):
        self.a.leer_datos.return_value = []
        self.config['rosario_folklore']['habilitada'] = True
        _, estado, _, _ = m.revisar(self.config, HOY, self.a)
        self.assertIn('desactivada', estado[m.ORIGEN_FOLK])
        self.assertEqual(self.a.leer_datos.call_count, 1)

    def test_conserva_por_falla_y_retira_si_desaparecio_de_revision_valida(self):
        anterior = m.convertir_refi(fila(), ficha(), URL, HOY)[0]
        self.assertEqual(m.combinar([anterior], [], set(), set(), HOY), [anterior])
        self.assertEqual(m.combinar([anterior], [], {m.ORIGEN_REFI}, {URL}, HOY), [anterior])
        self.assertEqual(m.combinar([anterior], [], {m.ORIGEN_REFI}, set(), HOY), [])

    def test_no_duplica_fuente_primaria_existente(self):
        nuevo = m.convertir_refi(fila(), ficha(), URL, HOY)[0]
        anterior = {**nuevo, 'origen': 'Sala oficial', 'precio': 3000}
        salida = m.combinar([anterior], [nuevo], {m.ORIGEN_REFI}, set(), HOY)
        self.assertEqual(salida, [anterior])

    def test_no_colapsa_otra_sede_u_otro_horario(self):
        a = m.convertir_refi(fila(), ficha(), URL, HOY)[0]
        self.assertFalse(m.misma_funcion(a, {**a, 'hora': '22:00'}))
        self.assertFalse(m.misma_funcion(a, {**a, 'lugar': 'Otro teatro'}))

    def test_actualiza_archivos_sin_borrar_otras_fuentes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / m.CONFIG.name).write_text(json.dumps(self.config))
            previo = {'fecha': HOY.isoformat(), 'hora': '17:00', 'nombre': 'Otro evento', 'lugar': 'Otra sala', 'origen': 'Municipalidad'}
            (root / 'eventos.json').write_text(json.dumps({'estado': 'completo', 'eventos': [previo]}))
            (root / 'fuentes_revisadas.json').write_text(json.dumps({'fuentes': {'Fuente previa': 'ok'}}))
            self.a.leer_datos.side_effect = [[fila()], ficha()]
            m.actualizar(root, self.a, HOY)
            datos = json.loads((root / 'eventos.json').read_text())
            self.assertEqual(len(datos['eventos']), 2)
            self.assertIn(previo, datos['eventos'])
            registro = json.loads((root / 'fuentes_revisadas.json').read_text())
            self.assertEqual(registro['fuentes']['Fuente previa'], 'ok')

    def test_descarta_urls_externas(self):
        for valor in ('https://otro.test/evento', '//otro.test/evento', 'javascript:alert(1)'):
            with self.assertRaises(ValueError):
                m.enlace_local('https://refiticket.ar/', valor)

    def test_403_pausa_y_conserva(self):
        self.a.leer_datos.side_effect = requests.HTTPError('HTTP 403')
        _, estado, exitosas, _ = m.revisar(self.config, HOY, self.a)
        self.assertEqual(exitosas, set())
        self.assertIn('no accesible', estado[m.ORIGEN_REFI])


class TransporteTests(unittest.TestCase):
    def test_cache_y_304_no_repiten_descargas(self):
        cache, reloj = {}, [1000000]
        a = m.Consulta(cache, reloj=lambda: reloj[0], dormir=lambda _: None)
        a.robots = Mock(return_value=5)
        r = Mock(status_code=200, text='{"eventos": []}', headers={'ETag': 'v1'})
        a.pedir = Mock(return_value=r)
        self.assertEqual(a.leer_datos(URL, m.catalogo_refi), [])
        self.assertEqual(a.leer_datos(URL, m.catalogo_refi), [])
        self.assertEqual(a.pedir.call_count, 1)
        reloj[0] += 7201
        a.pedir.return_value = Mock(status_code=304)
        self.assertEqual(a.leer_datos(URL, m.catalogo_refi), [])
        self.assertEqual(a.pedir.call_args.args[2], {'If-None-Match': 'v1'})

    def test_pausa_aun_con_cache(self):
        a = m.Consulta({'pausas': {'refiticket.ar': 2000000}, 'paginas': {URL: {'consultado': 1000000, 'datos': []}}}, reloj=lambda: 1000000)
        with self.assertRaises(ValueError):
            a.leer_datos(URL, m.catalogo_refi)


class FolklorePreparadoTests(unittest.TestCase):
    def test_descubre_slugs_nuevos_y_paginacion(self):
        html = '<a href="/evento/nuevo-estreno/">Otro evento</a><a href="/ciudad/rosario/page/2/" rel="next">Siguientes</a><a href="https://ajeno.test/evento/x/">x</a>'
        datos = m.listado_folklore(html, 'https://rosariofolklore.com.ar/ciudad/rosario/')
        self.assertEqual(datos['fichas'], ['https://rosariofolklore.com.ar/evento/nuevo-estreno/'])
        self.assertEqual(len(datos['siguientes']), 1)

    def test_ics_utc_y_ciudad(self):
        contenido = 'BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART:20310413T013000Z\nSUMMARY:Festival nuevo\nLOCATION:Sala X\\, Calle 42\\, Rosario\\, Santa Fe\nEND:VEVENT\nEND:VCALENDAR'
        datos = m.datos_ics(contenido, URL)
        eventos = m.convertir_folk_ics(datos, URL, HOY, 30)
        self.assertEqual((eventos[0]['fecha'], eventos[0]['hora']), ('2031-04-12', '22:30'))
        self.assertFalse(eventos[0]['fuente_verificada'])
        self.assertEqual(eventos[0]['descripcion'], '')


if __name__ == '__main__':
    unittest.main()
