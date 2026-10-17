> Actualización de criterio del 17/10/2026: ACR se importa directamente con enlace a su ficha. Sus publicaciones con los datos mínimos ya no necesitan corroboración oficial. Los pendientes enumerados abajo corresponden a otras fuentes y al corte anterior; no bloquean la integración de ACR.

# Pendientes de revisión — corte del 17/10/2026

No tenés que aprobarlos todos ni tocar JSON a mano. El cartel de revisión parcial mezcla problemas distintos; no significa que todos los eventos estén mal.

| Tipo | Estado observado | Qué hacer |
|---|---|---|
| Confirmación de eventos | 39 registros candidatos: 3 Rosario Times, 10 EntradaFan y 26 SalePlan | Buscar el anuncio de la sala, organizador o ticketera oficial. Comprobar título, fecha con año, hora y sede. Pasame el enlace oficial para incorporarlo o corregir el cruce automático. No marcarlo verificado sólo por aparecer en un agregador. |
| Consultas técnicas | La Orilla Infinita: 3; Provincial: 1; Alto Rosario: 1; CentroTicket: 1 | La actualización vuelve a intentar las consultas permitidas. Si se repite el mismo fallo, hay que revisar la respuesta o el formato del extractor; no es una tarea que debas resolver aprobando eventos. |
| Museos | Estévez, Museo de la Ciudad, Ángel Gallardo y Beatmemo: web pendiente; Experimental: revisión parcial | Revisar sus agendas oficiales y el diagnóstico del extractor. Que no haya datos interpretables no demuestra que no existan actividades. |
| Auditoría | Disfruta Rosario | Completar revisión actual de robots y condiciones antes de activar su consulta automática. No basta con cambiar el indicador de pendiente. |
| Permiso del titular | Rosario Folklore desactivada por falta de permiso de automatización | Pedir y conservar autorización para automatizar, con alcance y frecuencia. Mientras tanto, conservarla desactivada. |

## Qué podés hacer ahora

1. Subí el paquete respetando las carpetas. El cambio dispara pruebas y actualización automática.
2. Esperá a que termine «Actualizar agenda». Revisá «Pruebas de la agenda» para confirmar los tests.
3. Si querés recuperar un candidato concreto, abrí su referencia y buscá su fuente oficial. Enviame ese enlace; no hace falta que edites datos manualmente.
4. Para fallos técnicos persistentes, pasame el diagnóstico de Actions o pedime revisar salud_actualizacion.json y fuentes_revisadas.json actualizados.
5. No elimines un evento sólo por el aviso general. En este corte no hay eventos con revision_pendiente=true: los 39 registros están en el archivo de candidatos, separados de la agenda publicada.

Los 39 registros no equivalen a 39 eventos únicos perdidos: hay notas de prensa y posibles coincidencias con eventos ya publicados. Esta lista describe el estado guardado; no confirma individualmente las fechas de sus candidatos.

## Candidatos guardados antes de incorporar ACR

