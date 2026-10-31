import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gestion_agenda import guardar
from seguimiento_cobertura import completar_informe, medir_pendientes


def panel(fecha='2026-11-01T10:00:00-03:00', actual=True):
    return dict(generado=fecha, fuentes_son_del_intento_actual=actual,
                fuentes=[], alertas=[], estado='bien', resumen={})


class Seguimiento(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_fuente_desaparecida_sigue_visible_en_ejecuciones_siguientes(self):
        guardar(self.root/'estado_agenda.json', {'fuentes': [{'nombre': 'Museo'}]})
        for dia in ('2026-11-01', '2026-11-02'):
            p = panel(dia+'T10:00:00-03:00')
            completar_informe(self.root, p, {'fuentes': {}}, {}, guardar)
            self.assertEqual(p['fuentes'][0]['nombre'], 'Museo')
            self.assertFalse(p['fuentes'][0]['diagnostico_actual'])
            self.assertEqual(p['fuentes'][0]['estado'], 'pendiente')
            guardar(self.root/'estado_agenda.json', p)
        self.assertEqual(p['fuentes'][0]['dias_sin_diagnostico'], 1)

    def test_cero_fichas_municipales_no_es_resultado_sano(self):
        guardar(self.root/'revision_cobertura_municipal.json',
                {'revision': '2026-11-01T09:50:00-03:00', 'fichas_consultadas': 0})
        p = panel()
        completar_informe(self.root, p, {}, {'inicio':'2026-11-01T09:00:00-03:00'}, guardar)
        self.assertEqual(p['estado'], 'atencion')
        self.assertEqual(p['control_cobertura']['municipal']['fichas_consultadas'], 0)

    def test_revision_anterior_no_se_atribuye_a_esta_ejecucion(self):
        guardar(self.root/'revision_cobertura_municipal.json',
                {'revision':'2026-10-01T10:00:00-03:00', 'fichas_consultadas':40})
        p = panel()
        completar_informe(self.root, p, {}, {'inicio':'2026-11-01T09:00:00-03:00'}, guardar)
        self.assertIsNone(p['control_cobertura']['municipal']['fichas_consultadas'])

    def test_envejecimiento_no_se_reinicia_al_reintentar_y_no_expone_urls(self):
        e = dict(fuente='Fuente', visto='2026-10-20', resultado={'estado':'reintentar'})
        guardar(self.root/'cache_resolucion_candidatos.json', {'cola': {'url-secreta': e}})
        a = medir_pendientes(self.root, '2026-11-01', guardar)
        e['visto'] = '2026-11-02'
        guardar(self.root/'cache_resolucion_candidatos.json', {'cola': {'url-secreta': e}})
        b = medir_pendientes(self.root, '2026-11-02', guardar)
        self.assertEqual(a['antiguedad_maxima_dias'], 12)
        self.assertEqual(b['antiguedad_maxima_dias'], 13)
        self.assertNotIn('url-secreta', json.dumps(b))
        e['resultado']['estado'] = 'publicado'
        guardar(self.root/'cache_resolucion_candidatos.json', {'cola': {'url-secreta': e}})
        self.assertEqual(medir_pendientes(self.root, '2026-11-03', guardar)['cantidad'], 0)

    def test_verificacion_no_inventa_revision_actual_ni_tiempo_humano(self):
        p = panel(actual=False)
        completar_informe(self.root, p, {'fuentes':{'Museo':'revisada'}}, {}, guardar)
        self.assertIsNone(p['control_cobertura']['minutos_hasta_informe'])
        self.assertEqual(p['control_cobertura']['tiempo_intervencion_humana'], 'No medido')
        self.assertFalse(p['control_cobertura']['municipal']['diagnostico_actual'])

    def test_informe_no_presenta_salud_antigua_como_actual(self):
        import gestion_agenda as g
        evento = dict(fecha='2026-11-20', hora='20:00', nombre='Prueba', lugar='Sala',
                      origen='Museo', evento_url='https://example.org/evento')
        guardar(self.root/'eventos.json', {'eventos':[evento]})
        guardar(self.root/'reportes/contexto.json', {'inicio':'2026-11-01T09:00:00-03:00'})
        guardar(self.root/'salud_actualizacion.json', {'inicio':'2026-10-31T09:00:00-03:00',
                'fuentes':{'Museo':'revisada: 1 funciones'}})
        with patch.object(g, 'ahora', return_value='2026-11-01T10:00:00-03:00'):
            p = g.informe(self.root)
        self.assertFalse(p['fuentes_son_del_intento_actual'])
        self.assertFalse(p['fuentes'][0]['diagnostico_actual'])
