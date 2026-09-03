FROM python:3.11-slim

WORKDIR /app

# git: lo usa el boton "Actualizar ahora" de Ajustes para traer la version nueva del repo
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    libzbar0 \
    libimage-exiftool-perl \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# el repo montado en /app pertenece al usuario del host y el contenedor corre como root:
# sin esto git se niega a trabajar sobre el ("detected dubious ownership")
RUN git config --global --add safe.directory /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8500

# el puerto SIEMPRE viene de WEBTOOLS_PORT (definido en .env y pasado por docker-compose);
# 8500 solo es el valor por defecto si se ejecuta el contenedor sin esa variable
#
# --timeout 180: el default de gunicorn (30s) es mas corto que la descarga de video/audio
# (hasta 120s) y que subidas de archivos grandes en conexiones lentas; sin esto el worker
# se mata a mitad de peticion (WORKER TIMEOUT) antes de que la operacion pueda terminar
#
# --workers 1 --threads 8 en vez de --workers 2: el limitador de peticiones guarda las
# cuentas por IP en la memoria del proceso, asi que con dos workers cada uno llevaba su
# propio contador y el limite real era el doble del configurado. Un solo proceso con
# hilos comparte esos contadores -- el limite vuelve a ser el que dice config.ini -- y
# ademas atiende 8 peticiones a la vez en lugar de 2, que es lo que importa aqui: casi
# todo lo que hacen las herramientas es esperar a la red, a exiftool o a ffmpeg.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${WEBTOOLS_PORT:-8500} --workers 1 --threads ${WEBTOOLS_THREADS:-8} --timeout 180 app:app"]
