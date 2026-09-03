import json
import urllib.error

import pytest

import actualizador
from version import VERSION


class RespuestaFalsa:
    """Sustituto de lo que devuelve urlopen: solo hace falta que json.load lo pueda leer."""

    def __init__(self, contenido):
        self._contenido = json.dumps(contenido)

    def read(self):
        return self._contenido.encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def repoActualizable(monkeypatch):
    monkeypatch.setattr(actualizador, "estadoRepositorio", lambda: {"puedeAplicar": True, "motivo": "", "rama": "main"})
    monkeypatch.setattr(actualizador.Config, "permitirAplicarActualizacion", True)


def simularRelease(monkeypatch, **campos):
    monkeypatch.setattr(actualizador.urllib.request, "urlopen", lambda *a, **k: RespuestaFalsa(campos))


@pytest.mark.parametrize(
    "remota,instalada,esperado",
    [
        ("1.0.1", "1.0.0", True),
        ("1.1.0", "1.0.9", True),
        ("1.10.0", "1.9.0", True),  # comparacion numerica, no alfabetica
        ("1.0.0", "1.0.0", False),
        ("0.9.0", "1.0.0", False),
        ("2.0", "1.9.9", True),
        ("", "1.0.0", False),
    ],
)
def test_esMasNueva(remota, instalada, esperado):
    assert actualizador.esMasNueva(remota, instalada) is esperado


def test_comprobarActualizacion_detectaVersionNueva(monkeypatch, repoActualizable):
    simularRelease(
        monkeypatch,
        tag_name="v99.0.0",
        html_url="https://github.com/ejemplo/repo/releases/tag/v99.0.0",
        published_at="2026-01-15T10:00:00Z",
        body="  Novedades  ",
    )

    info = actualizador.comprobarActualizacion()

    assert info["versionInstalada"] == VERSION
    assert info["versionDisponible"] == "99.0.0"
    assert info["hayActualizacion"] is True
    assert info["publicada"] == "2026-01-15"
    assert info["notas"] == "Novedades"
    assert info["puedeAplicar"] is True
    assert info["error"] is None


def test_comprobarActualizacion_versionAlDia(monkeypatch, repoActualizable):
    simularRelease(monkeypatch, tag_name=f"v{VERSION}")

    info = actualizador.comprobarActualizacion()

    assert info["hayActualizacion"] is False
    assert info["versionDisponible"] == VERSION


def test_comprobarActualizacion_repoSinReleases(monkeypatch, repoActualizable):
    def sin404(*args, **kwargs):
        raise urllib.error.HTTPError("url", 404, "Not Found", {}, None)

    monkeypatch.setattr(actualizador.urllib.request, "urlopen", sin404)
    info = actualizador.comprobarActualizacion()

    # un repo sin releases no es un fallo del que alarmar, pero tampoco hay actualizacion
    assert info["hayActualizacion"] is False
    assert "no tiene ninguna release" in info["error"]


