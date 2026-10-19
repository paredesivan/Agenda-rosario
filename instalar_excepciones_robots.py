"""Instala excepciones por auditoría en fuentes_adicionales.py sin borrar pruebas.
Ejecutar desde raíz de Agenda-rosario: python instalar_excepciones_robots.py
"""
from pathlib import Path
import json

root = Path(__file__).resolve().parent
file = root / 'fuentes_adicionales.py'
original = file.read_text(encoding='utf-8')
marker = '    def robots(self, url):\n'
helper = '''    def excepcion_robots_auditada(self, url):
        """Sólo para rutas públicas con auditoría separada y explícita.

        Una regla robots no constituye por sí sola una restricción de acceso.
        Ausencia o incertidumbre en la auditoría mantiene el bloqueo.
        """
        registro = ROOT / 'excepciones_robots.json'
        try:
            reglas = json.loads(registro.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return False
        if not isinstance(reglas, dict):
            return False
        destino = urlsplit(url)
        if destino.scheme != 'https' or destino.username or destino.password:
            return False
        entradas = reglas.get('excepciones', [])
        if not isinstance(entradas, list):
            return False
        for entrada in entradas:
            if not isinstance(entrada, dict):
                continue
            if entrada.get('dominio') != destino.hostname:
                continue
            rutas = entrada.get('rutas_publicas', [])
            if not isinstance(rutas, list) or not any(
                isinstance(ruta, str) and ruta.startswith('/') and
                (destino.path == ruta or destino.path.startswith(ruta.rstrip('/') + '/'))
                for ruta in rutas
            ):
                continue
            if (entrada.get('acceso_publico_verificado') is True
                    and entrada.get('terminos_revisados') is True
                    and entrada.get('sin_prohibicion_contractual_aplicable') is True
                    and entrada.get('sin_barrera_tecnica') is True
                    and entrada.get('revision_legal') == 'sin_impedimento_identificado'
                    and isinstance(entrada.get('evidencia'), str)
                    and len(entrada['evidencia'].strip()) >= 20):
                return True
        return False

'''
old = "        if not parser.can_fetch(UA, url):\n            raise ValueError('ruta excluida por robots.txt')"
new = "        if not parser.can_fetch(UA, url) and not self.excepcion_robots_auditada(url):\n            raise ValueError('ruta excluida por robots.txt; excepción sin auditoría suficiente')"
if 'def excepcion_robots_auditada(' not in original:
    if original.count(marker) != 1 or original.count(old) != 1:
        raise SystemExit('No se reconoce la versión del recolector; no se modificó nada.')
    updated = original.replace(marker, helper + marker).replace(old, new)
    compile(updated, str(file), 'exec')
    file.write_text(updated, encoding='utf-8')
else:
    print('La excepción ya está instalada.')

policy = root / 'excepciones_robots.json'
if not policy.exists():
    policy.write_text(json.dumps({
        'version': 1,
        'excepciones': []
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Instalación completada. Ninguna fuente excluida se habilita sin auditoría.')
