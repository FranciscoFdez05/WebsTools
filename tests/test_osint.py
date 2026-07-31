import pytest

from categories.osint import logic


def test_esIpCloudflare_ipv4_en_rango():
    resultado = logic.esIpCloudflare("104.16.0.1")
    assert resultado["esCloudflare"] is True
    assert resultado["rango"] == "104.16.0.0/13"


def test_esIpCloudflare_ipv4_fuera_de_rango():
    resultado = logic.esIpCloudflare("8.8.8.8")
    assert resultado["esCloudflare"] is False


def test_esIpCloudflare_ipv6_en_rango():
    resultado = logic.esIpCloudflare("2606:4700::1")
    assert resultado["esCloudflare"] is True


def test_esIpCloudflare_ip_invalida():
    with pytest.raises(ValueError):
        logic.esIpCloudflare("no-es-una-ip")


def test_esIpCloudflare_vacio():
    with pytest.raises(ValueError):
        logic.esIpCloudflare("")


def test_comprobarSpf_sin_dominio():
    with pytest.raises(ValueError):
        logic.comprobarSpf("")


def test_comprobarDkim_sin_dominio():
    with pytest.raises(ValueError):
        logic.comprobarDkim("", "default")


def test_comprobarDkim_selector_por_defecto():
    with pytest.raises(ValueError):
        logic.comprobarDkim("", "")


def test_comprobarDmarc_sin_dominio():
    with pytest.raises(ValueError):
        logic.comprobarDmarc("")


def test_buscarAsn_sin_ip():
    with pytest.raises(ValueError):
        logic.buscarAsn("")


def test_buscarSubdominios_sin_dominio():
    with pytest.raises(ValueError):
        logic.buscarSubdominios("")


def test_comprobarPropagacionDns_sin_dominio():
    with pytest.raises(ValueError):
        logic.comprobarPropagacionDns("", "A")


def test_comprobarPropagacionDns_tipo_invalido():
    with pytest.raises(ValueError):
        logic.comprobarPropagacionDns("example.com", "PTR")
