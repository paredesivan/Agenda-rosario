import json
import unittest
from datetime import date
from unittest.mock import patch

from bs4 import BeautifulSoup
from actualizar_eventos import calendario_mec

URL = 'https://teatroastengo.ar/events/prueba/'
DIA = '2027-11-10'


class HorarioAstengo(unittest.TestCase):
    def extraer(self, descripcion):
        schema = dict(name='Concierto de prueba', url=URL, startDate=DIA+'T19:00:00')
        schema['@type'] = 'MusicEvent'
        listado = BeautifulSoup('<script type="application/ld+json">'+json.dumps(schema)+'</script>', 'html.parser')
        detalle = BeautifulSoup('<div class="mec-single-event-description">'+descripcion+'</div>'
                                '<div class="mec-single-event-time"><span class="mec-events-abbr">19:00 - 22:00</span></div>',
                                'html.parser')
        with patch('actualizar_eventos.descargar', return_value=detalle):
            eventos, errores = calendario_mec(listado, 'Teatro Astengo', URL, 'Mitre 754', date.fromisoformat(DIA))
        self.assertFalse(errores)
        return eventos[0]

    def test_hora_de_funcion_en_texto_de_la_misma_fecha(self):
        evento = self.extraer('El miércoles 10 de noviembre a las 20.00 horas. Apertura de puertas 19.00 horas.')
        self.assertEqual(evento['hora'], '20:00')

    def test_solo_apertura_no_se_anuncia_como_inicio(self):
        evento = self.extraer('Apertura de puertas 19.00 horas.')
        self.assertEqual(evento['hora'], 'Horario a confirmar')
        self.assertTrue(evento['horario_pendiente'])

    def test_horario_sin_etiqueta_de_apertura_se_conserva(self):
        self.assertEqual(self.extraer('Concierto de música de cámara.')['hora'], '19:00')
