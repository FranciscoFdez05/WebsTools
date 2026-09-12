"""Reconocimiento y OSINT sobre personas y sitios web.

Las herramientas de logic.py preguntan a DNS, WHOIS y servicios de geolocalizacion. Estas van
un paso mas alla: buscan un nombre de usuario en cientos de redes (al estilo de Sherlock),
comprueban en que servicios esta registrado un email (con la libreria holehe), y hacen el
reconocimiento clasico de un sitio: cabeceras, puertos, transferencia de zona, robots.txt,
historial en la Wayback Machine y extraccion de emails y enlaces de una pagina.

Casi todo aqui lanza muchas peticiones a la vez o descarga paginas enteras, por eso usa httpx
(un cliente compartido entre hilos) en vez del urllib de logic.py, y por eso las rutas mas
pesadas llevan un limite de peticiones propio en app.py.
"""

import concurrent.futures
import json
import os
import re
import socket
import time
import urllib.parse
import gzip
import urllib.request
import xml.etree.ElementTree as ElementTree

import dns.exception
import dns.query
import dns.rdatatype
import dns.resolver
import dns.zone
import httpx
import trio
from bs4 import BeautifulSoup, Comment
from holehe.core import get_functions, import_submodules, launch_module

from config import Config

# los sitios devuelven otra cosa (o un captcha) a los clientes que no parecen un navegador
USER_AGENT_NAVEGADOR = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

# paginas y sitemaps se descargan enteros para analizarlos; se corta aqui para que una URL
# que apunte a un archivo enorme no llene la memoria del servidor
MAX_BYTES_DESCARGA = 3 * 1024 * 1024

EXPRESION_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
EXPRESION_EMAILS_EN_TEXTO = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")


def _normalizarUrl(url):
    """Acepta 'example.com', 'example.com/ruta' o una URL completa; solo http y https."""
    url = (url or "").strip()
    if not url:
        raise ValueError("Indica una URL")
    if "://" not in url:
        url = "https://" + url
    partes = urllib.parse.urlsplit(url)
    if partes.scheme not in ("http", "https") or not partes.netloc:
        raise ValueError("URL invalida: tiene que ser http:// o https:// seguido de un dominio")
    return urllib.parse.urlunsplit(partes)


def _descargar(url, timeout=None, seguirRedirecciones=True):
    """GET de una URL con el cuerpo limitado a MAX_BYTES_DESCARGA. Devuelve (respuesta, bytes)."""
    timeout = timeout or Config.osintTimeoutSegundos
    try:
        with httpx.Client(timeout=timeout, follow_redirects=seguirRedirecciones, headers={"User-Agent": USER_AGENT_NAVEGADOR}) as cliente:
            with cliente.stream("GET", url) as respuesta:
                trozos = []
                leidos = 0
                for trozo in respuesta.iter_bytes():
                    trozos.append(trozo)
                    leidos += len(trozo)
                    if leidos >= MAX_BYTES_DESCARGA:
                        break
                return respuesta, b"".join(trozos)[:MAX_BYTES_DESCARGA]
    except httpx.HTTPError as error:
        raise ValueError(f"No se pudo conectar con {url}: {error}")


def _decodificar(respuesta, cuerpo):
    codificacion = respuesta.charset_encoding or "utf-8"
    try:
        return cuerpo.decode(codificacion, errors="replace")
    except LookupError:
        return cuerpo.decode("utf-8", errors="replace")


# --- buscar usuario (Sherlock) ------------------------------------------------------------

# lista de sitios y reglas de deteccion del proyecto Sherlock. La copia local es la de respaldo
# por si GitHub no responde; la remota se prefiere porque los sitios cambian su HTML a menudo
# y Sherlock corrige las reglas casi cada semana
RUTA_SITIOS_SHERLOCK = os.path.join(os.path.dirname(__file__), "sherlock_sites.json")
CACHE_SITIOS_SEGUNDOS = 24 * 3600
_cacheSitiosSherlock = {"sitios": None, "origen": None, "expira": 0.0}