| Fuente | Evento o referencia | Fecha informada | Hora informada |
|---|---|---|---|
| Rosario Times | [el tc vuelve a rosario despues de siete anos y llega el salon del automovil](https://rosariotimes.com/el-tc-vuelve-a-rosario-despues-de-siete-anos-y-llega-el-salon-del-automovil/) | Por confirmar | Por confirmar |
| Rosario Times | [llega el musical despertar de primavera a rosario cuando y donde comprar las entradas](https://rosariotimes.com/llega-el-musical-despertar-de-primavera-a-rosario-cuando-y-donde-comprar-las-entradas/) | Por confirmar | Por confirmar |
| Rosario Times | [stefano marconi el nino de 10 anos con el coeficiente intelectual mas alto del pais llega al salon del automovil de rosario](https://rosariotimes.com/stefano-marconi-el-nino-de-10-anos-con-el-coeficiente-intelectual-mas-alto-del-pais-llega-al-salon-del-automovil-de-rosario/) | Por confirmar | Por confirmar |
| EntradaFan | [Los Pericos Rosario](https://www.entradafan.com.ar/entradas-los-pericos-rosario/e/16583) | 2026-10-17 | 22:00 |
| EntradaFan | [David Bisbal Rosario](https://www.entradafan.com.ar/entradas-david-bisbal-rosario/e/16723) | 2026-10-18 | 21:00 |
| EntradaFan | [Festival Bandera Rosario](https://www.entradafan.com.ar/entradas-festival-bandera-rosario/e/17212) | 2026-10-24 | 10:00 |
| EntradaFan | [Benjamin Amadeo Rosario](https://www.entradafan.com.ar/entradas-benjamin-amadeo-rosario/e/16747) | 2026-10-24 | 21:00 |
| EntradaFan | [Camilo Rosario](https://www.entradafan.com.ar/entradas-camilo-rosario/e/16869) | 2026-10-30 | 21:00 |
| EntradaFan | [Un Poco de Ruido Rosario](https://www.entradafan.com.ar/entradas-un-poco-de-ruido-rosario/e/17585) | 2026-10-31 | 21:00 |
| EntradaFan | [Ciro y Los Persas Rosario](https://www.entradafan.com.ar/entradas-ciro-y-los-persas-rosario-/e/17859) | 2026-11-06 | 21:00 |
| EntradaFan | [Ciro y Los Persas Rosario](https://www.entradafan.com.ar/entradas-ciro-y-los-persas-rosario-/e/17056) | 2026-11-07 | 21:00 |
| EntradaFan | [Ronnie Wood Rosario](https://www.entradafan.com.ar/entradas-ronnie-wood-rosario/e/17756) | 2026-11-08 | 21:00 |
| EntradaFan | [Diego Torres Rosario](https://www.entradafan.com.ar/entradas-diego-torres-rosario/e/16748) | 2026-11-12 | 21:00 |
| SalePlan | [Candlelight: Tributo a Taylor Swift](https://saleplan.ar/santa-fe/rosario/planes/YEP007BGN837/candlelight-tributo-a-taylor-swift) | Por confirmar | Por confirmar |
| SalePlan | [Candlelight: Lo Mejor de Hans Zimmer](https://saleplan.ar/santa-fe/rosario/planes/GQTPDMR77BCK/candlelight-lo-mejor-de-hans-zimmer) | Por confirmar | Por confirmar |
| SalePlan | [Candlelight: De Música Ligera](https://saleplan.ar/santa-fe/rosario/planes/4EWY0B1WK49R/candlelight-de-musica-ligera) | Por confirmar | Por confirmar |
| SalePlan | [Candlelight: Las Cuatro Estaciones de Vivaldi](https://saleplan.ar/santa-fe/rosario/planes/B0V2Y6YFQWEK/candlelight-las-cuatro-estaciones-de-vivaldi) | Por confirmar | Por confirmar |
| SalePlan | [Candlelight: Tributo a Michael Jackson](https://saleplan.ar/santa-fe/rosario/planes/XE0SJG8QRNNQ/candlelight-tributo-a-michael-jackson) | Por confirmar | Por confirmar |
| SalePlan | [Candlelight: Tributo a Joan Manuel Serrat](https://saleplan.ar/santa-fe/rosario/planes/RA7P8ATRBTH7/candlelight-tributo-a-joan-manuel-serrat) | Por confirmar | Por confirmar |
| SalePlan | [Candlelight: Queen vs. ABBA](https://saleplan.ar/santa-fe/rosario/planes/R97VKAA5W67G/candlelight-queen-vs-abba) | Por confirmar | Por confirmar |
| SalePlan | [Agus Bernasconi: Siempre fue música](https://saleplan.ar/santa-fe/rosario/planes/CV6QMA2SGXKK/agus-bernasconi-siempre-fue-musica) | Por confirmar | Por confirmar |
| SalePlan | [Festival Ludueña](https://saleplan.ar/santa-fe/rosario/planes/KF2RZB1CYRYT/festival-luduena) | Por confirmar | Por confirmar |
| SalePlan | [Autochocador Club + Recreo Uruguayo, Club Forestal, Uhh! Tengo Ratas En Mi Atado](https://saleplan.ar/santa-fe/rosario/planes/55208EQYKF2Q/autochocador-club-recreo-uruguayo-club-forestal-uhh-tengo-ratas-en-mi-atado) | Por confirmar | Por confirmar |
| SalePlan | [Oliver Kozlov en vivo en Rosario](https://saleplan.ar/santa-fe/rosario/planes/Y9K1331MQ9V9/oliver-kozlov-en-vivo-en-rosario) | Por confirmar | Por confirmar |
| SalePlan | [El beso de la mujer araña](https://saleplan.ar/santa-fe/rosario/planes/B2JE0HM1KKSJ/el-beso-de-la-mujer-arana) | Por confirmar | Por confirmar |
| SalePlan | [La función de los invisibles](https://saleplan.ar/santa-fe/rosario/planes/8CCMKVZQNDDH/la-funcion-de-los-invisibles) | Por confirmar | Por confirmar |
| SalePlan | [Escenas de la vida conyugal](https://saleplan.ar/santa-fe/rosario/planes/783WGSEAAQWN/escenas-de-la-vida-conyugal) | Por confirmar | Por confirmar |
| SalePlan | [RODRIGO TAPARI - DECADA DISCO](https://saleplan.ar/santa-fe/rosario/planes/7ZPA91GXH6BC/rodrigo-tapari-decada-disco) | Por confirmar | Por confirmar |
| SalePlan | [Noche Magica de Gira](https://saleplan.ar/santa-fe/rosario/planes/C13A5PGH1PJR/noche-magica-de-gira) | Por confirmar | Por confirmar |
| SalePlan | [La Re en Rosario! (L 17/10](https://saleplan.ar/santa-fe/rosario/planes/4A903D7T0E5T/la-re-en-rosario-l-1710) | Por confirmar | Por confirmar |
| SalePlan | [TOMY BENASSI & ESTEBAN CALVET X RES](https://saleplan.ar/santa-fe/rosario/planes/RP6BGNBW5914/tomy-benassi-esteban-calvet-x-res) | Por confirmar | Por confirmar |
| SalePlan | [Milano en Rosario](https://saleplan.ar/santa-fe/rosario/planes/MXE9S0T9Q8VX/milano-en-rosario) | Por confirmar | Por confirmar |
| SalePlan | [El enfermo imaginario (versión litoraleña) / ESTRENO](https://saleplan.ar/santa-fe/rosario/planes/86Q7G7W4VX4F/el-enfermo-imaginario-version-litoralena-estreno) | Por confirmar | Por confirmar |
| SalePlan | [Los Palmae](https://saleplan.ar/santa-fe/rosario/planes/8S6MSG6RBA67/los-palmae) | Por confirmar | Por confirmar |
| SalePlan | [Claudio Gabis en ROSARIO](https://saleplan.ar/santa-fe/rosario/planes/G3S3VJ5VTZN4/claudio-gabis-en-rosario) | Por confirmar | Por confirmar |
| SalePlan | [PEÑA SAN MARTIN - educacion fisica](https://saleplan.ar/santa-fe/rosario/planes/1W1MH4BT3D9P/pena-san-martin-educacion-fisica) | Por confirmar | Por confirmar |
| SalePlan | [FACU MARTINEZ PRESENTA CANCIONES DORADAS DE TELENOVELAS II](https://saleplan.ar/santa-fe/rosario/planes/B3PZG0JQVG56/facu-martinez-presenta-canciones-doradas-de-telenovelas-ii) | Por confirmar | Por confirmar |
| SalePlan | [Candlelight: Tributo a Taylor Swift](https://saleplan.ar/santa-fe/rosario/planes/YEP007BGN837/candlelight-tributo-a-taylor-swift) | 2026-10-30 | 19:00 |
| SalePlan | [Candlelight: Lo Mejor de Hans Zimmer](https://saleplan.ar/santa-fe/rosario/planes/GQTPDMR77BCK/candlelight-lo-mejor-de-hans-zimmer) | 2026-10-30 | 21:30 |

ACR ya no añade candidatos pendientes de confirmación oficial: publica directamente las funciones vigentes con sus datos mínimos y su enlace. Este informe conserva el corte previo de las otras fuentes y no se actualiza automáticamente.
