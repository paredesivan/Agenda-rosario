# RefiTicket y Rosario Folklore

Revisión: 16 de octubre de 2026. Alcance: consulta de campos factuales de eventos
con enlace al origen para Salidas Rosario. Esta revisión no afirma una licencia
de reutilización ni sustituye el acuerdo del titular.

## RefiTicket: integración activa

- Portada: https://refiticket.ar/
- JavaScript público inspeccionado: https://refiticket.ar/static/js/home.js
- Catálogo GET utilizado por esa portada:
  https://refiticket.ar/obtener_eventos/?cantidad_eventos=100
- Robots: https://refiticket.ar/robots.txt respondió HTTP 200. El contenido
  observado consiste en comentarios explicativos de content signals, sin reglas
  User-agent/Disallow ni Crawl-delay. Se vuelve a comprobar durante la ejecución;
  un error o una prohibición detiene la consulta, sin suponer permiso.
- Condiciones legales: la portada renderiza modales vacíos titulados «Condiciones
  Legales», sin texto contractual ni enlace público en el pie para esas condiciones.
  La política de cookies existe, pero no es una licencia de reutilización.
- No se identificó permiso expreso ni frecuencia autorizada. Se configura una
  consulta acotada: mínimo 5 segundos entre GET al mismo dominio, caché de 2 horas,
  hasta 100 elementos de catálogo y hasta 30 fichas de Rosario por revisión.
- No se hace login, no se consulta checkout ni se utilizan endpoints privados.
  Se pausa el dominio ante 403/429 y se conserva la información anterior.
- No se guardan afiches, HTML ni sinopsis; sólo campos factuales y categorías.
  Las descripciones se analizan transitoriamente para clasificar, sin reproducirlas.

### Evidencia técnica

Se consultó en vivo el catálogo y las siete fichas futuras del período 16/10–15/11.
Las siete proporcionaron sede y fechas interpretables sin fallos. Se contrastó
el selector `#idFechasEventos` con el catálogo: no se inventan recurrencias.
La ficha real de Bestia Bebé publica 16/10/2026 a las 20:00; el catálogo anuncia
desde ARS 15.000. Su JSON-LD incluye `offers.price=0.00`, por lo cual ese campo
no se utiliza para declarar gratuidad. En eventos con varias funciones, el precio
global no se atribuye a cada sesión sin evidencia.

Los resultados se obtienen del catálogo del momento; ninguno de estos eventos
forma parte de una lista embebida en producción.

## Rosario Folklore: preparado y desactivado

- Sitio: https://rosariofolklore.com.ar/
- Términos revisados: https://rosariofolklore.com.ar/terminos/
- Fecha declarada de esos términos: 15 de septiembre de 2026.
- Permite mencionar y enlazar eventos. Restringe la extracción masiva y automática
  del catálogo y pide contactar al titular para acordar otros usos de los datos.
- Contacto publicado: WhatsApp 341 255 4543. No se envió una solicitud.
- robots.txt y el HTML/iCalendar en bruto no pudieron verificarse: las consultas
  desde este entorno devolvieron errores 502 o timeout. Eso NO se toma como permiso.
- Por esa restricción contractual y por la verificación técnica pendiente,
  el conector no realiza ninguna petición a esta fuente con la configuración incluida.
- Para activarlo se requieren tres condiciones explícitas en configuración:
  habilitada, permiso_automatizacion y referencia_permiso. Los límites deben
  adaptarse al acuerdo real. Nunca activar sólo para eludir los términos.
- El parser está probado con entradas sintéticas de listado, JSON-LD/iCalendar;
  no se presenta como probado contra el sitio en vivo. Si cambia o no contiene
  fecha completa, hora y ciudad verificables, se registra como pendiente.

## Integración y pruebas

Módulo separado, ejecutado desde la Action existente después de las fuentes
complementarias. Las pruebas anteriores siguen ejecutándose mediante unittest.
Se conserva el cron y se agregan las rutas nuevas al disparador push.

Las pruebas nuevas cubren descubrimiento posterior de eventos, múltiples funciones,
cancelaciones, ciudad, horizonte, precios ambiguos, clasificación, enlaces externos,
caché y respuestas 304, pausas, preservación de fuentes existentes y deduplicación.
La actualización usa escritura temporal y reemplazo atómico de cada archivo.

Los datos existentes prevalecen si coinciden título, sede y función. La combinación
no toca el frontend ni reemplaza los extractores anteriores. El repositorio remoto
no se modificó; el usuario recibe los archivos para subirlos.
