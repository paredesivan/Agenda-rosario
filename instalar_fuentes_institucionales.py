#!/usr/bin/env python3
"""Instala en Agenda-rosario conectores institucionales en modo seguro.

Ejecutar desde la raíz del repositorio: python instalar_fuentes_institucionales.py
No activa dominios pendientes de auditoría. Idempotente y con copias previas.
"""
from pathlib import Path
from datetime import datetime
import json
import shutil
import sys

PAQUETE = Path(__file__).resolve().parent
ROOT = PAQUETE if (PAQUETE / 'fuentes_ampliadas.py').exists() else PAQUETE.parent
MARCA = '# fuentes_institucionales_20261017'

CANDIDATAS = [
    {
        'nombre': 'CEC Rosario — agenda propia',
        'listado': 'https://www.cecrosario.gob.ar/events/',
        'adaptador': 'cec_evento', 'tipo': 'oficial', 'habilitada': False,
        'patron_ficha': r'^/events/[^/]+/?$', 'selector': 'a[href]',
        'cache_horas': 24, 'max_fichas_dia': 4,
        'motivo': 'Agenda pública comprobada; acceso HTTP directo 403 y robots.txt no verificable en la auditoría 17/10/2026. No activar sin resolver acceso legítimo, robots y condiciones. Adaptador preparado, sin fechas hardcodeadas.'
    },
    {
        'nombre': 'UCSF — agenda de eventos',
        'listado': 'https://www.ucsf.edu.ar/eventos/mes/',
        'adaptador': 'ucsf_evento', 'tipo': 'oficial', 'habilitada': False,
        'patron_ficha': r'^/evento/[^/]+/?$', 'selector': 'a[href]',
        'cache_horas': 24, 'max_fichas_dia': 4,
        'motivo': 'Agenda y ficha pública verificadas, pero robots.txt y términos de automatización no pudieron auditarse completamente. Se exige punto de encuentro real: no usar sede administrativa. No activar hasta revisión.'
    },
    {
        'nombre': 'UCA Rosario — campus y agenda',
        'listado': 'https://uca.edu.ar/es/campus-del-rosario',
        'adaptador': 'enlaces', 'tipo': 'descubrimiento', 'habilitada': False,
        'patron_ficha': r'^/es/eventos/[^/]+/?$', 'selector': 'a[href]',
        'cache_horas': 24,
        'motivo': 'Campus y agenda institucional identificados; rutas de fichas, robots y condiciones de uso aún no auditados. Sin publicaciones automáticas ni cursos.'
    },
    {
        'nombre': 'City Center Rosario — shows',
        'listado': 'https://www.citycenter-rosario.com.ar/es/shows',
        'adaptador': 'enlaces', 'tipo': 'descubrimiento', 'habilitada': False,
        'patron_ficha': r'^/es/show-detail/[^/]+/[^/]+/?$', 'selector': 'a[href]',
        'motivo': 'Cartelera de shows identificada pero listado dinámico sin fichas en HTML; términos de uso sección 4 restringen publicación/retransmisión de contenidos. Robots no auditado. No automatizar sin autorización o revisión jurídica.'
    },
    {
        'nombre': 'Pullman Rosario — eventos',
        'listado': 'https://pullman-rosario.ar/',
        'adaptador': 'enlaces', 'tipo': 'descubrimiento', 'habilitada': False,
        'patron_ficha': r'^/eventos/[^/]+/?$',
        'motivo': 'Hotel con espacios para eventos pero sin agenda pública de funciones verificable; se relaciona con City Center. No activar ni inventar eventos.'
    },
    {
        'nombre': 'Biblioteca Vigil — agenda propia',
        'listado': 'https://bibliotecavigil.org.ar/inicio/',
        'adaptador': 'enlaces', 'tipo': 'descubrimiento', 'habilitada': False,
        'patron_ficha': r'^/inicio/events/[^/]+/?$', 'selector': 'a[href]',
        'cache_horas': 24,
        'motivo': 'La institución publica teatro, visitas y observaciones; robots y condiciones no verificables en esta ejecución. Sus noticias contienen múltiples fechas: requieren adaptador por función. Ya aparece como espacio en catálogos existentes; no publicar duplicados.'
    },
    {
        'nombre': 'Colegio de Arquitectura y Urbanismo D2 — agenda',
        'listado': 'https://d2.capsf.ar/',
        'adaptador': 'enlaces', 'tipo': 'descubrimiento', 'habilitada': False,
        'patron_ficha': r'^/[^/]+/?$', 'selector': 'a[href]',
        'cache_horas': 24,
        'motivo': 'Calendario institucional con muestras, encuentros y cursos mezclados. Robots, términos, acceso público y parser por ficha pendientes; no activar.'
    },
    {
        'nombre': 'Alianza Francesa Rosario — agenda cultural',
        'listado': 'https://afrosario.org.ar/agenda-cultural/',
        'adaptador': 'enlaces', 'tipo': 'descubrimiento', 'habilitada': False,
        'patron_ficha': r'^/[^/]+/?$', 'selector': 'a[href]',
        'cache_horas': 24,
        'motivo': 'Asociación cultural sin fines de lucro con agenda propia. Listado mezcla noticias y fechas antiguas; robots, términos y ficha no auditados. No activar.'
    },
    {
        'nombre': 'Espacio Cultural Faro — Fundación Libertad',
        'listado': 'https://espacioculturalfaro.com.ar/',
        'adaptador': 'enlaces', 'tipo': 'descubrimiento', 'habilitada': False,
        'patron_ficha': r'^/[^/]+/?$', 'selector': 'a[href]',
        'cache_horas': 24,
        'motivo': 'Exhibiciones públicas y cursos en el mismo sitio; no se comprobó agenda fechada por función, robots ni términos. No activar.'
    }
]