# "populares": lo que interesa en la mayoria de busquedas, en una fraccion del tiempo que
# tarda recorrer los mas de 400 sitios de la lista completa
SITIOS_POPULARES = (
    "GitHub", "GitLab", "BitBucket", "Codeberg", "Docker Hub", "PyPi", "npm", "RubyGems", "Packagist",
    "Codepen", "Replit.com", "HackerNews", "DEV Community", "Medium", "Substack", "Hashnode", "Kaggle",
    "Hugging Face", "LeetCode", "HackerRank", "Codeforces", "HackTheBox", "TryHackMe", "VirusTotal",
    "Instagram", "Twitter", "threads", "Bluesky", "TikTok", "Telegram", "YouTube", "Twitch", "Kick",
    "Reddit", "Pinterest", "tumblr", "Snapchat", "LinkedIn", "VK", "mastodon.social",
    "Spotify", "SoundCloud", "Bandcamp", "last.fm", "Vimeo", "DailyMotion", "Flickr", "Imgur", "Giphy",
    "Unsplash", "DeviantArt", "Behance", "Dribbble", "ArtStation", "Patreon", "kofi", "BuyMeACoffee",
    "Gumroad", "Linktree", "About.me", "Gravatar", "Keybase", "Steam Community (User)", "Xbox Gamertag",
    "Roblox", "Minecraft", "Chess", "Lichess", "Duolingo", "Strava", "Wikipedia", "Wattpad", "GoodReads",
    "Letterboxd", "Trello", "Slack", "Pastebin", "Scratch", "Freelancer", "Trakt",
)
ALCANCES_SHERLOCK = ("populares", "todos", "todos+nsfw")
HILOS_SHERLOCK = 40
TIMEOUT_SHERLOCK_SEGUNDOS = 7
EXPRESION_USUARIO = re.compile(r"^[A-Za-z0-9._@-]{1,64}$")
# el mismo que manda Sherlock: las reglas de deteccion estan afinadas para lo que los sitios
# devuelven a este navegador
USER_AGENT_SHERLOCK = "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0"
# trozos de las paginas de bloqueo de los WAF mas comunes (copiados de Sherlock): si aparecen, el
# sitio no ha respondido sobre el usuario sino sobre nosotros
HUELLAS_WAF = (
    '.loading-spinner{visibility:hidden}body.no-js .challenge-running{display:none}body.dark{background-color:#222;color:#d9d9d9}body.dark a{color:#fff}body.dark a:hover{color:#ee730a;text-decoration:underline}body.dark .lds-ring div{border-color:#999 transparent transparent}body.dark .font-red{color:#b20f03}body.dark',
    '<span id="challenge-error-text">',
    "AwsWafIntegration.forceRefreshToken",
    '{return l.onPageView}}),Object.defineProperty(r,"perimeterxIdentifiers",{enumerable:',
)
CODIGOS_BLOQUEO = (403, 429, 503)
# retoques sobre las reglas de Sherlock para lo que falla desde aqui y no desde donde se prueban
# ellas: YouTube manda a los visitantes europeos a una pagina de consentimiento (HTTP 200)
# exista o no el canal, y esa cookie la salta
AJUSTES_LOCALES_SHERLOCK = {
    "YouTube": {"headers": {"Cookie": "SOCS=CAI"}},
}


def _cargarSitiosSherlock():
    """Sitios de Sherlock como {nombre: reglas}, de GitHub si responde y si no de la copia local.

    Se cachea un dia en memoria; reiniciar la aplicacion fuerza una descarga nueva.
    """
    ahora = time.time()
    if _cacheSitiosSherlock["sitios"] is not None and ahora < _cacheSitiosSherlock["expira"]:
        return _cacheSitiosSherlock["sitios"], _cacheSitiosSherlock["origen"]

    sitios, origen = None, "copia local"
    if Config.sherlockSitiosUrl:
        peticion = urllib.request.Request(Config.sherlockSitiosUrl, headers={"User-Agent": USER_AGENT_NAVEGADOR})
        try:
            with urllib.request.urlopen(peticion, timeout=Config.osintTimeoutSegundos) as respuesta:
                sitios = json.loads(respuesta.read().decode("utf-8"))
            origen = Config.sherlockSitiosUrl
        except Exception:
            sitios = None
    if not isinstance(sitios, dict):
        with open(RUTA_SITIOS_SHERLOCK, encoding="utf-8") as archivo:
            sitios = json.load(archivo)

    # el JSON trae una clave "$schema" y podria traer entradas mal formadas: solo valen las reglas
    sitios = {nombre: reglas for nombre, reglas in sitios.items() if isinstance(reglas, dict) and "url" in reglas and "errorType" in reglas}
    for nombre, ajustes in AJUSTES_LOCALES_SHERLOCK.items():
        if nombre in sitios:
            sitios[nombre] = {**sitios[nombre], **ajustes, "headers": {**sitios[nombre].get("headers", {}), **ajustes.get("headers", {})}}
    _cacheSitiosSherlock.update(sitios=sitios, origen=origen, expira=ahora + CACHE_SITIOS_SEGUNDOS)
    return sitios, origen


def _interpolar(plantilla, usuario):
    """Sustituye el '{}' de las reglas de Sherlock por el usuario, tambien dentro de dicts y listas."""
    if isinstance(plantilla, str):
        return plantilla.replace("{}", usuario)
    if isinstance(plantilla, dict):
        return {clave: _interpolar(valor, usuario) for clave, valor in plantilla.items()}
    if isinstance(plantilla, list):
        return [_interpolar(valor, usuario) for valor in plantilla]
    return plantilla


