import base64
import datetime
import glob
import http.client
import io
import ipaddress
import os
import random
import re
import secrets
import socket
import ssl
import tempfile
import urllib.parse

import qrcode
import yt_dlp
from PIL import Image
from pyzbar import pyzbar

FORMATOS_CLAVE_API = ("hex", "base64", "urlsafe")

# Descargador de video/audio: limitado a webs conocidas de video/streaming para evitar
# que el extractor generico de yt-dlp se use como vector de SSRF contra IPs internas.
DOMINIOS_DESCARGA_PERMITIDOS = (
    "youtube.com", "youtu.be", "twitter.com", "x.com", "tiktok.com",
    "instagram.com", "facebook.com", "vimeo.com", "twitch.tv", "reddit.com",
    "soundcloud.com", "dailymotion.com",
)

FORMATOS_DESCARGA_PERMITIDOS = ("mp4", "mp3")
CALIDADES_VIDEO_DESCARGA = ("mejor", "1080p", "720p", "480p", "360p")
CALIDADES_AUDIO_DESCARGA = ("320kbps", "192kbps", "128kbps")

TIMEOUT_DESCARGA_MEDIA_SEGUNDOS = 120
TAMANO_MAXIMO_DESCARGA_MEDIA_BYTES = 200 * 1024 * 1024

# InternetDownloader: proteccion SSRF. Solo esquemas web, sin seguir redirecciones ciegamente,
# resolucion de IP validada justo antes de conectar (evita rebinding DNS) y limites de tamano/tiempo
ESQUEMAS_DESCARGA_PERMITIDOS = ("http", "https")
TAMANO_MAXIMO_DESCARGA_BYTES = 100 * 1024 * 1024
TIMEOUT_CONEXION_DESCARGA_SEGUNDOS = 5
TIMEOUT_LECTURA_DESCARGA_SEGUNDOS = 15
MAX_REDIRECCIONES_DESCARGA = 2
TAMANO_CHUNK_DESCARGA_BYTES = 65536

RANGOS_BLOQUEADOS_IPV4 = ("127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16")
RANGOS_BLOQUEADOS_IPV6 = ("::1/128", "fc00::/7")
UNIDADES_LONGITUD = {"m": 1, "km": 1000, "cm": 0.01, "mm": 0.001, "mi": 1609.344, "yd": 0.9144, "ft": 0.3048, "in": 0.0254}
UNIDADES_PESO = {"kg": 1, "g": 0.001, "mg": 0.000001, "lb": 0.45359237, "oz": 0.028349523125, "t": 1000}
UNIDADES_DATOS = {"b": 1 / 8, "byte": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3, "tb": 1024**4}
CATEGORIAS_UNIDADES = {"longitud": UNIDADES_LONGITUD, "peso": UNIDADES_PESO, "datos": UNIDADES_DATOS}


def timestampAFecha(timestampUnix):
    try:
        timestampUnix = float(timestampUnix)
    except (TypeError, ValueError):
        raise ValueError("Timestamp invalido")
    try:
        fecha = datetime.datetime.fromtimestamp(timestampUnix, tz=datetime.timezone.utc)
    except (OverflowError, OSError, ValueError) as error:
        raise ValueError(f"Timestamp fuera de rango: {error}")
    return {"timestampUnix": timestampUnix, "fechaIso": fecha.isoformat()}


def fechaATimestamp(fechaIso):
    fechaIso = fechaIso.strip()
    if not fechaIso:
        raise ValueError("Indica una fecha en formato ISO 8601")
    try:
        fecha = datetime.datetime.fromisoformat(fechaIso)
    except ValueError as error:
        raise ValueError(f"Fecha invalida: {error}")
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=datetime.timezone.utc)
    return {"fechaIso": fecha.isoformat(), "timestampUnix": fecha.timestamp()}


