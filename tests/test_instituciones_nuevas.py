import unittest
from instituciones_nuevas import es_formacion, ficha_cec, ficha_ucsf


def cec(nombre='La hija sin cabeza', fecha='22/10/2026', hora='20:00 - 21:00', cuerpo=None):
    cuerpo = cuerpo or 'Jueves 22 de octubre, 20 h. Entradas a la venta próximamente. En el CEC, Rosario.'
    return f'''<html><main><h1>{nombre}</h1><article><p>{cuerpo}</p>
        <div><b>Fecha</b><span>{fecha}</span></div><div><b>Hora</b><span>{hora}</span></div>
        <div>Centro de Expresiones Contemporáneas, Rosario</div></article></main></html>'''


def ucsf(cuerpo=None, fecha='2026-10-31'):
    cuerpo = cuerpo or ('La propuesta es libre, gratuita y abierta a toda la comunidad. '
                      'Rosario. Punto de encuentro: Galería Rosario, Peatonal San Martín 862.')
    return f'''<html><main><h1>Rosario Moderna</h1><p>{cuerpo}</p>
    <h2>Detalles</h2><div>Fecha: 31 de octubre ({fecha})</div>
    <div>Hora: 16:00 - 19:00</div><h2>Local</h2>
    <div>UCSF Sede Rosario, Moreno 1056, Rosario</div></main></html>'''


class Formacion(unittest.TestCase):
    def test_cursos_excluidos(self):
        for nombre in ('Curso de fotografía', 'Taller de teatro', 'Workshop de diseño',
                       'Capacitación en liderazgo', 'Inscripción al curso de guitarra',
                       'Clase abierta de dibujo', 'Jornada de capacitación en tecnología',
                       'Charla-taller: diseñando el futuro', 'Convocatoria abierta a artistas'):
            with self.subTest(nombre=nombre):
                self.assertTrue(es_formacion(nombre))

    def test_no_falsos_positivos(self):
        for nombre in ('Encuentro de Academias y Talleres de Danza Folclórica',
                       'Festival de diseño con workshops', 'Charla sobre formación cultural',
                       'Presentación de libro', 'Concierto', 'Muestra de estudiantes'):
            with self.subTest(nombre=nombre):
                self.assertFalse(es_formacion(nombre))

    def test_categoria_formacion(self):
        self.assertTrue(es_formacion({'nombre': 'Introducción al cine', 'categorias': ['Aprendizaje']}))


class CEC(unittest.TestCase):
    def test_funcion_precisa(self):
        e = ficha_cec(cec(), 'https://www.cecrosario.gob.ar/events/obra/')[0]
        self.assertEqual((e['fecha'], e['hora'], e['hora_fin']), ('2026-10-22', '20:00', '21:00'))
        self.assertEqual(e['precio'], None)
        self.assertEqual(e['lugar'], 'Centro de Expresiones Contemporáneas (CEC)')

    def test_precio_y_edad_no_inventados(self):
        e = ficha_cec(cec(nombre='Gregorio Imaginario', fecha='31/10/2026', hora='17:30',
                          cuerpo='Sábado 31 de octubre, 17:30hs. CEC Rosario. Entrada general: $18.000.'),
                      'https://www.cecrosario.gob.ar/events/gregorio/')[0]
        self.assertEqual(e['precio'], 18000)
        self.assertNotIn('edad_minima', e)

    def test_multidia_con_horarios_independientes(self):
        raw = cec(nombre='DENSO: Encuentro de Diseño Rosarino', fecha='17 - 18/10/2026',
                  hora='Todo el día', cuerpo='''Centro de Expresiones Contemporáneas, Rosario.
                  Público general. Sábado 17 de octubre de 13 a 20 hs.
                  Domingo 18 de octubre de 15 a 18hs.''')
        eventos = ficha_cec(raw, 'https://www.cecrosario.gob.ar/events/denso/')
        self.assertEqual([(e['fecha'], e['hora'], e['hora_fin']) for e in eventos],
                         [('2026-10-17', '13:00', '20:00'), ('2026-10-18', '15:00', '18:00')])

    def test_multidia_sin_cronograma_rechazado(self):
        with self.assertRaises(ValueError):
            ficha_cec(cec(fecha='17 - 18/10/2026', hora='Todo el día'), 'https://www.cecrosario.gob.ar/events/denso/')

    def test_fechas_y_horas_invalidas(self):
        for fecha, hora in [('31/02/2026', '20:00'), ('22/10/2026', '99:00'), ('22/10/2026', '20:00 - 19:00')]:
            with self.subTest(fecha=fecha, hora=hora), self.assertRaises(ValueError):
                ficha_cec(cec(fecha=fecha, hora=hora), 'https://www.cecrosario.gob.ar/events/obra/')

    def test_sin_acceso_publico_rechazado(self):
        with self.assertRaises(ValueError):
            ficha_cec(cec(cuerpo='Actividad de inscripción privada en el CEC Rosario.'),
                      'https://www.cecrosario.gob.ar/events/obra/')

    def test_cursos_rechazados(self):
        with self.assertRaises(ValueError):
            ficha_cec(cec(nombre='Taller de danza'), 'https://www.cecrosario.gob.ar/events/taller/')


class UCSF(unittest.TestCase):
    def test_priorizar_sede_real(self):
        e = ficha_ucsf(ucsf(), 'https://www.ucsf.edu.ar/evento/rosario-moderna/')[0]
        self.assertEqual((e['fecha'], e['hora'], e['hora_fin']), ('2026-10-31', '16:00', '19:00'))
        self.assertEqual(e['lugar'], 'Galería Rosario')
        self.assertEqual(e['direccion'], 'Peatonal San Martín 862, Rosario')
        self.assertEqual(e['precio'], 0)

    def test_sin_punto_encuentro_no_usa_domicilio_institucional(self):
        with self.assertRaises(ValueError):
            ficha_ucsf(ucsf(cuerpo='Entrada libre y gratuita en Rosario.'),
                       'https://www.ucsf.edu.ar/evento/actividad/')

    def test_fecha_ausente_o_falsa(self):
        with self.assertRaises(ValueError):
            ficha_ucsf(ucsf(fecha='2026-02-31'), 'https://www.ucsf.edu.ar/evento/actividad/')

    def test_evento_no_publico(self):
        with self.assertRaises(ValueError):
            ficha_ucsf(ucsf(cuerpo='Reunión interna. Punto de encuentro: Galería Rosario, San Martín 862.'),
                       'https://www.ucsf.edu.ar/evento/actividad/')


if __name__ == '__main__':
    unittest.main()
