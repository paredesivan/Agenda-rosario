# Agenda Rosario — Política de fuentes y auditoría preliminar

**Fecha:** 14 de octubre de 2026. **Estado:** requiere revisión y adopción antes de ponerse en producción.

## Qué podemos publicar con menor riesgo

- Priorizar hechos verificables: nombre de la función, fecha, horario, sede, precio y enlace a su fuente.
- Evitar fotografías, afiches, artículos, sinopsis creativas o descripciones copiadas sin licencia o permiso.
- Escribir resúmenes propios; **acortar a 22 palabras un texto original no equivale a tener permiso para reproducirlo**.
- Publicar la fuente y permitir solicitudes de corrección o retiro.
- Verificar eventos y precios en sus fuentes oficiales; no inventar fechas o importes.

## Scraping técnico responsable

- Sólo contenido público. Nunca eludir logins, controles anti-bot, captchas ni bloqueos.
- Consultas moderadas por dominio; pausa y reducción cuando el servidor indique problemas.
- Ante HTTP 403/429, detener esa fuente durante la ejecución. No rotar IP ni agentes para evitar el bloqueo.
- Inspeccionar robots.txt y **también** los términos de uso; el primero no es una autorización legal.
- Preferir feeds de calendarios públicos, JSON-LD y fuentes oficiales, siempre según sus reglas de uso.
- Las respuestas 404/403/429 o fallas de conexión de robots.txt **no significan permiso**.

## Resultados del repositorio inspeccionado

- Archivo eventos.json al 14/10/2026 08:55: 508 eventos, 507 con evento_url; 0 con campo de foto/imagen, 0 con descripción de más de 220 caracteres.
- Fuentes destacadas por número: Municipalidad de Rosario (300), Microteatro (53), El Cairo (27), Broadway (13), Astengo (12), Rosario3 (10).
- Los recolectores ya contienen pausa de ~1,5 s por host en el flujo principal, y controles de 403/429; hay algunas rutas de acceso separadas que conviene unificar en una próxima intervención probada.
- La descripción visible incluye hasta 22 palabras procedentes de las fuentes. Prioridad: reemplazar estos extractos por información factual propia, conservando horarios que hoy pueden estar codificados en la descripción.

## Riesgos según condiciones revisadas

**Prioridad ALTA para revisión: Rosario3.** Robots.txt permite rastreo, pero sus términos establecen restricciones de uso comercial y reproducción de contenido, y condiciones sobre enlaces. Conviene reemplazar los 10 registros con fuentes oficiales cuando sea posible y no copiar textos periodísticos. La interpretación contractual de los enlaces requiere asesoramiento individualizado.

**Prioridad de revisión MEDIA: otros medios y carteleras de terceros.** Revisar condiciones de La Capital, El Ciudadano, Rosario en Cartel y plataformas de entradas antes de dar por aceptado su uso.

**Oportunidad: Municipalidad de Rosario.** Sus términos incluyen pautas para contenido sujeto a licencias Creative Commons 4.0 especificadas en cada activo digital. Confirmar licencia exacta y cumplir atribución cuando aplique.

**Resto de salas:** términos/robots y licencias aún pendientes de comprobación; no se concluye que todo esté autorizado.

## Enlaces consultados

- https://www.rosario3.com/robots.txt
- https://www.rosario3.com/pages/terminos-y-condiciones.html
- https://www.lacapital.com.ar/robots.txt
- https://www.rosario.gob.ar/inicio/node/1020
- https://www.argentina.gob.ar/normativa/nacional/42755/actualizacion
- https://www.argentina.gob.ar/normativa/nacional/ley-11179-16546/actualizacion

## Uso de la auditoría técnica

El archivo auditar_fuentes.py, ejecutado en la raíz del repositorio, inventaría las URL HTTPS literales presentes en los tres recolectores y consulta solamente el archivo robots.txt de cada dominio. Marca rutas restringidas, demoras indicadas y fallas; nunca toca eventos.json.

El workflow propuesto auditar_fuentes.yml ejecuta esto semanalmente y adjunta un JSON descargable a la ejecución de Actions. **No detiene la agenda ni aprueba automáticamente fuentes.** Los términos y licencias todavía deben revisarse manualmente.

## Contacto recomendado

Antes de difundir masivamente la agenda, habilitar una dirección de contacto o formulario sencillo para correcciones y solicitudes de retiro. La página actualmente sólo muestra un aviso sobre cambios de actividades.

**Estado de implementación:** los archivos de este paquete NO fueron subidos a GitHub. La integración rechazó las escrituras con error 403, y la página publicada no se modificó.
