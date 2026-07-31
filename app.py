import platform
import sys

from flask import Flask, render_template, request
from flask_limiter import Limiter

from config import Config


def _advertirSiWindows():
    # WebsTools esta pensado para correr en Linux (Docker); en Windows faltan por defecto
    # libmagic, libzbar y exiftool, de los que dependen deteccion de tipo, lectura de QR y metadatos de imagenes
    if platform.system() == "Windows":
        print(
            "ADVERTENCIA: WebsTools se esta ejecutando en Windows. Funcionalidad limitada: "
            "deteccion de tipo de archivo (libmagic), lectura de codigos QR (zbar), metadatos "
            "de imagenes (exiftool) y conversion de video/audio (ffmpeg) requieren dependencias "
            "nativas que no vienen instaladas por defecto en Windows. Se recomienda ejecutar en "
            "Linux (o via Docker) para funcionalidad completa.",
            file=sys.stderr,
        )


_advertirSiWindows()
from categories.archivos.routes import archivosBp
from categories.criptografia.routes import criptografiaBp
from categories.osint.routes import osintBp
from categories.texto.routes import textoBp
from categories.redes.routes import redesBp
from categories.utilidades.routes import utilidadesBp
from categories.json_prog.routes import jsonProgBp

# registro central de categorias, usado para la pantalla principal
CATEGORIAS = [
    {"slug": "archivos", "blueprint": "archivos", "nombre": "Analisis Archivos", "descripcion": "Hashes, metadatos, entropia y tipo real de archivo"},
    {"slug": "criptografia", "blueprint": "criptografia", "nombre": "Criptografia", "descripcion": "Claves RSA/AES, cifrado, JWT, certificados"},
    {"slug": "osint", "blueprint": "osint", "nombre": "OSINT", "descripcion": "WHOIS, DNS, geolocalizacion, subdominios"},
    {"slug": "redes", "blueprint": "redes", "nombre": "Redes", "descripcion": "Subredes, CIDR, validacion IP, direcciones MAC"},
    {"slug": "utilidades", "blueprint": "utilidades", "nombre": "Utilidades", "descripcion": "Conversores, generadores y herramientas varias"},
    {"slug": "texto", "blueprint": "texto", "nombre": "Texto", "descripcion": "Codificacion, generadores y comparador de texto"},
    {"slug": "json-prog", "blueprint": "json_prog", "nombre": "JSON y Programacion", "descripcion": "Formateo y validacion de JSON, XML, HTML, CSS, JS"},
]


def _obtenerIpCliente():
    forwardedFor = request.headers.get("X-Forwarded-For", "") if Config.confiarXForwardedFor else ""
    return forwardedFor.split(",")[0].strip() if forwardedFor else request.remote_addr


# limite global por IP para todas las herramientas; OSINT usa un limite mas estricto por ser mas sensible a abuso
limiter = Limiter(key_func=_obtenerIpCliente, default_limits=["20 per minute"])


def createApp():
    app = Flask(__name__)
    app.config.from_object(Config)

    limiter.init_app(app)
    limiter.limit("15 per minute")(osintBp)

    app.register_blueprint(archivosBp)
    app.register_blueprint(criptografiaBp)
    app.register_blueprint(osintBp)
    app.register_blueprint(textoBp)
    app.register_blueprint(redesBp)
    app.register_blueprint(utilidadesBp)
    app.register_blueprint(jsonProgBp)

    # descargas de video/audio son costosas en CPU/red/disco; limite mas estricto que el resto de utilidades
    limiter.limit("6 per minute")(app.view_functions["utilidades.apiDescargadorVideo"])

    @app.context_processor
    def injectClientIp():
        return {"clientIp": _obtenerIpCliente()}

    @app.route("/")
    def index():
        return render_template("index.html", categorias=CATEGORIAS)

    return app


app = createApp()

if __name__ == "__main__":
    app.run(host=Config.host, port=Config.port, debug=Config.debug)
