import subprocess
import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

class Workflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = yaml.load((ROOT / '.github/workflows/actualizar.yml').read_text(), Loader=yaml.BaseLoader)

    def test_instala_con_push_y_mantiene_horarios(self):
        trigger = self.workflow['on']
        self.assertIn('.github/workflows/actualizar.yml', trigger['push']['paths'])
        self.assertEqual({s['cron'] for s in trigger['schedule']}, {'17 */2 * * *', '10 12 * * 1'})
        self.assertEqual(trigger['workflow_dispatch']['inputs']['accion']['options'], ['actualizar', 'verificar', 'auditar'])
        self.assertIn('pull_request', trigger)
        self.assertEqual(self.workflow['concurrency']['cancel-in-progress'], 'false')

    def test_limites_y_sintaxis_shell_de_todos_los_pasos(self):
        for step in self.workflow['jobs']['agenda']['steps']:
            if 'run' not in step: continue
            with self.subTest(paso=step['name']):
                self.assertLessEqual(len(step['run']), 21000)
                subprocess.run(['bash', '-n'], input=step['run'], text=True, check=True, capture_output=True)

    def test_guardado_y_publicacion_despues_de_pruebas(self):
        steps = self.workflow['jobs']['agenda']['steps']
        ids = {s.get('id'): i for i, s in enumerate(steps) if s.get('id')}
        self.assertLess(ids['pruebas'], ids['actualizar'])
        self.assertLess(ids['navegador'], ids['guardar'])
        self.assertLess(ids['guardar'], ids['publicar'])
        for name in ('guardar', 'publicar'):
            self.assertIn("github.event_name != 'pull_request'", steps[ids[name]]['if'])
            self.assertIn("github.ref == 'refs/heads/main'", steps[ids[name]]['if'])
        self.assertTrue(any(s.get('if') == 'always()' and s.get('uses', '').startswith('actions/upload-artifact@') for s in steps))

    def test_instalacion_no_reescribe_workflows_con_token(self):
        source = (ROOT / 'instalar_entrega.py').read_text()
        self.assertIn("('.git', '.github')", source)
        source = (ROOT / 'gestion_agenda.py').read_text()
        self.assertIn("('.github', 'reportes')", source)
        self.assertNotIn("'--force'", source)
