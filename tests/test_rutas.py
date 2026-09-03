import base64
import io

import pytest

from app import app, limiter
from catalogo import obtenerHerramientas
from config import Config


@pytest.fixture
def cliente():
    # el limitador guarda las cuentas en memoria y vive en el modulo app: sin resetear, cada
    # test heredaria el cupo gastado por el anterior
    with app.app_context():
        limiter.reset()
    return app.test_client()


def test_configuracionLlegaAFlask():
    # Config usa camelCase y Flask solo lee atributos en MAYUSCULAS: hay que pasarle las claves
    # a mano o el limite de subida se queda sin aplicar
    assert app.config["MAX_CONTENT_LENGTH"] == Config.maxContentLength
    assert app.config["SECRET_KEY"] == Config.secretKey


def test_paginaPrincipalListaTodasLasHerramientas(cliente):
    respuesta = cliente.get("/")
    html = respuesta.get_data(as_text=True)

    assert respuesta.status_code == 200
    assert html.count("data-buscable") == len(obtenerHerramientas())


@pytest.mark.parametrize("herramienta", obtenerHerramientas(), ids=lambda h: h["categoriaSlug"] + "/" + h["slug"])
def test_cadaHerramientaTieneSuPagina(cliente, herramienta):
    respuesta = cliente.get(f"/{herramienta['categoriaSlug']}/{herramienta['slug']}")

    assert respuesta.status_code == 200
    assert "formHerramienta" in respuesta.get_data(as_text=True)


def test_navegarNoGastaElCupoDePeticiones(cliente):
    # el limite global es de 20/minuto: navegar mas de 20 veces no puede dejar fuera al usuario
    codigos = {cliente.get("/redes/").status_code for _ in range(30)}
    codigos.add(cliente.get("/").status_code)

    assert codigos == {200}


def test_ejecutarUnaHerramientaSiGastaCupo(cliente):
    codigos = [cliente.post("/redes/api/validar-ip", json={"ip": "1.1.1.1"}).status_code for _ in range(25)]

    assert codigos[0] == 200
    assert 429 in codigos


def test_limiteAlcanzadoRespondeJsonConRetryAfter(cliente):
    respuesta = None
    for _ in range(25):
        respuesta = cliente.post("/redes/api/validar-ip", json={"ip": "1.1.1.1"})
        if respuesta.status_code == 429:
            break

    assert respuesta.status_code == 429
    assert respuesta.is_json
    assert "Limite de peticiones" in respuesta.get_json()["error"]
    assert int(respuesta.headers["Retry-After"]) > 0


def test_rutaApiInexistenteRespondeJson(cliente):
    respuesta = cliente.post("/redes/api/no-existe")

    assert respuesta.status_code == 404
    assert respuesta.is_json
    assert respuesta.get_json()["codigo"] == 404


def test_paginaInexistenteSigueRespondiendoHtml(cliente):
    respuesta = cliente.get("/no-existe")

    assert respuesta.status_code == 404
    assert not respuesta.is_json


def test_falloInesperadoDeUnaHerramientaRespondeJson(cliente, monkeypatch):
    from categories.redes import logic

    def reventar(*args, **kwargs):
        raise RuntimeError("fallo inesperado")

    monkeypatch.setattr(logic, "validarIp", reventar)
    respuesta = cliente.post("/redes/api/validar-ip", json={"ip": "1.1.1.1"})

    assert respuesta.status_code == 500
    assert respuesta.is_json
    assert "Error interno" in respuesta.get_json()["error"]


def test_subidaMayorQueElLimiteSeRechaza(cliente):
    exceso = Config.maxContentLength + 1024
    datos = {"archivo": (io.BytesIO(b"A" * exceso), "grande.bin")}

    respuesta = cliente.post("/archivos/api/generar-hashes", data=datos, content_type="multipart/form-data")

    assert respuesta.status_code == 413
    assert respuesta.is_json
    assert "tamano maximo" in respuesta.get_json()["error"]


def test_healthzRespondeSinGastarCupo(cliente):
    # lo llama el healthcheck de docker cada 30 s: no puede consumir el limite del usuario
    codigos = {cliente.get("/healthz").status_code for _ in range(30)}

    assert codigos == {200}
    assert cliente.get("/healthz").get_json()["estado"] == "ok"


def test_ajustesSinPasswordSigueAbierto(cliente):
    assert Config.ajustesPassword == ""
    assert cliente.get("/ajustes").status_code == 200


def test_ajustesConPasswordPideAutenticacion(cliente, monkeypatch):
    monkeypatch.setattr(Config, "ajustesPassword", "secreta")

    respuesta = cliente.get("/ajustes")

    assert respuesta.status_code == 401
    assert "Basic" in respuesta.headers["WWW-Authenticate"]


def test_ajustesConPasswordCorrectaEntra(cliente, monkeypatch):
    monkeypatch.setattr(Config, "ajustesPassword", "secreta")
    credenciales = base64.b64encode(b"webstools:secreta").decode()

    respuesta = cliente.get("/ajustes", headers={"Authorization": f"Basic {credenciales}"})

    assert respuesta.status_code == 200


def test_accionesDeAjustesTambienPidenPassword(cliente, monkeypatch):
    monkeypatch.setattr(Config, "ajustesPassword", "secreta")

    for ruta in ("/api/ajustes/actualizar-herramientas", "/api/ajustes/actualizar-app"):
        respuesta = cliente.post(ruta)
        assert respuesta.status_code == 401, ruta
        # las rutas de api responden json, que es lo que espera el fetch de la pantalla
        assert respuesta.is_json, ruta


def test_consultarLaVersionNoPidePassword(cliente, monkeypatch):
    # la usa el aviso de la cabecera en todas las paginas y solo devuelve un numero
    import app as modulo

    monkeypatch.setattr(Config, "ajustesPassword", "secreta")
    monkeypatch.setattr(modulo, "comprobarActualizacion", lambda: {"versionInstalada": "1.0.0"})

    assert cliente.get("/api/ajustes/version").status_code == 200


def test_paginaDeHerramientaLlevaLosDatosDeRecientes(cliente):
    html = cliente.get("/redes/validar-ip").get_data(as_text=True)

    assert 'id="datosHerramienta"' in html
    assert 'data-categoria="Redes"' in html
