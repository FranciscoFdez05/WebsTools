# Changelog

Todos los cambios reseñables de WebsTools. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[versionado semantico](https://semver.org/lang/es/).

## [1.0.0] - 2026-09-03

Primera version publica. WebsTools reune 65 herramientas de ciberseguridad y administracion de
sistemas en una sola web, pensada para desplegarse en un servidor de la red local y usarse
desde el navegador de cualquier dispositivo de la LAN.

### Anadido

- **65 herramientas** repartidas en siete categorias: analisis de archivos (10), criptografia
  (9), OSINT (11), redes (7), texto (8), utilidades (12) y JSON/programacion (8).
- **Buscador global** en la pantalla principal, con filtro por nombre, descripcion y categoria,
  atajo `/` para enfocarlo, `Enter` para abrir la primera coincidencia y `Esc` para limpiar.
  Cada categoria tiene ademas su propio filtro.
- **Panel de resultados legible**: fichas de campo, tablas e insignias en lugar de un volcado de
  JSON, con estado y tiempo de la peticion, copia de un valor con un clic, botones de copiar y
  guardar el resultado entero y vista del JSON crudo.
- **Formularios con ayudas**: ejemplos dentro del campo, obligatorios marcados y validados antes
  de enviar, `Ctrl + Enter` para ejecutar y boton de limpiar.
- **Errores explicados** en el propio panel, tambien los del limitador y los archivos demasiado
  grandes, en vez de la pagina de error del servidor.
- **Rate limiting por IP**: 20 ejecuciones/minuto en general, 15 en OSINT y 6 en el descargador
  de video. Navegar por el catalogo no gasta cupo.
- **Actualizacion desde la propia web**: `/ajustes` compara la version instalada con la ultima
  release publicada en GitHub y, si hay una nueva, la trae con un `git pull --ff-only` sobre el
  clon desde el que corre la app. Se puede desactivar con `[actualizaciones] permitirAplicar`.
- **Recarga del catalogo de herramientas** desde `/ajustes`, sin reiniciar el servidor.
- **Despliegue en un comando** con `./docker-up.sh`: genera el `.env`, crea la `SECRET_KEY`,
  lee el puerto de `config.ini` y levanta el contenedor con las dependencias nativas incluidas.
- **Configuracion centralizada** en `config.ini`: puerto, tamano maximo de subida, timeouts de
  OSINT, confianza en `X-Forwarded-For` y ajustes de actualizacion.

### Corregido

- Las tarjetas de herramienta se pintaban debajo de las categorias en la pantalla principal y
  el buscador no ocultaba nada: el `display: flex` de las tarjetas y de las cuadriculas ganaba
  a la regla `display: none` que el navegador aplica al atributo `hidden`.

[1.0.0]: https://github.com/FranciscoFdez05/WebsTools/releases/tag/v1.0.0
