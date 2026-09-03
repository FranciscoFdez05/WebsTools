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
- **Rate limiting por IP**: 20 ejecuciones/minuto en general, 15 en OSINT, 6 en el descargador
  de video y 2 al actualizar la aplicacion. Navegar por el catalogo no gasta cupo.
- **Actualizacion desde la propia web**: `/ajustes` compara la version instalada con la ultima
  release publicada en GitHub y, si hay una nueva, la trae con un `git pull --ff-only` sobre el
  clon desde el que corre la app. Se puede desactivar con `[actualizaciones] permitirAplicar`.
- **Recarga del catalogo de herramientas** desde `/ajustes`, sin reiniciar el servidor.
- **Aviso de version nueva en la cabecera** de cualquier pagina, con el resultado cacheado una
  hora en el navegador para no gastar peticiones a GitHub en cada cambio de pagina.
- **Herramientas usadas recientemente** en la pantalla principal, guardadas en el navegador de
  quien mira y no en el servidor.
- **Contrasena opcional para los ajustes** (`[app] ajustesPassword` o `AJUSTES_PASSWORD`), que
  cubre la pantalla y las dos acciones capaces de cambiar el codigo que ejecuta el servidor.
- **`/healthz` y healthcheck** en `docker-compose.yml`, para ver si la aplicacion sigue
  respondiendo y no solo si el proceso sigue vivo.
- **Integracion continua** en GitHub Actions: la suite completa en Linux con las cuatro
  dependencias nativas instaladas -las que hacen que en Windows esos tests se salten-,
  construccion de la imagen Docker con arranque real contra `/healthz`, y comprobacion de que
  cada etiqueta `v*` coincide con el numero de `version.py`.
- **Despliegue en un comando** con `./docker-up.sh`: genera el `.env`, crea la `SECRET_KEY`,
  lee el puerto de `config.ini` y levanta el contenedor con las dependencias nativas incluidas.
- **Configuracion centralizada** en `config.ini`: puerto, tamano maximo de subida, timeouts de
  OSINT, confianza en `X-Forwarded-For` y ajustes de actualizacion.

### Corregido

- Las tarjetas de herramienta se pintaban debajo de las categorias en la pantalla principal y
  el buscador no ocultaba nada: el `display: flex` de las tarjetas y de las cuadriculas ganaba
  a la regla `display: none` que el navegador aplica al atributo `hidden`.
- El limite de peticiones era el doble del configurado: las cuentas por IP viven en la memoria
  del proceso y gunicorn arrancaba con dos workers, cada uno con su propio contador. Ahora
  arranca un solo proceso con ocho hilos, que ademas atiende mas peticiones a la vez.
- Detectar el tipo real de un archivo colgaba el proceso en Windows: `python-magic` busca
  `libmagic` al importarse y, si no la encuentra, el import se queda bloqueado en vez de
  fallar. Ahora se salta directamente a la deteccion por cabecera. Colgaba tambien la suite de
  tests entera, que ahora termina en un par de segundos.
- Analizar la firma de un ejecutable PE que declaraba menos entradas de directorio de las
  necesarias devolvia un error 500 (`IndexError`) en vez de informar de que no esta firmado.
- `X-Forwarded-For` se creia por defecto. Sin un proxy inverso delante, esa cabecera la elige
  quien hace la peticion, asi que bastaba con cambiarla en cada llamada para saltarse el rate
  limit. Ahora hay que activarla a mano (`[proxy] confiarXForwardedFor`).
- La imagen Docker copiaba dentro el entorno virtual del equipo de desarrollo, 110 MB de
  paquetes compilados para otro sistema operativo que ademas quedaban sin usar. Anadido un
  `.dockerignore`.
- Aviso al arrancar si la aplicacion esta usando la `SECRET_KEY` de ejemplo del repositorio,
  que es publica.

[1.0.0]: https://github.com/FranciscoFdez05/WebsTools/releases/tag/v1.0.0
