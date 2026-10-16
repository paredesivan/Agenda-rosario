PRUEBAS Y CORRECCION CM25 — ARCHIVOS PARA SUBIR

Repositorio: paredesivan/Agenda-rosario

Subí estos cuatro archivos respetando exactamente las rutas:

1. REEMPLAZAR en la raíz:
   fuentes_nuevas.py

2. AGREGAR:
   tests/test_cm25_integration.py
   .github/workflows/pruebas.yml
   e2e/test_agenda_browser.py

No reemplaces otros workflows ni borres archivos existentes.

Qué corrige y qué comprueba:
- Mueve la configuración de CM25 antes del catálogo que la usa. Esto corrige
  el NameError que hacía fallar la Action de actualización.
- Agrega pruebas de integración para confirmar que CM25 está registrada como
  fuente de prioridad alta, que se consulta su URL, que se procesa un evento y
  que se guarda la caché.
- Agrega una Action de pruebas para los cambios de código y los pull requests.
  Ejecuta comprobaciones de sintaxis, las pruebas Python y una prueba E2E en
  Chromium.
- La prueba E2E usa eventos ficticios servidos localmente. No consulta páginas
  externas. Comprueba que Teatro y Ferias se combinen como alternativas, que
  Gratis se aplique además como condición, y que se muestren los enlaces de
  información y mapa.

La Action existente “Actualizar agenda” ya ejecuta las pruebas Python antes de
consultar las fuentes. Después de subir estos archivos, revisá en la pestaña
Actions que termine correctamente tanto “Pruebas de la agenda” como “Actualizar
agenda”. La prueba de navegador corre en “Pruebas de la agenda”.
