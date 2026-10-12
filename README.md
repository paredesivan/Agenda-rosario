# Agenda Rosario

Agenda publicada en https://paredesivan.github.io/Agenda-rosario/.

## Actualización automática

GitHub Actions ejecuta cada hora, al minuto 17, los recolectores
`actualizar_eventos.py`, `fuentes_nuevas.py` y `precios_ticketek.py`.
Actualiza `eventos.json` en la raíz y registra las consultas complementarias
en `fuentes_revisadas.json`. Para ejecutar manualmente: Actions → Actualizar
agenda → Run workflow → main. Una nueva ejecución usa el código actual.

Las fuentes buscan funciones para los próximos 30 días. Las consultas fallidas
conservan registros futuros anteriores. Un 403/429 no se sortea; se registra.
Las fechas de publicación de noticias nunca se usan como fechas de funciones.

## Precios y enlaces

`precio: 0` significa gratuito confirmado. Un número positivo representa el
importe publicado. `precio_etiqueta` permite indicar “Desde”, rangos o
“Precio a confirmar”. `entrada_paga: true` indica acceso pago conocido aunque
no haya importe. `entradas_url` enlaza a compra; `evento_url` a la fuente.
Los importes Ticketek se leen sólo del espectáculo exacto enlazado por Astengo.

## Eventos manuales

Los objetos manuales deben incluir fecha, hora, nombre, lugar, dirección y
`origen: "Manual"`. Agregá `evento_url` sólo si tenés una fuente verificable.
Los datos incompletos requieren revisión: no se inventa un enlace.

## Prueba local

Instalá `requests` y `beautifulsoup4`; ejecutá `python -m http.server 8000`
y abrí http://localhost:8000.
