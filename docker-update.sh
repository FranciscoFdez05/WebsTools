#!/usr/bin/env sh
# Actualiza la instalacion en marcha y la deja comprobada.
#
# La actualizacion a mano era `git pull && ./docker-up.sh`, con cuatro cosas que
# solo se descubrian tarde:
#
#   1. `config.ini` esta versionado y el README manda editarlo para cambiar el
#      puerto, asi que casi toda instalacion en marcha lo tiene tocado y el pull
#      se para en seco. Aqui se detecta ANTES de tocar nada: si lo unico que
#      cambia es config.ini, el cambio se aparta y se vuelve a poner despues del
#      pull; si hay mas, se explica y no se toca nada.
#   2. Nada verificaba que la version nueva arrancase. El contenedor se quedaba
#      arriba con `restart: unless-stopped` reiniciandose en bucle, y te
#      enterabas al abrir la web. Aqui se espera a que `/healthz` responda, que
#      no dice solo que Flask este vivo: comprueba que el catalogo de
#      herramientas se ha cargado, que es lo que se rompe al actualizar.
#   3. `docker compose build` sin etiqueta deja solo la imagen nueva, asi que
#      volver atras era reconstruir desde el codigo anterior. Ahora cada version
#      queda etiquetada y la vuelta atras es inmediata.
#   4. Este script se actualiza a si mismo. El `git pull` reemplaza el fichero
#      que el interprete esta leyendo, y `sh` guarda un desplazamiento dentro de
#      el: si el fichero nuevo tiene otro tamano, las ordenes que quedan por leer
#      se descolocan y la actualizacion se queda a medias por un error de
#      sintaxis absurdo. Por eso lo primero que hace es ejecutarse desde una
#      copia (ver abajo).
#
# Si el arranque no responde, se vuelve solo a la imagen anterior.
#
# Uso: ./docker-update.sh [--sin-pull]
set -e

# El directorio del proyecto se fija antes que nada: la copia de la que se
# reejecuta vive en /tmp, asi que alli `dirname "$0"` ya no sirve.
WT_PROYECTO="${WT_PROYECTO:-$(cd "$(dirname "$0")" && pwd)}"
export WT_PROYECTO
cd "$WT_PROYECTO"

# Reejecutarse desde una copia: lo que corre es una foto del script, y el pull
# de mas abajo puede reemplazar el original sin descolocar esta ejecucion. Si no
# se pudiera crear la copia se sigue igualmente: es una proteccion, no un
# requisito.
if [ -z "$WT_UPDATE_COPIA" ]; then
    copia=$(mktemp "${TMPDIR:-/tmp}/docker-update.XXXXXX" 2>/dev/null) || copia=""
    if [ -n "$copia" ] && cp "$0" "$copia" 2>/dev/null; then
        WT_UPDATE_COPIA="$copia"
        export WT_UPDATE_COPIA
        codigo=0
        sh "$copia" "$@" || codigo=$?
        rm -f "$copia"
        exit "$codigo"
    fi
fi

SIN_PULL=0
[ "$1" = "--sin-pull" ] && SIN_PULL=1

SERVICIO="webtools"
IMAGEN="webstools"
ESPERA_SALUD=90   # segundos que se le dan a la version nueva para responder

# Con sudo, el git pull deja los ficheros del repositorio a nombre de root, y a
# partir de ahi ni tu usuario ni el boton de actualizar de la propia web pueden
# volver a escribir en el clon. Docker no necesita sudo cuando el usuario
# pertenece al grupo docker.
if [ "$(id -u)" -eq 0 ]; then
    echo "ERROR: no ejecutes docker-update.sh con sudo." >&2
    echo "       Ejecutalo como tu usuario normal: ./docker-update.sh" >&2
    exit 1
fi

# ── Interprete Python ─────────────────────────────────────────────────────────
# Mismo criterio que docker-up.sh; si el servidor no lo tiene, se usa la imagen
# base, que hace falta igualmente para construir el contenedor.
if command -v python3 >/dev/null 2>&1; then
    PY_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PY_CMD="python"
else
    PY_CMD=""
fi

run_py() {
    if [ -n "$PY_CMD" ]; then
        "$PY_CMD" -c "$1"
    else
        docker run --rm -v "$PWD:/w" -w /w python:3.11-slim python -c "$1"
    fi
}

version_del_codigo() {
    sed -n 's/^VERSION = "\(.*\)"/\1/p' version.py | head -n 1
}

# curl no viene de serie en toda instalacion minima; Python si esta si hemos
# llegado hasta aqui, y para el resto queda el propio contenedor
comprobar_salud() {
    if command -v curl >/dev/null 2>&1; then
        curl -fsS "http://localhost:${PORT}/healthz" 2>/dev/null
    else
        run_py "import urllib.request;print(urllib.request.urlopen('http://localhost:${PORT}/healthz',timeout=5).read().decode())" 2>/dev/null
    fi
}

aviso()  { printf '\n\033[33m%s\033[0m\n' "$*"; }
error()  { printf '\n\033[31m%s\033[0m\n' "$*" >&2; }
paso()   { printf '\n\033[36m── %s\033[0m\n' "$*"; }

# ── 1. Comprobaciones previas ─────────────────────────────────────────────────
paso "Comprobando el estado local"

if [ ! -f .env ]; then
    error "No hay .env. Esto es una instalacion nueva: usa ./docker-up.sh."
    exit 1
fi

if [ ! -d .git ]; then
    error "Esto no es un clon de git, asi que no hay de donde traer la version nueva."
    echo "       Instalalo con: git clone https://github.com/FranciscoFdez05/WebsTools.git" >&2
    exit 1