def convertirUnixTime(valor, unidad):
    unidad = unidad.lower()
    if unidad not in ("segundos", "milisegundos"):
        raise ValueError(f"Unidad no soportada: {unidad}")

    if valor is None or str(valor).strip() == "":
        segundos = datetime.datetime.now(datetime.timezone.utc).timestamp()
    else:
        try:
            valorNumerico = float(valor)
        except ValueError:
            raise ValueError("Valor invalido")
        segundos = valorNumerico / 1000 if unidad == "milisegundos" else valorNumerico

    try:
        fecha = datetime.datetime.fromtimestamp(segundos, tz=datetime.timezone.utc)
    except (OverflowError, OSError, ValueError) as error:
        raise ValueError(f"Valor fuera de rango: {error}")

    return {"segundos": segundos, "milisegundos": segundos * 1000, "fechaIso": fecha.isoformat()}


def _convertirTemperatura(valor, origen, destino):
    unidadesValidas = ("c", "f", "k")
    if origen not in unidadesValidas or destino not in unidadesValidas:
        raise ValueError("Unidades de temperatura validas: c (Celsius), f (Fahrenheit), k (Kelvin)")

    if origen == "c":
        celsius = valor
    elif origen == "f":
        celsius = (valor - 32) * 5 / 9
    else:
        celsius = valor - 273.15

    if destino == "c":
        resultado = celsius
    elif destino == "f":
        resultado = celsius * 9 / 5 + 32
    else:
        resultado = celsius + 273.15

    return {"categoria": "temperatura", "valor": valor, "unidadOrigen": origen, "unidadDestino": destino, "resultado": resultado}


def convertirUnidades(categoria, valor, unidadOrigen, unidadDestino):
    categoria = categoria.strip().lower()
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        raise ValueError("Valor invalido")
    unidadOrigen = unidadOrigen.strip().lower()
    unidadDestino = unidadDestino.strip().lower()

    if categoria == "temperatura":
        return _convertirTemperatura(valor, unidadOrigen, unidadDestino)

    factores = CATEGORIAS_UNIDADES.get(categoria)
    if factores is None:
        categoriasValidas = ", ".join(list(CATEGORIAS_UNIDADES.keys()) + ["temperatura"])
        raise ValueError(f"Categoria no soportada: {categoria}. Categorias validas: {categoriasValidas}")
    if unidadOrigen not in factores or unidadDestino not in factores:
        raise ValueError(f"Unidad no soportada para {categoria}. Unidades validas: {', '.join(factores.keys())}")

    valorBase = valor * factores[unidadOrigen]
    resultado = valorBase / factores[unidadDestino]
    return {"categoria": categoria, "valor": valor, "unidadOrigen": unidadOrigen, "unidadDestino": unidadDestino, "resultado": resultado}


def generarClaveApi(longitudBytes, formato):
    formato = formato.lower()
    if formato not in FORMATOS_CLAVE_API:
        raise ValueError(f"Formato no soportado: {formato}")
    try:
        longitudBytes = int(longitudBytes)
    except (TypeError, ValueError):
        raise ValueError("Longitud invalida")
    if not (8 <= longitudBytes <= 128):
        raise ValueError("La longitud debe estar entre 8 y 128 bytes")

    claveBytes = secrets.token_bytes(longitudBytes)
    if formato == "hex":
        clave = claveBytes.hex()
    elif formato == "base64":
        clave = base64.b64encode(claveBytes).decode("ascii")
    else:
        clave = base64.urlsafe_b64encode(claveBytes).decode("ascii").rstrip("=")

    return {"longitudBytes": longitudBytes, "formato": formato, "claveApi": clave}


def _esIpBloqueada(direccionIp):
    rangosBloqueados = RANGOS_BLOQUEADOS_IPV4 if direccionIp.version == 4 else RANGOS_BLOQUEADOS_IPV6
    if any(direccionIp in ipaddress.ip_network(rango) for rango in rangosBloqueados):
        return True
    # defensa en profundidad adicional a la lista explicita de rangos anterior
    return (
        direccionIp.is_private
        or direccionIp.is_loopback
        or direccionIp.is_link_local
        or direccionIp.is_reserved
        or direccionIp.is_multicast
        or direccionIp.is_unspecified
    )


