#!/usr/bin/env sh
# Instala WebsTools en un Ubuntu Server (o Debian) sin Docker y lo deja como servicio.
#
# Las 73 herramientas dependen, ademas de los paquetes de Python, de cuatro paquetes nativos
# que en una instalacion minima de Ubuntu Server no vienen: libmagic (tipo real de archivo),
# zbar (lectura de QR), exiftool (metadatos) y ffmpeg (conversion de video/audio). La imagen
# Docker ya los trae, pero fuera de Docker habia que instalarlos a mano, y el que se olvidaba
# de uno solo lo descubria al usar esa herramienta. Este script los instala todos, crea el
# entorno virtual, genera la SECRET_KEY y registra un servicio de systemd que arranca con el
# servidor, comprobando al final que la aplicacion responde de verdad.
#
# Se puede volver a ejecutar tantas veces como haga falta: reinstala lo que falte, vuelve a
# generar el servicio (por ejemplo tras cambiar el puerto en config.ini) y reinicia la app.
#
# Uso: ./install.sh              instala o reinstala lo que corra en este clon
#      ./install.sh --actualizar trae la version nueva con git pull y reinstala
set -e

RUTA="$(cd "$(dirname "$0")" && pwd)"
cd "$RUTA"

SERVICIO="webstools"
UNIDAD="/etc/systemd/system/${SERVICIO}.service"
ESPERA_SALUD=60   # segundos que se le dan a la aplicacion para responder
PAQUETES_APT="python3 python3-venv python3-pip git ca-certificates libmagic1 libzbar0 libimage-exiftool-perl ffmpeg"

aviso()  { printf '\n\033[33m%s\033[0m\n' "$*"; }
error()  { printf '\n\033[31m%s\033[0m\n' "$*" >&2; }
paso()   { printf '\n\033[36m── %s\033[0m\n' "$*"; }

ACTUALIZAR=0
for argumento in "$@"; do
    case "$argumento" in
        --actualizar) ACTUALIZAR=1 ;;
        -h|--help) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) error "Opcion desconocida: $argumento"; exit 1 ;;
    esac
done

# ── 0. Comprobaciones previas ─────────────────────────────────────────────────
paso "Comprobando el sistema"

# Como root, el clon y el venv quedan a nombre de root y el servicio correria como root sin
# necesidad. Se instala como el usuario normal, que es el dueno del clon y el que ejecutara
# la app: asi el boton de actualizar de la web puede hacer su git pull sobre el repositorio.
if [ "$(id -u)" -eq 0 ]; then
    error "No ejecutes install.sh como root ni con sudo."
    echo "       Ejecutalo como tu usuario normal: ./install.sh (pedira sudo cuando haga falta)" >&2
    exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
    error "Este instalador es para Ubuntu Server / Debian (usa apt-get)."
    echo "       En otras distribuciones instala a mano libmagic, zbar, exiftool y ffmpeg, o usa ./docker-up.sh" >&2
    exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
    error "No hay systemd (systemctl): el servicio no se puede registrar."
    echo "       Puedes arrancar la app a mano con .venv/bin/gunicorn, o usar ./docker-up.sh" >&2
    exit 1
fi

if ! command -v sudo >/dev/null 2>&1; then
    error "Hace falta sudo para instalar paquetes y registrar el servicio."
    exit 1
fi

USUARIO="$(id -un)"
GRUPO="$(id -gn)"
echo "Instalando en $RUTA como $USUARIO"

# ── 1. Traer la version nueva (solo con --actualizar) ─────────────────────────
# Mismo criterio que docker-update.sh: config.ini es donde se cambia el puerto, asi que
# tenerlo tocado es lo normal y se aparta durante el pull; cualquier otro cambio local para.
VERSION_ANTERIOR="$(sed -n 's/^VERSION = "\(.*\)"/\1/p' version.py | head -n 1)"
[ -n "$VERSION_ANTERIOR" ] || VERSION_ANTERIOR="desconocida"

if [ "$ACTUALIZAR" -eq 1 ]; then
    paso "Descargando la version nueva (instalada: $VERSION_ANTERIOR)"

    if [ ! -d .git ]; then
        error "Esto no es un clon de git, asi que no hay de donde traer la version nueva."
        exit 1
    fi

    AUTOSTASH=""
    if ! git diff --quiet 2>/dev/null; then
        # solo cambios de contenido: un chmod +x a los scripts no debe bloquear la actualizacion
        SUCIOS="$(git -c core.fileMode=false diff --name-only)"
        if [ -z "$SUCIOS" ] || [ "$SUCIOS" = "config.ini" ]; then
            [ -n "$SUCIOS" ] && aviso "config.ini tiene cambios locales (normal: es donde se cambia el puerto).
