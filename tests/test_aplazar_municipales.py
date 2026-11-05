import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import actualizar_eventos as m
from aplazar_municipales import registrar, planificar


class Aplazamientos(unittest.TestCase):
    def test_persiste_sin_extender_al_releer_el_mismo_error_y_reabre(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);registro=p/'registro.json';revision=p/'revision.json'
            ahora=datetime.fromisoformat('2026-11-02T10:00:00-03:00')
            r=dict(revision=ahora.isoformat(),fichas=[dict(url='https://www.rosario.gob.ar/inicio/a',error='403 Client Error')])
            revision.write_text(json.dumps(r))
            a,pausadas=planificar({'https://www.rosario.gob.ar/inicio/a','https://www.rosario.gob.ar/inicio/b'},revision,registro,ahora)
            self.assertEqual(a,{'https://www.rosario.gob.ar/inicio/b'})
            self.assertEqual(len(pausadas),1)
            original=registro.read_bytes()
            planificar(set(a),revision,registro,ahora+timedelta(days=1))
            self.assertEqual(registro.read_bytes(),original)
            a,pausadas=planificar({'https://www.rosario.gob.ar/inicio/a'},revision,registro,ahora+timedelta(days=7))
            self.assertEqual(len(a),1);self.assertFalse(pausadas)

    def test_no_aplaza_una_ficha_que_solo_heredo_la_pausa_del_host(self):
        with tempfile.TemporaryDirectory() as d:
            registro=registrar(dict(revision='2026-11-02T10:00:00-03:00',fichas=[dict(url='b',error='Fuente en pausa por HTTP 403/429'),dict(url='c',error='Timeout')]),Path(d)/'registro.json')
            self.assertEqual(registro,{})

    def test_mantiene_datos_y_consulta_otras_fichas_sin_tocar_pausa_http(self):
        with tempfile.TemporaryDirectory() as d, patch('builtins.print'):
            p=Path(d);ahora=datetime.fromisoformat('2026-11-02T10:00:00-03:00')
            urls=['https://www.rosario.gob.ar/inicio/actividad-'+str(i) for i in range(4)]
            es=[dict(fecha='2026-11-20',hora='20:00',nombre='Actividad '+str(i),lugar='Sala '+str(i),origen=m.ORIGEN,evento_url=u) for i,u in enumerate(urls)]
            (p/'eventos.json').write_text(json.dumps({'eventos':es}))
            (p/'revision_cobertura_municipal.json').write_text(json.dumps(dict(revision=ahora.isoformat(),fichas=[dict(url=urls[0],error='403 Client Error: Forbidden')])) )
            pausa=dict(**{'www.rosario.gob.ar':dict(pausado_hasta=9999999999)})
            (p/'estado_http.json').write_text(json.dumps(pausa))
            def consultar(u,hoy):
                m.DIAGNOSTICO_MUNICIPAL[u]=dict(url=u,funciones=1)
                return u,[next(e for e in es if e['evento_url']==u)],None,False
            with patch.object(m,'ARCHIVO',p/'eventos.json'),patch.object(m,'EXTRAS',()),patch.object(m,'datetime') as reloj,patch.object(m,'obtener_enlaces',return_value=(set(urls),[])),patch.object(m,'consultar_evento',side_effect=consultar) as llamadas:
                reloj.now.return_value=ahora;m.actualizar()
            self.assertEqual(llamadas.call_count,3)
            self.assertNotIn(urls[0],{c.args[0] for c in llamadas.call_args_list})
            self.assertEqual(len(json.loads((p/'eventos.json').read_text())['eventos']),4)
            diagnostico=json.loads((p/'revision_cobertura_municipal.json').read_text())
            self.assertEqual(diagnostico['fichas_aplazadas_por_bloqueo'],1)
            self.assertEqual(diagnostico['fichas_leidas'],3)
            self.assertEqual(json.loads((p/'estado_http.json').read_text()),pausa)

    def test_pausa_global_sigue_impidiendo_pedir_otras_fichas(self):
        from control_http import SesionControlada
        from requests import Request, RequestException
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'http.json';p.write_text(json.dumps({'www.rosario.gob.ar':{'pausado_hasta':200}}))
            s=SesionControlada(ruta=p,reloj=lambda:100,dormir=lambda n:None)
            with self.assertRaises(RequestException), patch('requests.Session.send') as red:
                s.send(Request('GET','https://www.rosario.gob.ar/inicio/otra').prepare())
            red.assert_not_called()
