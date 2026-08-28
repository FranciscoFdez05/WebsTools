import io
import ipaddress

import pytest
import qrcode

from categories.utilidades import logic


def test_timestampAFecha():
    resultado = logic.timestampAFecha(0)
    assert resultado["fechaIso"].startswith("1970-01-01")


def test_timestampAFecha_invalido():
    with pytest.raises(ValueError):
        logic.timestampAFecha("no-es-un-numero")


def test_fechaATimestamp():
    resultado = logic.fechaATimestamp("1970-01-01T00:00:00+00:00")
    assert resultado["timestampUnix"] == 0


def test_fechaATimestamp_invalida():
    with pytest.raises(ValueError):
        logic.fechaATimestamp("no-es-una-fecha")


def test_fechaATimestamp_vacia():
    with pytest.raises(ValueError):
        logic.fechaATimestamp("")


def test_convertirUnixTime_segundos():
    resultado = logic.convertirUnixTime("0", "segundos")
    assert resultado["segundos"] == 0
    assert resultado["milisegundos"] == 0


def test_convertirUnixTime_milisegundos():
    resultado = logic.convertirUnixTime("1000", "milisegundos")
    assert resultado["segundos"] == 1


def test_convertirUnixTime_ahora_sin_valor():
    resultado = logic.convertirUnixTime(None, "segundos")
    assert resultado["segundos"] > 0


def test_convertirUnixTime_unidad_invalida():
    with pytest.raises(ValueError):
        logic.convertirUnixTime("0", "minutos")


def test_convertirUnidades_longitud():
    resultado = logic.convertirUnidades("longitud", "1", "km", "m")
    assert resultado["resultado"] == 1000


def test_convertirUnidades_datos():
    resultado = logic.convertirUnidades("datos", "1", "gb", "mb")
    assert resultado["resultado"] == 1024


def test_convertirUnidades_temperatura_celsius_a_fahrenheit():
    resultado = logic.convertirUnidades("temperatura", "0", "c", "f")
    assert resultado["resultado"] == 32


def test_convertirUnidades_categoria_invalida():
    with pytest.raises(ValueError):
        logic.convertirUnidades("volumen", "1", "l", "ml")


def test_convertirUnidades_unidad_invalida():
    with pytest.raises(ValueError):
        logic.convertirUnidades("longitud", "1", "parsecs", "m")


def test_generarClaveApi_hex():
    resultado = logic.generarClaveApi(32, "hex")
    assert len(resultado["claveApi"]) == 64


def test_generarClaveApi_base64():
    resultado = logic.generarClaveApi(16, "base64")
    assert resultado["longitudBytes"] == 16


def test_generarClaveApi_formato_invalido():
    with pytest.raises(ValueError):
        logic.generarClaveApi(32, "octal")


def test_generarClaveApi_longitud_fuera_de_rango():
    with pytest.raises(ValueError):
        logic.generarClaveApi(4, "hex")


# --- InternetDownloader: tests de seguridad SSRF ---
# estos no requieren red: la resolucion de literales IP y el chequeo de esquema son locales


def test_esIpBloqueada_rangos_privados():
    assert logic._esIpBloqueada(ipaddress.ip_address("127.0.0.1")) is True
    assert logic._esIpBloqueada(ipaddress.ip_address("10.0.0.1")) is True
    assert logic._esIpBloqueada(ipaddress.ip_address("172.16.0.1")) is True
    assert logic._esIpBloqueada(ipaddress.ip_address("192.168.1.1")) is True
    assert logic._esIpBloqueada(ipaddress.ip_address("169.254.169.254")) is True
    assert logic._esIpBloqueada(ipaddress.ip_address("::1")) is True
    assert logic._esIpBloqueada(ipaddress.ip_address("fc00::1")) is True


def test_esIpBloqueada_ip_publica_permitida():
    assert logic._esIpBloqueada(ipaddress.ip_address("8.8.8.8")) is False


def test_descargarUrlSegura_localhost_bloqueado():
    with pytest.raises(ValueError):
        logic.descargarUrlSegura("http://127.0.0.1/")


def test_descargarUrlSegura_metadata_cloud_bloqueado():
    with pytest.raises(ValueError):
        logic.descargarUrlSegura("http://169.254.169.254/latest/meta-data/")


def test_descargarUrlSegura_red_privada_10_bloqueada():
    with pytest.raises(ValueError):
        logic.descargarUrlSegura("http://10.0.0.1/")


def test_descargarUrlSegura_red_privada_192_bloqueada():
    with pytest.raises(ValueError):
        logic.descargarUrlSegura("http://192.168.1.1/")


def test_descargarUrlSegura_ipv6_loopback_bloqueada():
    with pytest.raises(ValueError):
        logic.descargarUrlSegura("http://[::1]/")


