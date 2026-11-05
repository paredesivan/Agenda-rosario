import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import gestion_agenda as g
from seguimiento_cobertura import completar_informe


class Continuidad(unittest.TestCase):
    def test_alias_no_es_fuente_desaparecida(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fuentes = [dict(nombre='El Cairo Cine Público', estado='pendiente', eventos=52),
                       dict(nombre='El Cairo — CSV', estado='bien', motivo='Consulta completada.', accion='Sin intervención necesaria.')]
            for dia in ('2026-11-01', '2026-11-02'):
                p = dict(generado=dia+'T10:00:00-03:00', fuentes_son_del_intento_actual=True,
                         fuentes=fuentes, alertas=[], estado='bien', resumen={})
                completar_informe(root, p, {'fuentes':{'El Cairo — CSV':'revisada: 52 funciones'}}, {}, g.guardar)
                self.assertTrue(fuentes[0]['diagnostico_actual'])
                self.assertEqual(fuentes[0]['eventos'],52)
                self.assertEqual(fuentes[0]['estado'],'bien')
                self.assertNotIn('El Cairo Cine Público',p['control_cobertura']['fuentes_sin_diagnostico'])

    def test_alias_ausente_no_inventa_consulta(self):
        with tempfile.TemporaryDirectory() as d:
            p = dict(generado='2026-11-01T10:00:00-03:00', fuentes_son_del_intento_actual=True,
                     fuentes=[dict(nombre='ECU Espacio Cultural Universitario')],alertas=[],estado='bien',resumen={})
            completar_informe(Path(d),p,{'fuentes':{}},{},g.guardar)
            self.assertFalse(p['fuentes'][0]['diagnostico_actual'])

    def publicar(self, builds, runs):
        respuestas=iter(builds)
        def fake(args,**kwargs):
            text='correcto' if args[:2]==['git','rev-parse'] else ''
            if args[-1].endswith('/pages/builds/latest'):text=json.dumps(next(respuestas))
            elif '/actions/runs?' in args[-1]:text=json.dumps({'workflow_runs':runs})
            return subprocess.CompletedProcess(args,0,text,'')
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{'GITHUB_REPOSITORY':'owner/repo'}):
            root=Path(d);waits=[]
            g.publicar(root,fake,lambda n:waits.append(n))
            self.assertEqual(g.leer(root/'reportes/publicacion.json')['commit'],'correcto')
            return waits

    def test_cancelacion_duplicada_no_oculta_publicacion_exitosa(self):
        runs=[dict(head_sha='correcto',path='dynamic/pages/pages-build-deployment',status='completed',conclusion=c) for c in ['cancelled','success']]
        self.assertEqual(self.publicar([dict(commit='correcto',status='errored')],runs),[])

    def test_espera_publicacion_en_curso_del_mismo_commit(self):
        self.assertEqual(self.publicar([dict(commit='correcto',status='errored'),dict(commit='correcto',status='built')],[]),[10])

    def test_otra_version_o_action_principal_no_confirman_pages(self):
        runs=[dict(head_sha='otro',path='dynamic/pages/pages-build-deployment',status='completed',conclusion='success'),
              dict(head_sha='correcto',path='.github/workflows/actualizar.yml',status='completed',conclusion='success')]
        self.assertEqual(self.publicar([dict(commit='correcto',status='errored'),dict(commit='correcto',status='built')],runs),[10])

    def test_solo_cancelados_no_se_dan_por_publicados(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{'GITHUB_REPOSITORY':'owner/repo'}):
            def fake(args,**kwargs):
                text='correcto' if args[:2]==['git','rev-parse'] else ''
                if args[-1].endswith('/pages/builds/latest'):text=json.dumps(dict(commit='correcto',status='errored'))
                if '/actions/runs?' in args[-1]:text=json.dumps({'workflow_runs':[dict(head_sha='correcto',path='dynamic/pages/pages-build-deployment',status='completed',conclusion='cancelled')]})
                return subprocess.CompletedProcess(args,0,text,'')
            with self.assertRaises(RuntimeError):g.publicar(Path(d),fake,lambda n:None)
            self.assertFalse((Path(d)/'reportes/publicacion.json').exists())
