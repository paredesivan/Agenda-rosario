import unittest
from bs4 import BeautifulSoup
from precios_lavarden import listado, integrar, URL

class TestLavarden(unittest.TestCase):
    def test_precio_solo_para_misma_funcion_y_fuente(self):
        html = '''<div id="boxEvent"><h4 class="card-title">Paris Jazz Club: JAZZ CARTOONS</h4><p>24/10/2026, 21:00</p><p class="address">Teatro Lavarden, Rosario, Santa Fe</p><p>Desde ARS 30000</p><a class="buy-button" href="/Paris/">Comprar</a></div>'''
        fichas = listado(BeautifulSoup(html, 'html.parser'), URL)
        base = dict(nombre='Paris Jazz Club', fecha='2026-10-24', hora='21:00', evento_url='https://plataformalavarden.gob.ar/actividades/paris/')
        eventos = [base.copy(), dict(base, hora='20:00'), dict(base, evento_url='https://otro.com/paris/')]
        self.assertEqual(integrar(eventos, fichas, '2026-10-15 11:30'), 1)
        self.assertEqual(eventos[0]['precio'], 30000)
        self.assertIn('cargo de servicio', eventos[0]['precio_etiqueta'])
        self.assertNotIn('precio', eventos[1])
        self.assertNotIn('precio', eventos[2])
        self.assertEqual(integrar([base.copy()], fichas * 2, 'hoy'), 0)
        for cambiado in [html.replace('Rosario', 'Santa Fe'), html.replace('Comprar', 'Agotado'), html.replace('/Paris/', 'https://otro.com/')]:
            self.assertEqual(listado(BeautifulSoup(cambiado, 'html.parser'), URL), [])

    def test_ticket_precio_visible_y_no_apertura(self):
        from precios_lavarden import detalle_ticket, enlace_oficial
        html = '''<h1 class="event-title">El escritor de todas las cosas</h1>
        <p>Apertura de Puertas: 20:30hs</p><p>Entradas Online\n Desde: 40000</p>
        <select id="idFechasEventos"><option>16-10-2026, 21:00</option></select>
        <script type="application/ld+json">{"offers":{"price":"0.00","priceCurrency":"None"}}</script>'''
        f = detalle_ticket(BeautifulSoup(html, 'html.parser'), URL)
        self.assertEqual(f['precio'], 40000)
        self.assertEqual(f['funciones'], [('2026-10-16', '21:00')])
        varias = html.replace('</select>', '<option>17-10-2026, 21:00</option></select>')
        self.assertIsNone(detalle_ticket(BeautifulSoup(varias, 'html.parser'), URL)['precio'])
        agotado = html + '<div class="alert">Agotado</div>'
        self.assertIsNone(detalle_ticket(BeautifulSoup(agotado, 'html.parser'), URL)['precio'])
        links = '<a href="https://entradaslavarden.com/">Inicio</a><a href="https://entradaslavarden.com/Obra/">Ticket</a><a href="https://otro.com/">Otro</a>'
        self.assertEqual(enlace_oficial(BeautifulSoup(links, 'html.parser'), URL), ['https://entradaslavarden.com/Obra/'])

    def test_ficha_real_grandinetti(self):
        # Ejemplo de estructura pública sin copiar sinopsis ni imágenes.
        from precios_lavarden import ampliar
        class Fake:
            def __init__(self):
                self.cache = {'paginas': {}}
            def leer(self, url, parser, tipo):
                self.cache['paginas'][url] = {'consultado': 1792072800}
                html = ('<a href="https://entradaslavarden.com/Escritor/">Ticket</a>' if 'gob.ar' in url else
                        '<h1 class="event-title">El escritor de todas las cosas</h1><p>Entradas Online\n Desde: 40000</p><select id="idFechasEventos"><option>16-10-2026, 21:00</option></select>')
                return parser(BeautifulSoup(html, 'html.parser'), url)
        e = dict(nombre='Darío Grandinetti en «El escritor de todas las cosas»', fecha='2026-10-16', hora='21:00', precio=None, evento_url='https://plataformalavarden.gob.ar/actividades/escritor/')
        ampliar([e], Fake())
        self.assertEqual(e['precio'], 40000)
