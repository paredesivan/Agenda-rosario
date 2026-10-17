# Agenda Rosario — consulta factual y verificación

Revisión: 14/10/2026. Alcance adoptado para las fuentes nuevas: consulta acotada
de datos públicos de eventos. No se presume una licencia de contenido.

## Datos y materiales

Nombre del evento, fecha, horario y sede se tratan como información factual.
No se copian titulares periodísticos como nombres de eventos, sinopsis,
fotografías, afiches, logos ni diseños. No se replica la organización completa
de bases de terceros. La protección de una compilación y las condiciones de
acceso son cuestiones distintas del uso de un dato aislado.

Las nuevas fuentes sirven para descubrir candidatos. Sólo un respaldo oficial
permite incorporarlos a eventos.json. Se conserva el precio oficial existente;
los precios y la disponibilidad de EntradaFan no se presentan como oficiales.
Los campos ausentes se mantienen pendientes, sin inventarlos. La normalización
no corrige automáticamente años, sedes o horarios contradictorios.

## Límites configurados (no equivalen a permiso del proveedor)

- Una página de listado por fuente cada dos horas, sin recorrer su paginación.
- Hasta cuatro fichas distintas por dominio por día; caché de fichas por 24 h.
- Espera de al menos 5 s entre consultas, o Crawl-delay cuando sea mayor.
- Robots se verifica y conserva durante siete días; una exclusión se respeta.
- HTTP 403/429: pausa de al menos 24 h, respetando un Retry-After mayor.
- No se rotan IP, agentes o credenciales; no se usan APIs privadas ni logins.
- Redirecciones quedan pendientes, sin seguirlas a dominios no auditados.
- HTML se usa transitoriamente; el caché conserva únicamente datos y enlaces.
- Los dominios oficiales nuevos se registran como candidatos hasta auditarlos.

## Auditoría de las fuentes nuevas

Rosario Times: robots HTTP 200 permite páginas públicas y excluye /wp-admin/.
No se identificó licencia para reproducir artículos o imágenes. La decisión de
uso se limita a descubrimiento factual y enlaces; no afirma permiso general.

EntradaFan: robots HTTP 200 permite páginas públicas y excluye /api/ y
/test-error/. Es una plataforma de reventa. Sus términos, secciones 10 y 11,
restringen reproducción/explotación y regulan enlaces. Se limita la consulta a
un listado local y datos básicos, sin copiar textos, imágenes ni precios.
El alcance queda registrado; no se afirma que las cláusulas sean inaplicables.

SalePlan: robots HTTP 200 en la comprobación directa permite / y excluye
/wizadm y /go/. Una comprobación anterior devolvió 403; no se eludió un bloqueo,
y el recolector mantiene la detención si recibe nuevamente 403/429. Sus términos
secciones 11 y 12 restringen extracción masiva y scraping abusivo sin definir
un número de consultas. La navegación pública no supone aceptación contractual
según sus secciones 2 y 3. Se consulta una página local y hasta cuatro fichas
al día; no se descarga toda la base. Se verifica año y localidad en cada ficha:
la portada observada mezcla un encabezado de 2027 con fechas de 2026 e incluye
un radio de 50 km. No se infieren fechas a partir de ese encabezado.

Disfruta Rosario: se incorpora el registro del paquete pendiente como referencia
manual. Su auditoría sigue incompleta; no se habilita una consulta automática.

La auditoría no es un dictamen jurídico ni una autorización del proveedor.
Permisos y límites autorizados no encontrados se distinguen de los límites que
configuramos nosotros. Revaluar el alcance si aparecen nuevas restricciones.

## Fuentes de consulta

- https://www.argentina.gob.ar/normativa/nacional/norma-42755/actualizacion
- https://www.wipo.int/en/web/copyright/protection
- https://rosariotimes.com/robots.txt
- https://www.entradafan.com.ar/robots.txt
- https://www.entradafan.com.ar/terms
- https://saleplan.ar/robots.txt
- https://saleplan.ar/legal/terminos

El módulo anterior mantiene sus recolectores y pausas ya instalados. Esta
política no acredita retrospectivamente licencias de sus fuentes anteriores.


## Excepción editorial ACR, 17/10/2026

Por instrucción expresa del usuario, Agenda Cultural Rosario se acepta como
fuente de sus propias publicaciones. No se exige confirmación en otra fuente
ni se visitan sus enlaces externos. Las fichas vigentes con datos mínimos se
publican con enlace directo a ACR y descripción factual propia. Se quita el
límite de cuarenta funciones y el horizonte de treinta días para esta fuente.
Se excluyen suspendidas y vencidas; sin hora de fin se ocultan al comenzar.
Esta excepción cambia la validación editorial de los datos, no constituye una
licencia del titular ni una transferencia de responsabilidad. Se mantiene la
consulta del HTML público cada dos horas, el respeto de robots y las pausas.
Ver AUDITORIA_ACR.md para el alcance y la incertidumbre contractual registrada.


### Prioridad precisada por el usuario, 17/10/2026

Si una función de ACR coincide con una ficha primaria obtenida por los
recolectores existentes, se conserva esa ficha y su enlace. Sólo las funciones
sin ese respaldo usan el enlace y los datos mínimos de ACR. El cruce se ejecuta
cada vez por título, fecha, hora y sede. No usa una lista fija de pendientes,
IDs ni nombres de eventos. Los dominios prioritarios son configuración de
fuentes y no una lista de espectáculos. ACR permite publicar sin aprobación
manual los casos que no se logran corroborar independientemente.
