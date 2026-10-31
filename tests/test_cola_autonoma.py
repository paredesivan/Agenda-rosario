import copy
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import actualizar_eventos as municipal
import test_resolver_candidatos as fixtures
from resolver_candidatos import resolver
from cola_candidatos import resolver_local


class ColaAutonomaTests(unittest.TestCase):
    def test_cierra_vencida_sin_borrar_eventos_y_reabre_fecha_nueva(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            url = 'https://www.entradafan.com.ar/entradas-actividad/e/123'
            h = dict(nombre='Encuentro', fecha='2026-10-20', hora='20:00', lugar='Sala Abierta')
            entradas = [dict(fuente='EntradaFan', url=url, **h)]
            e = dict(h, fecha='2026-11-20', evento_url='https://teatro.example/a', origen='Teatro oficial')
            fixtures.ResolverTests().preparar(root, entradas, [e])
            a = fixtures.Acceso({})
            r = resolver(root, a, date(2026, 10, 31))
            self.assertEqual(r[0]['estado'], 'descartado')
            self.assertEqual(a.calls, [])
            self.assertEqual(json.loads((root/'eventos.json').read_text())['eventos'], [e])
            entradas[0]['fecha'] = '2026-11-20'
            (root/'candidatos_fuentes_adicionales.json').write_text(json.dumps({'candidatos': entradas}))
            r = resolver(root, fixtures.Acceso({}, copy.deepcopy(a.cache)), date(2026,11,1))
            self.assertEqual(r[0]['estado'], 'corroborado')

    def test_no_descarta_por_antiguedad_y_reconsulta_semanalmente(self):
        c = dict(fuente='SalePlan', hechos=[], primera_evidencia='2020-01-01')
        self.assertIsNone(resolver_local(c, [], date(2026,10,31), lambda h,b: None))
        c.update(hechos=[{'fecha':'2026-10-20'}], resultado={'estado':'descartado'}, resuelto_dia='2026-10-24')
        self.assertIsNone(resolver_local(c, [], date(2026,10,31), lambda h,b: None))
        c['resuelto_dia'] = '2026-10-25'
        self.assertEqual(resolver_local(c, [], date(2026,10,31), lambda h,b: None)['estado'], 'descartado')

    def test_no_cierra_si_queda_una_funcion_futura_sin_confirmar(self):
        c = dict(fuente='SalePlan', hechos=[{'fecha':'2026-10-20'}, {'fecha':'2026-11-20'}])
        self.assertIsNone(resolver_local(c, [], date(2026,10,31), lambda h,b: None))

    def test_avanzan_antiguos_con_novedades_diarias_sin_aumentar_cuota(self):
        with tempfile.TemporaryDirectory() as d, patch('builtins.print'):
            root = Path(d)
            antiguas = ['https://rosariotimes.com/antigua-'+str(i) for i in range(16)]
            cache = {'cola': {'Rosario Times|'+u:dict(fuente='Rosario Times', url=u, hechos=[], intento='2026-10-01', visto='2026-10-01') for u in antiguas}}
            leidas = set()
            for dia in range(4):
                nuevas = ['https://rosariotimes.com/nueva-'+str(dia)+'-'+str(i) for i in range(8)]
                fixtures.ResolverTests().preparar(root, [dict(fuente='Rosario Times', referencia=u) for u in nuevas])
                paginas = {u:'<article>Sin fecha verificable</article>' for u in antiguas+nuevas}
                paginas.update({c['url']:'<article>Sin fecha verificable</article>' for c in cache['cola'].values()})
                a = fixtures.Acceso(paginas, copy.deepcopy(cache))
                resolver(root, a, date(2026,10,31)+timedelta(days=dia))
                self.assertLessEqual(len(a.calls), 8)
                leidas.update(a.calls)
                cache = a.cache
            self.assertTrue(set(antiguas) <= leidas)

    def test_treinta_y_tres_pausadas_no_cuentan_como_lecturas(self):
        urls = ['https://www.rosario.gob.ar/inicio/a-'+str(i) for i in range(40)]
        municipal.DIAGNOSTICO_MUNICIPAL.clear()
        def consultar(url, hoy):
            error = '403 Client Error: Forbidden' if url == urls[6] else None
            municipal.DIAGNOSTICO_MUNICIPAL[url] = dict(url=url, funciones=0, **({'error':error} if error else {}))
            return url, [], error, False
        with patch.object(municipal, 'consultar_evento', side_effect=consultar) as leer:
            _, fallidas, pausadas = municipal.consultar_lote_municipal(urls, date(2026,10,31))
        self.assertEqual(leer.call_count, 7)
        self.assertEqual(len(municipal.DIAGNOSTICO_MUNICIPAL), 7)
        self.assertEqual(len(pausadas), 33)
        self.assertEqual(len(fallidas), 34)

    def test_pausa_previa_no_figura_como_consulta_real(self):
        urls = ['https://www.rosario.gob.ar/inicio/a-'+str(i) for i in range(40)]
        municipal.DIAGNOSTICO_MUNICIPAL.clear()
        def consultar(url, hoy):
            municipal.DIAGNOSTICO_MUNICIPAL[url] = {'url':url,'error':'Fuente en pausa por HTTP 403/429'}
            return url, [], 'Fuente en pausa por HTTP 403/429', False
        with patch.object(municipal, 'consultar_evento', side_effect=consultar):
            _, _, pausadas = municipal.consultar_lote_municipal(urls, date(2026,10,31))
        self.assertEqual(len(pausadas), 40)
        self.assertEqual(municipal.DIAGNOSTICO_MUNICIPAL, {})