def evaluarRespuestaSherlock(reglas, codigoEstado, texto):
    """True si, segun las reglas del sitio, la respuesta corresponde a un perfil existente.

    Es la misma logica que Sherlock: por mensaje de error en el HTML, por codigo de estado o por
    redireccion (si redirige, el perfil no existe). Separada de la peticion para poder probarla.
    """
    tipos = reglas["errorType"]
    if isinstance(tipos, str):
        tipos = [tipos]
    if any(tipo not in ("message", "status_code", "response_url") for tipo in tipos):
        raise ValueError(f"Tipo de deteccion desconocido: {tipos}")

    # varios tipos a la vez se combinan como en Sherlock: basta con que uno diga que no existe
    if "message" in tipos:
        mensajes = reglas.get("errorMsg", [])
        if isinstance(mensajes, str):
            mensajes = [mensajes]
        if any(mensaje in texto for mensaje in mensajes):
            return False
    if "status_code" in tipos:
        codigosError = reglas.get("errorCode")
        if isinstance(codigosError, int):
            codigosError = [codigosError]
        if codigosError and codigoEstado in codigosError:
            return False
        if not 200 <= codigoEstado < 300:
            return False
    if "response_url" in tipos and not 200 <= codigoEstado < 300:
        return False
    return True


def _comprobarSitioSherlock(cliente, nombre, reglas, usuario):
    urlPerfil = _interpolar(reglas["url"], usuario)
    resultado = {"sitio": nombre, "url": urlPerfil}

    expresion = reglas.get("regexCheck")
    if expresion and not re.match(expresion, usuario):
        return {**resultado, "estado": "no aplica", "detalle": "el sitio no admite ese formato de usuario"}

    porRedireccion = reglas["errorType"] == "response_url"
    metodo = reglas.get("request_method")
    if metodo:
        # Sherlock ignora urlProbe cuando la regla fija el metodo; se imita para que las reglas
        # se comporten igual que en el original
        urlPrueba = urlPerfil
    else:
        # con solo el codigo de estado basta un HEAD: no hace falta descargar el perfil entero
        metodo = "HEAD" if reglas["errorType"] == "status_code" else "GET"
        urlPrueba = _interpolar(reglas.get("urlProbe", reglas["url"]), usuario)
    cabeceras = {"User-Agent": USER_AGENT_SHERLOCK, **reglas.get("headers", {})}
    try:
        respuesta = cliente.request(
            metodo,
            urlPrueba,
            headers=cabeceras,
            json=_interpolar(reglas.get("request_payload"), usuario),
            # si el sitio redirige a los usuarios inexistentes, seguir la redireccion lo ocultaria
            follow_redirects=not porRedireccion,
        )
    except httpx.HTTPError as error:
        return {**resultado, "estado": "error", "detalle": type(error).__name__}

    texto = respuesta.text if metodo != "HEAD" else ""
    # un 403/429 o una pagina de desafio del WAF hablan de nosotros, no del usuario: Sherlock
    # los daria por perfil existente cuando la deteccion es por mensaje, y son falsos positivos
    if any(huella in texto for huella in HUELLAS_WAF) or (respuesta.status_code in CODIGOS_BLOQUEO and reglas["errorType"] != "status_code"):
        return {**resultado, "estado": "bloqueado", "detalle": f"HTTP {respuesta.status_code}"}

    encontrado = evaluarRespuestaSherlock(reglas, respuesta.status_code, texto)
    return {**resultado, "estado": "encontrado" if encontrado else "libre", "detalle": f"HTTP {respuesta.status_code}"}


def buscarUsuario(usuario, alcance="populares"):
    usuario = (usuario or "").strip()
    alcance = (alcance or "populares").strip().lower()
    if not usuario:
        raise ValueError("Indica un nombre de usuario")
    if not EXPRESION_USUARIO.match(usuario):
        raise ValueError("Usuario invalido: letras, numeros y . _ @ - (maximo 64 caracteres)")
    if alcance not in ALCANCES_SHERLOCK:
        raise ValueError(f"Alcance no soportado: {alcance}")

    sitios, origen = _cargarSitiosSherlock()
    if alcance == "populares":
        seleccion = {nombre: sitios[nombre] for nombre in SITIOS_POPULARES if nombre in sitios}
    elif alcance == "todos":
        seleccion = {nombre: reglas for nombre, reglas in sitios.items() if not reglas.get("isNSFW")}
    else:
        seleccion = dict(sitios)

    inicio = time.time()
    # un unico cliente para todos los hilos: reutiliza conexiones y es seguro compartirlo
    with httpx.Client(timeout=TIMEOUT_SHERLOCK_SEGUNDOS) as cliente:
        with concurrent.futures.ThreadPoolExecutor(max_workers=HILOS_SHERLOCK) as ejecutor:
            resultados = list(ejecutor.map(
                lambda entrada: _comprobarSitioSherlock(cliente, entrada[0], entrada[1], usuario),
                seleccion.items(),
            ))

    def sitiosCon(estado):
        return sorted((r["sitio"] for r in resultados if r["estado"] == estado), key=str.lower)

    perfiles = [{"sitio": r["sitio"], "url": r["url"]} for r in resultados if r["estado"] == "encontrado"]
    return {
        "usuario": usuario,
        "alcance": alcance,
        "sitiosComprobados": len(resultados),
        "encontrados": len(perfiles),
        "perfiles": sorted(perfiles, key=lambda perfil: perfil["sitio"].lower()),
        "libres": len(sitiosCon("libre")),
        "sitiosQueNosBloquean": ", ".join(sitiosCon("bloqueado")),
        "sitiosSinRespuesta": ", ".join(sitiosCon("error")),
        "sitiosQueNoAdmitenEseUsuario": ", ".join(sitiosCon("no aplica")),
        "duracionSegundos": round(time.time() - inicio, 1),
        "origenListaSitios": origen,
    }


