# WebsTools

## Despliegue en la LAN (servidor Linux + Docker)

```
git clone <repo> && cd WebsTools
chmod +x docker-up.sh    # solo la primera vez, si el bit de ejecucion se perdio
./docker-up.sh
```

`docker-up.sh` es el unico punto de entrada: crea el `.env` con una `SECRET_KEY`
aleatoria, lee el puerto de `config.ini` y levanta el contenedor. Al terminar
imprime la URL con la IP LAN del servidor.

Desde cualquier otro dispositivo de la red: `http://<ip-del-servidor>:<puerto>`
(por defecto el `8500`).

**Cambiar el puerto:** edita solo `port` en la seccion `[server]` de `config.ini`
y vuelve a ejecutar `./docker-up.sh`. Es la unica fuente del puerto — no lo pongas
a mano en `.env` ni en `docker-compose.yml`. No ejecutes `docker compose up`
directamente: sin las variables que exporta el script el arranque falla.

Si el puerto no responde desde otro equipo, abrelo en el firewall:
`sudo ufw allow 8500/tcp`.

Otros comandos: `docker compose logs -f webtools` (logs), `docker compose down` (parar).

## Dependencias nativas

Pensado para ejecutarse en Linux (nativo o via Docker). Al arrancar en Windows se muestra una
advertencia porque varias herramientas dependen de binerias/librerias nativas que no vienen
instaladas por defecto en ese sistema:

- **libmagic** (deteccion de tipo real de archivo)
- **libzbar** (lectura de codigos QR)
- **exiftool** (ver/editar/eliminar metadatos de imagenes)
- **ffmpeg** (conversion de video/audio del descargador multimedia)

En Linux (Debian/Ubuntu) instalalas con:

```
sudo apt-get install libmagic1 libzbar0 libimage-exiftool-perl ffmpeg
```

La imagen Docker (`Dockerfile`) ya incluye estas dependencias.