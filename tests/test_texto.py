import pytest

from categories.texto import logic


@pytest.mark.parametrize("formato", logic.FORMATOS_SOPORTADOS)
def test_codificar_decodificar_reversible(formato):
    original = "Hola Mundo 123"
    codificado = logic.codificar(original, formato)["resultado"]
    decodificado = logic.decodificar(codificado, formato)["resultado"]
    assert decodificado == original


def test_codificar_formato_invalido():
    with pytest.raises(ValueError):
        logic.codificar("texto", "formato-inexistente")


def test_decodificar_base64_invalida():
    with pytest.raises(ValueError):
        logic.decodificar("no es base64 valido!!", "base64")


def test_decodificarJwt():
    token = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0"
        ".dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    )
    resultado = logic.decodificarJwt(token)
    assert resultado["cabecera"]["alg"] == "HS256"
    assert resultado["cuerpo"]["name"] == "John Doe"


def test_decodificarJwt_formato_invalido():
    with pytest.raises(ValueError):
        logic.decodificarJwt("no-es-un-token")


def test_generarUuid_v4():
    resultado = logic.generarUuid("4")
    assert resultado["version"] == 4
    assert len(resultado["uuid"]) == 36


def test_generarUuid_v1():
    resultado = logic.generarUuid("1")
    assert resultado["version"] == 1


def test_generarUuid_version_invalida():
    with pytest.raises(ValueError):
        logic.generarUuid("5")


def test_generarContrasena_longitud():
    resultado = logic.generarContrasena(16, "si", "si", "si", "si")
    assert resultado["longitud"] == 16
    assert len(resultado["contrasena"]) == 16


def test_generarContrasena_sin_conjuntos():
    with pytest.raises(ValueError):
        logic.generarContrasena(16, "no", "no", "no", "no")


def test_generarContrasena_longitud_fuera_de_rango():
    with pytest.raises(ValueError):
        logic.generarContrasena(2, "si", "si", "no", "no")


def test_generarContrasena_solo_numeros():
    resultado = logic.generarContrasena(10, "no", "no", "si", "no")
    assert resultado["contrasena"].isdigit()


def test_generarPassphrase():
    resultado = logic.generarPassphrase(5, "-")
    assert resultado["numPalabras"] == 5
    assert len(resultado["passphrase"].split("-")) == 5


def test_generarPassphrase_fuera_de_rango():
    with pytest.raises(ValueError):
        logic.generarPassphrase(1, "-")


def test_comprobarFortalezaContrasena_debil():
    resultado = logic.comprobarFortalezaContrasena("123456")
    assert resultado["puntuacion"] <= 1


def test_comprobarFortalezaContrasena_vacia():
    with pytest.raises(ValueError):
        logic.comprobarFortalezaContrasena("")


def test_compararTextos_identicos():
    resultado = logic.compararTextos("hola\nmundo", "hola\nmundo")
    assert resultado["identicos"] is True
    assert resultado["similitud"] == 100.0


def test_compararTextos_diferentes():
    resultado = logic.compararTextos("hola\nmundo", "hola\npython")
    assert resultado["identicos"] is False
    assert "python" in resultado["diff"]
