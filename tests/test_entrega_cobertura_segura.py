import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from actualizacion_segura import ejecutar_etapa, validar
from cobertura_fuentes import ordenar_consultas
from control_http import SesionControlada
from cobertura_actual import generar as cobertura
import gestion_agenda as g

EVENTO = {'fecha': '2099-10-30', 'hora': '20:00', 'nombre': 'Evento de prueba',
          'lugar': 'Sala de prueba', 'evento_url': 'https://example.org/evento', 'precio': None}


class ValidacionPublicacion(unittest.TestCase):
    def test_rechaza_precio_fecha_enlaces_y_categorias_invalidos(self):
        for cambio in ({'precio': -1}, {'precio': True}, {'precio': float('nan')}, {'precio': float('inf')},
                       {'fecha': '20991030'}, {'fecha': 20261030}, {'hora': '25:70'},
                       {'evento_url': 'https://'}, {'evento_url': 'https://usuario:clave@example.org'},
                       {'evento_url': 'https://example.org/\nx'}, {'descripcion': {}}, {'categorias': 'teatro'},
                       {'fecha_fin':'2099-10-29'}, {'fecha_fin':'2099-02-30'}, {'hora_fin':'25:00'}):
            with self.subTest(cambio=cambio), self.assertRaises(ValueError):
                validar({'eventos': [{**EVENTO, **cambio}]})

    def test_acepta_horario_por_confirmar_y_precio_desconocido(self):
        self.assertTrue(validar({'eventos': [{**EVENTO, 'hora': 'Horario a confirmar'}]}))

    def test_precio_invalido_en_etapa_conserva_agenda_y_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = json.dumps({'eventos': [EVENTO]})
            (root/'eventos.json').write_text(original)
            def ejecutar(args, cwd, **kw):
                (cwd/'eventos.json').write_text(json.dumps({'eventos':[{**EVENTO, 'precio':-1}]}))
                (cwd/'cache_prueba.json').write_text('{"dato":"incorrecto"}')
            salida = ejecutar_etapa(root, 'prueba.py', 1, ejecutar)
            self.assertEqual(salida['estado'], 'fallida')
            self.assertEqual((root/'eventos.json').read_text(), original)
            self.assertFalse((root/'cache_prueba.json').exists())


class CoberturaYAcceso(unittest.TestCase):
    def test_pendientes_y_nuevas_se_consultan_antes_que_exitosas(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'revision.json'
            p.write_text(json.dumps({'fichas':[{'url':'a','funciones':1},{'url':'z','error':'presupuesto'}]}))
            self.assertEqual(ordenar_consultas({'z','a','nueva'},p), ['z','nueva','a'])
            # Una vez consultada la pendiente, la siguiente diferida toma prioridad.
            p.write_text(json.dumps({'fichas':[{'url':'z','funciones':1},{'url':'a','error':'presupuesto'}]}))
            self.assertEqual(ordenar_consultas({'z','a'},p), ['a','z'])

    def test_restriccion_contractual_no_realiza_peticion(self):
        sesion=SesionControlada()
        sesion.politica={'dominios':{'fuente.test':{'consulta_automatica':False}}}
        with patch('requests.Session.send') as send:
            for host in ('fuente.test','www.fuente.test','api.fuente.test'):
                with self.assertRaisesRegex(Exception, 'condiciones de uso'):
                    sesion.get('https://'+host+'/evento')
            send.assert_not_called()

    def test_informe_separa_error_de_exclusion_y_detecta_funcion_ausente(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            g.guardar(root/'eventos.json', {'eventos':[EVENTO]})
            otro={**EVENTO, 'fecha':'2099-11-01'}
            g.guardar(root/'revision_cobertura_municipal.json', {'revision':'2099-10-24T12:01', 'fichas':[
                {'url':'https://example.org/fallo','error':'presupuesto','funciones':0},
                {'url':'https://example.org/curso','motivos':['fuera de alcance'],'funciones':0},
                {'url':EVENTO['evento_url'],'funciones':2,'detalle_funciones':[EVENTO,otro]}]})
            r=cobertura(root,inicio='2099-10-24T12:00',hoy='2099-10-24')
            self.assertEqual(r['estados_municipales']['consulta_fallida'],1)
            self.assertEqual(r['estados_municipales']['sin_funciones_extraidas'],1)
            self.assertEqual(r['funciones_extraidas_ausentes'],[otro])
            self.assertTrue(r['municipal_del_intento_actual'])

    def test_ruta_robots_se_detiene_antes_de_descargar(self):
        sesion=SesionControlada()
        sesion.politica={'dominios':{'fuente.test':{'rutas_excluidas':['/privado/']}}}
        with patch('requests.Session.send') as send:
            with self.assertRaisesRegex(Exception,'robots'):
                sesion.get('https://www.fuente.test/privado/dato')
            send.assert_not_called()

    def test_respaldo_tras_timeout_no_elimina_pausa_http_nueva(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            g.guardar(root/'eventos.json',{'eventos':[EVENTO]});g.preparar(root)
            def fallo(*args,**kw):
                g.guardar(root/'estado_http.json',{'fuente.test':{'pausado_hasta':9999999999}})
                raise subprocess.TimeoutExpired('etapa',1)
            g.actualizar(root,fallo)
            self.assertEqual(g.leer(root/'estado_http.json')['fuente.test']['pausado_hasta'],9999999999)

    def test_avisos_visibles_sin_imprimir_errores_crudos(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);g.guardar(root/'estado_agenda.json',{'alertas':[{'mensaje':'18 fichas pendientes'}]})
            output=io.StringIO()
            with redirect_stdout(output): self.assertEqual(g.avisar(root),1)
            self.assertIn('::warning',output.getvalue())

    def test_auditoria_no_acepta_html_como_robots(self):
        from auditar_fuentes import revisar_host
        from unittest.mock import Mock
        r=revisar_host('fuente.test',{'https://fuente.test/agenda'},Mock(return_value=Mock(status_code=200,text='<html>error</html>')))
        self.assertEqual(r['estado'],'robots_no_interpretable')
