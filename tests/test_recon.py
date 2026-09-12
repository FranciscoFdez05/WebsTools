import json

import pytest

from categories.osint import recon
from categories.osint.routes import TOOLS


# --- comun ---------------------------------------------------------------------------------


@pytest.mark.parametrize("entrada, esperada", [
    ("example.com", "https://example.com"),
    ("  example.com/ruta?x=1 ", "https://example.com/ruta?x=1"),
    ("http://example.com", "http://example.com"),
])
def test_normalizarUrl_completaElEsquema(entrada, esperada):
    assert recon._normalizarUrl(entrada) == esperada


@pytest.mark.parametrize("entrada", ["", "   ", "ftp://example.com", "file:///etc/passwd", "https://"])
def test_normalizarUrl_rechazaLoQueNoEsHttp(entrada):
    with pytest.raises(ValueError):
        recon._normalizarUrl(entrada)


# --- buscar usuario (Sherlock) --------------------------------------------------------------


def test_sitiosSherlock_copiaLocalCargaYTraeLosPopulares(monkeypatch):
    # sin URL remota se usa la copia del repositorio, que es la que garantiza que la herramienta
    # funcione aunque GitHub no responda
    monkeypatch.setattr(recon.Config, "sherlockSitiosUrl", "")
    monkeypatch.setattr(recon, "_cacheSitiosSherlock", {"sitios": None, "origen": None, "expira": 0.0})

    sitios, origen = recon._cargarSitiosSherlock()

    assert origen == "copia local"
    assert len(sitios) > 400
    assert "$schema" not in sitios
    assert all("url" in reglas and "errorType" in reglas for reglas in sitios.values())
    faltan = [nombre for nombre in recon.SITIOS_POPULARES if nombre not in sitios]
    assert faltan == []
    assert sitios["YouTube"]["headers"]["Cookie"] == "SOCS=CAI"


def test_sitiosSherlock_siGithubFallaUsaLaCopiaLocal(monkeypatch):
    def urlopenQueFalla(*args, **kwargs):
        raise OSError("sin red")

    monkeypatch.setattr(recon.Config, "sherlockSitiosUrl", "https://example.invalid/data.json")
    monkeypatch.setattr(recon.urllib.request, "urlopen", urlopenQueFalla)
    monkeypatch.setattr(recon, "_cacheSitiosSherlock", {"sitios": None, "origen": None, "expira": 0.0})

    sitios, origen = recon._cargarSitiosSherlock()

    assert origen == "copia local"
    assert "GitHub" in sitios


def test_interpolar_sustituyeEnCadenasDictsYListas():
    plantilla = {"username": "{}", "anidado": ["{}", {"x": "{}"}], "numero": 3}
    assert recon._interpolar(plantilla, "ana") == {"username": "ana", "anidado": ["ana", {"x": "ana"}], "numero": 3}


@pytest.mark.parametrize("reglas, codigo, texto, esperado", [
    ({"errorType": "status_code"}, 200, "", True),
    ({"errorType": "status_code"}, 404, "", False),
    ({"errorType": "status_code"}, 302, "", False),
    ({"errorType": "status_code", "errorCode": 204}, 204, "", False),
    ({"errorType": "status_code", "errorCode": [404, 410]}, 410, "", False),
    ({"errorType": "message", "errorMsg": "No existe"}, 200, "<h1>No existe</h1>", False),
    ({"errorType": "message", "errorMsg": "No existe"}, 200, "<h1>Perfil de ana</h1>", True),
    ({"errorType": "message", "errorMsg": ["No existe", "Too Many"]}, 200, "429 Too Many Requests", False),
    ({"errorType": "response_url"}, 200, "", True),
    ({"errorType": "response_url"}, 301, "", False),
    ({"errorType": ["message", "status_code"], "errorMsg": "No existe"}, 404, "perfil", False),
    ({"errorType": ["message", "status_code"], "errorMsg": "No existe"}, 200, "perfil", True),
])
def test_evaluarRespuestaSherlock(reglas, codigo, texto, esperado):
    assert recon.evaluarRespuestaSherlock(reglas, codigo, texto) is esperado


