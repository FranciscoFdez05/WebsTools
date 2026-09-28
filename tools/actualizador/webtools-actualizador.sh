#!/usr/bin/env sh
# Vigilante de WebsTools: recoge la senial que deja el boton "Actualizacion completa" de
# Ajustes y ejecuta la actualizacion de verdad (build, comprobacion de salud, vuelta atras si
# hace falta), fuera del contenedor. Lo lanza el temporizador webstools-actualizador.timer
# cada 30s (lo instala install.sh, o tools/actualizador/instalar-vigilante.sh si se desplego
# con Docker). La app nunca hace esto ella misma: no podria reconstruir su propia imagen ni
# reiniciarse sin matarse a mitad de la operacion, asi que solo deja la senial y este script,
# que corre en el host, es quien de verdad actualiza.
#
# Uso: ./webtools-actualizador.sh   (pensado para el timer; tambien se puede lanzar a mano)
set -e
cd "$(dirname "$0")/../.."   # tools/actualizador/ -> raiz del repo

DATOS="data/tmp"
SOLICITADA="$DATOS/actualizacion.solicitada.json"
LATIDO="$DATOS/vigilante.latido"
CERROJO="$DATOS/actualizacion.lock"

mkdir -p "$DATOS"
# se toca en cada pasada, haya o no senial: es como el panel de Ajustes sabe que el vigilante
# esta instalado y vivo, en vez de dejar el boton esperando para siempre a que nadie responda
touch "$LATIDO"

# nada que hacer: la pasada mas barata posible, la de cada 30s sin que nadie haya pulsado nada
[ -f "$SOLICITADA" ] || exit 0

# cerrojo atomico con mkdir: si otra pasada ya esta trabajando (una actualizacion larga
# solapando con el siguiente disparo del timer), esta se retira sin tocar nada
mkdir "$CERROJO" 2>/dev/null || exit 0
trap 'rmdir "$CERROJO" 2>/dev/null' EXIT

if command -v python3 >/dev/null 2>&1; then
    PY_CMD=python3
elif command -v python >/dev/null 2>&1; then
    PY_CMD=python
else
    PY_CMD=""
fi

SOLICITADA_EN=""
if [ -n "$PY_CMD" ]; then
    SOLICITADA_EN=$("$PY_CMD" -c "import json; print(json.load(open('$SOLICITADA')).get('solicitadaEn') or '')" 2>/dev/null) || SOLICITADA_EN=""
fi

# se consume ANTES de empezar a actualizar: si se va la luz a mitad de camino, al volver no
# se relanza sola otra vez
rm -f "$SOLICITADA"

# escribe data/tmp/actualizacion.estado.json de forma atomica (temporal + rename), igual que
# actualizador.py en el lado de la app. Sin python (muy raro: docker-up.sh e install.sh ya lo
# exigen) simplemente no deja estado, y el panel se queda sin saber el resultado.
escribir_estado() {
    [ -n "$PY_CMD" ] || return 0
    "$PY_CMD" - "$1" "$2" "$SOLICITADA_EN" <<'PYEOF'
import json
import sys
import time
from pathlib import Path

estado, salida, solicitadaEn = sys.argv[1], sys.argv[2], (sys.argv[3] or None)
ruta = Path("data/tmp/actualizacion.estado.json")
ruta.parent.mkdir(parents=True, exist_ok=True)
datos = {
    "estado": estado,
    "actualizadoEn": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "solicitadaEn": solicitadaEn,
    "salida": salida,
}
temporal = ruta.with_name(ruta.name + ".tmp")
temporal.write_text(json.dumps(datos), encoding="utf-8")
temporal.replace(ruta)
PYEOF
}

escribir_estado en_marcha ""

# Docker si hay un docker-compose.yml y el contenedor "webtools" esta corriendo; si no,
# systemd si el servicio "webstools" de install.sh esta activo. Ninguno de los dos: no se
# sabe como actualizar y se deja constancia en vez de intentar algo a ciegas.
modo_despliegue() {
    if [ -f docker-compose.yml ] && command -v docker >/dev/null 2>&1 \
       && docker compose ps --status running --format '{{.Name}}' 2>/dev/null | grep -qx webtools; then
        echo docker
    elif command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet webstools 2>/dev/null; then
        echo systemd
    else
        echo desconocido
    fi
}

MODO=$(modo_despliegue)
case "$MODO" in
    docker)
        salida=$(./docker-update.sh 2>&1) && resultado=ok || resultado=fallo
        ;;
    systemd)
        salida=$(./install.sh --actualizar 2>&1) && resultado=ok || resultado=fallo
        ;;
    *)
        salida="No se detecto un despliegue Docker (contenedor webtools) ni un servicio systemd (webstools) activo: no se sabe con que actualizar."
        resultado=fallo
        ;;
esac

# el estado es para el panel de Ajustes, no un log: se recorta a las ultimas lineas
salida=$(printf '%s\n' "$salida" | tail -n 60)
escribir_estado "$resultado" "$salida"