# --- comprobar email (holehe) -------------------------------------------------------------

# estos modulos de holehe averiguan si el email existe pidiendo un restablecimiento de
# contrasena, y el sitio le manda un correo al dueno de la cuenta. Es lo que holehe excluye con
# --no-password-recovery; aqui se excluyen siempre para que la consulta no deje rastro
MODULOS_HOLEHE_EXCLUIDOS = ("adobe", "mail_ru", "odnoklassniki", "samsung")
TIMEOUT_HOLEHE_SEGUNDOS = 10
_modulosHolehe = None


def _cargarModulosHolehe():
    # importar los 120 modulos tarda: se hace una vez y se guarda
    global _modulosHolehe
    if _modulosHolehe is None:
        funciones = get_functions(import_submodules("holehe.modules"))
        _modulosHolehe = [funcion for funcion in funciones if funcion.__name__ not in MODULOS_HOLEHE_EXCLUIDOS]
    return _modulosHolehe


def comprobarEmail(email):
    email = (email or "").strip().lower()
    if not email:
        raise ValueError("Indica un email")
    if not EXPRESION_EMAIL.match(email):
        raise ValueError("Email invalido")

    modulos = _cargarModulosHolehe()

    async def lanzarTodos():
        salida = []
        async with httpx.AsyncClient(timeout=TIMEOUT_HOLEHE_SEGUNDOS) as cliente:
            async with trio.open_nursery() as nursery:
                for modulo in modulos:
                    # launch_module captura las excepciones del modulo y las anota como rateLimit
                    nursery.start_soon(launch_module, modulo, email, cliente, salida)
        return salida

    inicio = time.time()
    # holehe esta escrito sobre trio; trio.run levanta su propio bucle en el hilo de la peticion
    salida = trio.run(lanzarTodos)

    # algun modulo anota dos veces su resultado: se queda uno por sitio, el mas informativo
    porSitio = {}
    for resultado in salida:
        previo = porSitio.get(resultado.get("name"))
        if previo is None or (resultado.get("exists") and not previo.get("exists")) or (previo.get("rateLimit") and not resultado.get("rateLimit")):
            porSitio[resultado.get("name")] = resultado

    cuentas = []
    sinRespuesta = []
    for resultado in porSitio.values():
        if resultado.get("exists"):
            cuentas.append({
                "sitio": resultado.get("name"),
                "dominio": resultado.get("domain"),
                "emailRecuperacion": resultado.get("emailrecovery"),
                "telefono": resultado.get("phoneNumber"),
                "otros": json.dumps(resultado["others"], ensure_ascii=False) if resultado.get("others") else None,
            })
        elif resultado.get("rateLimit"):
            sinRespuesta.append(resultado.get("name"))

    return {
        "email": email,
        "sitiosComprobados": len(modulos),
        "registradoEn": len(cuentas),
        "cuentas": sorted(cuentas, key=lambda cuenta: cuenta["sitio"]),
        "noRegistrado": len(porSitio) - len(cuentas) - len(sinRespuesta),
        "sinRespuesta": len(sinRespuesta),
        "sitiosSinRespuesta": ", ".join(sorted(nombre for nombre in sinRespuesta if nombre)),
        "sitiosExcluidos": ", ".join(MODULOS_HOLEHE_EXCLUIDOS),
        "duracionSegundos": round(time.time() - inicio, 1),
    }


# --- cabeceras HTTP -----------------------------------------------------------------------

CABECERAS_SEGURIDAD = {
    "strict-transport-security": "Obliga al navegador a usar HTTPS en visitas posteriores",
    "content-security-policy": "Limita de donde se cargan scripts y recursos (mitiga XSS)",
    "x-frame-options": "Impide incrustar la pagina en un iframe (clickjacking)",
    "x-content-type-options": "Evita que el navegador adivine el tipo de contenido (nosniff)",
    "referrer-policy": "Controla que URL se envia como Referer a otros sitios",
    "permissions-policy": "Restringe camara, microfono, geolocalizacion y otras APIs",
}

