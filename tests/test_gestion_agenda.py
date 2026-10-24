import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import gestion_agenda as g
from instalar_entrega import aplicar, blob

EVENTO = {'fecha': '2099-10-22', 'hora': '20:00', 'nombre': 'Concierto de prueba',
          'lugar': 'Teatro de prueba', 'origen': 'Sala oficial', 'evento_url': 'https://example.org/evento'}


class Gestion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        g.guardar(self.root / 'eventos.json', {'eventos': [EVENTO]})
        g.guardar(self.root / 'cache_prueba.json', {'valor': 'original'})
        g.preparar(self.root)

    def test_error_restaura_datos_y_caches(self):
        def romper(*args, **kwargs):
            g.guardar(self.root / 'eventos.json', {'eventos': []})
            g.guardar(self.root / 'cache_prueba.json', {'valor': 'roto'})
            g.guardar(self.root / 'cache_nuevo.json', {'creado': True})
            raise subprocess.TimeoutExpired('actualizacion', 1)
        result = g.actualizar(self.root, romper)
        self.assertEqual(result['estado'], 'fallida')
        self.assertEqual(g.leer(self.root / 'eventos.json')['eventos'], [EVENTO])
        self.assertEqual(g.leer(self.root / 'cache_prueba.json'), {'valor': 'original'})
        self.assertFalse((self.root / 'cache_nuevo.json').exists())

    def test_datos_invalidos_tambien_restaura(self):
        def invalidar(*args, **kwargs):
            g.guardar(self.root / 'eventos.json', {'eventos': 'no es una lista'})
        self.assertTrue(g.actualizar(self.root, invalidar)['datos_conservados'])
        self.assertEqual(g.leer(self.root / 'eventos.json')['eventos'], [EVENTO])

    def test_fallo_no_publica_diagnostico_anterior_como_nuevo(self):
        g.guardar(self.root / 'salud_actualizacion.json', {'inicio': '2026-10-20T10:00:00-03:00', 'duplicados_unificados': 98, 'fuentes': {'Sala oficial': 'revisada: 1 funciones'}})
        g.guardar(self.root / 'reportes/resultado_actualizacion.json', {'estado': 'fallida', 'mensaje': 'Se conserva la agenda.'})
        report = g.informe(self.root)
        self.assertEqual(report['estado'], 'error')
        self.assertEqual(report['resumen']['duplicados'], 0)
        self.assertFalse(report['fuentes_son_del_intento_actual'])

    def test_comparacion_no_cuenta_vencidos_como_perdida(self):
        viejos = [dict(EVENTO, fecha='2000-01-01'), EVENTO]
        g.guardar(self.root / 'reportes/respaldo/eventos.json', {'eventos': viejos})
        report = g.informe(self.root)
        self.assertEqual(report['resumen']['ausentes'], 0)

    def test_cambio_fuente_no_es_alta_ni_baja(self):
        g.guardar(self.root / 'eventos.json', {'eventos': [dict(EVENTO, origen='Municipalidad', evento_url='https://rosario.gob.ar/ficha')]})
        report = g.informe(self.root)
        self.assertEqual(report['resumen']['nuevos'], 0)
        self.assertEqual(report['resumen']['ausentes'], 0)

    def test_caida_generica_y_sin_datos_privados(self):
        antes = [dict(EVENTO, nombre=f'Evento {n}') for n in range(6)]
        g.guardar(self.root / 'reportes/respaldo/eventos.json', {'eventos': antes})
        g.guardar(self.root / 'salud_actualizacion.json', {'fuentes': {'Sala oficial': 'ConnectTimeout: https://example.org/?token=secreto&email=privado@example.org'}})
        report = g.informe(self.root)
        self.assertTrue(any(a['tipo'] == 'caida' for a in report['alertas']))
        text = json.dumps(report)
        self.assertNotIn('secreto', text)
        self.assertNotIn('privado@example.org', text)

    def test_historial_acotado(self):
        g.guardar(self.root / 'historial_actualizaciones.json', [{'generado': f'2000-{n}', 'resumen': {}} for n in range(70)])
        g.informe(self.root)
        self.assertEqual(len(g.leer(self.root / 'historial_actualizaciones.json')), 30)

    def test_un_solo_informe_por_ejecucion(self):
        with patch.dict(os.environ, {'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '1'}):
            with patch.object(g, 'ahora', return_value='2026-10-22T10:00:00-03:00'):
                g.informe(self.root)
            with patch.object(g, 'ahora', return_value='2026-10-22T10:01:00-03:00'):
                g.informe(self.root)
        self.assertEqual(len(g.leer(self.root / 'historial_actualizaciones.json')), 1)

    def test_estado_cero_errores_y_pendientes_reales(self):
        self.assertEqual(g.clasificar_estado('revisada: 5 funciones, 0 errores')[0], 'bien')
        self.assertEqual(g.clasificar_estado('revisada: 5 funciones, 0 fichas pendientes')[0], 'bien')
        self.assertEqual(g.clasificar_estado('revisada: 5 funciones, 2 fichas pendientes')[0], 'pendiente')
        self.assertEqual(g.clasificar_estado('HTTP 429, pausa')[0], 'atencion')

    def test_no_publica_vacio_con_futuros(self):
        g.guardar(self.root / 'eventos.json', {'eventos': []})
        with self.assertRaises(ValueError): g.validar_publicacion(self.root)

    def test_no_publica_enlace_inseguro(self):
        g.guardar(self.root / 'eventos.json', {'eventos': [dict(EVENTO, evento_url='javascript:alert(1)')]})
        with self.assertRaises(ValueError): g.validar_publicacion(self.root)

    def test_archivo_solo_despues_de_desactivar(self):
        folder = self.root / '.github/workflows'
        folder.mkdir(parents=True)
        (folder / 'pruebas.yml').write_text('prueba')
        (self.root / 'agenda15-10.js').write_text('version vieja')
        def rechazar(*args, **kwargs): return subprocess.CompletedProcess(args, 1, '', '')
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'owner/repo'}):
            report = g.archivar(self.root, rechazar)
        self.assertEqual(report['pendientes'], ['pruebas.yml'])
        self.assertTrue((self.root / 'agenda15-10.js').exists())
        def aceptar(*args, **kwargs): return subprocess.CompletedProcess(args, 0, '', '')
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'owner/repo'}):
            report = g.archivar(self.root, aceptar)
        self.assertEqual(report['pendientes'], [])
        self.assertFalse((self.root / 'agenda15-10.js').exists())
        self.assertEqual((self.root / 'archivo/historico/agenda15-10.js.txt').read_text(), 'version vieja')
        self.assertTrue((folder / 'pruebas.yml').exists())

    def test_guardado_rechaza_cambios_concurrentes(self):
        commands = []
        def fake(args, **kwargs):
            commands.append(args)
            result = 'viejo' if args[-1] == 'HEAD' else 'nuevo'
            return subprocess.CompletedProcess(args, 0, result, '')
        with self.assertRaises(RuntimeError): g.guardar_cambios(self.root, fake)
        self.assertFalse(any('push' in c or 'add' in c for c in commands))

    def test_guardado_real_con_reportes_ignorados_y_archivos_eliminados(self):
        # Reproduce la carpeta que generaron las pruebas de navegador en Actions.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root, remoto = base / 'repo', base / 'remoto.git'
            root.mkdir()
            def git(*args, cwd=root):
                return subprocess.run(['git', *args], cwd=cwd, check=True,
                                      capture_output=True, text=True).stdout.strip()
            git('init', '--bare', '--initial-branch=main', str(remoto))
            git('init', '--initial-branch=main')
            git('config', 'user.name', 'Prueba')
            git('config', 'user.email', 'prueba@example.invalid')
            git('remote', 'add', 'origin', str(remoto))
            (root / '.gitignore').write_text('reportes/\n__pycache__/\n*.pyc\n')
            (root / 'eliminar.txt').write_text('anterior')
            g.guardar(root / 'eventos.json', {'eventos': [EVENTO]})
            folder = root / '.github/workflows'
            folder.mkdir(parents=True)
            (folder / 'prueba.yml').write_text('original')
            git('add', '.')
            git('commit', '-m', 'Base')
            git('push', 'origin', 'HEAD:main')
            (root / 'eliminar.txt').unlink()
            (root / 'nuevo[1].txt').write_text('nuevo')
            (root / ':literal.txt').write_text('nombre literal')
            (folder / 'prueba.yml').write_text('no debe guardarse')
            (root / 'reportes').mkdir()
            (root / 'reportes/resumen.md').write_text('informe generado')
            (root / '__pycache__').mkdir()
            (root / '__pycache__/modulo.pyc').write_bytes(b'cache')
            head = g.guardar_cambios(root)
            files = git('ls-tree', '-r', '--name-only', 'HEAD').splitlines()
            self.assertIn('nuevo[1].txt', files)
            self.assertIn(':literal.txt', files)
            self.assertNotIn('eliminar.txt', files)
            self.assertFalse(any(f.startswith(('reportes/', '__pycache__/')) for f in files))
            self.assertEqual(git('show', 'HEAD:.github/workflows/prueba.yml'), 'original')
            self.assertEqual(head, git('rev-parse', 'refs/heads/main', cwd=remoto))
            self.assertEqual(g.guardar_cambios(root), head)

    def test_publicacion_exige_commit_correcto(self):
        builds = iter([{'status': 'built', 'commit': 'otro'}, {'status': 'built', 'commit': 'correcto'}])
        def fake(args, **kwargs):
            output = 'correcto' if args[:2] == ['git', 'rev-parse'] else ''
            if args[-1].endswith('/pages/builds/latest'): output = json.dumps(next(builds))
            return subprocess.CompletedProcess(args, 0, output, '')
        waits = []
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'owner/repo'}):
            g.publicar(self.root, fake, lambda n: waits.append(n))
        self.assertEqual(waits, [10])
        self.assertEqual(g.leer(self.root / 'reportes/publicacion.json')['commit'], 'correcto')


