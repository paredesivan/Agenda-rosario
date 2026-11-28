import unittest
from datetime import date
from actualizar_eventos import sin_repetidos
from fuentes_ampliadas import feria_convocatoria, revisar

class CoberturaNoviembre(unittest.TestCase):
    def test_muestra_horario_no_confirmado(self):
        oficial = dict(fecha='2026-12-01', hora='Horario a confirmar', horario_pendiente=True,
                       nombre='Historia de las marchas', lugar='Museo de la Memoria',
                       origen='Municipalidad de Rosario', evento_url='https://www.rosario.gob.ar/inicio/prueba', precio=0)
        copia = dict(oficial, hora='10:00', horario_pendiente=False, origen='Agenda Cultural Rosario',
                     evento_url='https://agenda.example/muestra', descripcion='Muestras y Exposiciones: Historia de las marchas', precio=None)
        self.assertEqual(sin_repetidos([copia, oficial]), [oficial])
        self.assertEqual(len(sin_repetidos([copia, oficial, dict(copia, hora='18:00')])), 3)
        self.assertEqual(len(sin_repetidos([dict(copia, descripcion='Teatro'), oficial])), 2)
    def test_acronimo(self):
        a = dict(fecha='2026-12-01', hora='08:00', nombre='Muestra de arte', lugar='Centro Municipal de Distrito Centro Antonio Berni', origen='Municipalidad de Rosario', evento_url='https://www.rosario.gob.ar/inicio/prueba')
        b = dict(a, lugar='CMD Centro Antonio Berni', origen='Agenda Cultural Rosario', evento_url='https://agenda.example/muestra')
        self.assertEqual(sin_repetidos([b,a]), [a])
    def test_feria(self):
        html = '<h1>Convocatoria abierta Feria de libros</h1><p>La feria se desarrollará los días jueves 10, viernes 11 y sábado 12 de diciembre de 2026. La Feria se realizará en el Centro Cultural Parque de España de 17 a 21 h. Atención al público. Infraestructura gratuita. Inscripción hasta el 20 de noviembre.</p>'
        eventos = feria_convocatoria(html,'https://ccpe.org.ar/web/actividades/prueba/',{})
        self.assertEqual([e['fecha'] for e in eventos], ['2026-12-10','2026-12-11','2026-12-12'])
        self.assertTrue(all(e['hora']=='17:00' and 'precio' not in e for e in eventos))
        self.assertEqual(feria_convocatoria(html.replace('Feria de libros','Residencia de escritores'),'',{}),[])
        self.assertEqual(feria_convocatoria(html+'<p>Se suspende la feria</p>','',{}),[{'cancelado':True}])
        with self.assertRaises(ValueError): feria_convocatoria(html.replace('de 17 a 21 h',''),'',{})
    def test_rotacion(self):
        class Fake:
            def __init__(self): self.cache={}; self.calls=[]; self.t=0
            def reloj(self): self.t+=1; return self.t
            def leer_datos(self,url,parser,horas=2):
                self.calls.append(url)
                if url.endswith('/agenda/'): return parser('<a href="/evento/a/">A</a><a href="/evento/b/">B</a>',url)
                raise ValueError('error de prueba')
        f = dict(nombre='Prueba',listado='https://example.org/agenda/',adaptador='santafe',tipo='oficial',habilitada=True,patron_ficha='^/evento/[^/]+/$',max_fichas_por_fuente=1)
        acceso=Fake()
        for _ in range(2): revisar({'fuentes':[f]},acceso,date(2026,11,28))
        self.assertEqual(acceso.calls[1::2], ['https://example.org/evento/a/','https://example.org/evento/b/'])
