# Espacios de Rosario: fuentes oficiales

Revisión del 22/10/2026. Directorio: https://www.agendaculturalrosario.com.ar/espacios

Se recuperaron las 34 fichas de espacios del directorio. Se buscaron webs propias y enlaces institucionales; una URL de red social atribuida por ACR se mantiene como referencia sin corroborar cuando no existe respaldo independiente.

## Implementado

- Nuevo recolector de El Aserradero: descubre fichas /event/ de la portada, valida JSON-LD, sede y localidad, convierte UTC a Rosario, excluye cursos y conserva funciones futuras ante fallas. Sin títulos, fechas ni slugs de espectáculos fijos en el recolector.
- Los recolectores existentes siguen cubriendo teatros, ATIR, la Municipalidad, UNR y Santa Fe Cultura. El inventario no dispara una segunda consulta para cada sala.
- Directorio ACR revisado como máximo una vez al día, con caché y comprobación de cambios en condiciones. Descubre salas nuevas como pendientes de corroborar; no activa dominios externos aportados por terceros.
- Boletería El Aserradero: listado cada 2 horas; hasta 8 fichas nuevas al día, rotación, caché de 24 horas y transporte común que respeta robots y pausas 403/429. Si cambian las condiciones, se suspende esa consulta y se conserva la agenda.
- espacios.html permite consultar el inventario desde el celular. Cada registro distingue sitio institucional, cartelera, red corroborada y referencia secundaria.

## Verificaciones y límites

Prueba en vivo: 34 espacios recuperados y 6 funciones verificadas en fichas oficiales de El Aserradero. Integración con HTML real; pruebas de conservación, reemplazo de respaldo ACR, localidad, cursos, fecha sin hora y cambio de condiciones.
El precio JSON-LD de una ficha difería del importe final visible: el recolector enlaza la boletería y no publica un precio parcial.
Atlas devolvió HTTP 403; Club Fosse, La Grieta y La Manzana HTTP 503; La Comedia de Hacer Arte HTTP 500. No se activaron nuevos parsers para esas webs. La Sonrisa de Beckett respondió 200 con contenido ajeno de apuestas; se registró el problema sin activar un parser de esa página.
Mística.QTP y Casa Lealtad: sólo se encontró en esta revisión la referencia social de ACR; no se afirma que esté corroborada ni que sus agendas puedan extraerse automáticamente.
No equivale a 34 carteleras nuevas ni garantiza cobertura completa. Los enlaces institucionales compartidos son referencias: cada evento necesita fecha, sala y acceso público verificables.

## Inventario completo