# cabeceras que delatan servidor, framework o CDN
CABECERAS_TECNOLOGIA = ("server", "x-powered-by", "x-generator", "via", "x-aspnet-version", "x-aspnetmvc-version", "x-drupal-cache", "x-shopify-stage")
PISTAS_TECNOLOGIA = {
    "cf-ray": "Cloudflare", "cf-cache-status": "Cloudflare", "x-vercel-id": "Vercel", "x-github-request-id": "GitHub Pages",
    "x-amz-cf-id": "Amazon CloudFront", "x-served-by": "Fastly/Varnish", "x-varnish": "Varnish", "x-akamai-transformed": "Akamai",
    "x-nf-request-id": "Netlify", "x-wix-request-id": "Wix", "x-shopify-stage": "Shopify", "x-sucuri-id": "Sucuri",
}
COOKIES_TECNOLOGIA = {
    "phpsessid": "PHP", "jsessionid": "Java", "asp.net_sessionid": "ASP.NET", "csrftoken": "Django",
    "laravel_session": "Laravel", "xsrf-token": "Laravel/Angular", "_rails_session": "Ruby on Rails",
    "wordpress_test_cookie": "WordPress", "connect.sid": "Express (Node.js)", "ci_session": "CodeIgniter",
}


def _analizarCookie(cabeceraSetCookie):
    partes = [parte.strip() for parte in cabeceraSetCookie.split(";")]
    nombre = partes[0].split("=", 1)[0]
    atributos = {parte.split("=", 1)[0].lower(): parte for parte in partes[1:]}
    sameSite = atributos.get("samesite")
    return {
        "nombre": nombre,
        "secure": "secure" in atributos,
        "httpOnly": "httponly" in atributos,
        "sameSite": sameSite.split("=", 1)[1] if sameSite and "=" in sameSite else None,
    }


def analizarCabecerasHttp(url):
    url = _normalizarUrl(url)
    respuesta, _ = _descargar(url)

    cabeceras = {}
    for clave, valor in respuesta.headers.multi_items():
        clave = clave.lower()
        cabeceras[clave] = f"{cabeceras[clave]}\n{valor}" if clave in cabeceras else valor

    tecnologias = [f"{clave}: {cabeceras[clave]}" for clave in CABECERAS_TECNOLOGIA if clave in cabeceras]
    tecnologias += [pista for clave, pista in PISTAS_TECNOLOGIA.items() if clave in cabeceras]
    cookies = [_analizarCookie(valor) for valor in respuesta.headers.get_list("set-cookie")]
    tecnologias += [pista for cookie in cookies for nombre, pista in COOKIES_TECNOLOGIA.items() if cookie["nombre"].lower() == nombre]

    seguridad = [
        {"cabecera": nombre, "presente": nombre in cabeceras, "valor": cabeceras.get(nombre), "paraQueSirve": descripcion}
        for nombre, descripcion in CABECERAS_SEGURIDAD.items()
    ]
    return {
        "url": url,
        "urlFinal": str(respuesta.url),
        "codigoEstado": respuesta.status_code,
        "redirecciones": [{"codigo": previa.status_code, "de": str(previa.url), "a": previa.headers.get("location")} for previa in respuesta.history],
        "tecnologiasDetectadas": sorted(set(tecnologias)),
        "cabecerasSeguridadPresentes": sum(1 for entrada in seguridad if entrada["presente"]),
        "cabecerasSeguridad": seguridad,
        "cookies": cookies,
        "cabeceras": dict(sorted(cabeceras.items())),
    }


# --- escaner de puertos -------------------------------------------------------------------

PUERTOS_COMUNES = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns", 80: "http", 110: "pop3", 111: "rpcbind",
    135: "msrpc", 139: "netbios-ssn", 143: "imap", 389: "ldap", 443: "https", 445: "smb", 465: "smtps",
    587: "submission", 631: "ipp", 636: "ldaps", 873: "rsync", 993: "imaps", 995: "pop3s", 1080: "socks",
    1433: "mssql", 1521: "oracle", 1723: "pptp", 1883: "mqtt", 2049: "nfs", 2375: "docker", 2376: "docker-tls",
    3000: "http-alt", 3128: "squid", 3306: "mysql", 3389: "rdp", 5000: "http-alt", 5432: "postgresql",
    5672: "amqp", 5900: "vnc", 5985: "winrm", 6379: "redis", 8000: "http-alt", 8080: "http-proxy",
    8443: "https-alt", 8888: "http-alt", 9000: "http-alt", 9090: "http-alt", 9200: "elasticsearch",
    11211: "memcached", 27017: "mongodb",
}
MAX_PUERTOS_ESCANEO = 1024
HILOS_ESCANEO = 100
TIMEOUT_PUERTO_SEGUNDOS = 1.0


