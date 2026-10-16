import unittest
from datetime import date
from bs4 import BeautifulSoup
from actualizar_eventos import fechas_regla


def regla(fechas, dias='Todos los días', hora='20:30'):
    return BeautifulSoup(f'<div><span class="rule-fechas">{fechas}</span><span class="rule-dias">{dias}</span><span class="rule-hora">{hora}</span></div>', 'html.parser')


class Fechas(unittest.TestCase):
    def test_rango_cambia_de_anio_sin_inventar_anio(self):
        fechas = fechas_regla(regla('Del 30 de diciembre 2026 al 2 de enero 2027'), date(2026, 12, 31))
        self.assertEqual([f[0] for f in fechas], ['2026-12-31', '2027-01-01', '2027-01-02'])

    def test_recurrencia_respeta_dias_y_no_publica_vencidos(self):
        fechas = fechas_regla(regla('Del 1 de octubre 2026 al 31 de octubre 2026', 'Viernes'), date(2026, 10, 16))
        self.assertEqual([f[0] for f in fechas], ['2026-10-16', '2026-10-23', '2026-10-30'])

    def test_texto_sin_fecha_o_hora_no_genera_funciones(self):
        self.assertEqual(fechas_regla(regla('Publicado el 16 de octubre'), date(2026, 10, 16)), [])
        self.assertEqual(fechas_regla(regla('Del 1 de octubre al 31 de octubre', hora='A confirmar'), date(2026, 10, 16)), [])