Se apartan durante la descarga y se vuelven a aplicar despues."
            AUTOSTASH="--autostash"
        else
            error "Hay cambios locales que el pull pisaria:"
            echo "$SUCIOS" | sed 's/^/    /' >&2
            echo "       Guardalos (git stash) o descartalos (git checkout -- .) antes de actualizar." >&2
            exit 1
        fi
    fi

    # --ff-only: si la rama local ha divergido, mejor parar que dejar un conflicto a medias
    if ! git pull --ff-only $AUTOSTASH; then
        error "El pull no se pudo aplicar. No se ha tocado la instalacion."
        [ -n "$AUTOSTASH" ] && aviso "Revisa 'git stash list': tus cambios de config.ini pueden haberse quedado guardados."
        exit 1
    fi
fi

VERSION="$(sed -n 's/^VERSION = "\(.*\)"/\1/p' version.py | head -n 1)"
[ -n "$VERSION" ] || VERSION="desconocida"
if [ "$ACTUALIZAR" -eq 1 ] && [ "$VERSION" != "$VERSION_ANTERIOR" ]; then
    echo "Actualizando: $VERSION_ANTERIOR → $VERSION"
    if [ -f CHANGELOG.md ]; then
        paso "Novedades de la $VERSION"
        awk '/^## \[/{n++} n==1{print} n==2{exit}' CHANGELOG.md
    fi
fi

# ── 2. Paquetes del sistema ───────────────────────────────────────────────────
paso "Instalando los paquetes del sistema"
echo "$PAQUETES_APT" | tr ' ' '\n' | sed 's/^/    /'
sudo apt-get update -qq
# DEBIAN_FRONTEND: que exiftool/ffmpeg no se paren en una pregunta de configuracion
# shellcheck disable=SC2086  # la lista se parte en palabras a proposito
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends $PAQUETES_APT

# ── 3. Interprete de Python ───────────────────────────────────────────────────
# La app necesita 3.11 o superior (son las versiones que prueba la CI). Ubuntu 24.04 trae
# 3.12; Ubuntu 22.04 se queda en 3.10, y ahi hay que traer uno mas nuevo (ver el aviso).
PY=""
for candidato in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidato" >/dev/null 2>&1 \
       && "$candidato" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
        PY="$(command -v "$candidato")"
        break
    fi
done

if [ -z "$PY" ]; then
    error "Hace falta Python 3.11 o superior y solo hay $(python3 --version 2>&1)."
    cat <<'FIN' >&2

  En Ubuntu 22.04 se instala desde el PPA deadsnakes y luego se relanza este script:

      sudo add-apt-repository -y ppa:deadsnakes/ppa
      sudo apt-get install -y python3.12 python3.12-venv
      ./install.sh

FIN
    exit 1
fi
echo "Python: $PY ($("$PY" --version 2>&1))"

# ── 4. Entorno virtual y dependencias de Python ───────────────────────────────
paso "Instalando las dependencias de Python en .venv"

# Un venv creado con otro interprete (o copiado de otra maquina) no sirve: se rehace
if [ -d .venv ] && ! .venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    aviso "El .venv existente usa un Python demasiado antiguo: se vuelve a crear."
    rm -rf .venv
fi
[ -x .venv/bin/python ] || "$PY" -m venv .venv

.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt

# ── 5. Clave secreta ──────────────────────────────────────────────────────────
# Igual que docker-up.sh: la clave del repositorio es publica, con ella cualquiera podria
# firmar sesiones validas. Se genera una y se regenera si el .env aun tiene la de ejemplo.
if [ ! -f .env ] || grep -q '^SECRET_KEY=change-me-generate-a-real-one$' .env; then
    BASE=.env.example
    [ -f .env ] && BASE=.env
    SECRET_KEY="$(.venv/bin/python -c 'import secrets; print(secrets.token_hex(32))')"
    sed "s/^SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" "$BASE" > .env.tmp && mv .env.tmp .env
    echo "Escrito .env con una SECRET_KEY nueva generada automaticamente."
fi
# systemd lo lee como EnvironmentFile y la clave no debe poder leerla cualquier usuario
chmod 600 .env