def test_evaluarRespuestaSherlock_tipoDesconocido():
    with pytest.raises(ValueError):
        recon.evaluarRespuestaSherlock({"errorType": "magia"}, 200, "")


@pytest.mark.parametrize("usuario", ["", "   ", "con espacios", "a" * 65, "<script>"])
def test_buscarUsuario_rechazaUsuariosInvalidos(usuario):
    with pytest.raises(ValueError):
        recon.buscarUsuario(usuario)


def test_buscarUsuario_rechazaAlcanceDesconocido():
    with pytest.raises(ValueError):
        recon.buscarUsuario("ana", "algunos")


def test_buscarUsuario_agrupaLosResultados(monkeypatch):
    sitios = {
        "Uno": {"errorType": "status_code", "url": "https://uno.test/{}"},
        "Dos": {"errorType": "status_code", "url": "https://dos.test/{}"},
        "Tres": {"errorType": "message", "errorMsg": "x", "url": "https://tres.test/{}"},
        "Cuatro": {"errorType": "status_code", "url": "https://cuatro.test/{}", "regexCheck": "^[0-9]+$"},
        "Cinco": {"errorType": "status_code", "url": "https://cinco.test/{}"},
        "Guarro": {"errorType": "status_code", "url": "https://guarro.test/{}", "isNSFW": True},
    }
    estados = {"Uno": "encontrado", "Dos": "libre", "Tres": "bloqueado", "Cinco": "error", "Guarro": "encontrado"}

    def comprobarFalso(cliente, nombre, reglas, usuario):
        if reglas.get("regexCheck"):
            return {"sitio": nombre, "url": reglas["url"], "estado": "no aplica", "detalle": ""}
        return {"sitio": nombre, "url": reglas["url"].replace("{}", usuario), "estado": estados[nombre], "detalle": ""}

    monkeypatch.setattr(recon, "_cargarSitiosSherlock", lambda: (sitios, "prueba"))
    monkeypatch.setattr(recon, "_comprobarSitioSherlock", comprobarFalso)

    resultado = recon.buscarUsuario("ana", "todos")

    assert resultado["sitiosComprobados"] == 5  # sin el NSFW
    assert resultado["perfiles"] == [{"sitio": "Uno", "url": "https://uno.test/ana"}]
    assert resultado["encontrados"] == 1
    assert resultado["libres"] == 1
    assert resultado["sitiosQueNosBloquean"] == "Tres"
    assert resultado["sitiosSinRespuesta"] == "Cinco"
    assert resultado["sitiosQueNoAdmitenEseUsuario"] == "Cuatro"
    assert resultado["origenListaSitios"] == "prueba"

    assert recon.buscarUsuario("ana", "todos+nsfw")["sitiosComprobados"] == 6
    assert recon.buscarUsuario("ana", "populares")["sitiosComprobados"] == 0


def test_alcancesSherlock_sonLasOpcionesDelFormulario():
    campoAlcance = next(campo for campo in TOOLS["buscar-usuario"]["campos"] if campo["nombre"] == "alcance")
    assert campoAlcance["opciones"] == list(recon.ALCANCES_SHERLOCK)


# --- comprobar email (holehe) ---------------------------------------------------------------


@pytest.mark.parametrize("email", ["", "sin-arroba", "a@b", "a@b.", "@example.com", "ana@example.com extra"])
def test_comprobarEmail_rechazaEmailsInvalidos(email):
    with pytest.raises(ValueError):
        recon.comprobarEmail(email)


def test_modulosHolehe_excluyeLosQueAvisanAlDueno():
    modulos = recon._cargarModulosHolehe()
    nombres = {modulo.__name__ for modulo in modulos}

    assert len(modulos) > 100
    assert nombres.isdisjoint(recon.MODULOS_HOLEHE_EXCLUIDOS)
    assert "twitter" in nombres


