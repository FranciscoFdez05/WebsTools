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

    osintTimeoutSegundos = _leerInt("osint", "timeoutSegundos", 5)
    geolocalizacionUrl = _leerStr("osint", "geolocalizacionUrl", "http://ip-api.com/json/")

    confiarXForwardedFor = _leerBool("proxy", "confiarXForwardedFor", True)

    # actualizaciones: repositorio contra el que se compara la version instalada y si la app
    # puede aplicarlas ella misma con git pull (desactivalo si el servidor no debe tocar el codigo)
    repoGithub = _leerStr("actualizaciones", "repoGithub", "FranciscoFdez05/WebsTools")
    actualizacionesTimeoutSegundos = _leerInt("actualizaciones", "timeoutSegundos", 5)
    permitirAplicarActualizacion = _leerBool("actualizaciones", "permitirAplicar", True)
