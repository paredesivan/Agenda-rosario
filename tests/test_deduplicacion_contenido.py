"""Regresiones compartidas por la publicación y la vista del navegador."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path
from actualizar_eventos import sin_repetidos

BASE = dict(fecha='2026-10-22', hora='17:00', nombre='Encuentro de fotografía',
            lugar='Centro Cultural Parque de España',
            descripcion='Encuentro abierto de fotografía documental con artistas locales para recorrer imágenes históricas del barrio portuario.',
            origen='Agenda Cultural Rosario')

CASOS = [
    ('descripcion_similar', BASE, dict(BASE, nombre='Fotografía del barrio portuario',
        descripcion='Encuentro abierto de fotografía documental con artistas locales: recorrer imágenes históricas del barrio portuario.'), 1),
    ('sede_abreviada', BASE, dict(BASE, lugar='Parque España'), 1),
    ('sede_con_error', BASE, dict(BASE, lugar='Centro Cultural Parque de Espana'), 1),
    ('error_tipografico', dict(BASE, lugar='Galería La Tertulia'), dict(BASE, lugar='Galeria La Tertulíaa'), 1),
    ('hora_sin_cero', dict(BASE, hora='9:00–12:00'), dict(BASE, hora='09:00'), 1),
    ('otra_fecha', BASE, dict(BASE, fecha='2026-10-23'), 2),
    ('otra_hora', BASE, dict(BASE, hora='18:00'), 2),
    ('sin_hora', dict(BASE, hora='Horario a confirmar'), dict(BASE, hora='Horario a confirmar'), 2),
    ('sin_fecha', dict(BASE, fecha=''), dict(BASE, fecha=''), 2),
    ('otra_sede', BASE, dict(BASE, lugar='Parque Independencia'), 2),
    ('otra_sala', dict(BASE, lugar='Centro Cultural Parque España Sala 1'), dict(BASE, lugar='Centro Cultural Parque España Sala 2'), 2),
    ('otra_sala_con_nombre', dict(BASE, lugar='Centro Cultural Parque España Sala Borges'), dict(BASE, lugar='Centro Cultural Parque España Sala Cortázar'), 2),
    ('otra_direccion_numero', dict(BASE, lugar='Espacio Cultural 123'), dict(BASE, lugar='Espacio Cultural 124'), 2),
    ('sin_sede', dict(BASE, lugar=''), dict(BASE, lugar=''), 2),
    ('muestras_distintas_captura', dict(BASE, nombre='La Realidad oculta', lugar='Galería de Arte La Tertulia',
        descripcion='Muestras y Exposiciones: La Realidad oculta, en Galería de Arte La Tertulia. Información publicada por Agenda Cultural Rosario.'),
        dict(BASE, nombre='Poesía enmarcada', lugar='Galería de Arte La Tertulia',
        descripcion='Muestras y Exposiciones: Poesía enmarcada, en Galería de Arte La Tertulia. Información publicada por Agenda Cultural Rosario.'), 2),
    ('descripcion_generica_identica', dict(BASE, nombre='A favor de la fantasía', descripcion='El museo inaugura su programa curatorial anual con una selección de obras locales e internacionales.'),
        dict(BASE, nombre='Nivel de Río. Instalación de Maxi Murad', descripcion='El museo inaugura su programa curatorial anual con una selección de obras locales e internacionales.'), 2),
    ('solo_plantilla', dict(BASE, nombre='Retratos del río', descripcion='Muestras y exposiciones. Información publicada por Agenda Cultural Rosario.'),
        dict(BASE, nombre='Esculturas modernas', descripcion='Muestras y exposiciones. Información publicada por Agenda Cultural Rosario.'), 2),
]

DOMICILIO = dict(BASE, lugar='Casa de Cultura Barrial', direccion='ROCA JULIO N 4253, Rosario, Santa Fe')
CASOS += [
    ('direccion_dentro_sede', DOMICILIO, dict(BASE, lugar='Casa de Cultura Barrial, Roca 4253'), 1),
    ('calle_orden_invertido', dict(BASE, lugar='Secretaría de Cultura', direccion='DEL VALLE ARISTOBULO 2734, Rosario'), dict(BASE, lugar='Secretaría de Cultura, Av. Aristóbulo del Valle 2734'), 1),
    ('sede_sin_domicilio_no_presume', dict(BASE, lugar='Casa de Cultura Barrial'), dict(BASE, lugar='Casa de Cultura Barrial, Roca 4253'), 2),
    ('calle_distinta_misma_altura', DOMICILIO, dict(BASE, lugar='Casa de Cultura Barrial, Belgrano 4253'), 2),
    ('altura_distinta', DOMICILIO, dict(BASE, lugar='Casa de Cultura Barrial, Roca 4254'), 2),
    ('domicilio_con_localidad', DOMICILIO, dict(BASE, lugar='Casa de Cultura Barrial, Roca 4253, Rosario'), 1),
    ('domicilio_con_provincia_y_pais', DOMICILIO,
     dict(BASE, lugar='Casa de Cultura Barrial, Roca 4253, Rosario, Santa Fe, Argentina'), 1),
    ('otra_altura_con_localidad', DOMICILIO, dict(BASE, lugar='Casa de Cultura Barrial, Roca 4254, Rosario'), 2),
    ('otra_sala_con_localidad', dict(DOMICILIO, lugar='Casa de Cultura Barrial Sala Norte'),
     dict(BASE, lugar='Casa de Cultura Barrial Sala Sur, Roca 4253, Rosario'), 2),
    ('altura_bis', DOMICILIO, dict(BASE, lugar='Casa de Cultura Barrial, Roca 4253 bis'), 2),
    ('otra_sala_con_direccion', dict(DOMICILIO, lugar='Casa de Cultura Barrial Sala Norte'), dict(BASE, lugar='Casa de Cultura Barrial Sala Sur, Roca 4253'), 2),
    ('otra_hora_con_direccion', DOMICILIO, dict(BASE, lugar='Casa de Cultura Barrial, Roca 4253', hora='19:00'), 2),
]

CINE = dict(BASE, lugar='Centro Cultural Cine del Barrio', descripcion='')
PELÍCULA = dict(CINE, nombre='Historia del puerto', origen='Cine del Barrio',
                evento_url='https://cine.example/pelicula/puerto/',
                ciclo_nombre='Ciclo: Historias de la ciudad', ciclo_url='https://cine.example/ciclo/ciudad/')
CICLO = dict(CINE, nombre='Ciclo / Historias de la ciudad', origen='Agenda Cultural Rosario')
CASOS += [
    ('titulo_con_sede_y_subtitulo', dict(CINE, nombre='Casa de artistas en Cine del Barrio'),
     dict(CINE, nombre='Casa de artistas. Una historia colectiva'), 1),
    ('en_como_parte_del_titulo', dict(CINE, nombre='Noche en la ciudad'),
     dict(CINE, nombre='Noche. Una historia colectiva'), 2),
    ('sede_dentro_titulo_distinta', dict(CINE, nombre='Casa de artistas en Cine del Centro'),
     dict(CINE, nombre='Casa de artistas. Una historia colectiva'), 2),
    ('ciclo_y_pelicula_documentados', PELÍCULA, CICLO, 1),
    ('ciclo_sin_enlace_no_presume', dict(PELÍCULA, ciclo_url=''), CICLO, 2),
    ('ciclo_otro_horario', PELÍCULA, dict(CICLO, hora='18:00'), 2),
    ('ciclo_otra_sala', PELÍCULA, dict(CICLO, lugar='Cine del Barrio Sala 2'), 2),
]

class DeduplicacionContenido(unittest.TestCase):
    def test_publicacion(self):
        for nombre, a, b, cantidad in CASOS:
            for orden in ([a, b], [b, a]):
                with self.subTest(caso=nombre, primero=orden[0]['nombre']):
                    self.assertEqual(len(sin_repetidos(orden)), cantidad)

    @unittest.skipUnless(shutil.which('node'), 'Node no está instalado')
    def test_navegador_mismos_casos(self):
        codigo = (Path(__file__).resolve().parents[1] / 'agenda.js').read_text()
        codigo = codigo.split('function acrAvailable(')[0]
        codigo += '\nconst casos = ' + json.dumps(CASOS) + ';\n'
        codigo += '''for (const [nombre, a, b, cantidad] of casos) {
          for (const orden of [[a,b],[b,a]]) {
            if (deduplicatedEvents(orden).length !== cantidad) throw Error(nombre);
          }
        }'''
        subprocess.run(['node', '-e', codigo], check=True, capture_output=True, text=True)

    def test_ciclo_con_dos_peliculas_simultaneas_queda_sin_unificar(self):
        peliculas = [PELÍCULA, dict(PELÍCULA, nombre='Memoria del bosque'), CICLO]
        self.assertEqual(len(sin_repetidos(peliculas)), 3)
        codigo = (Path(__file__).resolve().parents[1] / 'agenda.js').read_text().split('function acrAvailable(')[0]
        codigo += '\nif (deduplicatedEvents(' + json.dumps(peliculas) + ').length !== 3) throw Error("ciclo ambiguo");'
        subprocess.run(['node', '-e', codigo], check=True, capture_output=True, text=True)

    def test_prioriza_oficial_y_no_modifica_originales(self):
        oficial = dict(BASE, origen='Centro Cultural Parque de España', evento_url='https://ccpe.org.ar/evento', precio=2500)
        copia = json.loads(json.dumps(BASE))
        for orden in ([BASE, oficial], [oficial, BASE]):
            self.assertEqual(sin_repetidos(orden), [oficial])
        self.assertEqual(BASE, copia)

    def test_deduplica_despues_de_proteger_respaldos(self):
        import tempfile
        from datetime import date
        from unittest.mock import patch
        import actualizacion_segura as segura
        oficial = dict(BASE, origen='Centro Cultural Parque de España', evento_url='https://ccpe.org.ar/evento')
        datos, avisos = segura.proteger({'eventos': [BASE]}, {'eventos': [oficial]}, date(2026, 10, 22))
        self.assertEqual(len(datos['eventos']), 2)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'eventos.json').write_text(json.dumps(datos))
            with patch.object(segura, 'ROOT', root), patch.object(segura, 'ETAPAS', [('fuente_prueba.py', 1)]), patch.object(segura, 'ejecutar_etapa', return_value={'estado': 'validada'}):
                segura.main()
            self.assertEqual(json.loads((root / 'eventos.json').read_text())['eventos'], [oficial])