class Instalador(unittest.TestCase):
    def test_repetible_sin_pisar_ediciones_posteriores(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'uno.py').write_text('original')
            payload = {'version': 'v1', 'files': {'uno.py': 'nuevo', 'dos.py': 'nuevo'},
                       'expected': {'uno.py': [blob(b'original')]}}
            self.assertTrue(aplicar(payload, root))
            (root / 'uno.py').write_text('cambio posterior')
            self.assertFalse(aplicar(payload, root))
            self.assertEqual((root / 'uno.py').read_text(), 'cambio posterior')

    def test_conflicto_no_escribe_parcialmente(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'dos.py').write_text('no conocido')
            payload = {'version': 'v1', 'files': {'uno.py': 'nuevo', 'dos.py': 'nuevo'}}
            with self.assertRaises(ValueError): aplicar(payload, root)
            self.assertFalse((root / 'uno.py').exists())
            self.assertEqual((root / 'dos.py').read_text(), 'no conocido')

    def test_rechaza_rutas_fuera_del_proyecto(self):
        with tempfile.TemporaryDirectory() as tmp:
            for path in ('../fuera.py', '/tmp/fuera.py', '.github/workflows/otra.yml'):
                with self.assertRaises(ValueError): aplicar({'version': 'v1', 'files': {path: 'x'}}, Path(tmp))

    def test_falla_de_escritura_restaurada(self):
        import instalar_entrega as m
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'uno.py').write_text('original')
            payload = {'version': 'v1', 'files': {'uno.py': 'nuevo', 'dos.py': 'nuevo'}, 'expected': {'uno.py': [blob(b'original')]}}
            real = m.os.replace
            calls = []
            def falla(src, dst):
                calls.append(dst)
                if len(calls) == 2: raise OSError('disco')
                return real(src, dst)
            with patch.object(m.os, 'replace', side_effect=falla):
                with self.assertRaises(OSError): aplicar(payload, root)
            self.assertEqual((root / 'uno.py').read_text(), 'original')
            self.assertFalse((root / '.agenda/entrega.json').exists())