def _resolverIpSegura(host):
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as error:
        raise ValueError(f"No se pudo resolver el host: {error}")

    ipsResueltas = []
    for info in infos:
        direccionTexto = info[4][0].split("%")[0]
        try:
            ipsResueltas.append(ipaddress.ip_address(direccionTexto))
        except ValueError:
            continue
    if not ipsResueltas:
        raise ValueError("No se pudo resolver el host a una direccion IP")

    # se rechazan todas las IPs si cualquiera de las resueltas es privada/reservada
    for direccionIp in ipsResueltas:
        if _esIpBloqueada(direccionIp):
            raise ValueError(f"El host resuelve a una direccion IP no permitida: {direccionIp}")

    return ipsResueltas[0]


def _conectarSocketSeguro(host, puerto, esHttps):
    # se resuelve y valida la IP justo antes de conectar, y se conecta directamente a esa IP
    # (en vez de dejar que la libreria HTTP vuelva a resolver el host) para evitar DNS rebinding
    direccionIp = _resolverIpSegura(host)
    try:
        sock = socket.create_connection((str(direccionIp), puerto), timeout=TIMEOUT_CONEXION_DESCARGA_SEGUNDOS)
    except OSError as error:
        raise ValueError(f"No se pudo conectar: {error}")
    sock.settimeout(TIMEOUT_LECTURA_DESCARGA_SEGUNDOS)
    if esHttps:
        try:
            contexto = ssl.create_default_context()
            sock = contexto.wrap_socket(sock, server_hostname=host)
        except ssl.SSLError as error:
            sock.close()
            raise ValueError(f"Error TLS: {error}")
    return sock


def _descargarUnaVez(url):
    partes = urllib.parse.urlparse(url)
    if partes.scheme not in ESQUEMAS_DESCARGA_PERMITIDOS:
        raise ValueError(f"Esquema no permitido: {partes.scheme or '(vacio)'}. Solo se permiten http y https")
    host = partes.hostname
    if not host:
        raise ValueError("La URL no tiene un host valido")
    try:
        puerto = partes.port or (443 if partes.scheme == "https" else 80)
    except ValueError as error:
        raise ValueError(f"Puerto invalido en la URL: {error}")

    ruta = partes.path or "/"
    if partes.query:
        ruta += f"?{partes.query}"

    sock = _conectarSocketSeguro(host, puerto, partes.scheme == "https")
    conexion = http.client.HTTPConnection(host, puerto, timeout=TIMEOUT_LECTURA_DESCARGA_SEGUNDOS)
    conexion.sock = sock
    try:
        conexion.request(
            "GET", ruta, headers={"Host": host, "User-Agent": "WebTools-InternetDownloader/1.0", "Accept-Encoding": "identity"}
        )
        respuesta = conexion.getresponse()

        if respuesta.status in (301, 302, 303, 307, 308):
            ubicacion = respuesta.headers.get("Location")
            if not ubicacion:
                raise ValueError("Redireccion sin cabecera Location")
            return None, urllib.parse.urljoin(url, ubicacion)

        if respuesta.status != 200:
            raise ValueError(f"El servidor respondio con estado {respuesta.status}")

        longitudDeclarada = respuesta.headers.get("Content-Length")
        if longitudDeclarada and int(longitudDeclarada) > TAMANO_MAXIMO_DESCARGA_BYTES:
            raise ValueError(f"El archivo supera el limite maximo de {TAMANO_MAXIMO_DESCARGA_BYTES} bytes")

        contenido = bytearray()
        while True:
            trozo = respuesta.read(TAMANO_CHUNK_DESCARGA_BYTES)
            if not trozo:
                break
            contenido.extend(trozo)
            if len(contenido) > TAMANO_MAXIMO_DESCARGA_BYTES:
                raise ValueError(f"El archivo supera el limite maximo de {TAMANO_MAXIMO_DESCARGA_BYTES} bytes")

        tipoContenido = respuesta.headers.get("Content-Type", "application/octet-stream")
        resultado = {"urlFinal": url, "tipoContenido": tipoContenido, "tamanoBytes": len(contenido), "contenido": bytes(contenido)}
        return resultado, None
    except (OSError, ssl.SSLError, http.client.HTTPException, TimeoutError) as error:
        raise ValueError(f"No se pudo completar la descarga: {error}")
    finally:
        conexion.close()


