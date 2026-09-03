import platform
import sys
import time

from flask import Flask, jsonify, render_template, request
from flask_limiter import Limiter
from werkzeug.exceptions import HTTPException, InternalServerError

from catalogo import (
    CATEGORIAS,
    nombreCategoria,
    normalizarCampos,
    obtenerCatalogo,
    obtenerHerramientas,
    recargarHerramientas,
)
from config import Config
from version import VERSION


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
from actualizador import aplicarActualizacion, comprobarActualizacion
from categories.archivos.routes import archivosBp
from categories.criptografia.routes import criptografiaBp
from categories.osint.routes import osintBp
from categories.texto.routes import textoBp
from categories.redes.routes import redesBp
from categories.utilidades.routes import utilidadesBp
from categories.json_prog.routes import jsonProgBp

# mensajes propios para lo que mas se ve desde el navegador: los de Werkzeug son genericos y en ingles
MENSAJES_ERROR = {
    400: "La peticion no es valida: revisa los datos introducidos.",
    404: "La ruta de esta herramienta no existe. Si acabas de anadirla, reinicia la aplicacion.",
    405: "Metodo no permitido en esta ruta.",
    413: (
        f"El archivo supera el tamano maximo permitido "
        f"({Config.maxContentLength // (1024 * 1024)} MB, ajustable en config.ini con [app] maxUploadMb)."
    ),
    500: "Error interno de la herramienta. Revisa los logs del servidor.",
}


def _obtenerIpCliente():
    forwardedFor = request.headers.get("X-Forwarded-For", "") if Config.confiarXForwardedFor else ""
    return forwardedFor.split(",")[0].strip() if forwardedFor else request.remote_addr


def _esRutaApi():
    # convencion del proyecto: todo lo que ejecuta una herramienta cuelga de /api/
    return "/api/" in request.path


# limite global por IP para todas las herramientas; OSINT usa un limite mas estricto por ser mas sensible a abuso
limiter = Limiter(key_func=_obtenerIpCliente, default_limits=["20 per minute"])


@limiter.request_filter
def _navegarNoGastaCupo():
    """Deja fuera del limitador todo lo que no ejecuta una herramienta.

    Los limites cuentan peticiones por IP, asi que aplicarlos tambien a las paginas hacia que
    veinte clics por el catalogo dejasen al usuario fuera de la app con un 429; y detras de un
    proxy inverso o de un NAT ese cupo lo comparten todos los equipos de la red.
    """
    return not _esRutaApi()


def _segundosHastaElReintento():
    """Cuanto falta para que se libere el limite que se acaba de agotar."""
    limiteActual = getattr(limiter, "current_limit", None)
    if limiteActual is None:
        return 60
    return max(int(limiteActual.reset_at - time.time()), 1)


def createApp():
    app = Flask(__name__)
    # Flask solo lee de un objeto los atributos en MAYUSCULAS y los de Config son camelCase:
    # hay que pasarle sus claves a mano o el limite de subida y la clave secreta no se aplican
    app.config["SECRET_KEY"] = Config.secretKey
    app.config["MAX_CONTENT_LENGTH"] = Config.maxContentLength
    # cabeceras X-RateLimit-* y Retry-After en las respuestas de las herramientas
    app.config["RATELIMIT_HEADERS_ENABLED"] = True

    # ayudantes del catalogo que usan las plantillas: campos normalizados del formulario de
    # herramienta y nombre legible de la categoria a la que pertenece
    app.jinja_env.filters["normalizarCampos"] = normalizarCampos
    app.jinja_env.globals["nombreCategoria"] = nombreCategoria

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

    # Las herramientas se consumen por fetch desde el navegador y esperan JSON. Sin esto, un
    # 429 del limitador, una subida demasiado grande o un fallo inesperado llegaban como la
    # pagina HTML de error de Flask y el front solo podia dar un mensaje generico.
    @app.errorhandler(HTTPException)
    def manejarErrorHttp(error):
        if not _esRutaApi():
            return error

        if error.code == 429:
            segundos = _segundosHastaElReintento()
            mensaje = f"Limite de peticiones alcanzado ({error.description}). Reintenta en {segundos} s."
        else:
            mensaje = MENSAJES_ERROR.get(error.code, error.description)

        respuesta = jsonify({"error": mensaje, "codigo": error.code})
        respuesta.status_code = error.code
        if error.code == 429:
            respuesta.headers["Retry-After"] = str(segundos)
        return respuesta

    @app.errorhandler(Exception)
    def manejarErrorInesperado(error):
        # las rutas convierten en 400 lo que el usuario puede corregir (ValueError); lo que
        # llega aqui es un fallo de la herramienta y merece quedar en el log del servidor
        app.logger.exception("Fallo no controlado en %s", request.path)
        if not _esRutaApi():
            return InternalServerError()
        return jsonify({"error": MENSAJES_ERROR[500], "codigo": 500}), 500

    @app.context_processor
    def injectClientIp():
        return {"clientIp": _obtenerIpCliente(), "version": VERSION}

    @app.route("/")
    def index():
        return render_template("index.html", categorias=CATEGORIAS, herramientas=obtenerHerramientas())

    @app.route("/ajustes")
    def ajustes():
        return render_template("ajustes.html", catalogo=obtenerCatalogo(), repoGithub=Config.repoGithub)

    # recargar el catalogo relee y reejecuta los modulos de cada categoria: mas caro que
    # una herramienta normal, asi que lleva un limite mas estricto
    @app.route("/api/ajustes/actualizar-herramientas", methods=["POST"])
    @limiter.limit("6 per minute")
    def apiActualizarHerramientas():
        resultado = recargarHerramientas()
        return jsonify(resultado), 500 if resultado["errores"] else 200

    # consultar GitHub cuesta una peticion de red por llamada: limite propio para que refrescar
    # la pagina de ajustes no gaste el cupo de las herramientas ni castigue a la API de GitHub
    @app.route("/api/ajustes/version")
    @limiter.limit("10 per minute")
    def apiVersion():
        return jsonify(comprobarActualizacion())

    # traer y ejecutar codigo nuevo es lo mas sensible que hace la app: limite muy estricto
    @app.route("/api/ajustes/actualizar-app", methods=["POST"])
    @limiter.limit("2 per minute")
    def apiActualizarApp():
        try:
            resultado = aplicarActualizacion()
        except ValueError as error:
            # aqui no se puede actualizar (sin git, con cambios locales, desactivado en config)
            return jsonify({"error": str(error), "codigo": 400}), 400
        return jsonify(resultado), 500 if resultado["error"] else 200

    return app


app = createApp()

if __name__ == "__main__":
    app.run(host=Config.host, port=Config.port, debug=Config.debug)
