# WebsTools

---

**Version 1.0.0**

Navaja suiza web para ciberseguridad y administracion de sistemas: **65 herramientas** de
analisis de archivos, criptografia, OSINT, redes, texto y utilidades, reunidas en una sola
interfaz. Se despliega con un unico comando en un servidor de la red local y queda accesible
desde el navegador de cualquier dispositivo de la LAN — sin instalar nada en los clientes.

![Menu principal de WebsTools](img/mainMenu.png)

## ✨ Características ✨

---

### 📁 Analisis de Archivos (10)

| Herramienta | Descripcion |
| --- | --- |
| Generar Hashes | Calcula MD5, SHA1, SHA256 y SHA512 de un archivo |
| Verificar Hash | Comprueba si el hash de un archivo coincide con el esperado |
| Detectar Tipo Real | Detecta el tipo real de un archivo por su contenido, no por la extension |
| Calcular Entropia | Entropia de Shannon, para detectar cifrado o empaquetado |
| Ver Metadatos | Muestra los metadatos EXIF de una imagen o de un PDF |
| Eliminar Metadatos | Limpia los metadatos y descarga el archivo saneado |
| Editar Metadatos | Edita etiquetas EXIF de una imagen y descarga el resultado |
| Extraer Strings | Extrae cadenas imprimibles de un binario (equivalente a `strings`) |
| Visor de Base de Datos | Explora una SQLite: tablas, vistas, esquema y filas |
| Analizar Firma Digital | Comprueba la firma Authenticode de un ejecutable PE de Windows |

### 🔐 Criptografia (9)

| Herramienta | Descripcion |
| --- | --- |
| Generar Claves RSA | Par de claves RSA privada y publica en formato PEM |
| Generar Clave AES | Clave AES aleatoria en Base64 y Hex |
| Cifrar AES-GCM | Cifra un texto con AES en modo GCM usando una clave Base64 |
| Descifrar AES-GCM | Descifra un texto cifrado con AES-GCM |
| Cifrar RSA | Cifra un texto con una clave publica RSA (OAEP-SHA256) |
| Descifrar RSA | Descifra un texto con una clave privada RSA (OAEP-SHA256) |
| Generar HMAC | Calcula el HMAC de un texto con una clave secreta |
| JWT Inspector | Decodifica un JWT y valida su firma si se aporta la clave o secreto |
| Generar Certificado Autofirmado | Certificado X.509 autofirmado junto a su clave privada |

### 🔎 OSINT (11)

| Herramienta | Descripcion |
| --- | --- |
| WHOIS | Datos de registro publico de un dominio |
| DNS Lookup | Consulta los registros DNS de un dominio |
| Reverse DNS | Nombre de host asociado a una IP |
| DNS Propagation | Consulta un registro contra varios resolvers publicos |
| Geolocalizacion IP | Ubicacion aproximada de una direccion IP |
| ASN Lookup | Sistema autonomo (ASN) al que pertenece una IP |
| Comprobar SPF | Comprueba si un dominio tiene un registro SPF publicado |
| Comprobar DKIM | Comprueba el registro DKIM de un dominio para un selector |
| Comprobar DMARC | Comprueba si un dominio tiene un registro DMARC publicado |
| Comprobar IP Cloudflare | Verifica si una IP esta en los rangos publicados por Cloudflare |
| Buscar Subdominios | Subdominios via Certificate Transparency (crt.sh) |

### 🌐 Redes (7)

| Herramienta | Descripcion |
| --- | --- |
| Conversor CIDR | Direccion de red, mascara y broadcast a partir de un CIDR |
| Calculadora de Subredes | Rango de hosts utilizables de una subred |
| Calculadora Wildcard | Mascara wildcard inversa de un CIDR |
| Validar IPv4/IPv6 | Comprueba validez y version de una IP |
| Conversor IP ↔ Decimal | IPv4 a su representacion decimal y viceversa |
| Conversor IPv4 ↔ IPv6 | IPv4 a IPv6 mapeada (`::ffff:a.b.c.d`) y viceversa |
| Generador de MAC Aleatorias | Direccion MAC unicast administrada localmente |

### 📝 Texto (8)

