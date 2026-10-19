import copy
import json
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path
from actualizacion_segura import proteger, validar, ejecutar_etapa

HOY = date(2026, 10, 16)

def evento(n=0, **extra):
    return {'fecha': '2026-10-20', 'hora': '20:00', 'nombre': f'Actividad {n}',
            'lugar': 'Sala', 'origen': 'Sala oficial', **extra}


class Seguridad(unittest.TestCase):
    def test_parser_vacio_conserva_fuente_aunque_otra_funcione(self):
        a = {'eventos': [evento()]}
        b = {'eventos': [evento(9, origen='Otra sala')]}
        salida, avisos = proteger(a, b, HOY)
        self.assertEqual(len(salida['eventos']), 2)
        self.assertTrue(salida['eventos'][1]['revision_pendiente'])
        self.assertEqual(avisos[0]['fuente'], 'Sala oficial')

    def test_caida_parcial_conserva_sin_duplicar(self):
        a = {'eventos': [evento(n) for n in range(10)]}
        b = {'eventos': [evento()]}
        salida, avisos = proteger(a, b, HOY)
        self.assertEqual(len(salida['eventos']), 10)
        self.assertEqual(len(avisos), 1)

    def test_vencidos_no_se_resucitan(self):
        salida, avisos = proteger({'eventos': [evento(fecha='2026-10-15')]}, {'eventos': []}, HOY)
        self.assertEqual(salida['eventos'], [])
        self.assertEqual(avisos, [])

    def test_actualizacion_normal_permite_cambio_de_hora(self):
        salida, avisos = proteger({'eventos': [evento()]}, {'eventos': [evento(hora='21:00')]}, HOY)
        self.assertEqual(len(salida['eventos']), 1)
        self.assertFalse(avisos)

    def test_fecha_invalida_y_datos_rotos_se_rechazan(self):
        for datos in ({}, {'eventos': 'mal'}, {'eventos': [evento(fecha='2026-02-30')]}, {'eventos': [evento(nombre='')]}):
            with self.subTest(datos=datos), self.assertRaises((ValueError, KeyError)):
                validar(datos)

    def test_fallo_timeout_o_json_roto_no_modifican_agenda(self):
        for modo in ('fallo', 'timeout', 'json', 'vacio'):
            with self.subTest(modo=modo), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                archivo = root / 'eventos.json'
                archivo.write_text(json.dumps({'eventos': [evento()]}))
                original = archivo.read_bytes()
                def falso(args, cwd, **kw):
                    (cwd / 'eventos.json').write_text('{')
                    if modo == 'fallo':
                        raise subprocess.CalledProcessError(1, args)
                    if modo == 'timeout':
                        raise subprocess.TimeoutExpired(args, 1)
                    if modo == 'vacio':
                        (cwd / 'eventos.json').write_text('{"eventos": []}')
                resultado = ejecutar_etapa(root, 'falso.py', 1, falso, HOY)
                if modo == 'vacio':
                    self.assertEqual(resultado['estado'], 'parcial')
                    self.assertEqual(len(json.loads(archivo.read_text())['eventos']), 1)
                else:
                    self.assertEqual(resultado['estado'], 'fallida')
                    self.assertEqual(archivo.read_bytes(), original)

    def test_etapa_valida_publica_y_guarda_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'eventos.json').write_text(json.dumps({'eventos': [evento()]}))
            def falso(args, cwd, **kw):
                (cwd / 'eventos.json').write_text(json.dumps({'eventos': [evento(hora='21:00')]}))
                (cwd / 'cache_prueba.json').write_text('{"dato": 1}')
            self.assertEqual(ejecutar_etapa(root, 'falso.py', 1, falso, HOY)['estado'], 'validada')
            self.assertEqual(json.loads((root / 'eventos.json').read_text())['eventos'][0]['hora'], '21:00')
            self.assertEqual(json.loads((root / 'cache_prueba.json').read_text()), {'dato': 1})

class FallosReales(unittest.TestCase):
    def test_subproceso_roto_conserva_agenda_y_pausa_http(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archivo = root / 'eventos.json'
            archivo.write_text(json.dumps({'eventos': [evento()]}))
            original = archivo.read_bytes()
            (root / 'falla.py').write_text('from pathlib import Path\nPath("eventos.json").write_text("roto")\nPath("estado_http.json").write_text(\'{"fuente.test":{"pausado_hasta":9999999999}}\')\nraise SystemExit(1)\n')
            resultado = ejecutar_etapa(root, 'falla.py', 5, hoy=HOY)
            self.assertEqual(resultado['estado'], 'fallida')
            self.assertEqual(archivo.read_bytes(), original)
            self.assertEqual(json.loads((root / 'estado_http.json').read_text())['fuente.test']['pausado_hasta'], 9999999999)

class SnapshotACR(unittest.TestCase):
    def test_no_resucita_suspendidos_tras_lectura_exitosa(self):
        anterior={'eventos':[evento(origen='Agenda Cultural Rosario')], 'revision_acr_id':'vieja'}
        despues={'eventos':[], 'revision_acr_id':'nueva'}
        salida,avisos=proteger(anterior,despues,HOY)
        self.assertEqual(len(salida['eventos']),1)
        self.assertTrue(salida['eventos'][0]['revision_pendiente'])

    def test_marcador_heredado_no_permite_borrar_si_falla(self):
        anterior={'eventos':[evento(origen='Agenda Cultural Rosario')], 'revision_acr_id':'igual'}
        despues={'eventos':[], 'revision_acr_id':'igual'}
        salida,avisos=proteger(anterior,despues,HOY)
        self.assertEqual(len(salida['eventos']),1)
        self.assertEqual(len(avisos),1)


class ConservacionPorEvento(unittest.TestCase):
    def test_no_pierde_uno_de_diez(self):
        antes = {'eventos': [evento(n, evento_url=f'https://fuente.example/{n}') for n in range(10)]}
        despues = {'eventos': copy.deepcopy(antes['eventos'][:-1])}
        resultado, avisos = proteger(antes, despues, HOY)
        self.assertEqual(len(resultado['eventos']), 10)
        self.assertEqual(sum(bool(e.get('revision_pendiente')) for e in resultado['eventos']), 1)
        self.assertTrue(avisos)

    def test_revision_sin_cancelacion_no_borra(self):
        e = evento(evento_url='https://fuente.example/cartel')
        salida, _ = proteger({'eventos': [e]}, {'eventos': [],
            'revision_ampliadas': {'id': 'nuevo', 'fichas_revisadas': [['Sala oficial', e['evento_url']]]}}, HOY)
        self.assertEqual(len(salida['eventos']), 1)
        self.assertTrue(salida['eventos'][0]['revision_pendiente'])

    def test_cancelacion_individual_con_evidencia(self):
        e = evento(evento_url='https://fuente.example/cartel')
        baja = {**e, 'motivo': 'cancelado', 'evidencia_url': e['evento_url']}
        salida, _ = proteger({'eventos': [e]}, {'eventos': [], 'bajas_confirmadas': [baja]}, HOY)
        self.assertEqual(salida['eventos'], [])

    def test_cambio_de_hora_no_duplica(self):
        e = evento(evento_url='https://fuente.example/cartel')
        salida, _ = proteger({'eventos': [e]}, {'eventos': [{**e, 'hora': '21:00'}]}, HOY)
        self.assertEqual(len(salida['eventos']), 1)
