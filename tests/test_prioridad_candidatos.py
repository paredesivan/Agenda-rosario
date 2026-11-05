import tempfile
import unittest
from datetime import date
from pathlib import Path

from cola_candidatos import prioridad_candidato, resolver_local, turnos_justos
from resolver_candidatos import detalle, noticia_ajena, resolver
import test_resolver_candidatos as fixtures


class PrioridadTests(unittest.TestCase):
    def test_fecha_proxima_y_antiguedad(self):
        hoy = date(2026, 11, 3)
        cerca = ('a', {'hechos': [{'fecha': '2026-11-05'}]})
        lejos = ('b', {'hechos': [{'fecha': '2026-12-05'}]})
        vieja = ('c', {'intento': '2026-10-20T09:00:00', 'hechos': []})
        self.assertLess(prioridad_candidato(cerca, hoy), prioridad_candidato(lejos, hoy))
        self.assertLess(prioridad_candidato(vieja, hoy), prioridad_candidato(cerca, hoy))

    def test_fechas_vencidas_y_futuras_no_corroboradas(self):
        hoy = date(2026, 11, 3)
        vencida = {'fuente': 'x', 'hechos': [{'fecha': '2026-11-02'}]}
        futura = {'fuente': 'x', 'hechos': [{'fecha': '2026-11-05'}]}
        self.assertEqual(resolver_local(vencida, [], hoy, lambda *_: None)['estado'], 'descartado')
        self.assertIsNone(resolver_local(futura, [], hoy, lambda *_: None))

    def test_noticia_y_evento_no_se_confunden(self):
        titulo = 'Se reactivaron las obras del gasoducto Rosario Oeste'
        self.assertTrue(noticia_ajena(titulo, False, [], [], set()))
        self.assertFalse(noticia_ajena(titulo, True, [], [], set()))
        self.assertFalse(noticia_ajena(titulo, False, [], ['https://teatro.example/a'], {'teatro.example'}))
        self.assertFalse(noticia_ajena('Festival en la autopista', False, [], [], set()))

    def test_resolucion_registra_ultimo_intento_y_revisa_descartado(self):
        url = 'https://rosariotimes.com/infraestructura/'
        html = '<h1>Se reactivaron las obras del gasoducto Rosario Oeste</h1><article>La obra avanza.</article>'
        with tempfile.TemporaryDirectory() as carpeta:
            root = Path(carpeta)
            fixtures.ResolverTests().preparar(root, [{'fuente': 'Rosario Times', 'url': url}])
            acceso = fixtures.Acceso({url: html})
            resultado = resolver(root, acceso, date(2026, 11, 3))[0]
            self.assertEqual(resultado['estado'], 'descartado')
            self.assertEqual(resultado['ultimo_intento']['estado'], 'descartado')
            self.assertEqual(acceso.calls, [url])
            resolver(root, acceso, date(2026, 11, 4))
            self.assertEqual(acceso.calls, [url])
            resolver(root, acceso, date(2026, 11, 11))
            self.assertEqual(acceso.calls, [url, url])

    def test_nunca_consultados_y_reintentos_reciben_turnos(self):
        filas = [('nuevo', {}), ('viejo', {'intento': '2026-11-01T00:00:00'})]
        orden = turnos_justos(filas, lambda p: prioridad_candidato(p, date(2026, 11, 3)))
        self.assertEqual({p[0] for p in orden}, {'nuevo', 'viejo'})


if __name__ == '__main__':
    unittest.main()