| Herramienta | Descripcion |
| --- | --- |
| Codificar Texto | Codifica a Base64, URL Encode, HTML Encode, Hex, Binario o ASCII |
| Decodificar Texto | Decodifica desde Base64, URL Encode, HTML Encode, Hex, Binario o ASCII |
| JWT Decoder | Cabecera y cuerpo de un JWT sin verificar la firma |
| Generador de UUID | UUID version 1 o version 4 |
| Generador de Contrasenas | Longitud y conjuntos de caracteres configurables |
| Generador de Passphrase | Estilo diceware, a partir de una wordlist embebida |
| Comprobar Fortaleza de Contrasena | Analisis con la libreria zxcvbn |
| Comparador de Textos (Diff) | Compara dos textos y muestra las diferencias linea a linea |

### 🛠️ Utilidades (12)

| Herramienta | Descripcion |
| --- | --- |
| Descargador de Video/Audio | MP4 o MP3 desde YouTube, Twitter/X, TikTok y otras webs |
| URL Directa de Video (VLC) | URL del stream para abrirla en VLC u otro reproductor, sin descargar nada |
| Internet Downloader | Descarga desde una URL publica (solo http/https, IPs privadas bloqueadas) |
| QR Generator | Genera un codigo QR desde un texto o URL y lo descarga como PNG |
| QR Reader | Lee el contenido de uno o varios codigos QR en una imagen |
| Conversor Timestamp ↔ Fecha | Timestamp Unix a ISO 8601 y viceversa |
| Conversor Unix Time | Entre segundos y milisegundos Unix |
| Conversor de Unidades | Longitud, peso, datos y temperatura |
| Generador de Claves API | Clave aleatoria criptograficamente segura |
| Generador de Lorem Ipsum | Parrafos de texto de relleno |
| Generador de Nombres Aleatorios | Nombres y apellidos aleatorios |
| Generador de User-Agent | User-Agent real de una lista curada por navegador |

### 💻 JSON y Programacion (8)

| Herramienta | Descripcion |
| --- | --- |
| Formatear JSON | Indenta y da formato legible a un JSON |
| Validar JSON | Comprueba si un texto es JSON valido |
| Minificar JSON | Elimina espacios y saltos de linea innecesarios de un JSON |
| Beautify XML | Indenta y da formato legible a un XML |
| Beautify HTML | Indenta y da formato legible a un HTML |
| Beautify CSS | Indenta y da formato legible a un CSS |
| Beautify JavaScript | Indenta y da formato legible a un JavaScript |
| Ofuscar JavaScript | Ofusca codigo JavaScript para dificultar su lectura manteniendolo ejecutable |

### Ademas

- 🔎 **Buscador global** — desde la pantalla principal se filtran todas las herramientas por
  nombre, descripcion o categoria: pulsa `/` para escribir, `Enter` para abrir la primera
  coincidencia y `Esc` para limpiar. Cada categoria tiene ademas su propio filtro.
- 📊 **Resultados legibles** — cada respuesta se presenta como fichas de campo, tablas e
  insignias en lugar de un volcado de JSON, con el estado y el tiempo de la peticion, copia de
  un valor con un clic y botones para copiar o guardar el resultado entero. El JSON crudo sigue
  a un clic con **Ver JSON**.
- ⚠️ **Errores explicados** — un fallo de la herramienta, el limite de peticiones o un archivo
  demasiado grande se explican en el panel en vez de aparecer como un JSON de error o una
  pagina HTML del servidor.
- ⌨️ **Formularios con ayudas** — ejemplos dentro del campo, campos obligatorios marcados y
  validados antes de enviar, `Ctrl + Enter` para ejecutar y `Limpiar` para empezar de cero.
- 🔒 **Rate limiting por IP** — 20 ejecuciones/minuto de forma global, 15 en OSINT, 6 en el
  descargador de video y 2 al actualizar la aplicacion, para evitar abusos desde la red. Solo cuentan las llamadas a las
  herramientas: navegar por el catalogo no gasta cupo. Al alcanzarlo, la respuesta dice en JSON
  cuantos segundos faltan y lo repite en la cabecera `Retry-After`.
- 🐳 **Despliegue en un comando** — `./docker-up.sh` genera el `.env`, crea la `SECRET_KEY` y
  levanta el contenedor con todas las dependencias nativas ya incluidas.
- ⚙️ **Configuracion centralizada** — puerto, limites de subida y timeouts en un unico `config.ini`.
- 🔄 **Ajustes con recarga de herramientas** — desde `/ajustes` (icono ⚙️ de la cabecera) se
  relee el catalogo de herramientas desde disco sin reiniciar el servidor.