def test_descargarUrlSegura_esquema_file_rechazado():
    with pytest.raises(ValueError):
        logic.descargarUrlSegura("file:///etc/passwd")


def test_descargarUrlSegura_esquema_ftp_rechazado():
    with pytest.raises(ValueError):
        logic.descargarUrlSegura("ftp://ejemplo.com/archivo")


def test_descargarUrlSegura_esquema_gopher_rechazado():
    with pytest.raises(ValueError):
        logic.descargarUrlSegura("gopher://ejemplo.com/")


def test_descargarUrlSegura_esquema_dict_rechazado():
    with pytest.raises(ValueError):
        logic.descargarUrlSegura("dict://ejemplo.com/")


def test_descargarUrlSegura_sin_url():
    with pytest.raises(ValueError):
        logic.descargarUrlSegura("")


def test_descargarUrlSegura_sin_host():
    with pytest.raises(ValueError):
        logic.descargarUrlSegura("http:///ruta-sin-host")


# --- QR ---


def test_generarQr():
    contenido = logic.generarQr("https://example.com")
    assert contenido[:8] == b"\x89PNG\r\n\x1a\n"


def test_generarQr_vacio():
    with pytest.raises(ValueError):
        logic.generarQr("")


def test_leerQr_roundtrip():
    imagenQr = qrcode.make("hola mundo")
    buffer = io.BytesIO()
    imagenQr.save(buffer, format="PNG")
    resultado = logic.leerQr(buffer.getvalue())
    assert resultado["encontrados"] == 1
    assert resultado["codigos"][0] == "hola mundo"


def test_leerQr_vacio():
    with pytest.raises(ValueError):
        logic.leerQr(b"")


def test_leerQr_sin_codigos():
    from PIL import Image

    imagenBlanca = Image.new("RGB", (50, 50), color="white")
    buffer = io.BytesIO()
    imagenBlanca.save(buffer, format="PNG")
    resultado = logic.leerQr(buffer.getvalue())
    assert resultado["encontrados"] == 0


# --- Lorem ipsum, nombres, user-agent ---


def test_generarLoremIpsum():
    resultado = logic.generarLoremIpsum(2, 3)
    assert len(resultado["parrafos"]) == 2
    assert resultado["parrafos"][0].startswith("Lorem ipsum dolor sit amet")


def test_generarLoremIpsum_fuera_de_rango():
    with pytest.raises(ValueError):
        logic.generarLoremIpsum(0, 3)


def test_generarNombresAleatorios():
    resultado = logic.generarNombresAleatorios(5, "masculino")
    assert resultado["cantidad"] == 5
    assert len(resultado["nombres"]) == 5


def test_generarNombresAleatorios_genero_invalido():
    with pytest.raises(ValueError):
        logic.generarNombresAleatorios(5, "otro")


def test_generarNombresAleatorios_cantidad_fuera_de_rango():
    with pytest.raises(ValueError):
        logic.generarNombresAleatorios(100, "aleatorio")


def test_generarUserAgent_navegador_especifico():
    resultado = logic.generarUserAgent("chrome")
    assert "Chrome" in resultado["userAgent"]


def test_generarUserAgent_aleatorio():
    resultado = logic.generarUserAgent("aleatorio")
    assert resultado["userAgent"]


def test_generarUserAgent_navegador_invalido():
    with pytest.raises(ValueError):
        logic.generarUserAgent("netscape")


class _YoutubeDlSimulado:
    def __init__(self, opciones):
        self.opciones = opciones

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def extract_info(self, url, download=False):
        return {
            "title": "Video de prueba",
            "duration": 120,
            "format": "22 - 1280x720",
            "ext": "mp4",
            "url": "https://cdn.example.com/video.mp4",
        }


def test_obtenerUrlDirecta(monkeypatch):
    monkeypatch.setattr(logic.yt_dlp, "YoutubeDL", _YoutubeDlSimulado)
    resultado = logic.obtenerUrlDirecta("https://youtu.be/hej5Houejpc", "720p")
    assert resultado["urlDirecta"] == "https://cdn.example.com/video.mp4"
    assert resultado["urlsDirectas"] == ["https://cdn.example.com/video.mp4"]
    assert resultado["titulo"] == "Video de prueba"


def test_obtenerUrlDirecta_dominio_no_permitido():
    with pytest.raises(ValueError):
        logic.obtenerUrlDirecta("https://ejemplo-no-permitido.com/video", "mejor")


def test_obtenerUrlDirecta_sin_url_en_la_respuesta(monkeypatch):
    class SinUrl(_YoutubeDlSimulado):
        def extract_info(self, url, download=False):
            return {"title": "Sin url"}

    monkeypatch.setattr(logic.yt_dlp, "YoutubeDL", SinUrl)
    with pytest.raises(ValueError):
        logic.obtenerUrlDirecta("https://youtu.be/hej5Houejpc", "mejor")
