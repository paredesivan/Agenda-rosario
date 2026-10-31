"""Turnos justos y resolución factual de candidatos, sin editar eventos."""
from datetime import date, timedelta


def fecha_valida(valor):
    try:
        return date.fromisoformat(valor)
    except (ValueError, TypeError):
        return None


def resolver_local(candidato, bases, hoy, coincidencia):
    hechos = candidato.get('hechos', [])
    if not hechos:
        return None
    fechas = [fecha_valida(h.get('fecha')) for h in hechos]
    if not all(fechas):
        return None
    if all(f < hoy for f in fechas):
        previo = candidato.get('resultado', {})
        desde = fecha_valida(candidato.get('resuelto_dia'))
        # La fecha cierra la función conocida, nunca declara vacía la página.
        # Se conserva la evidencia y se vuelve a consultar a la semana.
        if previo.get('estado') == 'descartado' and desde and hoy - desde >= timedelta(days=7):
            return None
        return dict(estado='descartado', motivo='Las fechas conocidas están vencidas; evidencia conservada y revisión semanal', funciones=0)
    # No cerrar una ficha si queda cualquier otra función sin corroborar.
    futuras = [h for h, f in zip(hechos, fechas) if f >= hoy]
    matches = [coincidencia(h, bases) for h in futuras]
    if matches and all(matches):
        for e in matches:
            if candidato['fuente'] not in e.setdefault('descubrimiento_fuentes', []):
                e['descubrimiento_fuentes'].append(candidato['fuente'])
        return dict(estado='corroborado', motivo='Todas las funciones futuras ya tienen respaldo prioritario', funciones=len(matches))
    return None


def turnos_justos(filas, prioridad):
    """Alterna nunca consultados y reintentos antiguos; no aumenta las cuotas."""
    nuevas = sorted((p for p in filas if not p[1].get('intento')), key=prioridad)
    antiguas = sorted((p for p in filas if p[1].get('intento')), key=prioridad)
    salida = []
    for i in range(max(len(nuevas), len(antiguas))):
        if i < len(antiguas):
            salida.append(antiguas[i])
        if i < len(nuevas):
            salida.append(nuevas[i])
    return salida
