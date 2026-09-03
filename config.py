import configparser
import os

parser = configparser.ConfigParser()
parser.read(os.path.join(os.path.dirname(__file__), "config.ini"))


def _leerBool(seccion, clave, porDefecto):
    return parser.getboolean(seccion, clave, fallback=porDefecto)


def _leerInt(seccion, clave, porDefecto):
    return parser.getint(seccion, clave, fallback=porDefecto)


def _leerStr(seccion, clave, porDefecto):
    return parser.get(seccion, clave, fallback=porDefecto)


class Config:
    # servidor: variables de entorno tienen prioridad sobre config.ini, util en Docker
    host = os.environ.get("WEBTOOLS_HOST", _leerStr("server", "host", "0.0.0.0"))
    port = int(os.environ.get("WEBTOOLS_PORT", _leerInt("server", "port", 5000)))
    debug = os.environ.get("FLASK_DEBUG", str(_leerBool("server", "debug", False))).lower() in ("1", "true")

    secretKey = os.environ.get("SECRET_KEY", _leerStr("app", "secretKey", "dev-secret-key-change-in-production"))
    maxContentLength = _leerInt("app", "maxUploadMb", 32) * 1024 * 1024

    # donde el limitador guarda las cuentas por IP. "memory://" las tiene en la memoria del
    # proceso, que es correcto porque la app corre en uno solo (ver el CMD del Dockerfile);
    # repartirla en varios workers exige un contador compartido, p. ej. redis://redis:6379
    rateLimitStorageUri = _leerStr("app", "rateLimitStorageUri", "memory://")

    # contrasena de la pantalla de ajustes. Vacia = sin contrasena, como hasta ahora. Puesta,
    # se pide antes de entrar a /ajustes y de recargar herramientas o actualizar la aplicacion
    # "or" y no el valor por defecto de os.environ.get: docker-compose pasa siempre la
    # variable, vacia si nadie la define, y esa cadena vacia pisaba lo puesto en config.ini
    ajustesPassword = os.environ.get("AJUSTES_PASSWORD") or _leerStr("app", "ajustesPassword", "")

    osintTimeoutSegundos = _leerInt("osint", "timeoutSegundos", 5)
    geolocalizacionUrl = _leerStr("osint", "geolocalizacionUrl", "http://ip-api.com/json/")

    # por defecto NO: sin un proxy inverso delante que la reescriba, la cabecera la pone quien
    # hace la peticion, y cualquiera podria cambiarla en cada llamada para saltarse el limite
    confiarXForwardedFor = _leerBool("proxy", "confiarXForwardedFor", False)

    # actualizaciones: repositorio contra el que se compara la version instalada y si la app
    # puede aplicarlas ella misma con git pull (desactivalo si el servidor no debe tocar el codigo)
    repoGithub = _leerStr("actualizaciones", "repoGithub", "FranciscoFdez05/WebsTools")
    actualizacionesTimeoutSegundos = _leerInt("actualizaciones", "timeoutSegundos", 5)
    permitirAplicarActualizacion = _leerBool("actualizaciones", "permitirAplicar", True)


CLAVE_INSEGURA = "dev-secret-key-change-in-production"


def claveEsInsegura():
    """True si la app va a firmar las sesiones con la clave de ejemplo del repositorio."""
    return Config.secretKey == CLAVE_INSEGURA
