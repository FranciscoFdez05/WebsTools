import pytest

from categories.redes import logic


def test_ipADecimal():
    resultado = logic.ipADecimal("192.168.1.1")
    assert resultado["decimal"] == 3232235777


def test_ipADecimal_invalida():
    with pytest.raises(ValueError):
        logic.ipADecimal("300.1.1.1")


def test_decimalAIp():
    resultado = logic.decimalAIp(3232235777)
    assert resultado["ip"] == "192.168.1.1"


def test_calcularSubred():
    resultado = logic.calcularSubred("192.168.1.0/24")
    assert resultado["direccionRed"] == "192.168.1.0"
    assert resultado["broadcast"] == "192.168.1.255"
    assert resultado["numHostsUtilizables"] == 254


def test_calcularSubred_invalida():
    with pytest.raises(ValueError):
        logic.calcularSubred("no-es-un-cidr")


def test_validarIp_valida():
    resultado = logic.validarIp("10.0.0.1")
    assert resultado["valida"] is True
    assert resultado["version"] == 4
    assert resultado["privada"] is True


def test_validarIp_invalida():
    resultado = logic.validarIp("no-es-una-ip")
    assert resultado["valida"] is False


def test_calcularWildcard():
    resultado = logic.calcularWildcard("192.168.1.0/24")
    assert resultado["wildcard"] == "0.0.0.255"


def test_generarMacAleatoria_formato():
    resultado = logic.generarMacAleatoria()
    partes = resultado["mac"].split(":")
    assert len(partes) == 6
    assert all(len(parte) == 2 for parte in partes)


def test_ipv4AIpv6():
    resultado = logic.ipv4AIpv6("192.168.1.1")
    assert resultado["ipv6"] == "::ffff:192.168.1.1"


def test_ipv4AIpv6_invalida():
    with pytest.raises(ValueError):
        logic.ipv4AIpv6("300.1.1.1")


def test_ipv6AIpv4():
    resultado = logic.ipv6AIpv4("::ffff:192.168.1.1")
    assert resultado["ipv4"] == "192.168.1.1"


def test_ipv6AIpv4_no_mapeada():
    with pytest.raises(ValueError):
        logic.ipv6AIpv4("2606:4700::1")


def test_ipv6AIpv4_invalida():
    with pytest.raises(ValueError):
        logic.ipv6AIpv4("no-es-una-ipv6")