def descargarUrlSegura(url):
    url = (url or "").strip()
    if not url:
        raise ValueError("Indica una URL")

    urlActual = url
    for _intento in range(MAX_REDIRECCIONES_DESCARGA + 1):
        resultado, urlRedirigida = _descargarUnaVez(urlActual)
        if resultado is not None:
            return resultado
        urlActual = urlRedirigida

    raise ValueError("Se supero el numero maximo de redirecciones permitidas")


def generarQr(texto):
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("Indica un texto o URL para generar el codigo QR")

    imagen = qrcode.make(texto)
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    return buffer.getvalue()


def leerQr(imagenBytes):
    if not imagenBytes:
        raise ValueError("El archivo esta vacio")
    try:
        imagen = Image.open(io.BytesIO(imagenBytes))
        imagen.load()
    except Exception as error:
        raise ValueError(f"No se pudo leer la imagen: {error}")

    codigosEncontrados = pyzbar.decode(imagen)
    codigos = [codigo.data.decode("utf-8", errors="replace") for codigo in codigosEncontrados]
    return {"encontrados": len(codigos), "codigos": codigos}


PALABRAS_LOREM_IPSUM = (
    "lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing", "elit", "sed", "do",
    "eiusmod", "tempor", "incididunt", "ut", "labore", "et", "dolore", "magna", "aliqua", "enim",
    "ad", "minim", "veniam", "quis", "nostrud", "exercitation", "ullamco", "laboris", "nisi", "aliquip",
    "ex", "ea", "commodo", "consequat", "duis", "aute", "irure", "in", "reprehenderit", "voluptate",
    "velit", "esse", "cillum", "eu", "fugiat", "nulla", "pariatur", "excepteur", "sint", "occaecat",
    "cupidatat", "non", "proident", "sunt", "culpa", "qui", "officia", "deserunt", "mollit", "anim",
    "id", "est", "laborum",
)


def _generarFraseLorem(numPalabras):
    palabras = [random.choice(PALABRAS_LOREM_IPSUM) for _ in range(numPalabras)]
    frase = " ".join(palabras)
    return frase[0].upper() + frase[1:] + "."


def generarLoremIpsum(numParrafos, numFrasesPorParrafo):
    try:
        numParrafos = int(numParrafos)
        numFrasesPorParrafo = int(numFrasesPorParrafo)
    except (TypeError, ValueError):
        raise ValueError("Numero de parrafos o frases invalido")
    if not (1 <= numParrafos <= 20):
        raise ValueError("El numero de parrafos debe estar entre 1 y 20")
    if not (1 <= numFrasesPorParrafo <= 20):
        raise ValueError("El numero de frases por parrafo debe estar entre 1 y 20")

    parrafos = []
    for indiceParrafo in range(numParrafos):
        frases = []
        if indiceParrafo == 0:
            frases.append("Lorem ipsum dolor sit amet, consectetur adipiscing elit.")
            frasesRestantes = numFrasesPorParrafo - 1
        else:
            frasesRestantes = numFrasesPorParrafo
        frases += [_generarFraseLorem(random.randint(6, 14)) for _ in range(frasesRestantes)]
        parrafos.append(" ".join(frases))

    return {"parrafos": parrafos, "texto": "\n\n".join(parrafos)}


