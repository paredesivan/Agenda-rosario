# CM25 — auditoría de incorporación

- Fuente primaria: `https://www.cm25.ar/novedades.html`, página oficial del Centro Cultural Madres de Plaza 25 de Mayo (CM25).
- Identidad/localización corroborada en páginas públicas del sitio: Corrientes 987, planta alta, Rosario.
- El sitio indica en su página de Actividades que sus actividades son de entrada libre y gratuita.
- Datos consultados por el adaptador: título, fecha, hora, sede/dirección y URL de la propia fuente. No copia imágenes ni descripciones editoriales.
- Frecuencia: el caché del recolector limita la consulta del listado a una vez cada dos horas y usa ETag/Last-Modified cuando el servidor los ofrece. Hay una pausa mínima entre peticiones.
- `robots.txt`: el entorno de auditoría no pudo recuperar `https://www.cm25.ar/robots.txt`; por eso la regla se consulta durante la ejecución. Si la respuesta bloquea la ruta o no puede interpretarse, el recolector se detiene para CM25.
- Términos/licencia: no se encontró una licencia o autorización expresa de reutilización. La incorporación se limita a datos factuales mínimos y atribución/enlace; esto no declara ni presume una licencia.
- Extracción: interpreta de forma genérica todos los encabezados compactos que publica CM25 (`DDMMM / título`) y busca la hora explícita en el texto de cada tarjeta. Incluye todas las tarjetas con fecha futura y horario explícito; si la fecha ya pasó, resuelve la próxima ocurrencia porque la página no publica año. Descarta tarjetas sin hora confirmada. No contiene nombres ni fechas de eventos en el código de producción.
- Corrección del 16-10-2026: el parser anterior esperaba fecha y hora dentro de la misma oración y devolvía cero. La prueba con el HTML oficial actual debe reconocer BANGNIER el 16 de octubre a las 20:30; la tarjeta del 22 de octubre queda pendiente porque no informa horario en el texto.