def parsearPuertos(texto):
    """'22, 80, 8000-8100' -> lista ordenada de puertos; vacio -> los comunes."""
    texto = (texto or "").strip()
    if not texto:
        return sorted(PUERTOS_COMUNES)

    puertos = set()
    for trozo in texto.split(","):
        trozo = trozo.strip()
        if not trozo:
            continue
        inicio, separador, fin = trozo.partition("-")
        try:
            desde = int(inicio)
            hasta = int(fin) if separador else desde
        except ValueError:
            raise ValueError(f"Puerto invalido: '{trozo}'")
        if not (1 <= desde <= hasta <= 65535):
            raise ValueError(f"Rango de puertos invalido: '{trozo}'")
        puertos.update(range(desde, hasta + 1))
        if len(puertos) > MAX_PUERTOS_ESCANEO:
            raise ValueError(f"Demasiados puertos: el maximo por escaneo es {MAX_PUERTOS_ESCANEO}")
    if not puertos:
        raise ValueError("Indica algun puerto")
    return sorted(puertos)


def _nombreServicio(puerto):
    if puerto in PUERTOS_COMUNES:
        return PUERTOS_COMUNES[puerto]
    try:
        return socket.getservbyport(puerto, "tcp")
    except OSError:
        return None


def escanearPuertos(host, puertos=""):
    host = (host or "").strip()
    if not host:
        raise ValueError("Indica un host o una IP")
    lista = parsearPuertos(puertos)

    try:
        familia, _, _, _, direccion = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)[0]
    except socket.gaierror:
        raise ValueError(f"No se pudo resolver el host '{host}'")
    ip = direccion[0]

    def probar(puerto):
        # connect_ex devuelve un codigo de error en vez de lanzar: 0 significa que aceptaron la conexion
        with socket.socket(familia, socket.SOCK_STREAM) as conexion:
            conexion.settimeout(TIMEOUT_PUERTO_SEGUNDOS)
            return puerto, conexion.connect_ex((ip, puerto)) == 0

    inicio = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=HILOS_ESCANEO) as ejecutor:
        resultados = list(ejecutor.map(probar, lista))

    abiertos = [{"puerto": puerto, "servicio": _nombreServicio(puerto)} for puerto, abierto in resultados if abierto]
    return {
        "host": host,
        "ip": ip,
        "puertosEscaneados": len(lista),
        "abiertos": len(abiertos),
        "puertosAbiertos": abiertos,
        "duracionSegundos": round(time.time() - inicio, 1),
    }


# --- transferencia de zona (AXFR) ---------------------------------------------------------

MAX_REGISTROS_ZONA = 500


def comprobarTransferenciaZona(dominio):
    dominio = (dominio or "").strip().lower().rstrip(".")
    if not dominio:
        raise ValueError("Indica un dominio")

    try:
        respuestasNs = dns.resolver.resolve(dominio, "NS")
    except dns.resolver.NXDOMAIN:
        raise ValueError("El dominio no existe")
    except dns.resolver.NoAnswer:
        raise ValueError("El dominio no tiene registros NS (no es una zona)")
    except dns.exception.DNSException as error:
        raise ValueError(f"Error DNS: {error}")

    servidores = []
    registros = []
    for respuesta in respuestasNs:
        servidor = respuesta.to_text().rstrip(".")
        entrada = {"servidor": servidor, "ip": None, "transferenciaPermitida": False, "detalle": None}
        try:
            entrada["ip"] = dns.resolver.resolve(servidor, "A")[0].to_text()
        except dns.exception.DNSException as error:
            entrada["detalle"] = f"no se pudo resolver: {error}"
            servidores.append(entrada)
            continue

        try:
            zona = dns.zone.from_xfr(dns.query.xfr(entrada["ip"], dominio, timeout=Config.osintTimeoutSegundos, lifetime=Config.osintTimeoutSegundos))
        except Exception as error:
            # un servidor bien configurado rechaza la peticion (REFUSED), corta la conexion o no
            # responde; cualquiera de las tres significa que la zona no se puede copiar
            entrada["detalle"] = f"rechazada ({type(error).__name__})"
            servidores.append(entrada)
            continue

        entrada["transferenciaPermitida"] = True
        entrada["detalle"] = f"{sum(1 for _ in zona.iterate_rdatas())} registros"
        servidores.append(entrada)
        if not registros:
            for nombre, ttl, dato in zona.iterate_rdatas():
                registros.append({"nombre": f"{nombre}.{dominio}" if str(nombre) != "@" else dominio, "tipo": dns.rdatatype.to_text(dato.rdtype), "valor": dato.to_text()})
                if len(registros) >= MAX_REGISTROS_ZONA:
                    break

    return {
        "dominio": dominio,
        "vulnerable": any(entrada["transferenciaPermitida"] for entrada in servidores),
        "servidoresNombre": servidores,
        "registrosObtenidos": len(registros),
        "registros": registros,
    }


# --- Wayback Machine ----------------------------------------------------------------------