def test_comprobarEmail_resumeLaSalidaDeHolehe(monkeypatch):
    salida = [
        {"name": "twitter", "domain": "twitter.com", "rateLimit": False, "exists": True, "emailrecovery": "t***@gmail.com", "phoneNumber": None, "others": None},
        {"name": "github", "domain": "github.com", "rateLimit": False, "exists": False, "emailrecovery": None, "phoneNumber": None, "others": None},
        {"name": "discord", "domain": "discord.com", "rateLimit": True, "exists": False, "emailrecovery": None, "phoneNumber": None, "others": None},
        # el mismo sitio anotado dos veces: primero sin respuesta y luego con resultado
        {"name": "imgur", "domain": "imgur.com", "rateLimit": True, "exists": False, "emailrecovery": None, "phoneNumber": None, "others": None},
        {"name": "imgur", "domain": "imgur.com", "rateLimit": False, "exists": True, "emailrecovery": None, "phoneNumber": None, "others": {"FullName": "Ana"}},
    ]
    monkeypatch.setattr(recon, "_cargarModulosHolehe", lambda: [object()] * 4)
    monkeypatch.setattr(recon.trio, "run", lambda funcion: salida)

    resultado = recon.comprobarEmail("  Ana@Example.com ")

    assert resultado["email"] == "ana@example.com"
    assert resultado["sitiosComprobados"] == 4
    assert resultado["registradoEn"] == 2
    assert [cuenta["sitio"] for cuenta in resultado["cuentas"]] == ["imgur", "twitter"]
    assert resultado["cuentas"][1]["emailRecuperacion"] == "t***@gmail.com"
    assert json.loads(resultado["cuentas"][0]["otros"]) == {"FullName": "Ana"}
    assert resultado["noRegistrado"] == 1
    assert resultado["sinRespuesta"] == 1
    assert resultado["sitiosSinRespuesta"] == "discord"
    assert "adobe" in resultado["sitiosExcluidos"]


# --- cabeceras HTTP -------------------------------------------------------------------------


def test_analizarCookie_leeLosAtributosDeSeguridad():
    cookie = recon._analizarCookie("sesion=abc123; Path=/; Secure; HttpOnly; SameSite=Lax")
    assert cookie == {"nombre": "sesion", "secure": True, "httpOnly": True, "sameSite": "Lax"}

    cookie = recon._analizarCookie("visitas=3; Path=/")
    assert cookie == {"nombre": "visitas", "secure": False, "httpOnly": False, "sameSite": None}


def test_analizarCabecerasHttp_rechazaUrlInvalida():
    with pytest.raises(ValueError):
        recon.analizarCabecerasHttp("ftp://example.com")


# --- escaner de puertos ---------------------------------------------------------------------


def test_parsearPuertos_vacioSonLosComunes():
    assert recon.parsearPuertos("") == sorted(recon.PUERTOS_COMUNES)
    assert 22 in recon.parsearPuertos(None)


def test_parsearPuertos_listaYRangos():
    assert recon.parsearPuertos("80, 22,443") == [22, 80, 443]
    assert recon.parsearPuertos("8000-8003,22") == [22, 8000, 8001, 8002, 8003]
    assert recon.parsearPuertos("80,80,80") == [80]


@pytest.mark.parametrize("texto", ["abc", "0", "65536", "100-50", ",", "1-2000", "80-"])
def test_parsearPuertos_rechazaEntradasInvalidas(texto):
    with pytest.raises(ValueError):
        recon.parsearPuertos(texto)


def test_escanearPuertos_sinHost():
    with pytest.raises(ValueError):
        recon.escanearPuertos("", "80")


def test_escanearPuertos_hostQueNoResuelve():
    with pytest.raises(ValueError):
        recon.escanearPuertos("no-existe.invalid", "80")


