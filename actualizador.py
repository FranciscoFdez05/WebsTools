"""Comprobacion y aplicacion de actualizaciones de WebsTools desde GitHub.

La comprobacion pregunta a la API de GitHub por la ultima release publicada del repositorio
y la compara con la version local de version.py. Aplicarla es un "git pull --ff-only" sobre
el propio arbol de trabajo desde el que corre la app: por eso solo funciona si el despliegue
es un clon de git (en Docker, con el repo montado en /app, ver docker-compose.yml) y nunca
acepta remoto ni rama de la peticion, siempre los suyos.
"""

import json
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from catalogo import recargarHerramientas
from config import Config
from version import VERSION

# raiz del proyecto: es tambien el clon de git sobre el que se actualiza
RAIZ = Path(__file__).resolve().parent

# git pull sale a la red: mas lento que un comando local, pero no debe colgar la peticion
TIMEOUT_GIT_SEGUNDOS = 120
TIMEOUT_GIT_LOCAL_SEGUNDOS = 15

# las notas de una release pueden ser larguisimas; en ajustes solo cabe un resumen
MAX_CARACTERES_NOTAS = 1200

# "v1.2.3", "1.2.3-beta": se compara solo la parte numerica
_NUMERO_VERSION = re.compile(r"(\d+(?:\.\d+)*)")


def _versionComoTupla(version):
    """Version como tupla de enteros para poder ordenarlas ("1.10.0" > "1.9.0")."""
    coincidencia = _NUMERO_VERSION.search(version or "")
    if not coincidencia:
        return ()
    return tuple(int(parte) for parte in coincidencia.group(1).split("."))


def esMasNueva(remota, instalada):
    """True si la version remota es posterior a la instalada.

    Si alguna no tiene numero reconocible se cae a comparar el texto: sin numeros no hay
    forma de ordenarlas, pero un nombre distinto sigue indicando que hay algo nuevo.
    """
    remotaTupla, instaladaTupla = _versionComoTupla(remota), _versionComoTupla(instalada)
    if not remotaTupla or not instaladaTupla:
        return bool(remota) and remota != instalada
    return remotaTupla > instaladaTupla


