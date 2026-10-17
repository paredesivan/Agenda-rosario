# Ampliación de fuentes — 17/10/2026

Se integra una etapa aislada en `actualizacion_segura.py`. El alcance de uso es
consulta acotada de información factual y enlaces. No constituye permiso del
proveedor ni licencia general. No se descargan imágenes ni se reproducen
sinopsis; el HTML se procesa transitoriamente y no se guarda en caché.

| Fuente | Acceso comprobado | Uso implementado | Pendiente |
|---|---|---|---|
| Santa Fe Cultura | Listado y ficha HTTP 200; robots 200 excluye wp-admin y permite páginas públicas | Publicación factual primaria, listado filtrado Rosario y JSON-LD propio de cada ficha; ubicación visible bajo «¿Dónde?» | No se identificó licencia general ni frecuencia autorizada; revisar ante cambios de condiciones |
| Planaxia | Portada/listado 200; robots excluye wp-admin | Descubrimiento diario de enlaces, sin títulos periodísticos, imágenes o textos | Confirmación oficial de eventos y condiciones de cualquier ampliación de uso |
| FAER | Portada 200; robots con Crawl-delay 60, Visit-time 0300-1200, Request-rate 6/60m y 3/60m fuera de esa ventana | Descubrimiento semanal sólo dentro de UTC 03–12; 60 s entre peticiones; portada y robots, sin recorrer fichas | Comprobación real de descubrimiento en ventana; programación vigente de próximas ediciones; licencia general no identificada |
| TuTicket | Cartelera y términos legibles; robots 200 contiene HTML | Comprobar robots y detenerse si no es interpretable | Auditoría de acceso y adaptador específico de cartelera HTML; no queda importando funciones |
| Alpogo | Apertura web devolvió 403 | Registro desactivado, sin consultas ni evasión | Condiciones, robots y acceso autorizado |
| Turbo Entrada | Portada requiere JavaScript; robots devuelve HTML | Registro desactivado | Condiciones y adaptación pública sin API privada |
| TicketWay | Catálogo dinámico; robots devuelve HTML | Registro desactivado | Condiciones y adaptación de catálogo |

## Límites que configuramos

No son límites autorizados por los proveedores. Santa Fe Cultura: un listado
cada 2 h, máximo 4 fichas por ejecución, caché de fichas de 24 h, separación
mínima de 5 s o mayor Crawl-delay. Planaxia: un listado cada 24 h. FAER: una
portada cada 168 h, robots conservado siete días; ventana UTC 03–12 y separación
de 60 s, menos documentos que su Request-rate. No se siguen páginas de agenda
ni se descargan grillas. Los cambios en las reglas se vuelven a comprobar antes
de consultar. No se usan logins, rotación de IP ni servicios para evitar bloqueos.

Se reutiliza el acceso controlado existente: 403/429 conserva pausa de al menos
24 h o Retry-After mayor; no sigue redirecciones no auditadas. Los fallos no
borran eventos anteriores. El diagnóstico distingue fuentes registradas,
consultadas, diferidas por horario, con errores y con candidatos. El número de
funciones interpretadas no equivale al de eventos netos agregados después de
la deduplicación.

Los candidatos de medios y FAER se conservan para revisión, no se insertan en
la agenda. El catálogo completo no se ha probado ni queda autorizado por ser
público. Una futura ampliación exige adaptar y revisar cada fuente pendiente.

## Referencias revisadas

- https://www.santafecultura.gob.ar/agenda/?localidad=rosario
- https://www.santafecultura.gob.ar/robots.txt
- https://www.santafecultura.gob.ar/evento/problema-1/ (sólo comprobación del parser; no figura fija en el recolector)
- https://www.tuticket.com.ar/
- https://www.tuticket.com.ar/robots.txt
- https://www.tuticket.com.ar/terminos-y-condiciones.html
- https://planaxia.com/categoria/agenda/
- https://planaxia.com/robots.txt
- https://faer.ar/
- https://faer.ar/robots.txt
- https://alpogo.com/
- https://turboentrada.com/robots.txt
- https://www.ticketway.com.ar/robots.txt
