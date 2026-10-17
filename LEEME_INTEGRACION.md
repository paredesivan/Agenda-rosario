# Integración institucional de Salidas Rosario

Paquete elaborado el 17/10/2026 sobre el repositorio
`paredesivan/Agenda-rosario` (rama `main`, commit observado
`7e5e1b9d3ef25e57c5ed93c65b437fc4785ecc0c`).

## Estado real

**No se pudo escribir en GitHub:** el conector respondió HTTP 403
`Resource not accessible by integration` al intentar crear una rama, y
previamente también al actualizar un archivo. Este paquete es una preparación
para instalar, no un despliegue ya realizado. **Ninguna fuente nueva queda
activada** sin auditoría completa.

## Instalación (cuando esté disponible escritura o una terminal)

1. Descomprimir el ZIP dentro de la raíz del repositorio, manteniendo la
   subcarpeta `agenda_instituciones/`.
2. Ejecutar `python agenda_instituciones/instalar_fuentes_institucionales.py`.
   El instalador modifica `fuentes_ampliadas.py`, `fuentes_ampliadas.json` y
   `actualizacion_segura.py`; copia `instituciones_nuevas.py`, el test nuevo y
   la auditoría. Conserva respaldo de los originales.
3. Ejecutar `python -m unittest discover -s tests -v`. No activar ninguna
   fuente si falla un test.
4. Revisar la auditoría y robots/condiciones de cada fuente. Activar una sola
   a la vez cambiando `habilitada` de `false` a `true` únicamente tras pasar
   los controles de acceso, HTML real y permiso contractual que correspondan.
5. Ejecutar el workflow de actualización y comprobar que no aparecen cursos,
   horarios inventados ni duplicados. El CI existente correrá tests al subir
   los archivos modificados.

El instalador es idempotente; ejecutar dos veces no duplica las nueve fuentes.
El filtro global excluye cursos en el archivo de salida de la actualización,
pero no toca los datos actuales hasta que se ejecute el actualizador.

## Pruebas realizadas sin red

`python -m unittest discover -s tests -v`: **17/17 correctas** sobre
fixtures sintéticas del adaptador y del instalador. No se ejecutó la batería
original del repositorio ni se realizó E2E en los sitios nuevos; hacerlo en
GitHub Actions una vez instalado es requisito antes de publicar.

## Archivos del paquete

- `instalar_fuentes_institucionales.py`: aplicación segura con respaldos.
- `instituciones_nuevas.py`: parsers de CEC y UCSF y filtro de cursos.
- `tests/test_instituciones_nuevas.py`: pruebas de eventos, horas, acceso y sedes.
- `tests/test_instalacion.py`: pruebas de idempotencia y compatibilidad del instalador.
- `AUDITORIA_NUEVAS_INSTITUCIONES.md`: evaluación de nueve fuentes y motivos de espera.

No se copian fotos ni textos de terceros, ni se eluden restricciones.
