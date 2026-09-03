#!/usr/bin/env sh
# Lanza el stack leyendo el puerto directamente de config.ini, para que
# el mapeo host:contenedor de docker-compose.yml (${PORT}) coincida
# siempre con el valor real que usa la app. Uso: ./docker-up.sh [args...]
set -e
cd "$(dirname "$0")"

# python3 en la mayoria de distros; algunas instalaciones minimas solo traen "python"
if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "ERROR: hace falta python3 (o python) para leer config.ini y generar la SECRET_KEY." >&2
    exit 1
fi

# Crea .env a partir de .env.example con una SECRET_KEY aleatoria ya generada,
# para no tener que hacerlo a mano. Tambien la regenera si el .env existente
# todavia tiene el valor de ejemplo: es publico en el repo y firmar sesiones
# con el equivale a no tener secreto.
if [ ! -f .env ] || grep -q '^SECRET_KEY=change-me-generate-a-real-one$' .env; then
    BASE=.env.example
    [ -f .env ] && BASE=.env
    SECRET_KEY=$($PY -c "import secrets; print(secrets.token_hex(32))")
    sed "s/^SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" "$BASE" > .env.tmp && mv .env.tmp .env
    echo "Escrito .env con una SECRET_KEY nueva generada automaticamente."
fi

PORT=$($PY -c "import configparser;c=configparser.ConfigParser();c.read('config.ini');print(c.getint('server','port',fallback=8500))")
export PORT

# La imagen se etiqueta con la version del codigo. Sin esto, la primera
# actualizacion no encontraria imagen anterior a la que volver.
WEBSTOOLS_VERSION=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' version.py | head -n 1)
[ -n "$WEBSTOOLS_VERSION" ] || WEBSTOOLS_VERSION=latest
export WEBSTOOLS_VERSION

docker compose up -d --build "$@"

# IP LAN del servidor: es la que tienen que usar los demas dispositivos de la red.
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -n "$IP" ] || IP="<ip-del-servidor>"
echo ""
echo "WebsTools levantado. Accesible desde cualquier dispositivo de la LAN en:"
echo "  http://$IP:$PORT"
echo ""
echo "Si no responde desde otro equipo, abre el puerto en el firewall del servidor:"
echo "  sudo ufw allow $PORT/tcp"
