import pytest

from categories.json_prog import logic


def test_formatearJson():
    resultado = logic.formatearJson('{"b":1,"a":2}')
    assert '"b": 1' in resultado["resultado"]
    assert "\n" in resultado["resultado"]


def test_formatearJson_invalido():
    with pytest.raises(ValueError):
        logic.formatearJson("{no es json}")


def test_validarJson_valido():
    resultado = logic.validarJson('{"clave": "valor"}')
    assert resultado["valido"] is True
    assert resultado["error"] is None


def test_validarJson_invalido():
    resultado = logic.validarJson("{clave sin comillas}")
    assert resultado["valido"] is False
    assert resultado["error"] is not None


def test_minificarJson():
    resultado = logic.minificarJson('{\n  "a": 1,\n  "b": 2\n}')
    assert resultado["resultado"] == '{"a":1,"b":2}'


def test_beautifyXml():
    resultado = logic.beautifyXml("<root><a>1</a></root>")
    assert "<root>" in resultado["resultado"]
    assert "\n" in resultado["resultado"]


def test_beautifyXml_invalido():
    with pytest.raises(ValueError):
        logic.beautifyXml("<root><a></root>")


def test_beautifyXml_vacio():
    with pytest.raises(ValueError):
        logic.beautifyXml("")


def test_beautifyHtml():
    resultado = logic.beautifyHtml("<html><body><p>hola</p></body></html>")
    assert "<p>" in resultado["resultado"]


def test_beautifyHtml_vacio():
    with pytest.raises(ValueError):
        logic.beautifyHtml("")


def test_beautifyCss():
    resultado = logic.beautifyCss("body{color:red;}")
    assert "color: red" in resultado["resultado"]


def test_beautifyCss_vacio():
    with pytest.raises(ValueError):
        logic.beautifyCss("")


def test_beautifyJavascript():
    resultado = logic.beautifyJavascript("function f(){return 1;}")
    assert "function f()" in resultado["resultado"]


def test_beautifyJavascript_vacio():
    with pytest.raises(ValueError):
        logic.beautifyJavascript("")


def test_ofuscarJavascript_charcode():
    resultado = logic.ofuscarJavascript("alert(1)", "charcode")
    assert resultado["resultado"].startswith("eval(String.fromCharCode(")
    assert str(ord("a")) in resultado["resultado"]


def test_ofuscarJavascript_base64():
    resultado = logic.ofuscarJavascript("alert(1)", "base64")
    assert "atob(" in resultado["resultado"]


def test_ofuscarJavascript_hexadecimal():
    resultado = logic.ofuscarJavascript("ab", "hexadecimal")
    assert "\\x61\\x62" in resultado["resultado"]


def test_ofuscarJavascript_vacio():
    with pytest.raises(ValueError):
        logic.ofuscarJavascript("", "charcode")


def test_ofuscarJavascript_tecnica_invalida():
    with pytest.raises(ValueError):
        logic.ofuscarJavascript("alert(1)", "inexistente")
