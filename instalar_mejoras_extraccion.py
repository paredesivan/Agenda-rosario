"""Instalador transaccional de mejoras para extractores de Agenda Rosario.
No modifica fuentes deshabilitadas, cuotas HTTP, robots ni agrega eventos.
La acción de GitHub ejecuta pruebas antes de publicar cambios.
"""
from pathlib import Path

CAMBIOS = {
    'fuentes_nuevas.py': [
        ('if not INTERES.search(titular) or "/seccion/" in link or "/secciones/" in link or "/tag/" in link:',
         'if "/seccion/" in link or "/secciones/" in link or "/tag/" in link:'),
        ('for link in enlaces[:14]:', 'for link in enlaces[:20]:'),
    ],
    'fuentes_ampliadas.py': [
        ("enlaces = list({e['url']: e for e in enlaces}.values())",
         "enlaces = list({e['url'].rstrip('/'): e for e in enlaces}.values())"),
    ],
    'fuentes_adicionales.py': [
        ("    return refs[:24]\n\n\ndef listado_entradafan", 
         "    refs = list({e['referencia'].rstrip('/'): e for e in refs}.values())\n    return refs[:24]\n\n\ndef listado_entradafan"),
    ],
    'resolver_candidatos.py': [
        ("        filas.sort(key=lambda par: (par[1].get('intento', ''), -date.fromisoformat(par[1]['visto']).toordinal(), par[0]))",
         "        filas.sort(key=prioridad_pendiente)"),
        ('def resolver(root=ROOT, acceso=None, hoy=None):',
         """def prioridad_pendiente(par):
    # Primero pendientes sin intento; luego los menos recientes.
    clave, candidato = par
    intento = candidato.get('intento') or ''
    visto = candidato.get('visto') or ''
    return (bool(intento), intento, visto, clave)


def resolver(root=ROOT, acceso=None, hoy=None):"""),
    ],
}

def transformar(originales, validar_sintaxis=True):
    resultado = {}
    for archivo, reglas in CAMBIOS.items():
        codigo = originales[archivo]
        for antes, despues in reglas:
            # Permite reinstalar sin cambios: no duplicar funciones ni bloques.
            if despues in codigo:
                continue
            if codigo.count(antes) == 1:
                codigo = codigo.replace(antes, despues, 1)
            elif codigo.count(despues) != 1:
                raise ValueError('Código inesperado o ancla ambigua: ' + archivo + ': ' + antes[:65])
        resultado[archivo] = codigo
    if validar_sintaxis:
        for archivo, codigo in resultado.items():
            compile(codigo, archivo, 'exec')
    return resultado

def instalar(raiz=None):
    raiz = Path(raiz or Path(__file__).resolve().parent)
    originales = {f: (raiz/f).read_text(encoding='utf-8') for f in CAMBIOS}
    cambios = transformar(originales)
    # Todas las validaciones antes de cualquier escritura.
    for f, texto in cambios.items():
        if texto != originales[f]:
            temporal = (raiz/f).with_suffix('.py.tmp')
            temporal.write_text(texto, encoding='utf-8')
            temporal.replace(raiz/f)
    return [f for f in CAMBIOS if cambios[f] != originales[f]]

if __name__ == '__main__':
    print('Módulos actualizados:', instalar())
