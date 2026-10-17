# Fuentes institucionales de Salidas Rosario — revisión 17/10/2026

## Resultado

Se revisó el repositorio `paredesivan/Agenda-rosario` en `main` (commit
`7e5e1b9d3ef25e57c5ed93c65b437fc4785ecc0c`). Ya existían adaptadores
para UNR, Humanidades, Gamma, Instituto Politécnico, Santa Fe Cultura y fuentes
de teatros/salas. No se duplican esas entradas.

Se agregan **nueve registros de fuentes candidatas desactivadas**, dos
adaptadores de fichas oficiales listos para pruebas y una exclusión conservadora
de cursos en la etapa final. La auditoría incompleta **no se presenta como
permiso**. Ninguna fuente nueva queda consultándose ni publicando eventos hasta
superar las comprobaciones.

| Fuente | Página oficial y evidencia | Robots / términos | Decisión |
|---|---|---|---|
| CEC Rosario | https://www.cecrosario.gob.ar/events/ contiene funciones con fecha y hora, incluida la del 22/10/2026; algunos eventos son multifecha | Apertura directa del sitio devolvió HTTP 403 desde el acceso de comprobación; robots.txt no pudo verificarse; no se identificó autorización expresa de automatización | **Desactivada**. Adaptador preparado para ficha propia; nunca inferir horas de "Todo el día" |
| Universidad Católica de Santa Fe (UCSF) | https://www.ucsf.edu.ar/eventos/mes/ y https://www.ucsf.edu.ar/evento/rosario-moderna-una-invitacion-a-volver-a-mirar-la-ciudad/ muestran eventos y fechas | robots.txt no verificable en esta sesión; no se identificó licencia de reproducción ni frecuencia autorizada | **Desactivada**. Adaptador exige fecha, horario y punto de encuentro del evento, no la sede administrativa que figura en el bloque "Local" |
| UCA Rosario | https://uca.edu.ar/es/campus-del-rosario muestra agenda institucional con actividades y formación mezcladas | robots y términos de extracción no auditados; ruta de fichas no comprobada | **Desactivada**. Pendiente descubrir estructura y descartar formación |
| City Center Rosario | https://www.citycenter-rosario.com.ar/es/shows muestra cartelera de espectáculos | https://www.citycenter-rosario.com.ar/en/terminos-condiciones, sección 4: contenidos protegidos, publicación/retransmisión prohibidas; robots no verificado; listado dinámico | **Desactivada**. No reproducir ni automatizar sin revisión jurídica/autorización |
| Hotel Pullman Rosario | https://pullman-rosario.ar/ y https://www.citycenter-rosario.com.ar/es/hotel-spa/promocion-detail/763/PULLMAN-SUNSETS; promoción de enero 2026, vencida | Sin agenda pública independiente de funciones futuras comprobable ni robots auditado | **Desactivada**. No convertir disponibilidad de salones en eventos públicos |
| Biblioteca Vigil | https://bibliotecavigil.org.ar/inicio/ publica teatro, visitas y observaciones; algunas noticias contienen varios eventos | robots no accesible desde esta sesión; sin autorización de extracción verificada | **Desactivada**. Ya se la reconoce como espacio cultural; falta adaptador por función y evitar duplicados |
| Colegio de Arquitectura y Urbanismo D2 | https://d2.capsf.ar/ muestra calendario con actividades y cursos mezclados | robots, términos, condiciones de acceso y fichas sin auditar | **Desactivada**. Pendiente adaptador y exclusión de formación |
| Alianza Francesa de Rosario | https://afrosario.org.ar/agenda-cultural/ ofrece agenda de una asociación sin fines de lucro | fechas antiguas y noticias mezcladas; robots y términos no verificados | **Desactivada**. Pendiente verificación por ficha |
| Espacio Cultural Faro (Fundación Libertad) | https://espacioculturalfaro.com.ar/ anuncia exhibiciones y capacitaciones | sin agenda fechada verificable por función ni robots/términos auditados | **Desactivada**. No publicar cursos ni exhibiciones sin horarios |


### Reglas incorporadas

- Se rechazan cursos, talleres formativos, workshops, clases, capacitaciones,
  diplomaturas y otras ofertas formativas por **título inicial o categoría**.
  Una función llamada «Encuentro de Academias y Talleres de Danza» NO se
  descarta por contener la palabra «talleres».
- Para CEC, la ficha debe incluir fecha completa, horario, evidencia de sede y
  acceso público. Si es multifecha, sólo se crean funciones con horarios
  específicos para **cada** fecha. Precio solo cuando se publica explícitamente.
- Para UCSF, la ficha debe mostrar fecha de evento, hora y **punto de encuentro
  explícito**. El domicilio administrativo de la universidad no reemplaza el
  punto real de salida.
- La consulta de nuevas fuentes, una vez habilitadas, pasará por el mismo
  control de robots, caché, cuotas diarias, 403/429 y deduplicación ya existente.
- No se copian imágenes, sinopsis ni artículos. Solo se conservan datos mínimos
  y enlace oficial, cuando se habilite una fuente auditada.
- Ante HTTP fallido o parseo incompleto, no se considera revisada la ficha y se
  preserva el dato válido anterior. Las fuentes pendientes no hacen consultas.

### Límites previstos para eventual habilitación

Listado cada 24 horas, máximo cuatro fichas por fuente y ejecución, máximo
cuatro fichas por host/día, caché de 24 horas, al menos 5 segundos entre
peticiones o mayor Crawl-delay. Son límites **configurados por el proyecto**,
no frecuencias autorizadas por los titulares.

### Validación

Pruebas sintéticas sin red: formato de fecha, horas, funciones multifecha,
precio, público general, rechazo de cursos, prevención de falsas exclusiones,
sede efectiva y negativa ante información insuficiente. **No equivalen a
pruebas end-to-end en los sitios reales.** Al no existir escritura de GitHub
con la integración actual, el CI del repositorio todavía no pudo ejecutarse
sobre este cambio. Ejecutar la batería completa en GitHub Actions después de
instalar el paquete y antes de activar fuentes.

### Desbloqueos pendientes

1. Resolver permiso de escritura GitHub: el conector devuelve HTTP 403
   «Resource not accessible by integration» tanto al actualizar un archivo
   como al crear una rama.
2. Auditar robots.txt y términos de cada dominio desde un acceso autorizado.
3. Verificar HTML real de fichas y listados, con pruebas de integración en vivo.
4. Activar **una por una** únicamente las fuentes que superen esos controles.
5. Comprobar que la actualización y el CI no introducen regresiones.

Esta revisión es técnica, no un dictamen jurídico ni una afirmación de licencia.
