# Corrección de cobertura — 24/10/2026

La extracción municipal admite propuestas culturales y recreativas públicas,
gratuitas y pagas. Conserva el precio general y sus condiciones; no interpreta
la gratuidad de menores como gratuidad para todo público. Los cursos siguen
excluidos. El filtro GRATIS de la página continúa funcionando con el precio.

El lector acepta rangos con mes compartido y toma un horario de la descripción
sólo si es inequívoco y corresponde a una única sede y calendario. Conserva
los horarios de comienzo; el cierre no se convierte en otra función. Si sólo
falta el horario, lo identifica como pendiente, sin inventarlo.

`config_recoleccion.json` fija un horizonte de 180 días para el recolector
principal y los lectores complementarios de `fuentes_nuevas.py`. Otros lectores
con su propia configuración conservan sus límites. No se fuerzan años que la
fuente no permite verificar ni se habilitan fuentes bloqueadas.

La consulta municipal guarda `revision_cobertura_municipal.json` con el número
de fichas consultadas, errores, funciones extraídas y motivos de exclusión por
ficha. El resumen de Actions muestra esos conteos si pertenecen al intento
actual. Los datos se conservan mediante la actualización segura existente.

Las pruebas usan fragmentos factuales de cinco fichas municipales reales.
Comprueban 59 fechas entre el 24/10 y el 23/11 de 2026 y 74 hasta el cierre de
esas programaciones. Son datos de prueba: el recolector no incorpora eventos
fijos. Las nuevas propuestas se descubren durante cada actualización normal.

La discrepancia de Mozart entre la fuente municipal y La Comedia requiere
corroboración: no se elimina ni se traslada una fecha sólo para igualar el
contador. No se promete un total publicado antes de ejecutar las fuentes.

Instalación: reemplazar `.github/workflows/actualizar.yml` con el archivo único
entregado. El push a main inicia instalación, pruebas y actualización. El
instalador comprueba versiones antes de escribir y es repetible. Conserva la
actualización cada dos horas, la auditoría semanal y las pruebas de navegador
antes de publicar. No hace falta subir por separado los archivos incluidos.
