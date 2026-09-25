# Changelog

Todos los cambios reseñables de WebsTools. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[versionado semantico](https://semver.org/lang/es/).

## [1.1.1] - 2026-09-25

Mejoras en el Probador de API: mas detalle sobre por que se acepta o rechaza una clave, y un
modo de envio en lote para probarla varias veces seguidas.

### Anadido

- **Envio en lote en el Probador de API**: numero de peticiones (hasta 100) e intervalo entre
  ellas configurables, con un boton para detener el lote a medias. Cada peticion queda registrada
  en una tabla -numero, si fue aceptada o rechazada, hora, codigo HTTP y duracion- y un clic en la
  fila despliega el detalle completo de esa peticion (cabeceras, cuerpo de la respuesta). Un
  resumen en vivo cuenta cuantas se han aceptado, rechazado o quedado en otro estado.
- La respuesta del Probador de API incluye ahora `categoriaEstado` (exito, rechazada, no
  encontrada, limite alcanzado, error del servidor o desconocido), para distinguir de un vistazo
  el tipo de resultado sin mirar el codigo HTTP.

### Cambiado

- El motivo de un 401 y el de un 403 ya no comparten el mismo mensaje: ahora dicen si la clave no
  esta autenticada o si esta autenticada pero sin permisos. Cuando la API devuelve un mensaje de
  error en el cuerpo (campos como `error`, `message` o `detail`) o una cabecera
  `WWW-Authenticate`, se anaden al motivo en vez de quedarse solo con el codigo de estado.

## [1.1.0] - 2026-09-13

Ocho herramientas de reconocimiento nuevas, un probador de claves API y un instalador para
Ubuntu Server sin Docker. Con esta version WebsTools llega a **74 herramientas** y se despliega
de dos maneras: con Docker, como hasta ahora, o como servicio de systemd sobre el propio
sistema.

### Anadido

- **Ocho herramientas de reconocimiento y OSINT** (la categoria pasa de 11 a 19):
  - **Buscar Usuario (Sherlock)**: busca un nombre de usuario en mas de 400 redes sociales y
    sitios web con la lista de sitios y las reglas de deteccion del proyecto Sherlock. La lista
    se refresca a diario desde GitHub y viene una copia en el repositorio por si no responde.
    Se puede limitar a unos 80 sitios populares (unos diez segundos) o recorrerlos todos, con o
    sin los marcados como NSFW. Un 403, un 429 o una pagina de desafio de un WAF se cuentan
    como "nos bloquean" en vez de como perfil encontrado, que es el falso positivo mas comun.
  - **Comprobar Email (Holehe)**: en que servicios esta registrado un email, con los 120
    modulos de la libreria holehe. Se excluyen siempre los cuatro modulos que averiguan la
    respuesta pidiendo un restablecimiento de contrasena, porque avisan al dueno de la cuenta.
  - **Analizar Cabeceras HTTP**: cabeceras de respuesta, cadena de redirecciones, cookies con
    sus atributos `Secure`/`HttpOnly`/`SameSite`, tecnologias que delatan servidor, framework o
    CDN, y las seis cabeceras de seguridad habituales con cual falta y para que sirve cada una.
  - **Escaner de Puertos**: conexion TCP a los 48 puertos mas habituales o a la lista y rangos
    que se indiquen (hasta 1024 por escaneo), con el nombre del servicio de cada uno abierto.
  - **Transferencia de Zona DNS (AXFR)**: pide la zona completa a cada servidor de nombres del
    dominio y, si alguno la entrega, muestra los registros expuestos.
  - **Wayback Machine**: primera captura, ultimas veinte capturas y enlaces al historico de una
    URL en archive.org.
  - **Extraer Datos de una Pagina**: emails, telefonos, perfiles en redes sociales, dominios
    enlazados, scripts de terceros y comentarios HTML de una pagina, junto a su titulo,
    descripcion, idioma y generador.
  - **robots.txt y Sitemap**: reglas por `User-agent`, sitemaps declarados y URLs que publican
    (sigue un indice de sitemaps y lee tambien los comprimidos).
- Limite propio de **3 ejecuciones por minuto** en Buscar Usuario, Comprobar Email y el Escaner
  de Puertos, que abren cientos de conexiones cada vez.
- `[osint] sherlockSitiosUrl` en `config.ini`: de donde se refresca la lista de sitios de
  Sherlock; vacia, se usa solo la copia del repositorio.
- **Probador de API** en Utilidades: envia una clave API (y un secreto opcional) a la URL que se
  indique -por cabecera `Authorization: Bearer`, `X-API-Key`, autenticacion basica o parametro
  de consulta, a eleccion- y dice si la clave fue aceptada, rechazada o si el endpoint dio algun
  otro error, junto al codigo de estado, la duracion, las cabeceras de limite de peticiones y el
  cuerpo de la respuesta.
- Dependencias nuevas: `holehe`, `httpx` y `trio`. No hacen falta paquetes nativos nuevos.
- **`install.sh`: instalacion nativa en Ubuntu Server**, sin Docker. Fuera de Docker habia que
  instalar a mano los cuatro paquetes nativos (`libmagic1`, `libzbar0`,
  `libimage-exiftool-perl`, `ffmpeg`) de los que dependen la deteccion de tipo, la lectura de
  QR, los metadatos y la conversion de video, y el que se dejaba uno lo descubria al usar esa
  herramienta. El script los instala con `apt`, crea el entorno virtual con Python 3.11+ (en
  Ubuntu 22.04 explica como traerlo del PPA deadsnakes), genera el `.env` con una `SECRET_KEY`
  aleatoria y registra el servicio `webstools` en systemd con los mismos parametros de gunicorn
  que la imagen Docker y el puerto de `config.ini`. Corre con el usuario que instala, dueno del
  clon, asi que el boton de actualizar de la web sigue funcionando. Abre el puerto en `ufw` si
  esta activo y espera a que `/healthz` responda antes de dar la instalacion por buena. Se
  puede relanzar para reinstalar o tras cambiar el puerto, y con `--actualizar` hace el `git
  pull` (apartando `config.ini` como `docker-update.sh`), reinstala las dependencias y
  reinicia.
- La CI ejecuta `install.sh` en un Ubuntu limpio y comprueba que el servicio queda activo,
  `/healthz` responde, las dependencias nativas cargan y el script es idempotente.

### Cambiado

- Los mensajes de la pantalla de ajustes dicen como reiniciar y como actualizar en los dos
  despliegues (`docker compose restart webtools` / `sudo systemctl restart webstools`).

### Corregido

- `docker-up.sh` y `docker-update.sh` estaban en el repositorio sin el bit de
  ejecucion (el proyecto se desarrolla en Windows, donde no existe): en un clon nuevo en Linux
  `./docker-up.sh` fallaba con `Permission denied` y habia que hacer `chmod +x` a mano.
- Ese `chmod +x` era ademas para git un cambio local, y `docker-update.sh` se negaba a
  actualizar por el ("Hay cambios locales que el pull pisaria: docker-up.sh,
  docker-update.sh") sin que nadie hubiese editado nada. Ahora solo cuentan los cambios de
  contenido: los de permisos se apartan y se restauran solos, como los de `config.ini`.

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
- **`docker-update.sh`**: actualiza la instalacion en marcha con un comando. Aparta los
  cambios locales de `config.ini` para que el pull no choque, etiqueta cada imagen con su
  version, espera a que la aplicacion responda de verdad y **vuelve sola a la version anterior**
  si la nueva no arranca en 90 segundos. Se reejecuta desde una copia, porque el propio `git
  pull` reemplaza el fichero que el interprete esta leyendo.
- **`/healthz` y healthcheck** en `docker-compose.yml`. No dice solo que el proceso siga vivo:
  cuenta las herramientas del catalogo y responde 503 si no hay ninguna, que es como se
  manifiesta una actualizacion con un modulo de categoria roto.
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

[1.1.1]: https://github.com/FranciscoFdez05/WebsTools/releases/tag/v1.1.1
[1.1.0]: https://github.com/FranciscoFdez05/WebsTools/releases/tag/v1.1.0
[1.0.0]: https://github.com/FranciscoFdez05/WebsTools/releases/tag/v1.0.0
