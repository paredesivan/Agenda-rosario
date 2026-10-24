"""Regresiones de cobertura: hechos de fichas reales y casos ambiguos."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from bs4 import BeautifulSoup
import actualizar_eventos as a
from cobertura_fuentes import horizonte_dias

ROOT = Path(__file__).resolve().parent
HOY = date(2026, 10, 24)


def html(value):
    return BeautifulSoup(value, 'html.parser')


def ficha(titulo='Actividad', reglas='', descripcion='', etiqueta='Infancias'):
    return html(f'<main><h1>{titulo}</h1><div class="etiqueta-actividad">{etiqueta}</div>'
                f'<div class="descripcion">{descripcion}</div><div class="cuando-fechas">{reglas}</div></main>')


def regla(sede='Sala Uno', fecha='DEL 24 AL 31 DE Octubre', hora='De 15 a 19 horas', acceso='Gratis'):
    return (f'<div class="rule"><span class="rule-fechas">{fecha}</span>'
            '<span class="rule-dias">Sábado</span>'
            f'<span class="rule-hora">{hora}</span><p class="title-lugar">{sede}</p>'
            f'<p class="direccion-lugar">Calle 123</p><div class="entrada-actividad">{acceso}</div></div>')


class CoberturaReal(unittest.TestCase):
    def test_recupera_59_fechas_y_74_con_el_horizonte_ampliado(self):
        recuperados = []
        for nombre, esperado, hora, precio in [('pokemon', 5, '15:00', 0), ('granja', 22, '10:00', 1000),
                ('jardin', 14, '13:00', 1000), ('isla', 14, '14:00', 1000), ('siestario', 4, '15:00', 0)]:
            with self.subTest(ficha=nombre):
                soup = html((ROOT/'fixtures/cobertura'/f'{nombre}.html').read_text())
                diagnostico = {}
                eventos = a.extraer_eventos(soup, f'https://www.rosario.gob.ar/inicio/{nombre}', HOY, diagnostico)
                cerca = [e for e in eventos if e['fecha'] <= '2026-11-23']
                self.assertEqual(len(cerca), esperado)
                self.assertTrue(all(e['hora'] == hora and e['precio'] == precio for e in eventos))
                self.assertEqual(diagnostico['funciones'], len(eventos))
                self.assertEqual(len({a.clave(e) for e in eventos}), len(eventos))
                recuperados.extend(eventos)
        self.assertEqual(len(recuperados), 74)
        self.assertEqual(sum(e['fecha'] <= '2026-11-23' for e in recuperados), 59)
        self.assertEqual(len(a.sin_repetidos(recuperados)), 74)

    def test_horizonte_configurable_y_no_fecha_invalida(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'config.json'
            self.assertEqual(horizonte_dias(path), 180)
            path.write_text('{"dias_futuros":60}')
            self.assertEqual(horizonte_dias(path), 60)
            for valor in [0, 367, '180', True]:
                path.write_text(json.dumps({'dias_futuros': valor}))
                with self.assertRaises(ValueError): horizonte_dias(path)
        bad = html(regla(fecha='DEL 31 DE Febrero AL 31 DE Marzo'))
        self.assertEqual(a.fechas_regla(bad, HOY), [])

    def test_horizonte_recupera_venta_futura_sin_duplicar_turnos(self):
        fecha = a.fechas_publicadas('Sábado 5 de diciembre de 2026 a las 13:00 Hs. Sábado 5 de diciembre de 2026 a las 19:00 Hs.', HOY)
        self.assertEqual(fecha, [('2026-12-05', '13:00'), ('2026-12-05', '19:00')])
        with patch.object(a, 'HORIZONTE_DIAS', 30):
            self.assertEqual(a.fechas_publicadas('Lunes 30 de noviembre de 2026 a las 20:00 Hs.', HOY), [])
        self.assertEqual(a.fechas_publicadas('Lunes 30 de noviembre de 2026 a las 20:00 Hs.', HOY), [('2026-11-30', '20:00')])


class NoInventarFunciones(unittest.TestCase):
    def test_precio_general_no_se_vuelve_gratis_por_menores(self):
        soup = ficha(reglas=regla(acceso='Paga. $1000'), descripcion='Entrada general $1.000. Menores de 4 años gratis.')
        self.assertTrue(all(e['precio'] == 1000 for e in a.extraer_eventos(soup, 'https://fuente.test/x', HOY)))
        soup = ficha(reglas=regla(acceso='Paga. Consultar'), descripcion='Menores de cuatro años gratis.')
        eventos = a.extraer_eventos(soup, 'https://fuente.test/x', HOY)
        self.assertTrue(eventos)
        self.assertTrue(all(e['precio'] is None for e in eventos))

    def test_cursos_siguen_excluidos_y_dejan_motivo(self):
        diagnostico = {}
        soup = ficha('Curso de teatro para infancias', regla())
        self.assertEqual(a.extraer_eventos(soup, 'https://fuente.test/x', HOY, diagnostico), [])
        self.assertIn('formación', diagnostico['motivos'][0])

    def test_no_cruza_horarios_sedes_ni_precios(self):
        soup = ficha(reglas=regla('Sala Uno', hora='15:00', acceso='Gratis') +
                     regla('Sala Dos', hora='18:00', acceso='Paga. $2000'))
        eventos = a.extraer_eventos(soup, 'https://fuente.test/x', HOY)
        self.assertEqual({(e['lugar'],e['hora'],e['precio']) for e in eventos},
                         {('Sala Uno','15:00',0),('Sala Dos','18:00',2000)})

    def test_horas_ambiguas_no_se_inventan(self):
        soup = ficha(reglas=regla(hora=''), descripcion='Visitas de 10 a 12 h y de 15 a 19 h.')
        eventos = a.extraer_eventos(soup, 'https://fuente.test/x', HOY)
        self.assertTrue(eventos)
        self.assertTrue(all(e['horario_pendiente'] and e['hora'] == 'Horario a confirmar' for e in eventos))

    def test_cierre_no_es_segunda_funcion(self):
        soup = ficha(reglas='<time datetime="2026-10-30T19:00:00-03:00"><span class="hora-desde">19</span></time>'
                     '<time datetime="2026-10-30T23:59:00-03:00"><span class="hora-hasta">23:59</span></time>'
                     '<p class="title-lugar">Sala</p><div class="entrada-actividad">Gratis</div>')
        eventos = a.extraer_eventos(soup, 'https://fuente.test/x', HOY)
        self.assertEqual([(e['fecha'],e['hora']) for e in eventos], [('2026-10-30','19:00')])

    def test_sin_sede_no_publica_y_diagnostica(self):
        soup = ficha(reglas=regla().replace('<p class="title-lugar">Sala Uno</p>',''))
        diagnostico = {}
        self.assertEqual(a.extraer_eventos(soup, 'https://fuente.test/x', HOY, diagnostico), [])
        self.assertIn('Bloque sin sede verificable', diagnostico['motivos'])

    def test_falla_http_queda_registrada_sin_mentir_extraccion_vacia(self):
        import requests
        with patch.object(a, 'descargar', side_effect=requests.Timeout('timeout de prueba')):
            url, eventos, error, eliminado = a.consultar_evento('https://fuente.test/falla', HOY)
        self.assertEqual(eventos, [])
        self.assertTrue(error)
        self.assertFalse(eliminado)
        self.assertIn('error', a.DIAGNOSTICO_MUNICIPAL[url])
