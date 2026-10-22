import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import fuentes_espacios_oficiales as f


def pagina(nombre='Concierto de prueba', fecha='2099-10-23T00:00:00Z', **cambios):
    url = 'https://www.elaserradero.com.ar/event/prueba'
    e = {'@type': 'MusicEvent', 'name': nombre, 'startDate': fecha,
         'offers': {'url': url, 'price': 8000},
         'location': {'name': 'El Aserradero', 'address': {'streetAddress': 'Montevideo 1518, Rosario, Santa Fe'}}}
    e.update(cambios)
    return '<script type="application/ld+json">'+json.dumps(e)+'</script>', url


class Espacios(unittest.TestCase):
    def test_directorio_admite_espacios_nuevos_no_enlaces_externos(self):
        h = '<h2><a href="/espacios/sala-nueva">Sala nueva</a></h2>'
        h += '<h2><a href="https://evil.invalid/espacios/sala">Externa</a></h2>'
        self.assertEqual(f.directorio(h), [{'nombre': 'Sala nueva', 'directorio': f.DIRECTORIO+'/sala-nueva'}])
        with self.assertRaises(ValueError): f.directorio('<h1>Sin datos</h1>')

    def test_utc_se_convierte_al_dia_local_y_no_publica_precio_incompleto(self):
        e = f.ficha_aserradero(*pagina())[0]
        self.assertEqual((e['fecha'], e['hora']), ('2099-10-22', '21:00'))
        self.assertIsNone(e['precio'])
        self.assertEqual(e['descripcion'], '')

    def test_fecha_sin_hora(self):
        e = f.ficha_aserradero(*pagina(fecha='2099-10-22'))[0]
        self.assertTrue(e['horario_pendiente'])
        self.assertEqual(e['hora'], 'Horario a confirmar')

    def test_otra_ciudad_formacion_cancelaciones_y_recomendaciones(self):
        casos = [pagina(nombre='Taller de danza'), pagina(eventStatus='https://schema.org/EventCancelled'),
                 pagina(location={'name': 'El Aserradero', 'address': {'streetAddress': 'Montevideo 1518, Buenos Aires'}}),
                 pagina(offers={'url': 'https://www.elaserradero.com.ar/event/otro'}),
                 pagina(fecha='a confirmar')]
        for args in casos:
            with self.subTest(args=args), self.assertRaises(ValueError): f.ficha_aserradero(*args)

    def test_listado_descubre_sin_slugs_fijos(self):
        base = 'https://www.elaserradero.com.ar/'
        h = '<title>El Aserradero</title><a href="/event/nueva-funcion">Nueva</a><a href="https://otro.com/event/falso">Falso</a>'
        self.assertEqual(f.listado_aserradero(h, base), [base+'event/nueva-funcion'])

    def test_prioridad_oficial_y_conservacion_de_funciones_ausentes(self):
        oficial = f.ficha_aserradero(*pagina())[0]
        acr = dict(oficial, origen='Agenda Cultural Rosario', evento_url='https://www.agendaculturalrosario.com.ar/eventos/prueba')
        otro = dict(acr, fecha='2099-10-23')
        salida = f.combinar([acr, otro], [oficial])
        self.assertEqual(len(salida), 2)
        self.assertIn(oficial, salida)
        self.assertIn(otro, salida)
        self.assertEqual(f.combinar(salida, []), salida)

    def test_html_escapa_titulos_y_no_enlaza_esquemas_inseguros(self):
        h = f.tabla([{'nombre': '<script>mal</script>', 'estado': 'Pendiente', 'sitio': 'javascript:alert(1)'}], '2099-01-01')
        self.assertNotIn('<script>', h)
        self.assertNotIn('javascript:', h)

    def test_fallo_de_red_preserva_agenda_e_inventario(self):
        config = json.loads((f.ROOT / 'espacios_oficiales.json').read_text())
        oficial = f.ficha_aserradero(*pagina())[0]
        class Fallo:
            cache = {}
            def leer_datos(self, *a, **k): raise ValueError('Error simulado')
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'espacios_oficiales.json').write_text(json.dumps(config))
            (root/'eventos.json').write_text(json.dumps({'eventos': [oficial]}))
            (root/'revision_espacios_oficiales.json').write_text(json.dumps({'espacios': [{'nombre': 'Descubierto antes', 'directorio': f.DIRECTORIO+'/anterior', 'estado': 'Pendiente'}]}))
            resultado = f.actualizar(root, Fallo(), date(2099, 10, 22))
            self.assertEqual(json.loads((root/'eventos.json').read_text())['eventos'], [oficial])
            self.assertEqual(len(resultado['espacios']), len(config['espacios'])+1)

    def test_etapa_conectada_una_sola_vez_y_antes_de_resolucion(self):
        from actualizacion_segura import ETAPAS
        nombres = [n for n, t in ETAPAS]
        self.assertEqual(nombres.count('fuentes_espacios_oficiales.py'), 1)
        self.assertLess(nombres.index('fuentes_espacios_oficiales.py'), nombres.index('resolver_candidatos.py'))

    def test_ficha_real_capturada_sin_imagenes_ni_sinopsis(self):
        h = (Path(__file__).parent/'fixtures/aserradero_ficha.html').read_text()
        url = 'https://www.elaserradero.com.ar/event/167983-sound-on-liga'
        e = f.ficha_aserradero(h, url)[0]
        self.assertEqual((e['fecha'], e['hora']), ('2026-10-22', '21:00'))
        self.assertEqual(e['lugar'], 'El Aserradero')

    def test_cambio_de_condiciones_detiene_catalogo(self):
        config = json.loads((f.ROOT/'espacios_oficiales.json').read_text())
        class Cambiaron:
            cache = {}
            urls = []
            def leer_datos(self, url, *a, **k):
                self.urls.append(url)
                return 'hash-distinto'
        acceso = Cambiaron()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'espacios_oficiales.json').write_text(json.dumps(config))
            (root/'eventos.json').write_text('{"eventos": []}')
            f.actualizar(root, acceso)
        self.assertNotIn(f.DIRECTORIO, acceso.urls)
        self.assertNotIn(config['aserradero']['listado'], acceso.urls)

    def test_pagina_y_revision_sobreviven_aislamiento(self):
        from actualizacion_segura import ejecutar_etapa
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'eventos.json').write_text('{"eventos": []}')
            def proceso(args, cwd, **kwargs):
                (cwd/'espacios.html').write_text('<h1>Espacios revisados</h1>')
                (cwd/'revision_espacios_oficiales.json').write_text('{"espacios": []}')
            r = ejecutar_etapa(root, 'fuentes_espacios_oficiales.py', 10, proceso)
            self.assertEqual(r['estado'], 'validada')
            self.assertTrue((root/'revision_espacios_oficiales.json').exists())
            self.assertIn('Espacios revisados', (root/'espacios.html').read_text())


if __name__ == '__main__':
    unittest.main()
