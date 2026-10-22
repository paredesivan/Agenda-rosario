# Entregas de Agenda Rosario

El dueño trabaja desde un teléfono Android y no dispone de una computadora para ejecutar scripts.

- El conector de GitHub es sólo de consulta. No intentar crear, actualizar ni publicar archivos por el conector hasta que el dueño vuelva a autorizarlo expresamente.
- Revisar la versión actual del repositorio antes de preparar cambios.
- Resolver los cambios relacionados en una entrega completa. No pedir que el usuario arme una cadena de parches.
- Entregar un único `actualizar.yml` autocontenido cuando no se pueda escribir directamente: se sube a `.github/workflows/actualizar.yml` y se instala con ese push.
- Mantener una tarea principal que coordine pruebas, actualización, diagnóstico y publicación. Conservar la ejecución cada dos horas y la auditoría semanal.
- No incorporar eventos hardcodeados. Los ejemplos fijos pertenecen exclusivamente a las pruebas.
- Conservar datos ante fallos; no reemplazar una agenda válida por una extracción incompleta o inválida.
- No usar force-push ni rebase para publicar resultados de un checkout antiguo.
- Incrementar el identificador de entrega para cada paquete nuevo y respetar el límite de 21.000 caracteres por paso `run` de GitHub Actions.
- Las instalaciones deben ser repetibles, comprobar versiones y no sobrescribir cambios desconocidos.
- Ejecutar pruebas relevantes, incluidas las de navegador cuando se modifica la interfaz.
- Mantener el panel `estado.html` sin credenciales, datos privados ni operaciones de escritura. Es público, no un área autenticada.
- Conservar los artefactos históricos necesarios para pruebas. No reactivar instaladores anteriores sin revisar qué sobrescriben.
- Proponer y aplicar simplificaciones dentro del pedido autorizado, sin trasladar pasos técnicos evitables al usuario.
- Informar archivo, ubicación y estado real: preparado, instalado o publicado. No afirmar despliegue sin evidencia.