| Espacio | Sitio institucional o referencia | Cartelera / cobertura | Estado |
|---|---|---|---|
| Teatro El Círculo | https://www.teatroelcirculo.com/home | https://www.teatroelcirculo.com/home | Recolector existente: web del teatro; el dominio .com.ar de ACR no reemplaza al comprobado. |
| Plataforma Lavardén | https://plataformalavarden.gob.ar/ | https://plataformalavarden.gob.ar/agenda/ | Recolector existente: web provincial y Entradas Lavardén. |
| Centro Cultural Parque de España (CCPE) | https://ccpe.org.ar/ | https://ccpe.org.ar/web/agenda/ | Recolector existente: agenda del CCPE. |
| Teatro Municipal La Comedia | https://teatrolacomedia.gob.ar/ | https://teatrolacomedia.gob.ar/espectaculos/programacion/ | Recolector existente: programación oficial. |
| Complejo Cultural Atlas (CCA) | https://ccatlas.org.ar/ | https://ccatlas.org.ar/ | Sitio confirmado por ETUR; HTTP 403 en esta revisión. Se conserva cobertura por fuentes existentes; sin eludir bloqueo. |
| Mística.QTP | https://instagram.com/mistica.qtp |  | Sólo perfil indicado por ACR; no se corroboró web propia ni cartelera extraíble. Se conserva ACR como respaldo; no se automatiza Instagram. |
| Casa Lealtad | https://instagram.com/casalealtad |  | Sólo perfil indicado por ACR; no se corroboró web propia ni cartelera extraíble. Se conserva ACR como respaldo; no se automatiza Instagram. |
| ECU - Espacio Cultural Universitario | https://unr.edu.ar/espacio-cultural-universitario/ | https://unr.edu.ar/agenda/ | Institución y agenda UNR verificadas; recolector existente valida sede ECU y excluye formación. |
| Centro Cultural Güemes | https://urbangroup.com.ar/areas/centro-cultural-guemes/ | https://entradaplay.com/ | Web institucional de su operador; cartelera con Entrada Play ya cubierta. Página institucional no se convierte en eventos. |
| Galpón 11 | https://www.rosario.gob.ar/inicio/centros-culturales-y-teatros | https://www.rosario.gob.ar/inicio/agenda | Municipal: directorio oficial; cobertura mediante agenda municipal existente. |
| Centro Cultural Roberto Fontanarrosa | https://www.rosario.gob.ar/inicio/centros-culturales-y-teatros | https://www.rosario.gob.ar/inicio/agenda | Municipal: directorio oficial y agenda existente; no usar horario institucional como horario de evento. |
| Centro Cultural Parque Alem | https://www.rosario.gob.ar/inicio/centros-culturales-y-teatros | https://www.rosario.gob.ar/inicio/agenda | Municipal: directorio oficial y agenda existente. |
| Centro Cultural Cine Lumière | https://lumiererosario.gob.ar/web/ | https://www.rosario.gob.ar/inicio/agenda | Web declarada por la Municipalidad; esta URL HTTPS no fue comprobada en vivo. Agenda municipal existente como cobertura. |
| Centro Cultural El Obrador | https://www.rosario.gob.ar/inicio/centros-culturales-y-teatros | https://www.rosario.gob.ar/inicio/agenda | Municipal: ficha y Facebook institucional corroborados; agenda municipal existente. |
| Casa Arijón | https://www.santafecultura.gob.ar/ | https://www.santafecultura.gob.ar/agenda/?localidad=rosario | Espacio provincial: fuente Santa Fe Cultura existente; no usar noticia antigua como agenda permanente. |
| Teatro Caras y Caretas | https://www.instagram.com/teatrocarasycaretas/ | https://www.teatrosatir.ar/salas/caras-y-caretas/ | Sala identificada en ATIR; recolector ATIR ya existente. No se duplica el rastreo. |
| Club Fosse Teatro Concert | https://clubfosse.net/ | https://www.teatrosatir.ar/salas/club-fosse/ | Sala identificada en ATIR; recolector ATIR ya existente. No se duplica el rastreo. Web propia devolvió HTTP 503: no se activó consulta adicional. |
| Cultural de Abajo | https://www.instagram.com/culturaldeabajosub/ | https://www.teatrosatir.ar/salas/cultural-de-abajo/ | Sala identificada en ATIR; recolector ATIR ya existente. No se duplica el rastreo. |
| Teatro La Escalera | https://instagram.com/laescalera.teatro | https://www.teatrosatir.ar/salas/la-escalera/ | Sala identificada en ATIR; recolector ATIR ya existente. No se duplica el rastreo. |
| Espacio Bravo Teatro | https://www.instagram.com/espacio.bravo.teatro/ | https://www.teatrosatir.ar/salas/espacio-bravo/ | Sala identificada en ATIR; recolector ATIR ya existente. No se duplica el rastreo. |
| Centro Cultural La Grieta | https://lagrietarosario.com.ar/ | https://www.teatrosatir.ar/salas/la-grieta/ | Sala identificada en ATIR; recolector ATIR ya existente. No se duplica el rastreo. Web propia devolvió HTTP 503: no se activó consulta adicional. |
| Teatro de la Manzana | https://www.teatrodelamanzana.com/ | https://www.teatrosatir.ar/salas/teatro-de-la-manzana/ | Sala identificada en ATIR; recolector ATIR ya existente. No se duplica el rastreo. Web propia devolvió HTTP 503: no se activó consulta adicional. |
| La Morada | https://www.instagram.com/la_morada_teatro/ | https://www.teatrosatir.ar/salas/la-morada/ | Sala identificada en ATIR; recolector ATIR ya existente. No se duplica el rastreo. |
| La Orilla Infinita | https://laorillainfinita.com.ar/ | https://laorillainfinita.com.ar/ | Recolector directo existente y ATIR. Sin consultas duplicadas. |
| La Sonrisa de Beckett | https://www.lasonrisadebeckett.com.ar/ | https://www.teatrosatir.ar/salas/la-sonrisa-de-beckett/ | Sala identificada en ATIR; recolector ATIR ya existente. No se duplica el rastreo. Web propia HTTP 200 pero con contenido ajeno de apuestas: parser nuevo no activado; requiere revisión del sitio. |
| La Tornería Espacio Cultural | https://www.instagram.com/latorneriacultural/ | https://www.teatrosatir.ar/salas/la-torneria/ | Sala identificada en ATIR; recolector ATIR ya existente. No se duplica el rastreo. |
| Tandava Arte y Movimiento |  | https://www.teatrosatir.ar/salas/tandava/ | Sala identificada en ATIR; recolector ATIR ya existente. No se duplica el rastreo. |
| Teatro del Rayo (El Rayo Misterioso) | https://elrayomisterioso.org.ar/ | https://elrayomisterioso.org.ar/index.php/es/component/sppagebuilder/?view=page&id=219 | Recolector directo existente y ATIR. Sin consultas duplicadas. |
| La Comedia de Hacer Arte | https://lacomediadehacerarte.com/ |  | Web propia identificada; HTTP 500 observado. No se activa un parser sin cartelera verificable; se conserva respaldo ACR. |
| El Cairo Cine Público | https://elcairocinepublico.gob.ar/ | https://elcairocinepublico.gob.ar/ | Recolector existente del cine público; agenda y calendario. |
| Teatro Broadway | https://teatrobroadwayrosario.com/ | https://teatrobroadwayrosario.com/ | Recolector existente de la web oficial. |
| Teatro Fundación Astengo | https://teatroastengo.ar/ | https://teatroastengo.ar/events/ | Recolector existente de la web oficial; no se sustituye por el dominio alternativo sin verificar de ACR. |
| Teatro AEC - Asoc. Empleados de Comercio | https://www.aecrosario.org.ar/ | https://www.aecrosario.org.ar/cultura/teatro/ | Recolector oficial existente: Teatro AEC; gratuito para afiliados no implica gratuito para todos. |
| El Aserradero | https://www.elaserradero.com.ar/ | https://www.elaserradero.com.ar/ | Nueva fuente directa: portada y ficha JSON-LD verificadas; consulta acotada y rotación. Precio final se consulta en boletería. |

