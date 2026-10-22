# Una sola entrega para Agenda Rosario

## Instalación desde el teléfono

Subir el archivo entregado con el nombre exacto `actualizar.yml` dentro de `.github/workflows/`, reemplazando el existente, y confirmar el cambio en `main`. Ese mismo push inicia **Agenda: instalar, comprobar y actualizar**. No hace falta ejecutar varios instaladores ni disponer de Python en el teléfono.

La primera ejecución instala la versión incluida, ejecuta las pruebas, actualiza las fuentes, verifica la web y guarda los cambios. Las siguientes reutilizan la instalación. Una versión nueva comprueba el contenido esperado antes de escribir. Si encuentra modificaciones desconocidas, se detiene sin sobrescribirlas.

## Qué se conserva

- Consulta de eventos cada dos horas, minuto 17 UTC. GitHub puede demorar los horarios programados.
- Auditoría de acceso los lunes a las 09:10 de Rosario, dentro de la misma tarea principal. No habilita fuentes automáticamente.
- Fuentes y reglas editoriales existentes, conservación ante fallos y deduplicación por fecha, hora, sede y contenido.
- Pruebas en cada cambio relevante y en solicitudes de incorporación de cambios (pull requests), sin publicar desde estas últimas.

## Control desde el celular

Abrir `https://salidasrosario.com.ar/estado.html` y guardarlo como favorito. Muestra el informe publicado, el estado reciente de la tarea consultado a GitHub, fuentes pendientes, fichas conservadas, duplicados unificados al cierre y hasta 30 informes. Si GitHub no responde, lo indica expresamente y mantiene el informe anterior.

Este panel es público y de solo lectura. No aloja tokens ni pretende autenticar al dueño. Los controles de escritura abren GitHub, que verifica la cuenta del usuario. No se agrega a la navegación pública de la agenda.

**Actualizar** consulta fuentes y publica resultados comprobados. **Verificar** revisa el código y la web sin consultar fuentes de eventos. **Auditar** revisa accesos sin habilitar fuentes. Todas se eligen en Run workflow de la misma tarea.

## Publicación protegida

Se prueba el código antes de consultar fuentes y la web antes de guardar. Las fallas de una etapa conservan los datos anteriores. Si la actualización completa termina con error o excede el límite, se restaura el conjunto de datos respaldado y se informa el fallo. Nunca se publica una agenda vacía si antes había funciones futuras.

El guardado rechaza resultados si `main` cambió durante el trabajo; no usa force-push. Los cambios realizados directamente por fuera de esta tarea siguen sujetos a la configuración de publicación de GitHub Pages existente.

Las ejecuciones de Actions guardan durante 30 días el diagnóstico y una copia de los archivos públicos recibidos, llamada `respaldo_publicado.json.gz`. Las versiones anteriores también permanecen en el historial de Git. No se realizan publicaciones de código que haya fallado las pruebas.

## Tareas y archivos históricos

Después de pasar las pruebas, se desactivan únicamente las tareas reemplazadas: pruebas separadas, auditoría separada, reparación de pausas e instaladores conocidos. Se guardan copias legibles en `archivo/automatizaciones`. Los workflows originales permanecen desactivados porque el token normal de Actions no debe usarse para reescribir workflows.

Los scripts históricos sin uso activo y la versión vieja de `agenda.js` se trasladan a `archivo/historico` con extensión `.txt`. Se mantienen `corregir_pausas.py` e `instalar_fuentes_institucionales.py`: todavía los necesitan pruebas existentes. No se eliminan cachés, datos ni auditorías legales. Si una tarea no puede desactivarse, queda indicado y no se retiran los scripts asociados.

## Cómo interpretar los números

Se comparan funciones futuras usando la misma fecha de corte para que el paso de un día no parezca una pérdida. Los cambios de fuente equivalentes se cruzan como la misma función. “Ausentes” no demuestra por sí solo una falla: puede representar una baja confirmada o un cambio de datos. “Conservadas” cuenta fichas futuras con revisión pendiente. “Duplicados al cierre” cuenta los que elimina la pasada final; no todas las unificaciones realizadas dentro de cada extractor.

Una caída de al menos la mitad de las fichas de una fuente que antes tenía cinco o más genera aviso; no elimina ni inventa eventos. El historial permite ver si el problema persiste. La lista de nuevas y ausentes del informe se limita a 40 ejemplos, pero los totales cuentan todos.
