# Fuente primaria prioritaria y ACR como respaldo

Revisión y cambio de alcance: 17/10/2026.

- Agenda pública: https://www.agendaculturalrosario.com.ar/agenda
- Robots: https://www.agendaculturalrosario.com.ar/robots.txt
- Términos: https://www.agendaculturalrosario.com.ar/terminos

Robots HTTP 200 permite la agenda pública y restringe administración, cuentas
y rutas API con excepciones. El recolector consulta sólo el HTML de /agenda;
no usa APIs, inicios de sesión, imágenes ni sitios enlazados.
Se conserva el ritmo configurado de una consulta por dos horas, con caché y
pausa mínima de cinco segundos. Son límites nuestros, no una autorización del titular.

El usuario prioriza las fichas que ya se obtuvieron de fuentes primarias. ACR
se usa como respaldo cuando no hay una función coincidente. El cruce dinámico
compara título, fecha, hora y sede; nunca consulta una lista fija de eventos.
Para el respaldo ACR no se exige una segunda confirmación oficial. Se elimina el límite de cuarenta funciones y el
filtro de treinta días. Se procesan todas las funciones vigentes del HTML público.
La descripción mínima se redacta con nombre, disciplina y lugar, y atribuye el
dato a ACR. No se conservan sinopsis, imágenes ni contactos de remitentes.
La atribución enlaza directamente a la ficha de ACR. No se etiqueta como una
confirmación independiente del organizador: fuente_verificada queda en false.

Los términos, sección 4, autorizan cita y divulgación con mención y enlace;
no contienen una licencia específica que aclare la extracción automática
integral de la cartelera. El cambio de criterio editorial del usuario no resuelve
esa incertidumbre ni sustituye un permiso del titular. La atribución identifica
la procedencia: no afirma una transferencia jurídica de responsabilidad.

Las funciones suspendidas se excluyen tanto por indicadores estructurados como
por el título y la nota de cada función. Los cierres explícitos determinan la
caducidad. Sin cierre publicado, la ficha se oculta al comenzar para no inventar
su duración. Las nuevas cancelaciones dependen de la próxima lectura de la fuente.

La auditoría semanal incluye las fuentes automáticas configuradas. Si aparecen
restricciones nuevas, reevaluar el alcance. Esta revisión no es un dictamen jurídico.
