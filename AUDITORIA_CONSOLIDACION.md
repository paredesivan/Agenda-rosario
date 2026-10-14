# Comparación de paquetes y GitHub

Revisión 14/10/2026. Base: `afbe9d2bc259295830e6250d232a53e7bece5536`.

| Paquete inspeccionado | Resultado |
| --- | --- |
| agenda_rosario_timeout_microteatro.zip | Pendiente: integrar precio de producto y límites de ejecución sobre los archivos vigentes. Integrado en este paquete, sin requerir ejecutar reparar_agenda.py. |
| agenda_rosario_correccion_segura.zip | auditar_fuentes.py, corregir_pausas.py y sus tests coinciden con GitHub; las pausas ya están presentes en el recolector. No reenviar versiones viejas. |
| agenda_rosario_auditoria_preventiva.zip | Auditoría posterior ya presente. Política actualizada para reflejar la decisión de consulta factual acotada. |
| control_fuentes_salidas_rosario.zip | Pendiente de adaptar al esquema: registro de Disfruta Rosario incorporado; cinco funciones ya existentes, sin duplicarlas. |
| auditoria_disfruta_rosario(1).json | Auditoría incompleta: conserva referencia manual; no habilita consulta automática. |
| fuentes_adicionales_rosario.zip de este chat | Sustituido: se implementa consulta automática limitada en vez de dejar indiscriminadamente las tres fuentes en consulta manual. |
| agenda_rosario_actualizada.zip y agenda_rosario_precios_ticketek.zip | Versiones de interfaz de 4 KB frente a la actual de 17 KB. El recolector actual incorpora más fuentes y funciones. No usar para reemplazar el código vigente. |
| ampliacion_agenda_rosario.zip | Recolector antiguo; sus mejoras están contenidas y ampliadas en el actual. No restaurarlo. |
| agenda_rosario_actualizacion.zip | Recolector inicial anterior a pausas y ampliaciones actuales. No restaurarlo. |
| agenda_rosario_web.zip | HTML inicial anterior a la interfaz separada actual. No restaurarlo. |

## Cambios técnicos finales

- `fuentes_nuevas.py`: precio de producto Microteatro y conexión con el recolector adicional.
- `fuentes_adicionales.py`: hechos y enlaces, localidad exacta, fechas completas,
  comprobación contra registros oficiales, candidatos separados, caché,
  solicitudes condicionales, robots, pausas y cupo diario de fichas.
- `fuentes_adicionales.json`: registro y decisiones explícitas de alcance.
- `eventos_verificados_adicionales.json`: completar metadatos de funciones ya
  presentes sin reemplazar precios ni importar una segunda copia.
- `.github/workflows/actualizar.yml`: límites de tiempo, disparadores para archivos
  nuevos y persistencia de caché y candidatos entre ejecuciones.
- `tests/test_fuentes_adicionales.py`: verificación de hechos, precios, años,
  otras ciudades, bloqueos, robots, caché, Retry-After y límites diarios.

## Comprobación

24 pruebas pasadas. La comprobación HTTP pudo consultar las tres páginas y
robots. Primera revisión del módulo: tres coincidencias de EntradaFan con
registros oficiales, cuatro referencias de Rosario Times y 24 candidatos de
SalePlan pendientes; cero importaciones nuevas con respaldo oficial.
La revisión posterior del parser de EntradaFan comprobó también las filas HTML
con fecha ISO, porque el JSON-LD del sitio sólo incluía algunas funciones.

La interfaz publicada y los archivos de datos no se reemplazan con snapshots.
El ZIP incluye únicamente código/configuración/documentación a actualizar.
La caché y los candidatos se generan al ejecutar Actions; no se entrega una
instantánea local para hacerla pasar por una actualización publicada.

Esta comparación cubre los paquetes disponibles localizados por nombre en los
archivos del proyecto, no afirma acceso a todas las conversaciones históricas.
