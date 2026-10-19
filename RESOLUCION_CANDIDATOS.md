# Resolución automática de candidatos

`Actualizar agenda` ejecuta `resolver_candidatos.py` después de los recolectores
principales y de `fuentes_ampliadas.py`. No requiere ejecutar otra tarea ni
editar una lista de espectáculos. El disparador programado continúa cada dos
horas.

## Recorrido de una publicación nueva

1. Los listados públicos descubren las URLs de Rosario Times, EntradaFan,
   SalePlan, Planaxia y las novedades del Politécnico en cada actualización,
   sujeto a la caché ya configurada para cada fuente.
2. Una cola persistente revisa primero URLs nuevas y luego las menos recientes.
   La lectura de fichas conserva la caché de 24 h y una cuota de cuatro fichas
   por dominio por día. Los descartes se vuelven a comprobar semanalmente.
   Una URL diferida por cuota conserva su prioridad para el próximo turno.
3. Se extraen campos factuales de la ficha propia, nunca una recomendación
   lateral. Los medios y la reventa se cruzan por título, fecha, hora y sede
   con fuentes primarias o con ACR, aceptada por el proyecto como respaldo.
4. Se leen los enlaces oficiales de los artículos sólo en dominios ya
   configurados y auditados. Una ficha primaria estructurada válida puede
   incorporar un evento nuevo, incluso sin una ficha previa en la agenda.
   Las noticias institucionales necesitan fecha completa, sede Rosario y
   acceso público. Se excluyen cursos y avisos administrativos.
5. Un evento con fecha completa y sin hora usa `Horario a confirmar`. Nunca se
   usa la fecha de la noticia como fecha del acto, el año del reloj para suplir
   un año ausente, ni el encabezado general de SalePlan para fechar funciones.
   El año de publicación de Planaxia sólo sirve para buscar corroboración.
6. Las fichas oficiales gestionadas por este resolver se vuelven a leer. Un
   cambio válido de horario reemplaza las funciones de esa URL; una cancelación
   explícita las retira. Los fallos conservan los eventos anteriores. El
   protector de la actualización aislada reconoce cada revisión válida.

## Diagnóstico

`revision_resolucion_candidatos.json` distingue, por URL y fuente:

- `publicado`: se procesaron funciones primarias publicables; no equivale al
  número neto de eventos nuevos, porque se deduplican contra la agenda.
- `corroborado`: hay respaldo prioritario ya publicado.
- `descartado`: funciones vencidas, formación, aviso administrativo o una
  cancelación identificable.
- `pendiente`: el contenido no alcanza para verificar el evento. El motivo
  indica los campos o la ficha primaria que faltan; se reintenta automáticamente.
- `reintentar`: fallo de acceso o cuota con motivo concreto.
- `diferido`: otra URL ocupa el turno acotado de esta ejecución.

La misma resolución se anota en los archivos `candidatos_*.json` y el resumen
actualiza `fuentes_revisadas.json`. La cola y el diagnóstico sobreviven a las
actualizaciones aisladas y se guardan con el commit automático del workflow.
Los fallos del listado tampoco vacían el último conjunto descubierto.

## Alcance de acceso

Se reutilizan el User-Agent, robots, pausas, timeouts y transporte del proyecto.
No se siguen redirecciones, rutas privadas, `/go/`, APIs no auditadas, redes
sociales ni dominios nuevos encontrados casualmente en una nota. El acceso
público no se presenta como una licencia de textos o imágenes. No se guardan
artículos completos, afiches, sinopsis ni precios de reventa.

No se garantiza que toda publicación pueda convertirse en evento: una nota
sin año, sede o respaldo requiere más evidencia. Un bloqueo 403/429, una ficha
sin estructura compatible o un enlace a un dominio nuevo quedan diagnosticados;
no se completan con datos inventados ni con eventos cargados a mano.

## Validación

La suite incorpora pruebas de una segunda ejecución con una publicación nueva,
actualización del mismo artículo, cancelación posterior, conservación ante
fallos, rotación sin inanición de la cola, cuotas persistentes, exclusión de
cursos, localidad, fechas, horarios desconocidos, URL propia, parámetros de
identidad, fuentes apagadas y ausencia de consultas a dominios arbitrarios.

Ejecutar: `python -m unittest discover -s tests -v`.
