import pytest

from categories.criptografia import logic


def test_generarClaveRsa():
    resultado = logic.generarClaveRsa(2048)
    assert "BEGIN PRIVATE KEY" in resultado["clavePrivada"]
    assert "BEGIN PUBLIC KEY" in resultado["clavePublica"]


def test_generarClaveRsa_tamano_invalido():
    with pytest.raises(ValueError):
        logic.generarClaveRsa(1024)


def test_generarClaveAes():
    resultado = logic.generarClaveAes(256)
    assert resultado["tamano"] == 256
    assert len(resultado["claveHex"]) == 64


def test_generarClaveAes_tamano_invalido():
    with pytest.raises(ValueError):
        logic.generarClaveAes(100)


def test_cifrarAes_descifrarAes_roundtrip():
    clave = logic.generarClaveAes(256)["claveBase64"]
    cifrado = logic.cifrarAes("mensaje secreto", clave)
    resultado = logic.descifrarAes(clave, cifrado["nonceBase64"], cifrado["textoCifradoBase64"])
    assert resultado["textoPlano"] == "mensaje secreto"


def test_descifrarAes_clave_incorrecta():
    clave = logic.generarClaveAes(256)["claveBase64"]
    otraClave = logic.generarClaveAes(256)["claveBase64"]
    cifrado = logic.cifrarAes("mensaje secreto", clave)
    with pytest.raises(ValueError):
        logic.descifrarAes(otraClave, cifrado["nonceBase64"], cifrado["textoCifradoBase64"])


def test_cifrarAes_clave_invalida():
    with pytest.raises(ValueError):
        logic.cifrarAes("texto", "no-es-base64-valido!!")


def test_cifrarRsa_descifrarRsa_roundtrip():
    claves = logic.generarClaveRsa(2048)
    cifrado = logic.cifrarRsa("hola mundo", claves["clavePublica"])
    resultado = logic.descifrarRsa(cifrado["textoCifradoBase64"], claves["clavePrivada"])
    assert resultado["textoPlano"] == "hola mundo"


def test_cifrarRsa_clave_invalida():
    with pytest.raises(ValueError):
        logic.cifrarRsa("texto", "no es una clave PEM")


def test_generarHmac():
    resultado = logic.generarHmac("texto", "clave", "sha256")
    assert resultado["algoritmo"] == "sha256"
    assert len(resultado["hmac"]) == 64


def test_generarHmac_algoritmo_invalido():
    with pytest.raises(ValueError):
        logic.generarHmac("texto", "clave", "md5")


def test_generarHmac_sin_clave():
    with pytest.raises(ValueError):
        logic.generarHmac("texto", "", "sha256")


def test_inspeccionarJwt_sin_secreto():
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dummy"
    resultado = logic.inspeccionarJwt(token, "")
    assert resultado["cabecera"]["alg"] == "HS256"
    assert resultado["firmaValida"] is None


def test_inspeccionarJwt_formato_invalido():
    with pytest.raises(ValueError):
        logic.inspeccionarJwt("no.es.un.jwt.valido", "")


def test_inspeccionarJwt_hmac_firma_valida():
    import base64
    import hashlib
    import hmac
    import json

    cabecera = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    cuerpo = base64.urlsafe_b64encode(json.dumps({"sub": "123"}).encode()).decode().rstrip("=")
    mensaje = f"{cabecera}.{cuerpo}".encode()
    firma = hmac.new(b"secreto", mensaje, hashlib.sha256).digest()
    firmaB64 = base64.urlsafe_b64encode(firma).decode().rstrip("=")
    token = f"{cabecera}.{cuerpo}.{firmaB64}"

    resultado = logic.inspeccionarJwt(token, "secreto")
    assert resultado["firmaValida"] is True


def test_generarCertificadoAutofirmado():
    resultado = logic.generarCertificadoAutofirmado("example.com", 30, 2048)
    assert "BEGIN CERTIFICATE" in resultado["certificadoPem"]
    assert "BEGIN PRIVATE KEY" in resultado["clavePrivadaPem"]
    assert resultado["nombreComun"] == "example.com"


def test_generarCertificadoAutofirmado_sin_cn():
    with pytest.raises(ValueError):
        logic.generarCertificadoAutofirmado("", 30, 2048)


def test_generarCertificadoAutofirmado_dias_invalidos():
    with pytest.raises(ValueError):
        logic.generarCertificadoAutofirmado("example.com", 0, 2048)