- ⬆️ **Actualizacion desde la propia web** — `/ajustes` compara la version instalada con la
  ultima release publicada en GitHub y, si hay una nueva, la trae con un `git pull` sin
  entrar por SSH al servidor.
- 🕘 **Herramientas recientes** — la pantalla principal recuerda las ultimas seis que has
  abierto y las deja a un clic. Se guardan en tu navegador, no en el servidor, asi que cada
  dispositivo tiene las suyas.
- 🔔 **Aviso de version nueva** — si hay una release mas reciente aparece un indicador en la
  cabecera de cualquier pagina, sin tener que entrar a mirar en ajustes.
- 🔑 **Ajustes con contrasena opcional** — `ajustesPassword` protege la pantalla de ajustes y
  sus acciones, que son las que pueden cambiar el codigo que ejecuta el servidor.
- 🔁 **Reinicio automatico y healthcheck** — el contenedor usa `restart: unless-stopped` y
  publica `/healthz`, asi que sobrevive a reinicios del servidor y deja ver si esta sano.

## 🖥️ Requisitos

---

**Para el despliegue (recomendado):**

- Un servidor Linux en la LAN con **Docker** y el plugin **Docker Compose v2**
- **Python 3** en el host, unicamente para que `docker-up.sh` lea `config.ini` y genere la clave
- El puerto elegido (por defecto el `8500`) libre y abierto en el firewall

**Para ejecutarlo sin Docker (desarrollo):** Python 3.11+ y estas dependencias nativas, de las
que dependen varias herramientas:

| Paquete | Herramientas que lo necesitan |
| --- | --- |
| `libmagic1` | Deteccion de tipo real de archivo |
| `libzbar0` | Lectura de codigos QR |
| `libimage-exiftool-perl` | Ver, editar y eliminar metadatos de imagenes |
| `ffmpeg` | Conversion de video/audio del descargador multimedia |

```bash
sudo apt-get install libmagic1 libzbar0 libimage-exiftool-perl ffmpeg
```

> ⚠️ En **Windows** la app arranca pero muestra un aviso: esas cuatro dependencias no vienen de
> serie y las herramientas que las usan fallaran. Para funcionalidad completa, usa Linux o Docker.
> La imagen Docker ya las incluye todas.

## 📦 Guía de instalación ⚙️

---

### Opcion A — Docker (recomendada)

```bash
git clone https://github.com/FranciscoFdez05/WebsTools.git
cd WebsTools
chmod +x docker-up.sh    # solo la primera vez, si se perdio el bit de ejecucion
./docker-up.sh
```

`docker-up.sh` es el **unico punto de entrada**. En cada arranque:

1. Crea el `.env` a partir de `.env.example` con una `SECRET_KEY` aleatoria de 32 bytes (y la
   regenera si detecta que aun tiene el valor de ejemplo).
2. Lee el puerto de `config.ini` y lo exporta para que `docker-compose.yml` publique el mismo
   valor dentro y fuera del contenedor.
3. Construye la imagen y levanta el servicio en segundo plano.
4. Imprime la URL con la IP LAN del servidor.

> ❌ No ejecutes `docker compose up` directamente: sin las variables que exporta el script el
> arranque falla a proposito, para no levantar el servicio con una clave insegura o un puerto
> descoordinado.

### Opcion B — Local, sin Docker

```bash
git clone https://github.com/FranciscoFdez05/WebsTools.git
cd WebsTools
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## 📋 Guía de uso 🕹️

---

### Acceder desde otro dispositivo de la LAN

Abre en el navegador de cualquier movil, portatil o tablet de la misma red:

```
http://<ip-del-servidor>:<puerto>
```

Por ejemplo `http://192.168.1.50:8500`. La IP exacta te la imprime `docker-up.sh` al terminar.
No hay que instalar nada en el dispositivo cliente.

Si desde el servidor funciona pero desde otro equipo no, casi siempre es el firewall:

```bash
sudo ufw allow 8500/tcp
```

### La pantalla de una herramienta

A la izquierda queda el formulario y a la derecha el panel de resultados. Los campos
obligatorios llevan un asterisco y se validan antes de enviar nada, los campos vacios no se
envian (asi la herramienta aplica su valor por defecto) y `Ctrl + Enter` ejecuta sin soltar el
teclado.

En el panel, la cabecera indica si la ejecucion fue bien y cuanto tardo. Un clic sobre
cualquier valor lo copia al portapapeles -util para hashes, claves y tokens-, **Copiar** y
**Guardar .json** se llevan el resultado completo y **Ver JSON** alterna entre la vista legible
y la respuesta cruda de la API. Las herramientas que generan un archivo lo descargan solas y
dejan en el panel su nombre, tamano, una previsualizacion si es una imagen y un enlace para
volver a descargarlo.