## Auditoría de la fuente nueva

El Aserradero: portada y ficha HTTP 200; robots.txt HTTP 404 verificado. Condiciones leídas en https://www.elaserradero.com.ar/terms-of-service. La cláusula de uso se refiere a gestión y venta de entradas del organizador; se adoptó una lectura acotada de consulta factual pública, sin afirmar una licencia general. Sólo se guardan hechos y enlaces. No compras, imágenes, sinopsis, APIs privadas ni acceso con cuenta.
ACR: robots permite /espacios y excluye rutas administrativas y API. Condiciones leídas en https://www.agendaculturalrosario.com.ar/terminos. Se atribuye el directorio y se enlaza; no se replican sinopsis, afiches, descripciones de salas ni publicaciones editoriales.
Fuentes institucionales de corroboración: https://www.teatrosatir.ar/salas/ ; https://www.rosario.gob.ar/inicio/centros-culturales-y-teatros ; https://unr.edu.ar/espacio-cultural-universitario/ ; https://rosario.tur.ar/donde-ir/cultura/centros-culturales/complejo-cultural-atlas?lang=es ; https://urbangroup.com.ar/areas/centro-cultural-guemes/ .

## Subida desde Android

Reemplazar únicamente .github/workflows/actualizar.yml con el archivo entregado. El push instala el paquete y ejecuta pruebas antes de guardar y publicar. No volver a ejecutar una corrida vieja. No hay que ejecutar Python en el teléfono.

La corrección anterior del guardado de reportes ignorados está incluida. El instalador rechaza sobrescribir cambios que no conoce. Hasta completar Actions, el estado es preparado, no publicado.
