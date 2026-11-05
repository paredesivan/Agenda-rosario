import unittest
from datetime import date
from bs4 import BeautifulSoup
import requests
from fuente_colectividades import BASE, ORIGEN, recolectar, tarjetas_publicadas


def html(texto):
    return BeautifulSoup(texto, 'html.parser')


class Colectividades(unittest.TestCase):
    def fixture(self, anio=2026):
        vinculos = '\n'.join(
            f'<a href="/inicio/colectividades-{anio}-dia-{i}">{i + 5:02d}.11 '
            f'42° Encuentro y Fiesta Nacional de Colectividades Colectividades {anio} - Día {i}</a>'
            for i in range(1, 11))
        return html(f'<main><h1>Colectividades {anio}</h1>'
                    '<p>Del 6 al 15 de noviembre en el Parque Nacional a la Bandera.</p>'
                    '<p>Todos los días desde las 19 h.</p>' + vinculos + '</main>')

    def test_diez_jornadas_extraidas_del_indice(self):
        t, _ = tarjetas_publicadas(self.fixture(), date(2026, 11, 5))
        self.assertEqual(list(sorted(t)), [f'2026-11-{i:02d}' for i in range(6, 16)])
        self.assertEqual(t['2026-11-06'][1], '19:00')

    def test_ano_dinamico_sin_fechas_fijas(self):
        t, _ = tarjetas_publicadas(self.fixture(2027), date(2027, 11, 5))
        self.assertEqual(len(t), 10)
        self.assertTrue(all(k.startswith('2027-') for k in t))

    def test_precio_y_deduplicacion_url(self):
        portada = self.fixture()
        def descargar(url):
            if url == BASE:
                return portada
            ordinal = int(url.rsplit('-', 1)[-1])
            return html(f'<main><h1>Colectividades 2026 - Día {ordinal}</h1>'
                        f'<p>{ordinal + 5} DE Noviembre</p><p>DE 19 a 23:59 horas</p>'
                        '<p>Parque a La Bandera</p><p>Gratis</p></main>')
        eventos = recolectar(date(2026, 11, 5), descargar)
        self.assertEqual(len(eventos), 10)
        self.assertEqual(len({e['fecha'] for e in eventos}), 10)
        self.assertTrue(all(e['precio'] == 0 for e in eventos))
        self.assertTrue(all(e['origen'] == ORIGEN for e in eventos))
        self.assertTrue(all(e['evento_url'].startswith('https://www.rosario.gob.ar/inicio/') for e in eventos))

    def test_fallo_detalle_conserva_fecha_sin_inventar_gratuidad(self):
        def descargar(url):
            if url != BASE:
                raise requests.HTTPError('403')
            return self.fixture()
        eventos = recolectar(date(2026, 11, 5), descargar)
        self.assertEqual(len(eventos), 10)
        self.assertTrue(all(e['precio'] is None for e in eventos))

    def test_no_duplica_la_ficha_de_acr(self):
        try:
            from actualizar_eventos import sin_repetidos
        except ImportError:
            self.skipTest('Integración comprobable al instalar en Agenda Rosario')
        oficial = recolectar(date(2026, 11, 15),
                             lambda url: self.fixture() if url == BASE else
                             html('<main><h1>Colectividades 2026</h1><p>15 de noviembre</p>Gratis</main>'))[0]
        acr = {**oficial, 'nombre': 'Encuentro y Fiesta Nacional de Colectividades 2026',
               'evento_url': 'https://www.agendaculturalrosario.com.ar/eventos/fiesta',
               'origen': 'Agenda Cultural Rosario'}
        resultado = sin_repetidos([acr, oficial])
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]['origen'], ORIGEN)

    def test_no_generar_sin_hora_o_lugar(self):
        pagina = html('<main><p>Del 6 al 15 de noviembre.</p><a href="/inicio/colectividades-2026-dia-1">06.11</a></main>')
        with self.assertRaises(ValueError):
            tarjetas_publicadas(pagina, date(2026, 11, 5))

    def test_no_aceptar_anio_vencido(self):
        pagina = self.fixture(2026)
        t, _ = tarjetas_publicadas(pagina, date(2027, 1, 1))
        self.assertEqual(t, {})

    def test_ignorar_enlaces_externos_y_fechas_fuera_de_rango(self):
        pagina = self.fixture()
        main = pagina.select_one('main')
        main.append(html('<a href="https://noticia.example/inicio/colectividades-2026-dia-11">16.11</a>'))
        main.append(html('<a href="/inicio/colectividades-2026-dia-12">22.11</a>'))
        t, _ = tarjetas_publicadas(pagina, date(2026, 11, 5))
        self.assertEqual(len(t), 10)


if __name__ == '__main__':
    unittest.main()