def _git(*argumentos, timeout=TIMEOUT_GIT_LOCAL_SEGUNDOS):
    """Ejecuta git en la raiz del proyecto. Devuelve (ok, salida)."""
    proceso = subprocess.run(
        ["git", *argumentos],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    salida = (proceso.stdout + proceso.stderr).strip()
    return proceso.returncode == 0, salida


def estadoRepositorio():
    """Si se puede aplicar la actualizacion aqui y, si no, por que no.

    Aplicarla necesita git instalado y que el codigo que ejecuta la app sea un clon con
    remoto; ademas se niega a pisar cambios locales sin confirmar, que un pull perderia o
    dejaria a medias en un conflicto.
    """
    if not shutil.which("git"):
        return {"puedeAplicar": False, "motivo": "git no esta instalado en el servidor.", "rama": None}

    if not (RAIZ / ".git").exists():
        return {
            "puedeAplicar": False,
            "motivo": "La aplicacion no se ejecuta desde un clon de git, asi que no hay de donde traer los cambios.",
            "rama": None,
        }

    okRama, rama = _git("rev-parse", "--abbrev-ref", "HEAD")
    if not okRama:
        return {"puedeAplicar": False, "motivo": f"No se pudo leer la rama actual: {rama}", "rama": None}

    okRemoto, _ = _git("remote", "get-url", "origin")
    if not okRemoto:
        return {"puedeAplicar": False, "motivo": "El clon no tiene configurado el remoto origin.", "rama": rama}

    okEstado, salida = _git("status", "--porcelain")
    if okEstado and salida:
        return {
            "puedeAplicar": False,
            "motivo": "Hay cambios locales sin confirmar: confirmalos o descartalos antes de actualizar.",
            "rama": rama,
        }

    return {"puedeAplicar": True, "motivo": "", "rama": rama}


def _pedirUltimaRelease():
    url = f"https://api.github.com/repos/{Config.repoGithub}/releases/latest"
    peticion = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"WebsTools/{VERSION}",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(peticion, timeout=Config.actualizacionesTimeoutSegundos) as respuesta:
        return json.load(respuesta)


def comprobarActualizacion():
    """Compara la version instalada con la ultima release publicada en GitHub."""
    estado = estadoRepositorio()
    resultado = {
        "versionInstalada": VERSION,
        "versionDisponible": None,
        "hayActualizacion": False,
        "url": f"https://github.com/{Config.repoGithub}/releases",
        "publicada": None,
        "notas": "",
        "puedeAplicar": estado["puedeAplicar"] and Config.permitirAplicarActualizacion,
        "motivoNoAplicar": estado["motivo"],
        "rama": estado["rama"],
        "error": None,
    }

    if estado["puedeAplicar"] and not Config.permitirAplicarActualizacion:
        resultado["motivoNoAplicar"] = (
            "Aplicar actualizaciones esta desactivado en config.ini ([actualizaciones] permitirAplicar)."
        )

    try:
        release = _pedirUltimaRelease()
    except urllib.error.HTTPError as error:
        # 404 es el caso normal de un repo sin releases todavia, no un fallo del que alarmar
        resultado["error"] = (
            "El repositorio todavia no tiene ninguna release publicada."
            if error.code == 404
            else f"GitHub respondio {error.code} al consultar la ultima release."
        )
        return resultado
    except Exception as error:
        resultado["error"] = f"No se pudo consultar GitHub: {type(error).__name__}: {error}"
        return resultado

    etiqueta = release.get("tag_name") or release.get("name") or ""
    resultado["versionDisponible"] = etiqueta.lstrip("vV") or None
    resultado["hayActualizacion"] = esMasNueva(resultado["versionDisponible"], VERSION)
    resultado["url"] = release.get("html_url") or resultado["url"]
    resultado["publicada"] = (release.get("published_at") or "")[:10] or None
    resultado["notas"] = (release.get("body") or "").strip()[:MAX_CARACTERES_NOTAS]
    return resultado


def aplicarActualizacion():
    """Trae los cambios del remoto con un fast-forward y recarga el catalogo.

    Solo fast-forward: si la rama local ha divergido del remoto, el pull se niega en vez de
    fusionar o dejar conflictos en un servidor donde nadie los va a resolver a mano. El
    proceso de Python sigue con el codigo viejo en memoria, asi que se recarga el catalogo
    para que los cambios en herramientas se vean al momento y se avisa de que las rutas
    nuevas, las dependencias y la propia version solo entran al reiniciar.
    """
    if not Config.permitirAplicarActualizacion:
        raise ValueError("Aplicar actualizaciones esta desactivado en config.ini ([actualizaciones] permitirAplicar).")

    estado = estadoRepositorio()
    if not estado["puedeAplicar"]:
        raise ValueError(estado["motivo"])

    _, commitAnterior = _git("rev-parse", "--short", "HEAD")

    okPull, salidaPull = _git("pull", "--ff-only", timeout=TIMEOUT_GIT_SEGUNDOS)
    if not okPull:
        return {
            "actualizado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "aplicado": False,
            "error": f"git pull fallo: {salidaPull}",
            "salida": salidaPull,
            "commitAnterior": commitAnterior,
            "commitNuevo": commitAnterior,
            "cambios": [],
            "requiereReinicio": False,
            "versionInstalada": VERSION,
            "catalogo": None,
        }

    _, commitNuevo = _git("rev-parse", "--short", "HEAD")
    huboCambios = commitNuevo != commitAnterior

    cambios = []
    if huboCambios:
        okLog, salidaLog = _git("log", "--oneline", "--no-decorate", f"{commitAnterior}..{commitNuevo}")
        if okLog and salidaLog:
            cambios = salidaLog.splitlines()

    return {
        "actualizado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "aplicado": huboCambios,
        "error": None,
        "salida": salidaPull,
        "commitAnterior": commitAnterior,
        "commitNuevo": commitNuevo,
        "cambios": cambios,
        # la version en memoria y las rutas registradas siguen siendo las de antes del pull
        "requiereReinicio": huboCambios,
        "versionInstalada": VERSION,
        "catalogo": recargarHerramientas() if huboCambios else None,
    }
