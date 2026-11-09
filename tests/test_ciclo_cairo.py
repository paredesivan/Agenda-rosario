"""La asociación del ciclo sale de la ficha propia, nunca del menú."""
import unittest
from datetime import date
from unittest.mock import patch
from bs4 import BeautifulSoup
import fuentes_nuevas as fuentes

URL = 'https://elcairocinepublico.gob.ar/pelicula-de-sala/prueba/'
ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20301108T180000
SUMMARY:Película de prueba
URL:https://elcairocinepublico.gob.ar/pelicula-de-sala/prueba/
END:VEVENT
END:VCALENDAR"""
TAG = '<span class="categoria-online-tag"><a rel="tag" href="/cartelera-de-sala/categoria/prueba/">Ciclo de prueba</a></span>'


class CicloCairo(unittest.TestCase):
    def extraer(self, contenido):
        with patch.object(fuentes, 'HORIZONTE_DIAS', 0), patch.object(
                fuentes, 'descargar_texto_publico', return_value=ICS), patch.object(
                fuentes, 'descargar', return_value=BeautifulSoup(contenido, 'html.parser')):
            return fuentes.leer_cairo(date(2030, 11, 8))[0][0]

    def test_etiqueta_propia_frente_menu_externo_o_ambiguo(self):
        evento = self.extraer(TAG)
        self.assertEqual(evento['ciclo_nombre'], 'Ciclo de prueba')
        self.assertEqual(evento['ciclo_url'], 'https://elcairocinepublico.gob.ar/cartelera-de-sala/categoria/prueba/')
        for html in (TAG.replace('categoria-online-tag', 'menu'),
                     TAG.replace('href="/', 'href="https://externo.example/'),
                     TAG + TAG):
            with self.subTest(html=html):
                self.assertNotIn('ciclo_nombre', self.extraer(html))
