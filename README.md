# Agenda Rosario

Web estática sin frameworks. Código separado y funciones cortas.

## Publicar

1. Creá un repositorio público llamado `agenda-rosario` en GitHub.
2. Subí **el contenido** de esta carpeta a la raíz del repositorio.
3. En **Settings → Pages → Build and deployment**, elegí **Deploy from a branch**, `main`, `/ (root)`.
4. La web quedará en `https://paredesivan.github.io/agenda-rosario/` si tu usuario es `Paredesivan`.

## Agregar un evento

Abrí `data/eventos.json` y agregá un objeto dentro de `eventos` siguiendo el ejemplo.
`evento_url` debe ser el enlace HTTPS **directo a la ficha oficial**; si no lo tenés, dejalo vacío. Nunca uses búsquedas de Google como sustituto.
`direccion` se usa para abrir Google Maps.

## Actualizaciones

La página vuelve a consultar `data/eventos.json` cada hora mientras esté abierta.
GitHub Actions ejecuta **una validación horaria**, no una búsqueda automática de eventos.
Para descubrir y publicar eventos sin intervención hace falta conectar fuentes oficiales, extraer fechas/precios y verificar enlaces. Se dejó deliberadamente sin publicar información no verificada.

## Probar en tu PC

Desde la carpeta del proyecto ejecutá `python -m http.server 8000` y abrí `http://localhost:8000`.