fi

# config.ini se distribuye con el codigo y a la vez es donde el README manda
# cambiar el puerto: tenerlo modificado es lo normal, no un descuido. Se aparta
# durante el pull y se vuelve a poner despues.
AUTOSTASH=""
if [ "$SIN_PULL" -eq 0 ] && ! git diff --quiet 2>/dev/null; then
    SUCIOS=$(git diff --name-only)
    if [ "$SUCIOS" = "config.ini" ]; then
        aviso "config.ini tiene cambios locales (normal: es donde se cambia el puerto).
Se apartan durante la descarga y se vuelven a aplicar despues."
        AUTOSTASH="--autostash"
    else
        error "Hay cambios locales que el pull pisaria:"
        echo "$SUCIOS" | sed 's/^/    /' >&2
        cat <<'FIN'

  Confirmalos o guardalos antes de actualizar:

      git stash            para apartarlos y recuperarlos luego con git stash pop
      git checkout -- .    para descartarlos

FIN
        exit 1
    fi
fi

VERSION_ANTERIOR=$(version_del_codigo)
[ -n "$VERSION_ANTERIOR" ] || VERSION_ANTERIOR="desconocida"
echo "Version instalada: $VERSION_ANTERIOR"

# ── 2. Traer los cambios ──────────────────────────────────────────────────────
if [ "$SIN_PULL" -eq 0 ]; then
    paso "Descargando la version nueva"
    # --ff-only: si la rama local ha divergido, mejor parar que dejar un
    # conflicto a medias en un servidor donde nadie lo va a resolver
    if ! git pull --ff-only $AUTOSTASH; then
        error "El pull no se pudo aplicar. No se ha tocado el contenedor."
        [ -n "$AUTOSTASH" ] && aviso "Revisa 'git stash list': tus cambios de config.ini pueden haberse quedado guardados."
        exit 1
    fi
fi

VERSION_NUEVA=$(version_del_codigo)
[ -n "$VERSION_NUEVA" ] || VERSION_NUEVA="desconocida"

if [ "$VERSION_NUEVA" = "$VERSION_ANTERIOR" ]; then
    aviso "Ya estabas en la $VERSION_NUEVA. Se reconstruye igualmente."
else
    echo "Actualizando: $VERSION_ANTERIOR → $VERSION_NUEVA"
    if [ -f CHANGELOG.md ]; then
        paso "Novedades de la $VERSION_NUEVA"
        awk '/^## \[/{n++} n==1{print} n==2{exit}' CHANGELOG.md
    fi
fi

# ── 3. Puerto ─────────────────────────────────────────────────────────────────
# Igual que en docker-up.sh y con la misma capa de configuracion que la app,
# para que el mapeo de Docker y el puerto real no puedan desincronizarse.
PORT=$(run_py "import configparser;c=configparser.ConfigParser();c.read('config.ini');print(c.getint('server','port',fallback=8500))") || PORT=""
[ -n "$PORT" ] || PORT=8500
export PORT
export WEBSTOOLS_VERSION="$VERSION_NUEVA"

# ── 4. Construir y levantar ───────────────────────────────────────────────────
paso "Construyendo la imagen $IMAGEN:$VERSION_NUEVA"
docker compose build

paso "Levantando"
docker compose up -d

# ── 5. Comprobar que arranca de verdad ────────────────────────────────────────
# /healthz no dice solo que el proceso este vivo: cuenta las herramientas del
# catalogo y responde 503 si no se ha cargado ninguna, que es exactamente lo que
# rompe una actualizacion con un modulo de categoria a medio migrar.
paso "Esperando a que responda (hasta ${ESPERA_SALUD}s)"

sano=0
i=0
while [ "$i" -lt "$ESPERA_SALUD" ]; do
    if comprobar_salud >/dev/null 2>&1; then
        sano=1
        break
    fi
    i=$((i + 1))
    printf '.'
    sleep 1
done
printf '\n'

if [ "$sano" -eq 1 ]; then
    paso "Actualizacion correcta"
    comprobar_salud || true
    printf '\n\nVersion %s en marcha en el puerto %s.\n' "$VERSION_NUEVA" "$PORT"
    exit 0
fi

# ── 6. Vuelta atras ───────────────────────────────────────────────────────────
error "La version $VERSION_NUEVA no responde tras ${ESPERA_SALUD}s. Volviendo atras."

echo
echo "Ultimas lineas del log:"
docker compose logs --tail 40 "$SERVICIO" 2>&1 || true

if [ "$VERSION_ANTERIOR" != "desconocida" ] \
   && docker image inspect "${IMAGEN}:${VERSION_ANTERIOR}" >/dev/null 2>&1; then
    paso "Levantando de nuevo la $VERSION_ANTERIOR"
    WEBSTOOLS_VERSION="$VERSION_ANTERIOR" docker compose up -d --no-build
    aviso "Se ha vuelto a la $VERSION_ANTERIOR. El codigo del repositorio SI esta actualizado:
para dejarlo tambien como estaba, ejecuta  git checkout v${VERSION_ANTERIOR}"
else
    error "No hay imagen etiquetada de la $VERSION_ANTERIOR; no se puede volver sola."
    echo "       Vuelve al codigo anterior y reconstruye:" >&2
    echo "           git checkout v${VERSION_ANTERIOR} && ./docker-up.sh" >&2
fi

cat <<'FIN'

  WebsTools no guarda datos propios: la vuelta atras deja la aplicacion como
  estaba. Lo unico que el rollback no toca es el codigo del clon, que se queda
  en la version nueva hasta que hagas el git checkout de arriba.

FIN
exit 1
