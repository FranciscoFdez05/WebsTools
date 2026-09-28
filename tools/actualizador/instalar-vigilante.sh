#!/usr/bin/env sh
# Instala el vigilante de actualizaciones de WebsTools: un temporizador de systemd que cada
# 30s comprueba si el boton "Actualizacion completa" de Ajustes ha dejado una senial y, si la
# hay, ejecuta webtools-actualizador.sh (que a su vez llama a ./docker-update.sh o a
# ./install.sh --actualizar, segun el despliegue).
#
# install.sh ya lo instala solo al final de una instalacion nativa. Este script es para quien
# desplego con Docker (docker-up.sh no toca systemd ni pide sudo a proposito) y quiere que el
# boton de Ajustes complete de verdad la actualizacion en vez de solo el pull rapido.
#
# Se puede volver a ejecutar cuantas veces haga falta: reescribe las unidades y reinicia el
# timer, sin tocar nada mas.
#
# Uso: sudo ./tools/actualizador/instalar-vigilante.sh
set -e

RUTA="$(cd "$(dirname "$0")/../.." && pwd)"
SERVICIO="webstools-actualizador"
UNIDAD_SERVICIO="/etc/systemd/system/${SERVICIO}.service"
UNIDAD_TIMER="/etc/systemd/system/${SERVICIO}.timer"

aviso()  { printf '\n\033[33m%s\033[0m\n' "$*"; }
error()  { printf '\n\033[31m%s\033[0m\n' "$*" >&2; }
paso()   { printf '\n\033[36m── %s\033[0m\n' "$*"; }

if [ "$(id -u)" -ne 0 ]; then
    error "Hace falta sudo: sudo $0"
    exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
    error "No hay systemd (systemctl) en este host: el vigilante no se puede registrar."
    echo "       Sin el, el boton \"Actualizacion completa\" de Ajustes se queda pidiendo para siempre." >&2
    exit 1
fi

if [ ! -f "$RUTA/tools/actualizador/webtools-actualizador.sh" ]; then
    error "No se encuentra $RUTA/tools/actualizador/webtools-actualizador.sh"
    exit 1
fi
chmod +x "$RUTA/tools/actualizador/webtools-actualizador.sh"

# el vigilante tiene que correr como el usuario dueno del clon, nunca como root:
# docker-update.sh e install.sh --actualizar se niegan a ejecutarse como root a proposito
USUARIO="${SUDO_USER:-}"
[ -n "$USUARIO" ] || USUARIO="$(stat -c '%U' "$RUTA" 2>/dev/null || true)"
GRUPO="$(id -gn "$USUARIO" 2>/dev/null || true)"
if [ -z "$USUARIO" ] || [ "$USUARIO" = "root" ]; then
    USUARIO="${USUARIO:-root}"
    GRUPO="${GRUPO:-root}"
    aviso "No se pudo determinar con certeza el usuario dueno del clon: el vigilante correra como root.
docker-update.sh e install.sh --actualizar se niegan a ejecutarse como root, asi que la
actualizacion fallara de forma segura (sin tocar nada) en vez de correr con privilegios de mas.
Para arreglarlo, edita User= y Group= en $UNIDAD_SERVICIO y luego:
    sudo systemctl daemon-reload && sudo systemctl restart ${SERVICIO}.timer"
fi

paso "Registrando $SERVICIO como $USUARIO en $RUTA"

tee "$UNIDAD_SERVICIO" >/dev/null <<FIN
# Generado por tools/actualizador/instalar-vigilante.sh de WebsTools. No se edita a mano:
# se sobreescribe cada vez que se vuelve a ejecutar ese script.
[Unit]
Description=Vigilante de actualizaciones de WebsTools
Documentation=https://github.com/FranciscoFdez05/WebsTools

[Service]
Type=oneshot
User=${USUARIO}
Group=${GRUPO}
WorkingDirectory=${RUTA}
ExecStart=${RUTA}/tools/actualizador/webtools-actualizador.sh
FIN

tee "$UNIDAD_TIMER" >/dev/null <<FIN
# Generado por tools/actualizador/instalar-vigilante.sh de WebsTools.
[Unit]
Description=Comprueba cada 30s si hay una actualizacion de WebsTools pedida desde Ajustes

[Timer]
OnBootSec=30s
OnUnitActiveSec=30s
AccuracySec=5s

[Install]
WantedBy=timers.target
FIN

systemctl daemon-reload
systemctl enable --quiet --now "${SERVICIO}.timer"

cat <<FIN

Vigilante instalado y en marcha: cada 30s comprueba si hay una actualizacion pedida desde
Ajustes -> Actualizacion completa.

Gestion:
  sudo systemctl status ${SERVICIO}.timer      cuando corrio la ultima vez / la proxima
  sudo journalctl -u ${SERVICIO} -f            logs de cada pasada
  sudo systemctl stop ${SERVICIO}.timer        desactivarlo
FIN
