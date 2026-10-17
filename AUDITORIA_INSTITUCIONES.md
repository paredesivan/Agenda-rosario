# Actividades de instituciones de Rosario

Revisión: 17/10/2026. Base de trabajo: commit 53082fda39d7091edbd250e83d2a587b251cb97e.

## Alcance

Se incorporan conectores de fuentes, no una lista fija de eventos. Se publican
únicamente fichas con fecha completa, hora, sede y dirección en Rosario y acceso
explícito a público general. Las actividades exclusivamente internas o para
profesionales se rechazan. Una convocatoria o inscripción académica no se
transforma en una salida por el solo hecho de figurar en una agenda.

Se reutilizan el control HTTP, robots, las pausas 403/429, la caché y la fusión
por función existentes. Sin fotos, afiches, sinopsis ni recomendaciones médicas.
La descripción guardada se genera con condiciones factuales: inscripción y
cupos limitados. Se enlaza la ficha oficial; nunca se completa una inscripción.

## Revisión por sitio

| Fuente | Robots observado por HTTP | Contenido y condiciones | Decisión |
|---|---|---|---|
| Grupo Gamma, Charlas a la comunidad | 404 en /robots.txt | Se leyó /politica-medios-sociales, enlazada al pie. Incluye los sitios, responsabilidad sobre contenidos y propiedad intelectual; no se encontró autorización expresa de extracción automática ni licencia general. Derechos reservados. El listado se presenta como eventos para la comunidad. | Consulta factual mínima con enlace; no se afirma licencia ni permiso contractual. Sólo sección pública /pacientes/charlas-a-la-comunidad, sin portales de pacientes, APIs administrativas ni datos personales. |
| UNR, /agenda/ | 404 en /robots.txt | Agenda institucional que mezcla cultura y formación. No se identificó licencia general o condiciones específicas de automatización en esta revisión. Los términos de otras facultades no se trasladan a este dominio. | Datos factuales de fichas abiertas con fecha propia comprobable; nunca usar fecha de publicación como año del evento. |
| Humanidades y Artes UNR | 200; excluye /wp-admin/ y un JSON de caché, permite admin-ajax.php | Agenda oficial. No se identificó licencia general ni frecuencia autorizada. Se consulta HTML público, sin usar admin-ajax. | Mismo adaptador conservador; fichas sin horario, sede o acceso público quedan en candidatos. |
| Instituto Politécnico, sitio principal | 200; excluye /wp-admin/, permite admin-ajax.php | Novedades escolares mezcladas con avisos internos. No se identificó licencia general ni frecuencia autorizada. | Sólo descubrimiento de enlaces del listado; no publicación automática de noticias como eventos. |
| EventosIPS | 200, permite / | HTML observado presenta esqueleto de carga, sin catálogo interpretable. Pie con derechos reservados; auditoría de catálogo/condiciones incompleta. | Desactivado, registrado con motivo. No se investigaron APIs privadas ni se eludieron controles. |
| Escuela Superior de Comercio UNR | 200, User-agent: * sin exclusiones | Novedades en página única y contenido interno mezclado. Sin adaptación verificada por actividad. | Registrada y desactivada hasta adaptar fecha y acceso por actividad. |
| Hospital Italiano Rosario | No auditado | La búsqueda no identificó agenda pública verificable para comunidad; campus ofrece formación profesional. | Registrado y desactivado. El Hospital Italiano de Buenos Aires no se incorpora como fuente local. |

La ausencia de robots o de una prohibición identificada no concede licencia.
Esta revisión registra observaciones y un uso factual limitado; no es un dictamen
jurídico. Si aparece una restricción o se solicita detener consultas, desactivar
la fuente en la configuración. No se afirma una frecuencia autorizada por los
titulares.

## Límites configurados

Listado: cada 24 horas. Fichas institucionales: caché de 24 horas, hasta cuatro
URLs por host y fecha local, contando intentos fallidos para evitar insistir.
Robots: caché de siete días; mínimo cinco segundos entre documentos, o la demora
superior indicada por robots. Hasta cuatro fichas por fuente y ejecución, dentro
del presupuesto diario. Sin paginación masiva ni copia de bases completas.

Los errores no vacían eventos existentes. Sólo una ficha interpretada con éxito
puede reemplazar su publicación anterior; las cancelaciones confirmadas se
registran mediante la revisión de URL que ya reconoce la actualización segura.
Los rangos de varias fechas sin cronograma no se multiplican en funciones.

## Pruebas

Se agregó tests/test_instituciones_eventos.py sin eliminar pruebas anteriores.
Cubre datos mínimos, inscripción, cupos, ciudad, acceso restringido, modalidad,
cancelación, fecha propia frente a recomendaciones, rangos, errores de red y
presupuesto diario. La comprobación en vivo se documenta en LEEME_INSTITUCIONES.txt.