NOMBRES_MASCULINOS = (
    "Alejandro", "Carlos", "Daniel", "Diego", "Eduardo", "Fernando", "Gabriel", "Hugo", "Ivan", "Javier",
    "Luis", "Manuel", "Mario", "Miguel", "Pablo", "Rafael", "Ruben", "Sergio", "Tomas", "Victor",
)
NOMBRES_FEMENINOS = (
    "Alicia", "Beatriz", "Carla", "Diana", "Elena", "Fernanda", "Gabriela", "Ines", "Julia", "Laura",
    "Maria", "Marta", "Natalia", "Paula", "Raquel", "Sara", "Sofia", "Teresa", "Valeria", "Veronica",
)
APELLIDOS = (
    "Garcia", "Fernandez", "Gonzalez", "Rodriguez", "Lopez", "Martinez", "Sanchez", "Perez", "Gomez", "Martin",
    "Jimenez", "Ruiz", "Hernandez", "Diaz", "Moreno", "Alvarez", "Romero", "Alonso", "Gutierrez", "Navarro",
)


def generarNombresAleatorios(cantidad, genero):
    try:
        cantidad = int(cantidad)
    except (TypeError, ValueError):
        raise ValueError("Cantidad invalida")
    if not (1 <= cantidad <= 50):
        raise ValueError("La cantidad debe estar entre 1 y 50")

    genero = (genero or "aleatorio").lower()
    if genero not in ("masculino", "femenino", "aleatorio"):
        raise ValueError(f"Genero no soportado: {genero}")

    nombres = []
    for _ in range(cantidad):
        generoElegido = random.choice(("masculino", "femenino")) if genero == "aleatorio" else genero
        listaNombres = NOMBRES_MASCULINOS if generoElegido == "masculino" else NOMBRES_FEMENINOS
        nombres.append(f"{random.choice(listaNombres)} {random.choice(APELLIDOS)} {random.choice(APELLIDOS)}")

    return {"cantidad": cantidad, "genero": genero, "nombres": nombres}


USER_AGENTS_POR_NAVEGADOR = {
    "chrome": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
    ),
    "firefox": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0",
        "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
    ),
    "safari": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    ),
    "edge": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
    ),
}


def generarUserAgent(navegador):
    navegador = (navegador or "aleatorio").lower()
    if navegador == "aleatorio":
        todos = [userAgent for lista in USER_AGENTS_POR_NAVEGADOR.values() for userAgent in lista]
        return {"navegador": "aleatorio", "userAgent": random.choice(todos)}
    if navegador not in USER_AGENTS_POR_NAVEGADOR:
        raise ValueError(f"Navegador no soportado: {navegador}. Usa: {', '.join(USER_AGENTS_POR_NAVEGADOR.keys())} o aleatorio")
    return {"navegador": navegador, "userAgent": random.choice(USER_AGENTS_POR_NAVEGADOR[navegador])}


def _hostDescargaPermitido(host):
    host = host.lower()
    return any(host == dominio or host.endswith(f".{dominio}") for dominio in DOMINIOS_DESCARGA_PERMITIDOS)


def _validarUrlDescarga(url):
    url = (url or "").strip()
    if not url:
        raise ValueError("Indica una URL")
    partes = urllib.parse.urlparse(url)
    if partes.scheme not in ("http", "https"):
        raise ValueError("Solo se permiten URLs http/https")
    if not partes.hostname or not _hostDescargaPermitido(partes.hostname):
        raise ValueError(f"Dominio no soportado. Dominios permitidos: {', '.join(DOMINIOS_DESCARGA_PERMITIDOS)}")
    return url


def _alturaDesdeCalidadDescarga(calidad):
    if calidad and calidad.endswith("p") and calidad[:-1].isdigit():
        return int(calidad[:-1])
    return None


def _bitrateDesdeCalidadDescarga(calidad):
    if calidad and calidad.endswith("kbps") and calidad[:-4].isdigit():
        return calidad[:-4]
    return "192"


def _formatoYtDlpDescarga(calidad):
    altura = _alturaDesdeCalidadDescarga(calidad)
    if altura is None:
        return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    return f"bestvideo[ext=mp4][height<={altura}]+bestaudio[ext=m4a]/best[ext=mp4][height<={altura}]/best"


