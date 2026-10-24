# Revisión de fuentes — 24/10/2026

Base revisada: 9a3a85710a8736f30d71b7548d185c74dc1ebbc8.
Esta revisión distingue la evidencia técnica, las condiciones de uso y los
límites de la comprobación. No acredita una licencia ni un dictamen jurídico.

## Cobertura comprobada

El archivo recibido contiene 1.145 funciones. El informe municipal del
24/10/2026 a las 12:58 registra 134 fichas intentadas: 116 lecturas sin error
y 18 intentos detenidos por presupuesto de consultas. De las 116 lecturas,
93 produjeron funciones y 23 no produjeron funciones. El dato antiguo
"41 sin funciones" mezclaba esas 23 con los 18 errores; no eran 41 exclusiones.

El presupuesto general era 120 solicitudes por host y proceso. Las páginas
de listado también consumen solicitudes. El recorrido alfabético repetido
podía postergar siempre las mismas fichas. Se configura un máximo municipal
de 240 solicitudes, manteniendo las pausas y los controles HTTP. Además,
las consultas fallidas y las fichas nuevas toman prioridad en el siguiente
intento. Sigue siendo un límite, no una garantía de descargar cualquier volumen.

Se descargó el HTML público actual de ACR y se cotejaron 527 funciones vigentes
con corte uniforme al 24/10/2026 a las 15:00 de Argentina: las 527 tenían
coincidencia en la agenda, incluyendo fichas provenientes de fuentes oficiales.
Una comparación inicial por nombre de sala daba una falsa ausencia para
Teatro del Rayo; el cotejo de título, fecha, hora y sede equivalente la resolvió.
Este resultado verifica la representación de las funciones interpretadas en
esa página, no todo lo publicado por ACR fuera de ella ni las demás fuentes.

La ficha oficial "Un cielo de seis cuerdas" publica el 30 de octubre, de 20 a
23:59, en La Casa del Tango, gratis. Su URL figura entre las consultas detenidas.
La comprobación web independiente pudo leerla; la descarga HTTP directa de
la Municipalidad desde este entorno devolvió 503. No se incorporó como evento
fijo ni se alteró eventos.json para forzar un aumento del contador.

Referencias:
- https://www.agendaculturalrosario.com.ar/agenda
- https://www.rosario.gob.ar/inicio/un-cielo-de-seis-cuerdas

## Robots y condiciones

`excepciones_robots.json` contiene una lista vacía: no hay excepciones activas.
Existe código capaz de aceptar una excepción documentada. Su existencia no
demuestra que se esté usando. No se agregaron excepciones ni se habilitaron
fuentes bloqueadas. Los 403/429 y Retry-After mantienen sus pausas; una
restauración de respaldo ya no elimina una pausa recibida en el intento fallido.

El robots de ACR respondió 200 y permite /agenda; restringe administración,
cuentas y rutas de API. El robots de Ticketek respondió 200 y excluye
/websource/. Esa exclusión se aplica en el transporte común, también antes
de seguir una redirección hacia esa ruta. Se mantienen esas comprobaciones
separadas de los términos.
El robots municipal no pudo verificarse de nuevo aquí (503); no se presenta
como autorización nueva. El primer intento del robots de Passline agotó el
tiempo de espera; la auditoría ampliada posterior pudo leerlo con HTTP 200.
No se confunde esa lectura con sus condiciones contractuales.

Las condiciones oficiales publicadas por Passline, sección TERCERO, limitan
el uso al ámbito personal y restringen la descarga de contenidos. Se deja
su dominio y subdominios sin consultas automáticas mediante
`acceso_fuentes.json`, aplicado en el transporte común antes de enviar una
solicitud. Se preservan las fichas existentes; se pueden incorporar datos
desde las fuentes oficiales independientes. No se pidió autorización a nadie.
La página de condiciones tiene referencias comerciales a Chile: esta decisión
de operación no determina la aplicabilidad jurídica de cada cláusula en Argentina.

Se leyó también la página oficial estática de condiciones de Ticketek. Su
contenido trata principalmente compras, entradas y transmisiones; no se deduce
de ella un permiso de scraping o republicación. No se amplía su acceso.

La auditoría semanal ahora inventaría referencias de todos los módulos de
recolección y sus configuraciones, no sólo tres módulos. Distingue el HTML
devuelto por error como robots no interpretable y conserva la revisión de
condiciones junto al resultado técnico. El inventario de referencias incluye
fuentes inactivas y enlaces: no es un registro de solicitudes realizadas.
Los demás términos pendientes siguen identificados como pendientes, sin
marcarlos aprobados automáticamente.

La ejecución ampliada inventarió 79 dominios: 37 sin restricciones detectadas
para las rutas referenciadas, 10 sin robots, 18 errores de transporte, 6
respuestas para revisar, 2 redirecciones pendientes, 2 respuestas HTML no
interpretables, 3 referencias sociales no rastreadas y una ruta restringida.
La ruta restringida es un enlace de Google Maps para que lo abra el visitante;
el recolector no descarga ese mapa. Estos resultados son observaciones de
este entorno y no acreditan que una fuente caída esté permanentemente caída.
Se adjunta el resultado completo como `auditoria_fuentes_20261024.json`.
Las demoras encontradas para FAER (60 s), La Comedia de Hacer Arte (60 s) y
La Sonrisa de Beckett (10 s) quedan además fijadas en el transporte común.
Ticketek se comprobó separadamente y se añade como referencia dinámica
explícita de la auditoría semanal, porque su enlace se descubre en Astengo.

Referencias oficiales consultadas:
- https://home.passline.com/terminos-y-condiciones
- https://aws-static.ticketek.com.ar/queue/terminos-y-condiciones.html
- https://www.agendaculturalrosario.com.ar/robots.txt
- https://www.ticketek.com.ar/robots.txt
- https://www.rfc-editor.org/rfc/rfc9309.html

## Informes actuales y límites

`COBERTURA_ACTUAL.md` y `cobertura_actual.json` se regeneran en cada ejecución.
Separan consultas fallidas, fichas sin funciones y el detalle de candidatos.
Las nuevas lecturas municipales registran cada función para comprobar si está
representada en la agenda final. Un informe antiguo sin ese detalle se marca
como no medible por función, no como cero pérdidas.

`PENDIENTES_REVISION.md` conserva su carácter histórico del 17/10. Sus 39
registros no describen el corte actual. No se borran sus evidencias.

No se ejecutó la actualización integral de todas las fuentes desde este
entorno. La cantidad que se recuperará con el nuevo presupuesto deberá
verificarse al completar la ejecución de GitHub. No se promete un total mayor.
