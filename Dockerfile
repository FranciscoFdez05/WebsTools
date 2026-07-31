FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    libzbar0 \
    libimage-exiftool-perl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8500

# el puerto SIEMPRE viene de WEBTOOLS_PORT (definido en .env y pasado por docker-compose);
# 8500 solo es el valor por defecto si se ejecuta el contenedor sin esa variable
# --timeout 180: el default de gunicorn (30s) es mas corto que la descarga de video/audio
# (hasta 120s) y que subidas de archivos grandes en conexiones lentas; sin esto el worker
# se mata a mitad de peticion (WORKER TIMEOUT) antes de que la operacion pueda terminar
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${WEBTOOLS_PORT:-8500} --workers 2 --timeout 180 app:app"]
