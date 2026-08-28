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