# ── 6. Puerto ─────────────────────────────────────────────────────────────────
# config.ini es la unica fuente del puerto, tambien aqui: se lee con la misma capa que la app
HOST="$(.venv/bin/python -c "import configparser;c=configparser.ConfigParser();c.read('config.ini');print(c.get('server','host',fallback='0.0.0.0'))")"
PORT="$(.venv/bin/python -c "import configparser;c=configparser.ConfigParser();c.read('config.ini');print(c.getint('server','port',fallback=8500))")"

# ── 7. Servicio de systemd ────────────────────────────────────────────────────
paso "Registrando el servicio $SERVICIO"

# Los mismos parametros de gunicorn que el Dockerfile, y por las mismas razones: un solo
# proceso con hilos para que el limitador comparta sus contadores, y timeout de 180 s porque
# el descargador de video y las subidas grandes tardan mas que los 30 s por defecto.
# El .env entra como EnvironmentFile: SECRET_KEY, FLASK_DEBUG y AJUSTES_PASSWORD.
sudo tee "$UNIDAD" >/dev/null <<FIN
# Generado por install.sh de WebsTools. Para cambiar puerto o usuario, edita config.ini o
# vuelve a ejecutar ./install.sh en vez de tocar este fichero: se sobreescribe.
[Unit]
Description=WebsTools ${VERSION} (navaja suiza web de ciberseguridad y administracion)
Documentation=https://github.com/FranciscoFdez05/WebsTools
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${USUARIO}
Group=${GRUPO}
WorkingDirectory=${RUTA}
EnvironmentFile=${RUTA}/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=${RUTA}/.venv/bin/gunicorn --bind ${HOST}:${PORT} --workers 1 --threads 8 --timeout 180 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
FIN

sudo systemctl daemon-reload
sudo systemctl enable --quiet "$SERVICIO"
sudo systemctl restart "$SERVICIO"

# ── 8. Firewall ───────────────────────────────────────────────────────────────
# Solo si ufw esta activo: si no lo esta, abrir una regla no cambia nada y activar el
# firewall por su cuenta podria dejar fuera al SSH de quien esta instalando.
if command -v ufw >/dev/null 2>&1 && sudo ufw status 2>/dev/null | grep -q '^Status: active'; then
    paso "Abriendo el puerto $PORT en ufw"
    sudo ufw allow "$PORT/tcp" >/dev/null && echo "Regla anadida: $PORT/tcp"
fi

# ── 9. Comprobar que responde de verdad ───────────────────────────────────────
# /healthz cuenta las herramientas del catalogo y responde 503 si no hay ninguna: distingue
# "el proceso esta arriba" de "la aplicacion sirve"
paso "Esperando a que responda (hasta ${ESPERA_SALUD}s)"

comprobar_salud() {
    .venv/bin/python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:${PORT}/healthz',timeout=5).read().decode())" 2>/dev/null
}

sano=0
i=0
while [ "$i" -lt "$ESPERA_SALUD" ]; do
    if comprobar_salud >/dev/null; then
        sano=1
        break
    fi
    i=$((i + 1))
    printf '.'
    sleep 1
done
printf '\n'

if [ "$sano" -ne 1 ]; then
    error "La aplicacion no responde tras ${ESPERA_SALUD}s."
    echo
    echo "Ultimas lineas del log:"
    sudo journalctl -u "$SERVICIO" -n 40 --no-pager 2>&1 || true
    if [ "$ACTUALIZAR" -eq 1 ] && [ "$VERSION_ANTERIOR" != "desconocida" ] && [ "$VERSION" != "$VERSION_ANTERIOR" ]; then
        cat <<FIN

  Para volver a la version anterior:

      git checkout v${VERSION_ANTERIOR} && ./install.sh

FIN
    fi
    exit 1
fi

comprobar_salud || true

# ── 10. Listo ─────────────────────────────────────────────────────────────────
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[ -n "$IP" ] || IP="<ip-del-servidor>"
cat <<FIN

WebsTools $VERSION instalado como servicio de systemd. Accesible desde cualquier
dispositivo de la LAN en:
  http://$IP:$PORT

Gestion del servicio:
  sudo systemctl status $SERVICIO      estado
  sudo journalctl -u $SERVICIO -f      logs en vivo
  sudo systemctl restart $SERVICIO     reiniciar (tras actualizar desde la web)
  ./install.sh --actualizar            traer la version nueva y reinstalar
FIN