URL_CDX_WAYBACK = "https://web.archive.org/cdx/search/cdx"
# el indice CDX tarda varios segundos en responder incluso a consultas pequenas
TIMEOUT_WAYBACK_SEGUNDOS = 30
ULTIMAS_CAPTURAS = 20


def _consultarCdx(url, **parametros):
    consulta = urllib.parse.urlencode({"url": url, "output": "json", "fl": "timestamp,original,statuscode,mimetype", **parametros})
    peticion = urllib.request.Request(f"{URL_CDX_WAYBACK}?{consulta}", headers={"User-Agent": USER_AGENT_NAVEGADOR})
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT_WAYBACK_SEGUNDOS) as respuesta:
            filas = json.loads(respuesta.read().decode("utf-8") or "[]")
    except Exception as error:
        raise ValueError(f"No se pudo consultar la Wayback Machine: {error}")
    # la primera fila es la cabecera con los nombres de campo
    return [_capturaWayback(fila) for fila in filas[1:]]


def _capturaWayback(fila):
    marca, original, codigo, tipo = fila
    return {
        "fecha": f"{marca[0:4]}-{marca[4:6]}-{marca[6:8]} {marca[8:10]}:{marca[10:12]}:{marca[12:14]}",
        "codigo": codigo,
        "tipo": tipo,
        "url": f"https://web.archive.org/web/{marca}/{original}",
    }


def consultarWayback(url):
    url = _normalizarUrl(url)
    # dos consultas acotadas (la primera captura y las N ultimas): pedir el historico entero de
    # un sitio grande, aunque sea agrupado por anos, tarda minutos o directamente no responde
    primeras = _consultarCdx(url, limit=1)
    if not primeras:
        return {"url": url, "archivada": False, "primeraCaptura": None, "ultimaCaptura": None, "ultimasCapturas": []}
    ultimas = _consultarCdx(url, limit=-ULTIMAS_CAPTURAS)

    return {
        "url": url,
        "archivada": True,
        "primeraCaptura": primeras[0],
        "ultimaCaptura": ultimas[-1] if ultimas else primeras[0],
        "ultimasCapturas": list(reversed(ultimas)),
    }


# --- extraer datos de una pagina ----------------------------------------------------------

DOMINIOS_REDES_SOCIALES = (
    "facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com", "youtube.com", "tiktok.com",
    "github.com", "gitlab.com", "t.me", "telegram.me", "wa.me", "whatsapp.com", "discord.gg", "discord.com",
    "pinterest.com", "reddit.com", "threads.net", "bsky.app", "mastodon.social", "twitch.tv", "medium.com",
    "vimeo.com", "flickr.com", "tumblr.com", "snapchat.com", "spotify.com", "soundcloud.com", "patreon.com",
)
MAX_ELEMENTOS_EXTRAIDOS = 200


def _dominioDe(url):
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _esRedSocial(host):
    return any(host == dominio or host.endswith("." + dominio) for dominio in DOMINIOS_REDES_SOCIALES)


def extraerDatosPagina(url):
    url = _normalizarUrl(url)
    respuesta, cuerpo = _descargar(url)
    urlFinal = str(respuesta.url)
    html = _decodificar(respuesta, cuerpo)
    soup = BeautifulSoup(html, "html.parser")

    def meta(nombre):
        etiqueta = soup.find("meta", attrs={"name": nombre}) or soup.find("meta", attrs={"property": nombre})
        return etiqueta.get("content", "").strip() if etiqueta else None

    dominioBase = _dominioDe(urlFinal)
    emails = set(EXPRESION_EMAILS_EN_TEXTO.findall(html))
    telefonos = set()
    internos, externos, redesSociales = set(), set(), set()
    for enlace in soup.find_all("a", href=True):
        href = enlace["href"].strip()
        if href.startswith("mailto:"):
            emails.add(href[7:].split("?", 1)[0])
            continue
        if href.startswith("tel:"):
            telefonos.add(href[4:])
            continue
        absoluta = urllib.parse.urljoin(urlFinal, href)
        if not absoluta.startswith(("http://", "https://")):
            continue
        host = _dominioDe(absoluta)
        if _esRedSocial(host):
            redesSociales.add(absoluta.split("#", 1)[0])
        elif host == dominioBase:
            internos.add(absoluta)
        else:
            externos.add(host)

    scripts = {_dominioDe(script["src"]) for script in soup.find_all("script", src=True) if "://" in script["src"] or script["src"].startswith("//")}
    scripts.discard(dominioBase)
    comentarios = [texto.strip() for texto in soup.find_all(string=lambda nodo: isinstance(nodo, Comment))]

    return {
        "url": urlFinal,
        "titulo": soup.title.get_text(strip=True) if soup.title else None,
        "descripcion": meta("description") or meta("og:description"),
        "generador": meta("generator"),
        "idioma": (soup.html.get("lang") if soup.html else None) or None,
        "emails": sorted(emails)[:MAX_ELEMENTOS_EXTRAIDOS],
        "telefonos": sorted(telefonos)[:MAX_ELEMENTOS_EXTRAIDOS],
        "redesSociales": sorted(redesSociales)[:MAX_ELEMENTOS_EXTRAIDOS],
        "enlacesInternos": len(internos),
        "dominiosExternos": sorted(externos - scripts)[:MAX_ELEMENTOS_EXTRAIDOS],
        "scriptsExternos": sorted(scripts)[:MAX_ELEMENTOS_EXTRAIDOS],
        "comentariosHtml": [comentario[:300] for comentario in comentarios if comentario][:20],
    }