### Actualizar WebsTools a una version nueva

El icono ⚙️ de la cabecera abre `/ajustes`. Su primera seccion muestra la version instalada y
consulta la ultima release publicada en el repositorio. Si hay una mas nueva aparece el boton
**Actualizar ahora**, que hace un `git pull --ff-only` sobre el propio clon desde el que corre
la app y muestra los commits que ha traido.

Despues de actualizar hay que **reiniciar** para que entren las rutas nuevas, las dependencias
y el numero de version, porque el proceso sigue con el codigo anterior cargado en memoria:

```bash
docker compose restart webtools     # o ./docker-up.sh si el requirements.txt ha cambiado
```

Para que el boton funcione, el despliegue tiene que cumplir tres cosas, que la propia pantalla
comprueba y explica si fallan:

- El codigo se ejecuta desde un **clon de git** con el remoto `origin` configurado (es lo que
  deja `git clone` de la guia de instalacion).
- **git** esta instalado donde corre la app. La imagen Docker ya lo trae, y
  `docker-compose.yml` monta el clon del host en `/app` para que el pull actualice los dos a la
  vez, no solo el contenedor.
- **No hay cambios locales sin confirmar**: un `pull` sobre un arbol sucio se quedaria a medias
  en un conflicto, asi que se rechaza antes de empezar.

Tambien se niega a fusionar: si la rama local ha divergido del remoto, el pull se aborta y lo
dice, en vez de dejar conflictos en un servidor donde nadie los va a resolver.

> 🔒 Cualquiera que llegue a la web puede pulsar ese boton, y lo que trae es codigo que el
> servidor ejecutara. En una red en la que no confies del todo, pon
> `permitirAplicar = false` en `config.ini`: la app seguira avisando de que hay una version
> nueva, pero solo se podra aplicar a mano desde el servidor.

### Proteger los ajustes con contrasena

La pantalla de ajustes es la unica que puede cambiar lo que el servidor ejecuta, asi que admite
una contrasena. Vacia (por defecto) se comporta como siempre y no pide nada:

```ini
[app]
ajustesPassword = la-que-quieras
```

En Docker se puede pasar tambien por entorno, que tiene prioridad: `AJUSTES_PASSWORD` en el
`.env`. Se pide con autenticacion HTTP basica -el dialogo propio del navegador, sin formulario
que mantener- y cubre `/ajustes`, recargar herramientas y actualizar la aplicacion. El usuario
da igual, solo se comprueba la contrasena.

Queda fuera a proposito la consulta de version (`/api/ajustes/version`): solo devuelve un
numero y la usa el aviso de la cabecera en todas las paginas.

### Recargar el catalogo de herramientas

La segunda seccion de `/ajustes` tiene el boton **Actualizar herramientas**, que vuelve a leer
desde disco el catalogo de cada categoria y muestra las herramientas anadidas o eliminadas sin
reiniciar el contenedor: util despues de editar nombres, descripciones o campos de una
herramienta, y lo que la app hace sola tras traer una actualizacion.

Una herramienta **nueva con su propia ruta API** si necesita reiniciar la aplicacion, porque
Flask no admite registrar rutas nuevas con el servidor ya arrancado:

```bash
docker compose restart webtools
```

### Cambiar el puerto

Edita **solo** el valor `port` de la seccion `[server]` en `config.ini` y vuelve a lanzar el script:

```ini
[server]
host = 0.0.0.0
port = 8500
debug = false
```

```bash
./docker-up.sh
```

`config.ini` es la unica fuente del puerto — no lo definas a mano en `.env`, en
`docker-compose.yml` ni como variable de entorno suelta, o los valores se desincronizaran.

### Otros ajustes de `config.ini`