def test_comprobarActualizacion_githubCaido(monkeypatch, repoActualizable):
    def reventar(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(actualizador.urllib.request, "urlopen", reventar)
    info = actualizador.comprobarActualizacion()

    assert info["error"].startswith("No se pudo consultar GitHub")
    assert info["versionInstalada"] == VERSION


def test_comprobarActualizacion_aplicarDesactivadoEnConfig(monkeypatch):
    monkeypatch.setattr(actualizador, "estadoRepositorio", lambda: {"puedeAplicar": True, "motivo": "", "rama": "main"})
    monkeypatch.setattr(actualizador.Config, "permitirAplicarActualizacion", False)
    simularRelease(monkeypatch, tag_name="v99.0.0")

    info = actualizador.comprobarActualizacion()

    assert info["hayActualizacion"] is True
    assert info["puedeAplicar"] is False
    assert "permitirAplicar" in info["motivoNoAplicar"]


def test_estadoRepositorio_rechazaCambiosSinConfirmar(monkeypatch):
    monkeypatch.setattr(actualizador.shutil, "which", lambda nombre: "/usr/bin/git")
    monkeypatch.setattr(actualizador.Path, "exists", lambda self: True)
    monkeypatch.setattr(actualizador, "_git", lambda *args, **kwargs: (True, "M app.py" if args[0] == "status" else "main"))

    estado = actualizador.estadoRepositorio()

    assert estado["puedeAplicar"] is False
    assert "cambios locales" in estado["motivo"]


def test_estadoRepositorio_sinGitInstalado(monkeypatch):
    monkeypatch.setattr(actualizador.shutil, "which", lambda nombre: None)

    estado = actualizador.estadoRepositorio()

    assert estado["puedeAplicar"] is False
    assert "git no esta instalado" in estado["motivo"]


def test_aplicarActualizacion_traeLosCambiosYPideReinicio(monkeypatch, repoActualizable):
    comandos = []

    def gitFalso(*args, **kwargs):
        comandos.append(args)
        if args[0] == "rev-parse":
            return True, "bbbbbbb" if comandos.count(args) > 1 else "aaaaaaa"
        if args[0] == "pull":
            return True, "Updating aaaaaaa..bbbbbbb"
        if args[0] == "log":
            return True, "bbbbbbb un cambio\nccccccc otro cambio"
        return True, ""

    monkeypatch.setattr(actualizador, "_git", gitFalso)
    monkeypatch.setattr(actualizador, "recargarHerramientas", lambda: {"totalHerramientas": 65})

    resultado = actualizador.aplicarActualizacion()

    assert ("pull", "--ff-only") in comandos
    assert resultado["aplicado"] is True
    assert resultado["error"] is None
    assert resultado["commitAnterior"] == "aaaaaaa"
    assert resultado["commitNuevo"] == "bbbbbbb"
    assert len(resultado["cambios"]) == 2
    # el proceso sigue con el codigo viejo cargado: la version nueva solo entra al reiniciar
    assert resultado["requiereReinicio"] is True
    assert resultado["catalogo"]["totalHerramientas"] == 65


def test_aplicarActualizacion_sinNadaQueTraer(monkeypatch, repoActualizable):
    monkeypatch.setattr(actualizador, "_git", lambda *args, **kwargs: (True, "aaaaaaa" if args[0] == "rev-parse" else "Already up to date."))

    resultado = actualizador.aplicarActualizacion()

    assert resultado["aplicado"] is False
    assert resultado["error"] is None
    assert resultado["requiereReinicio"] is False
    assert resultado["catalogo"] is None


def test_aplicarActualizacion_pullQueFalla(monkeypatch, repoActualizable):
    def gitFalso(*args, **kwargs):
        if args[0] == "pull":
            return False, "fatal: Not possible to fast-forward, aborting."
        return True, "aaaaaaa"

    monkeypatch.setattr(actualizador, "_git", gitFalso)
    resultado = actualizador.aplicarActualizacion()

    assert resultado["aplicado"] is False
    assert "fast-forward" in resultado["error"]
    assert resultado["commitNuevo"] == resultado["commitAnterior"]


def test_aplicarActualizacion_seNiegaSiNoSePuede(monkeypatch):
    monkeypatch.setattr(actualizador.Config, "permitirAplicarActualizacion", True)
    monkeypatch.setattr(
        actualizador,
        "estadoRepositorio",
        lambda: {"puedeAplicar": False, "motivo": "git no esta instalado en el servidor.", "rama": None},
    )

    # ValueError: las rutas lo traducen a un 400 con el motivo, no a un 500
    with pytest.raises(ValueError, match="git no esta instalado"):
        actualizador.aplicarActualizacion()


def test_aplicarActualizacion_desactivadaEnConfig(monkeypatch):
    monkeypatch.setattr(actualizador.Config, "permitirAplicarActualizacion", False)

    with pytest.raises(ValueError, match="permitirAplicar"):
        actualizador.aplicarActualizacion()
