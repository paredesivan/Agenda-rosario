# Salas nuevas mediante carteleras Passline — 18/10/2026

Se agregan seis carteleras dinámicas, sin títulos, fechas ni slugs de eventos fijos:
Floyd Bar, Somos Musica, Club Mercury, Complejo Forest, QUE SEA ROCK y Playa de la musica.
La presencia de una sala no implica que todos sus eventos estén en Passline.

## Acceso y condiciones

- Robots: https://www.passline.com/robots.txt devolvió HTTP 200 y texto de reglas.
  User-agent * excluye carro, tickets y ciertas operaciones personales; las rutas
  /venue/ y /eventos/ consultadas no están excluidas para AgendaRosario.
- Las seis carteleras y fichas revisadas devolvieron HTML público HTTP 200, sin
  iniciar sesión, ejecutar JavaScript, comprar entradas ni consultar APIs privadas.
- Se revisaron la portada /home, las carteleras y la ficha de Floyd: el pie remite
  genéricamente a términos de la aplicación, sin enlace a condiciones de extracción.
  No se encontró allí una prohibición explícita relevante para esta consulta factual.
  Esto no equivale a licencia ni a una autorización expresa del proveedor.
- Por el criterio indicado por el usuario se habilita la consulta acotada de hechos.
  No se copian afiches, imágenes, sinopsis, diseños ni información de compradores.
- Un listado por sala al día; hasta ocho fichas por sala por ejecución, cada ficha
  con caché de 24 horas. Separación mínima de 5 s; robots durante siete días;
  HTTP 403/429 pausa por 24 h o Retry-After mayor. No se eluden bloqueos.

## Verificación por ficha

Se exige JSON-LD propio (nombre + URL de oferta), o campos visibles propios con
URL canónica coincidente cuando el JSON-LD está vacío. Se valida sede coincidente con la sala,
fecha ISO completa y localidad Rosario. Passline suele cargar el nombre del bar
como addressLocality; en ese caso se exige el bloque visible de la propia sede
terminado en Santa Fe, ROSARIO. No basta la palabra Rosario en el título.
Se rechazan provincias distintas de Santa Fe y no se importan recomendaciones
ni cursos, clases, talleres, seminarios o capacitación. Una fecha sin hora usa
Horario a confirmar. Se mantienen restricciones de edad explícitas.

No se publica un precio mínimo de lote como precio vigente ni un final técnico
como duración del espectáculo. Se enlaza la ficha para condiciones y precios.
Las fichas fallidas conservan los eventos existentes; una suspensión confirmada
permite retirar la ficha propia. La fusión usa la deduplicación existente y da
prioridad a las fuentes primarias sobre ACR.

## Otras candidatas comprobadas

- Eleven Flow y Qué Hacemos: el acceso directo devolvió 403. No se activan ni se
  intenta sortear el bloqueo; se usaron sólo resultados públicos de búsqueda.
- Atlas: el acceso directo a robots y actividades devolvió 403. Se conserva su
  cobertura existente por CentroTicket; no se agrega un recolector directo.
- Ticketon: robots.txt devuelve HTML de la portada con HTTP 200; no se pudo
  verificar un archivo de reglas válido. No se agrega extracción automática.
- Indie Hoy: cartelera accesible; robots excluye GPTBot/Google-Extended/CCBot y
  ciertas rutas. No se añade otra agenda secundaria para copiar su cartelera.

El resultado vivo y los recuentos se encuentran en revision_passline_venues.json.
Las carteleras con fechas de diciembre quedan conectadas para próximas novedades,
pero se distinguen del incremento específico de octubre y noviembre.
