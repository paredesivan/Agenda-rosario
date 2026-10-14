"""Corrección puntual e idempotente de pausas por dominio para Agenda Rosario.

Se ejecuta una sola vez mediante GitHub Actions y guarda en git los cambios a
actualizar_eventos.py y fuentes_nuevas.py. No altera eventos ni fuentes.
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PAUSAS_LITERAL = '''# Pausas solicitadas en robots.txt, revisadas el 14/10/2026.
# La pausa general mínima sigue siendo 1,5 segundos.
PAUSAS_POR_HOST = {
    "bibliotecavigil.org.ar": 60.0,
    "www.metropolitano.ar": 10.0,
    "www.teatrosatir.ar": 10.0,
}

'''


def sustituir_exacto(texto, original, nuevo, esperado, archivo):
    cantidad_original = texto.count(original)
    cantidad_nueva = texto.count(nuevo)
    if cantidad_original == esperado and cantidad_nueva == 0:
        return texto.replace(original, nuevo)
    if cantidad_original == 0 and cantidad_nueva == esperado:
        return texto  # Ya aplicado.
    raise ValueError(
        f"{archivo}: estructura inesperada: originales={cantidad_original}, "
        f"corregidos={cantidad_nueva}; no modificar para evitar errores"
    )


def actualizar_principal(texto):
    nombre = "actualizar_eventos.py"
    ancla = "ULTIMA, BLOQUEADOS, FALLAS = {}, set(), {}"
    if "PAUSAS_POR_HOST =" not in texto:
        if texto.count(ancla) != 1:
            raise ValueError(f"{nombre}: falta el punto de inserción de la configuración")
        texto = texto.replace(ancla, PAUSAS_LITERAL + ancla)
    elif texto.count('"bibliotecavigil.org.ar": 60.0') != 1 or texto.count('"www.teatrosatir.ar": 10.0') != 1:
        raise ValueError(f"{nombre}: pausas preexistentes distintas; revisión manual")
    return sustituir_exacto(
        texto,
        "espera = 1.5 - (monotonic() - ULTIMA.get(host, 0))",
        "espera = max(1.5, PAUSAS_POR_HOST.get(host, 1.5)) - (monotonic() - ULTIMA.get(host, 0))",
        1, nombre)


def actualizar_fuentes(texto):
    nombre = "fuentes_nuevas.py"
    texto = sustituir_exacto(
        texto,
        "from actualizar_eventos import SESION, BLOQUEADOS, ULTIMA, monotonic, sleep\n",
        "from actualizar_eventos import SESION, BLOQUEADOS, ULTIMA, monotonic, sleep, PAUSAS_POR_HOST\n",
        2, nombre)
    return sustituir_exacto(
        texto,
        "espera = 1.5 - (monotonic() - ULTIMA.get(host, 0))",
        "espera = max(1.5, PAUSAS_POR_HOST.get(host, 1.5)) - (monotonic() - ULTIMA.get(host, 0))",
        2, nombre)


def main():
    cambios = []
    for archivo, funcion in (("actualizar_eventos.py", actualizar_principal),
                             ("fuentes_nuevas.py", actualizar_fuentes)):
        ruta = RAIZ / archivo
        original = ruta.read_text(encoding="utf-8")
        nuevo = funcion(original)
        # Validar sintaxis de todo el archivo antes de escribir nada.
        compile(nuevo, str(ruta), "exec")
        cambios.append((ruta, original, nuevo))
    for ruta, original, nuevo in cambios:
        if nuevo != original:
            ruta.write_text(nuevo, encoding="utf-8")
            print("Corregido:", ruta.name)
        else:
            print("Ya estaba corregido:", ruta.name)


if __name__ == "__main__":
    main()