| Clave | Que hace |
| --- | --- |
| `[app] maxUploadMb` | Tamano maximo de los archivos que se pueden subir (32 MB por defecto) |
| `[app] ajustesPassword` | Contrasena de `/ajustes` y de sus acciones. Vacia = sin contrasena |
| `[app] rateLimitStorageUri` | Donde se cuentan las peticiones por IP. `memory://` sirve con un solo proceso |
| `[osint] timeoutSegundos` | Timeout de las consultas WHOIS/DNS |
| `[osint] geolocalizacionUrl` | Servicio de geolocalizacion por IP |
| `[proxy] confiarXForwardedFor` | Usar `X-Forwarded-For` como IP real del cliente. Ponlo en `true` **solo** si hay un proxy inverso delante; si no, cualquiera puede falsear la cabecera y saltarse el rate limit. Por eso viene en `false` |
| `[actualizaciones] repoGithub` | Repositorio con cuya ultima release se compara la version instalada |
| `[actualizaciones] timeoutSegundos` | Timeout de la consulta a la API de GitHub |
| `[actualizaciones] permitirAplicar` | Deja que el boton de Ajustes traiga la version nueva con `git pull`. En `false` solo avisa |

### Gestion del contenedor

```bash
docker compose logs -f webtools    # ver los logs en vivo
docker compose restart webtools    # reiniciar
docker compose down                # parar y eliminar el contenedor
./docker-up.sh                     # reconstruir y levantar tras cambiar codigo o config
```

### Tests

```bash
pytest
```

En Windows se saltan solos los tests que necesitan `libmagic` o `exiftool`, que no estan
disponibles ahi. Esos se ejecutan de verdad en la CI de GitHub Actions, que instala las cuatro
dependencias nativas en Linux, corre la suite completa y ademas construye la imagen Docker y
comprueba que la aplicacion levanta y responde en `/healthz`.

## 🏷️ Publicar una version 🏷️

---

La version vive en un unico sitio, [`version.py`](version.py), y de ahi la leen el pie de
pagina, la pantalla de ajustes y la comparacion con GitHub. El numero sigue
[versionado semantico](https://semver.org/lang/es/): parche para correcciones, menor para
herramientas o funciones nuevas compatibles, mayor para cambios que rompen un despliegue
existente.

Para publicar:

1. Sube `VERSION` en [`version.py`](version.py).
2. Anade la entrada correspondiente al [CHANGELOG](CHANGELOG.md).
3. Confirma los dos cambios y etiqueta el commit con el **mismo numero** precedido de `v`:

   ```bash
   git commit -am "Release 1.1.0"
   git tag -a v1.1.0 -m "WebsTools 1.1.0"
   git push origin main --follow-tags
   ```

4. Crea la **release** en GitHub, que es lo que la app consulta:

   ```bash
   gh release create v1.1.0 --title "WebsTools 1.1.0" --notes-file CHANGELOG.md
   ```

> ⚠️ La app compara contra **releases publicadas**, no contra etiquetas. Una etiqueta sin
> release no hace que nadie vea la actualizacion.

La CI comprueba en cada etiqueta que el numero coincide con el de `version.py`, para que no se
publique una release cuyo numero no sea el que la aplicacion muestra.

## 🤝 Contribuciones 🤝

---

Las contribuciones son bienvenidas. Para proponer un cambio:

1. Haz un fork del repositorio y crea una rama descriptiva (`git checkout -b feature/mi-herramienta`).
2. Sigue las convenciones del proyecto: nombres en `camelCase`, codigo y comentarios en espanol
   sin tildes, y la logica de cada herramienta separada en `logic.py` de su ruta en `routes.py`.
3. Anade una herramienta nueva registrandola en el diccionario `TOOLS` de la categoria que le
   corresponda, dentro de [categories/](categories/). Cada campo se declara con `nombre`,
   `tipo` y `etiqueta`, y admite ademas estas claves opcionales:

   | Clave | Que hace |
   | --- | --- |
   | `placeholder` | Ejemplo dentro del campo. Si no se indica, se saca de la etiqueta cuando acaba en `(ej. ...)` |
   | `ayuda` | Aclaracion bajo el campo. Si no se indica, se saca de la etiqueta cuando acaba en otro parentesis, como `(4-128)` |
   | `requerido` | Marca el campo como obligatorio y lo valida antes de enviar. Ya lo son por defecto los archivos y el campo unico de una herramienta |
   | `defecto` | Valor con el que aparece relleno el campo |
4. Acompana el cambio con tests en [tests/](tests/) y comprueba que `pytest` pasa en verde.
5. Abre un Pull Request explicando que aporta el cambio.

Si encuentras un fallo o se te ocurre una herramienta util, abre un issue.

## 📜 Licencia

---

📄 Este proyecto está licenciado bajo la Licencia MIT. Consulta el archivo `LICENSE` para más detalles..

---

**Developed with ❤️ by [Francisco](https://github.com/FranciscoFdez05)**