def test_escanearPuertos_detectaUnPuertoAbiertoEnLocal():
    import socket

    with socket.socket() as servidor:
        servidor.bind(("127.0.0.1", 0))
        servidor.listen(1)
        puerto = servidor.getsockname()[1]
        # un puerto vecino sin nadie escuchando: el rango cubre uno abierto y uno cerrado
        cerrado = puerto - 1 if puerto > 1 else puerto + 1

        resultado = recon.escanearPuertos("127.0.0.1", f"{min(puerto, cerrado)}-{max(puerto, cerrado)}")

    assert resultado["ip"] == "127.0.0.1"
    assert resultado["puertosEscaneados"] == 2
    assert [entrada["puerto"] for entrada in resultado["puertosAbiertos"]] == [puerto]


# --- transferencia de zona ------------------------------------------------------------------


def test_comprobarTransferenciaZona_sinDominio():
    with pytest.raises(ValueError):
        recon.comprobarTransferenciaZona("")


# --- Wayback Machine ------------------------------------------------------------------------


def test_capturaWayback_formateaLaFechaYLaUrl():
    captura = recon._capturaWayback(["20240506070809", "http://example.com/", "200", "text/html"])
    assert captura == {
        "fecha": "2024-05-06 07:08:09",
        "codigo": "200",
        "tipo": "text/html",
        "url": "https://web.archive.org/web/20240506070809/http://example.com/",
    }


def test_consultarWayback_sinCapturas(monkeypatch):
    monkeypatch.setattr(recon, "_consultarCdx", lambda url, **parametros: [])
    resultado = recon.consultarWayback("example.com")
    assert resultado["archivada"] is False
    assert resultado["ultimasCapturas"] == []


def test_consultarWayback_ordenaLasUltimasDeMasReciente(monkeypatch):
    def cdxFalso(url, **parametros):
        if parametros.get("limit") == 1:
            return [recon._capturaWayback(["20000101000000", url, "200", "text/html"])]
        return [recon._capturaWayback([f"2024010{i}000000", url, "200", "text/html"]) for i in range(1, 4)]

    monkeypatch.setattr(recon, "_consultarCdx", cdxFalso)
    resultado = recon.consultarWayback("example.com")

    assert resultado["archivada"] is True
    assert resultado["primeraCaptura"]["fecha"].startswith("2000-01-01")
    assert resultado["ultimaCaptura"]["fecha"].startswith("2024-01-03")
    assert [captura["fecha"][:10] for captura in resultado["ultimasCapturas"]] == ["2024-01-03", "2024-01-02", "2024-01-01"]


# --- extraer datos de una pagina ------------------------------------------------------------


class RespuestaFalsa:
    def __init__(self, url, codigo=200, cabeceras=None):
        self.url = url
        self.status_code = codigo
        self.headers = cabeceras or {}
        self.charset_encoding = "utf-8"


def test_extraerDatosPagina_sacaEmailsEnlacesYRedes(monkeypatch):
    html = """
    <html lang="es"><head><title> Mi Empresa </title>
    <meta name="description" content="Fontaneria en Madrid"><meta name="generator" content="WordPress 6.5">
    <script src="https://cdn.jsdelivr.net/npm/x.js"></script><script src="/local.js"></script>
    </head><body><!-- TODO: quitar el usuario admin -->
    <a href="mailto:Info@miempresa.es?subject=hola">email</a>
    <a href="tel:+34600000000">llamar</a>
    <a href="/contacto">contacto</a><a href="https://miempresa.es/blog">blog</a>
    <a href="https://www.instagram.com/miempresa/#top">ig</a><a href="https://twitter.com/miempresa">tw</a>
    <a href="https://proveedor.com/x">prov</a><a href="javascript:void(0)">nada</a>
    <p>Escribe a soporte@miempresa.es o a soporte@miempresa.es</p>
    </body></html>
    """
    monkeypatch.setattr(recon, "_descargar", lambda url, **kw: (RespuestaFalsa("https://miempresa.es/"), html.encode("utf-8")))

    datos = recon.extraerDatosPagina("miempresa.es")

    assert datos["titulo"] == "Mi Empresa"
    assert datos["descripcion"] == "Fontaneria en Madrid"
    assert datos["generador"] == "WordPress 6.5"
    assert datos["idioma"] == "es"
    assert datos["emails"] == ["Info@miempresa.es", "soporte@miempresa.es"]
    assert datos["telefonos"] == ["+34600000000"]
    assert datos["redesSociales"] == ["https://twitter.com/miempresa", "https://www.instagram.com/miempresa/"]
    assert datos["enlacesInternos"] == 2
    assert datos["dominiosExternos"] == ["proveedor.com"]
    assert datos["scriptsExternos"] == ["cdn.jsdelivr.net"]
    assert datos["comentariosHtml"] == ["TODO: quitar el usuario admin"]