def construir(archivos):
    py = archivos['fuentes_ampliadas.py']
    inicio = "from fuentes_adicionales import norm"
    if MARCA not in py:
        if inicio not in py:
            raise ValueError('No se reconoce import de fuentes_ampliadas.py')
        py = py.replace(inicio, inicio + '\nfrom instituciones_nuevas import ficha_cec, ficha_ucsf, es_formacion  ' + MARCA, 1)
    rama = "    if fuente['adaptador'] in ('gamma_comunidad', 'institucion_mec'):"
    nueva = ("    if fuente['adaptador'] == 'cec_evento':\n"
             "        return ficha_cec(contenido, url, fuente)\n"
             "    if fuente['adaptador'] == 'ucsf_evento':\n"
             "        return ficha_ucsf(contenido, url, fuente)\n")
    if nueva not in py:
        if rama not in py:
            raise ValueError('No se reconoce despacho de ficha en fuentes_ampliadas.py')
        py = py.replace(rama, nueva + rama, 1)
    viejo = "if e.get('cancelado') or not hoy.isoformat() <= e['fecha'] <= hasta.isoformat():"
    nuevo = "if e.get('cancelado') or es_formacion(e) or not hoy.isoformat() <= e['fecha'] <= hasta.isoformat():"
    if viejo in py:
        py = py.replace(viejo, nuevo, 1)
    elif nuevo not in py:
        raise ValueError('No se reconoce filtro de fichas de fuentes_ampliadas.py')
    compile(py, 'fuentes_ampliadas.py', 'exec')
    archivos['fuentes_ampliadas.py'] = py

    segura = archivos['actualizacion_segura.py']
    importacion = 'from control_http import atomico'
    if MARCA not in segura:
        if importacion not in segura:
            raise ValueError('No se reconoce import de actualizacion_segura.py')
        segura = segura.replace(importacion, importacion + '\nfrom instituciones_nuevas import es_formacion  ' + MARCA, 1)
    fin = "    atomico(ROOT / 'eventos.json', datos)"
    filtro = "    datos['eventos'] = [e for e in datos['eventos'] if not es_formacion(e)]  " + MARCA + "\n"
    if filtro not in segura:
        if segura.count(fin) != 1:
            raise ValueError('No se reconoce guardado final de actualizacion_segura.py')
        segura = segura.replace(fin, filtro + fin, 1)
    compile(segura, 'actualizacion_segura.py', 'exec')
    archivos['actualizacion_segura.py'] = segura

    config = json.loads(archivos['fuentes_ampliadas.json'])
    if not isinstance(config.get('fuentes'), list):
        raise ValueError('Config de fuentes inválida')
    existentes = {f.get('nombre') for f in config['fuentes']}
    urls = {f.get('listado', '').rstrip('/') for f in config['fuentes']}
    for candidata in CANDIDATAS:
        if candidata['nombre'] not in existentes and candidata['listado'].rstrip('/') not in urls:
            config['fuentes'].append(candidata)
    archivos['fuentes_ampliadas.json'] = json.dumps(config, ensure_ascii=False, indent=2) + '\n'
    return archivos


def instalar(raiz=ROOT):
    raiz = Path(raiz)
    obligatorios = ['fuentes_ampliadas.py', 'actualizacion_segura.py', 'fuentes_ampliadas.json']
    for archivo in obligatorios:
        if not (raiz / archivo).is_file():
            raise ValueError(f'Falta {archivo}; no se escribió nada')
    originales = {nombre: (raiz / nombre).read_text(encoding='utf-8') for nombre in obligatorios}
    resultado = construir(dict(originales))
    destino_modulo = raiz / 'instituciones_nuevas.py'
    destino_tests = raiz / 'tests' / 'test_instituciones_nuevas.py'
    destino_auditoria = raiz / 'AUDITORIA_NUEVAS_INSTITUCIONES.md'
    fuentes = {
        destino_modulo: PAQUETE / 'instituciones_nuevas.py',
        destino_tests: PAQUETE / 'tests' / 'test_instituciones_nuevas.py',
        destino_auditoria: PAQUETE / 'AUDITORIA_NUEVAS_INSTITUCIONES.md',
    }
    for origen in fuentes.values():
        if not origen.is_file():
            raise ValueError(f'Falta en el paquete: {origen}')
    compile(fuentes[destino_modulo].read_text(encoding='utf-8'), str(destino_modulo), 'exec')
    compile(fuentes[destino_tests].read_text(encoding='utf-8'), str(destino_tests), 'exec')
    backup = raiz / ('.respaldo_fuentes_institucionales_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    backup.mkdir(exist_ok=False)
    for nombre in obligatorios:
        shutil.copy2(raiz / nombre, backup / nombre)
    for destino in fuentes:
        if destino.exists():
            copia = backup / destino.relative_to(raiz)
            copia.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destino, copia)
    for nombre, contenido in resultado.items():
        temporal = raiz / (nombre + '.nuevas.tmp')
        temporal.write_text(contenido, encoding='utf-8')
        temporal.replace(raiz / nombre)
    for destino, origen in fuentes.items():
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origen, destino)
    return backup


if __name__ == '__main__':
    try:
        respaldo = instalar()
    except (OSError, ValueError, KeyError) as error:
        sys.exit('No se instaló: ' + str(error))
    print('Código, pruebas y fuentes pendientes incorporados. Respaldo:', respaldo)
    print('Las nuevas fuentes están DESACTIVADAS hasta completar auditoría de robots, condiciones y acceso.')
    print('Ejecutar: python -m unittest discover -s tests -v')