# --- robots.txt y sitemap -----------------------------------------------------------------

MAX_SITEMAPS_LEIDOS = 5
MAX_URLS_SITEMAP = 200


def parsearRobots(texto):
    """Reglas de un robots.txt agrupadas por User-agent, mas las lineas Sitemap sueltas."""
    grupos = []
    sitemaps = []
    grupoActual = None
    for linea in texto.splitlines():
        linea = linea.split("#", 1)[0].strip()
        if not linea or ":" not in linea:
            continue
        directiva, _, valor = linea.partition(":")
        directiva, valor = directiva.strip().lower(), valor.strip()
        if directiva == "sitemap":
            sitemaps.append(valor)
        elif directiva == "user-agent":
            # varios User-agent seguidos comparten el mismo bloque de reglas
            if grupoActual is None or grupoActual["disallow"] or grupoActual["allow"]:
                grupoActual = {"agentes": [], "disallow": [], "allow": []}
                grupos.append(grupoActual)
            grupoActual["agentes"].append(valor)
        elif directiva in ("disallow", "allow") and grupoActual is not None:
            grupoActual[directiva].append(valor)
    return grupos, sitemaps


def _leerSitemap(url, leidos, urls, pendientes):
    try:
        respuesta, cuerpo = _descargar(url)
        if respuesta.status_code != 200:
            leidos.append({"sitemap": url, "leido": False, "urls": 0, "detalle": f"HTTP {respuesta.status_code}"})
            return
        # los sitemaps grandes se publican como .xml.gz
        if cuerpo[:2] == b"\x1f\x8b":
            cuerpo = gzip.decompress(cuerpo)
        raiz = ElementTree.fromstring(cuerpo)
    except (ValueError, OSError, ElementTree.ParseError) as error:
        leidos.append({"sitemap": url, "leido": False, "urls": 0, "detalle": f"no es un sitemap valido ({str(error)[:80]})"})
        return

    # los sitemaps llevan el namespace en cada etiqueta: se mira solo el nombre local
    etiquetaRaiz = raiz.tag.rsplit("}", 1)[-1]
    locs = [nodo.text.strip() for nodo in raiz.iter() if nodo.tag.rsplit("}", 1)[-1] == "loc" and nodo.text]
    if etiquetaRaiz == "sitemapindex":
        pendientes.extend(locs)
        leidos.append({"sitemap": url, "leido": True, "urls": 0, "detalle": f"indice con {len(locs)} sitemaps"})
    else:
        urls.extend(locs)
        leidos.append({"sitemap": url, "leido": True, "urls": len(locs), "detalle": None})


def analizarRobotsSitemap(url):
    url = _normalizarUrl(url)
    partes = urllib.parse.urlsplit(url)
    base = f"{partes.scheme}://{partes.netloc}"

    urlRobots = f"{base}/robots.txt"
    respuesta, cuerpo = _descargar(urlRobots)
    existe = respuesta.status_code == 200 and "text/html" not in respuesta.headers.get("content-type", "")
    grupos, sitemaps = parsearRobots(_decodificar(respuesta, cuerpo)) if existe else ([], [])

    # copia: la cola se va vaciando y los declarados tienen que salir enteros en la respuesta
    pendientes = list(sitemaps) or [f"{base}/sitemap.xml"]
    leidos, urls = [], []
    while pendientes and len(leidos) < MAX_SITEMAPS_LEIDOS:
        _leerSitemap(pendientes.pop(0), leidos, urls, pendientes)

    return {
        "sitio": base,
        "robots": {
            "url": urlRobots,
            "existe": existe,
            "codigoEstado": respuesta.status_code,
            "rutasBloqueadas": sum(len(grupo["disallow"]) for grupo in grupos),
            "reglas": [{"userAgent": ", ".join(grupo["agentes"]), "disallow": "\n".join(grupo["disallow"]), "allow": "\n".join(grupo["allow"])} for grupo in grupos],
            "sitemapsDeclarados": sitemaps,
        },
        "sitemap": {
            "urlsEncontradas": len(urls),
            "sitemapsLeidos": leidos,
            "sitemapsPendientes": len(pendientes),
            "urls": urls[:MAX_URLS_SITEMAP],
        },
    }