# --- robots.txt y sitemap -------------------------------------------------------------------


def test_parsearRobots_agrupaPorUserAgentYSacaSitemaps():
    texto = """
    # comentario
    User-agent: Googlebot
    User-agent: Bingbot
    Disallow: /privado/
    Allow: /privado/publico.html

    User-agent: *
    Disallow: /admin
    Disallow: /tmp  # inline

    Sitemap: https://example.com/sitemap.xml
    """
    grupos, sitemaps = recon.parsearRobots(texto)

    assert sitemaps == ["https://example.com/sitemap.xml"]
    assert grupos == [
        {"agentes": ["Googlebot", "Bingbot"], "disallow": ["/privado/"], "allow": ["/privado/publico.html"]},
        {"agentes": ["*"], "disallow": ["/admin", "/tmp"], "allow": []},
    ]


def test_parsearRobots_vacio():
    assert recon.parsearRobots("") == ([], [])


def test_analizarRobotsSitemap_leeIndiceYSitemap(monkeypatch):
    paginas = {
        "https://example.com/robots.txt": (200, b"User-agent: *\nDisallow: /admin\nSitemap: https://example.com/indice.xml\n"),
        "https://example.com/indice.xml": (200, b'<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://example.com/s1.xml</loc></sitemap></sitemapindex>'),
        "https://example.com/s1.xml": (200, b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/a</loc></url><url><loc>https://example.com/b</loc></url></urlset>'),
    }

    def descargarFalso(url, **kw):
        codigo, cuerpo = paginas[url]
        return RespuestaFalsa(url, codigo, {"content-type": "text/plain" if url.endswith(".txt") else "application/xml"}), cuerpo

    monkeypatch.setattr(recon, "_descargar", descargarFalso)

    resultado = recon.analizarRobotsSitemap("https://example.com/cualquier/ruta")

    assert resultado["sitio"] == "https://example.com"
    assert resultado["robots"]["existe"] is True
    assert resultado["robots"]["rutasBloqueadas"] == 1
    assert resultado["robots"]["reglas"] == [{"userAgent": "*", "disallow": "/admin", "allow": ""}]
    assert resultado["robots"]["sitemapsDeclarados"] == ["https://example.com/indice.xml"]
    assert resultado["sitemap"]["urlsEncontradas"] == 2
    assert resultado["sitemap"]["urls"] == ["https://example.com/a", "https://example.com/b"]
    assert [entrada["sitemap"] for entrada in resultado["sitemap"]["sitemapsLeidos"]] == ["https://example.com/indice.xml", "https://example.com/s1.xml"]


def test_analizarRobotsSitemap_sinRobotsPruebaSitemapPorDefecto(monkeypatch):
    def descargarFalso(url, **kw):
        if url.endswith("robots.txt"):
            return RespuestaFalsa(url, 404, {"content-type": "text/html"}), b"<html>404</html>"
        return RespuestaFalsa(url, 404, {}), b"<html>404</html>"

    monkeypatch.setattr(recon, "_descargar", descargarFalso)

    resultado = recon.analizarRobotsSitemap("example.com")

    assert resultado["robots"]["existe"] is False
    assert resultado["robots"]["reglas"] == []
    assert resultado["sitemap"]["urlsEncontradas"] == 0
    assert resultado["sitemap"]["sitemapsLeidos"] == [{"sitemap": "https://example.com/sitemap.xml", "leido": False, "urls": 0, "detalle": "HTTP 404"}]