def obtenerUrlDirecta(url, calidad):
    # equivalente a: yt-dlp -g -f "best[ext=mp4]" URL
    # devuelve la URL directa del stream para abrirla en VLC sin descargar nada
    url = _validarUrlDescarga(url)
    calidad = (calidad or "mejor").strip().lower()
    altura = _alturaDesdeCalidadDescarga(calidad)
    if altura is None:
        formatoYtDlp = "best[ext=mp4]/best"
    else:
        formatoYtDlp = f"best[ext=mp4][height<={altura}]/best[height<={altura}]/best"

    opciones = {
        "format": formatoYtDlp,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": TIMEOUT_DESCARGA_MEDIA_SEGUNDOS,
    }
    try:
        with yt_dlp.YoutubeDL(opciones) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as error:
        raise ValueError(f"No se pudo obtener la URL directa: {error}")

    if not isinstance(info, dict):
        raise ValueError("No se pudo obtener informacion del video")

    # con formatos combinados (video+audio separados) yt-dlp devuelve varias URLs
    formatosSolicitados = info.get("requested_formats")
    if formatosSolicitados:
        urlsDirectas = [formato.get("url") for formato in formatosSolicitados if formato.get("url")]
    else:
        urlsDirectas = [info["url"]] if info.get("url") else []

    if not urlsDirectas:
        raise ValueError("El extractor no devolvio ninguna URL directa")

    return {
        "titulo": info.get("title", ""),
        "duracionSegundos": info.get("duration"),
        "formatoSeleccionado": info.get("format", ""),
        "extension": info.get("ext", ""),
        "calidad": calidad,
        "urlDirecta": urlsDirectas[0],
        "urlsDirectas": urlsDirectas,
    }


def descargarMedia(url, formato, calidad):
    url = _validarUrlDescarga(url)
    formato = (formato or "").strip().lower()
    if formato not in FORMATOS_DESCARGA_PERMITIDOS:
        raise ValueError(f"Formato no soportado: {formato}. Usa mp4 o mp3")
    calidad = (calidad or "mejor").strip().lower()

    with tempfile.TemporaryDirectory(prefix="webtools-media-") as directorioTemporal:
        opciones = {
            "outtmpl": os.path.join(directorioTemporal, "%(id)s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": TIMEOUT_DESCARGA_MEDIA_SEGUNDOS,
            "max_filesize": TAMANO_MAXIMO_DESCARGA_MEDIA_BYTES,
            "restrictfilenames": True,
        }
        if formato == "mp3":
            opciones["format"] = "bestaudio/best"
            opciones["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": _bitrateDesdeCalidadDescarga(calidad),
            }]
        else:
            opciones["format"] = _formatoYtDlpDescarga(calidad)
            opciones["merge_output_format"] = "mp4"
            opciones["postprocessors"] = [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}]

        try:
            with yt_dlp.YoutubeDL(opciones) as ydl:
                info = ydl.extract_info(url, download=True)
        except yt_dlp.utils.DownloadError as error:
            raise ValueError(f"No se pudo descargar: {error}")

        archivosGenerados = glob.glob(os.path.join(directorioTemporal, "*"))
        if not archivosGenerados:
            raise ValueError("La descarga no genero ningun archivo")
        rutaArchivo = max(archivosGenerados, key=os.path.getsize)

        if os.path.getsize(rutaArchivo) > TAMANO_MAXIMO_DESCARGA_MEDIA_BYTES:
            raise ValueError(f"El archivo supera el limite maximo de {TAMANO_MAXIMO_DESCARGA_MEDIA_BYTES} bytes")

        with open(rutaArchivo, "rb") as archivo:
            contenido = archivo.read()

        titulo = info.get("title", "descarga") if isinstance(info, dict) else "descarga"
        nombreArchivo = re.sub(r"[^\w\-. ]", "_", titulo).strip()[:80] or "descarga"
        extension = "mp3" if formato == "mp3" else "mp4"
        return {
            "contenido": contenido,
            "nombreArchivo": f"{nombreArchivo}.{extension}",
            "tipoContenido": "audio/mpeg" if formato == "mp3" else "video/mp4",
        }
