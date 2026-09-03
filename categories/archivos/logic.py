import hashlib
import io
import json
import math
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import tempfile
from collections import Counter

from PIL import Image

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

ALGORITMOS_HASH = ("md5", "sha1", "sha256", "sha512")
LONGITUD_MAXIMA_STRINGS = 500
TIMEOUT_EXIFTOOL_SEGUNDOS = 10

FIRMA_SQLITE = b"SQLite format 3\x00"
FILAS_MAXIMAS_BD = 200
FILAS_POR_DEFECTO_BD = 50
LONGITUD_MAXIMA_CELDA = 500
BYTES_PREVIA_BLOB = 32


def _exiftoolDisponible():
    return shutil.which("exiftool") is not None


def _ejecutarExiftool(argumentos):
    if not _exiftoolDisponible():
        raise ValueError(
            "exiftool no esta disponible en el servidor; es necesario para procesar metadatos de imagenes "
            "(en Windows suele no estar instalado, ver advertencia de arranque)"
        )
    try:
        return subprocess.run(["exiftool", *argumentos], capture_output=True, timeout=TIMEOUT_EXIFTOOL_SEGUNDOS, check=False)
    except subprocess.TimeoutExpired:
        raise ValueError("exiftool tardo demasiado en procesar el archivo")


def _extensionImagen(imagen, nombreDeclarado=""):
    if imagen.format:
        return imagen.format.lower()
    if "." in nombreDeclarado:
        return nombreDeclarado.rsplit(".", 1)[-1].lower()
    return "jpg"


def generarHashes(fileBytes):
    if not fileBytes:
        raise ValueError("El archivo esta vacio")
    resultado = {}
    for algoritmo in ALGORITMOS_HASH:
        hasher = hashlib.new(algoritmo)
        hasher.update(fileBytes)
        resultado[algoritmo] = hasher.hexdigest()
    return resultado


def verificarHash(fileBytes, hashEsperado, algoritmo):
    algoritmo = algoritmo.lower()
    if algoritmo not in ALGORITMOS_HASH:
        raise ValueError(f"Algoritmo no soportado: {algoritmo}")
    if not fileBytes:
        raise ValueError("El archivo esta vacio")
    hasher = hashlib.new(algoritmo)
    hasher.update(fileBytes)
    hashCalculado = hasher.hexdigest()
    coincide = hashCalculado.lower() == hashEsperado.strip().lower()
    return {"algoritmo": algoritmo, "hashCalculado": hashCalculado, "hashEsperado": hashEsperado, "coincide": coincide}


def _cargarMagic():
    """El modulo magic, o None si aqui no se puede usar.

    En Windows, python-magic busca libmagic con ctypes nada mas importarse y, cuando no la
    encuentra, el propio "import magic" se queda colgado en vez de fallar: colgaba la
    herramienta, y con ella el hilo que atendia la peticion. Alli se va directo a la deteccion
    por cabecera, salvo que se pida lo contrario con WEBTOOLS_USAR_LIBMAGIC=1 para quien si la
    tenga instalada. En Linux, que es donde corre la aplicacion, no cambia nada.
    """
    if platform.system() == "Windows" and os.environ.get("WEBTOOLS_USAR_LIBMAGIC", "") not in ("1", "true"):
        return None
    try:
        import magic
        return magic
    except Exception:
        # tampoco solo ImportError: con libmagic instalada pero rota o de otra arquitectura,
        # python-magic revienta con OSError al cargarla por ctypes
        return None


def detectarTipoArchivo(fileBytes, nombreDeclarado=""):
    if not fileBytes:
        raise ValueError("El archivo esta vacio")

    magic = _cargarMagic()
    if magic is None:
        mimeType, descripcion = _detectarTipoPorCabecera(fileBytes)
    else:
        mimeType = magic.from_buffer(fileBytes, mime=True)
        descripcion = magic.from_buffer(fileBytes)

    extensionDeclarada = nombreDeclarado.rsplit(".", 1)[-1].lower() if "." in nombreDeclarado else ""
    return {
        "mimeType": mimeType,
        "descripcion": descripcion,
        "extensionDeclarada": extensionDeclarada or None,
    }


def _detectarTipoPorCabecera(fileBytes):
    firmas = {
        b"\x89PNG\r\n\x1a\n": ("image/png", "Imagen PNG"),
        b"\xff\xd8\xff": ("image/jpeg", "Imagen JPEG"),
        b"GIF87a": ("image/gif", "Imagen GIF"),
        b"GIF89a": ("image/gif", "Imagen GIF"),
        b"%PDF": ("application/pdf", "Documento PDF"),
        b"PK\x03\x04": ("application/zip", "Archivo ZIP u OOXML"),
        b"MZ": ("application/x-msdownload", "Ejecutable Windows PE"),
        b"\x7fELF": ("application/x-elf", "Ejecutable ELF"),
    }
    for firma, (mimeType, descripcion) in firmas.items():
        if fileBytes.startswith(firma):
            return mimeType, descripcion
    return "application/octet-stream", "Tipo desconocido (libmagic no disponible)"


def calcularEntropia(fileBytes):
    if not fileBytes:
        raise ValueError("El archivo esta vacio")
    longitud = len(fileBytes)
    contador = Counter(fileBytes)
    entropia = 0.0
    for cuenta in contador.values():
        probabilidad = cuenta / longitud
        entropia -= probabilidad * math.log2(probabilidad)

    if entropia > 7.5:
        interpretacion = "Muy alta: probablemente cifrado o comprimido"
    elif entropia > 6.5:
        interpretacion = "Alta: posible compresion o empaquetado"
    elif entropia > 4.0:
        interpretacion = "Media: datos mixtos o texto con estructura"
    else:
        interpretacion = "Baja: datos muy repetitivos o texto plano"

    return {"entropia": round(entropia, 4), "tamanoBytes": longitud, "interpretacion": interpretacion}


def verMetadatos(fileBytes, nombreDeclarado=""):
    if not fileBytes:
        raise ValueError("El archivo esta vacio")
    mimeType = detectarTipoArchivo(fileBytes, nombreDeclarado)["mimeType"]
    if mimeType.startswith("image/"):
        return _verMetadatosImagen(fileBytes, nombreDeclarado)
    if mimeType == "application/pdf":
        return _verMetadatosPdf(fileBytes)
    raise ValueError(f"Tipo de archivo no soportado para metadatos: {mimeType}")


def _verMetadatosImagen(fileBytes, nombreDeclarado=""):
    try:
        imagen = Image.open(io.BytesIO(fileBytes))
        imagen.load()
    except Exception as error:
        raise ValueError(f"No se pudo leer la imagen: {error}")

    extension = _extensionImagen(imagen, nombreDeclarado)
    with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as temporal:
        temporal.write(fileBytes)
        rutaTemporal = temporal.name
    try:
        resultado = _ejecutarExiftool(["-json", "-G0:1", rutaTemporal])
        if resultado.returncode != 0:
            raise ValueError(f"exiftool no pudo leer los metadatos: {resultado.stderr.decode(errors='replace').strip()}")
        metadatos = json.loads(resultado.stdout.decode(errors="replace"))[0]
        metadatos.pop("SourceFile", None)
    finally:
        os.unlink(rutaTemporal)

    return {"formato": imagen.format, "dimensiones": f"{imagen.width}x{imagen.height}", "modo": imagen.mode, "metadatos": metadatos}


def _verMetadatosPdf(fileBytes):
    if PdfReader is None:
        raise ValueError("Soporte de PDF no disponible en el servidor")
    try:
        lector = PdfReader(io.BytesIO(fileBytes))
    except Exception as error:
        raise ValueError(f"No se pudo leer el PDF: {error}")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporal:
        temporal.write(fileBytes)
        rutaTemporal = temporal.name
    try:
        resultado = _ejecutarExiftool(["-json", "-G0:1", rutaTemporal])
        if resultado.returncode != 0:
            raise ValueError(f"exiftool no pudo leer los metadatos: {resultado.stderr.decode(errors='replace').strip()}")
        metadatos = json.loads(resultado.stdout.decode(errors="replace"))[0]
        metadatos.pop("SourceFile", None)
    finally:
        os.unlink(rutaTemporal)

    return {"numPaginas": len(lector.pages), "metadatos": metadatos}


def eliminarMetadatos(fileBytes, nombreDeclarado=""):
    if not fileBytes:
        raise ValueError("El archivo esta vacio")
    mimeType = detectarTipoArchivo(fileBytes, nombreDeclarado)["mimeType"]
    if mimeType.startswith("image/"):
        return _eliminarMetadatosImagen(fileBytes, nombreDeclarado)
    if mimeType == "application/pdf":
        return _eliminarMetadatosPdf(fileBytes)
    raise ValueError(f"Tipo de archivo no soportado para eliminar metadatos: {mimeType}")


def _eliminarMetadatosImagen(fileBytes, nombreDeclarado=""):
    try:
        imagen = Image.open(io.BytesIO(fileBytes))
        imagen.load()
    except Exception as error:
        raise ValueError(f"No se pudo leer la imagen: {error}")

    extension = _extensionImagen(imagen, nombreDeclarado)
    with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as temporal:
        temporal.write(fileBytes)
        rutaTemporal = temporal.name
    try:
        resultado = _ejecutarExiftool(["-all=", "-overwrite_original", rutaTemporal])
        if resultado.returncode != 0:
            raise ValueError(f"exiftool no pudo eliminar los metadatos: {resultado.stderr.decode(errors='replace').strip()}")
        with open(rutaTemporal, "rb") as archivoLimpio:
            contenido = archivoLimpio.read()
    finally:
        os.unlink(rutaTemporal)
    return contenido, extension


def _eliminarMetadatosPdf(fileBytes):
    # exiftool -all= limpia tambien el XMP embebido, no solo el diccionario /Info;
    # dejar el XMP intacto (como hacia el enfoque anterior basado solo en pypdf)
    # es una fuga de privacidad ya que ahi tambien puede haber autor, software, fechas, etc.
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporal:
        temporal.write(fileBytes)
        rutaTemporal = temporal.name
    try:
        resultado = _ejecutarExiftool(["-all=", "-overwrite_original", rutaTemporal])
        if resultado.returncode != 0:
            raise ValueError(f"exiftool no pudo eliminar los metadatos: {resultado.stderr.decode(errors='replace').strip()}")
        with open(rutaTemporal, "rb") as archivoLimpio:
            contenido = archivoLimpio.read()
    finally:
        os.unlink(rutaTemporal)
    return contenido, "pdf"


def editarMetadatosImagen(fileBytes, metadatosJson, nombreDeclarado=""):
    if not fileBytes:
        raise ValueError("El archivo esta vacio")
    try:
        cambios = json.loads(metadatosJson) if metadatosJson else {}
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON de metadatos invalido: {error}")
    if not isinstance(cambios, dict) or not cambios:
        raise ValueError("Los metadatos deben ser un objeto JSON de etiqueta:valor, ej. {\"Artist\": \"nombre\"}")

    try:
        imagen = Image.open(io.BytesIO(fileBytes))
        imagen.load()
    except Exception as error:
        raise ValueError(f"No se pudo leer la imagen: {error}")

    extension = _extensionImagen(imagen, nombreDeclarado)
    with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as temporal:
        temporal.write(fileBytes)
        rutaTemporal = temporal.name
    try:
        argumentosEtiquetas = [f"-{etiqueta}={valor}" for etiqueta, valor in cambios.items()]
        resultado = _ejecutarExiftool([*argumentosEtiquetas, "-overwrite_original", rutaTemporal])
        if resultado.returncode != 0:
            raise ValueError(f"exiftool no pudo editar los metadatos: {resultado.stderr.decode(errors='replace').strip()}")
        with open(rutaTemporal, "rb") as archivoEditado:
            contenido = archivoEditado.read()
    finally:
        os.unlink(rutaTemporal)
    return contenido, extension


def extraerStrings(fileBytes, longitudMinima=4):
    if not fileBytes:
        raise ValueError("El archivo esta vacio")
    try:
        longitudMinima = int(longitudMinima)
    except (TypeError, ValueError):
        raise ValueError("Longitud minima invalida")
    if longitudMinima < 1:
        raise ValueError("La longitud minima debe ser mayor que 0")

    patron = re.compile(rb"[\x20-\x7e]{%d,}" % longitudMinima)
    encontradas = [coincidencia.decode("ascii") for coincidencia in patron.findall(fileBytes)]
    return {
        "totalEncontradas": len(encontradas),
        "cadenas": encontradas[:LONGITUD_MAXIMA_STRINGS],
        "truncado": len(encontradas) > LONGITUD_MAXIMA_STRINGS,
    }


def _formatearCelda(valor):
    if isinstance(valor, (bytes, bytearray)):
        previa = bytes(valor[:BYTES_PREVIA_BLOB]).hex()
        return f"<BLOB {len(valor)} bytes: {previa}{'...' if len(valor) > BYTES_PREVIA_BLOB else ''}>"
    if isinstance(valor, str) and len(valor) > LONGITUD_MAXIMA_CELDA:
        return valor[:LONGITUD_MAXIMA_CELDA] + "..."
    return valor


def _abrirBaseDatosSoloLectura(rutaTemporal):
    # mode=ro evita cualquier escritura y immutable=1 evita que sqlite intente crear
    # ficheros -wal/-journal junto al temporal o recuperar el diario de una BD copiada
    uri = f"file:{rutaTemporal}?mode=ro&immutable=1"
    conexion = sqlite3.connect(uri, uri=True, timeout=5)
    conexion.text_factory = lambda dato: dato.decode("utf-8", errors="replace")
    return conexion


def _listarObjetos(conexion):
    filas = conexion.execute(
        "SELECT name, type, sql FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()
    objetos = []
    for nombre, tipo, sql in filas:
        columnas = [columna[1] for columna in conexion.execute(f'PRAGMA table_info("{nombre}")').fetchall()]
        try:
            filasTotales = conexion.execute(f'SELECT COUNT(*) FROM "{nombre}"').fetchone()[0]
        except sqlite3.Error:
            # una vista puede depender de funciones o tablas ausentes; no debe romper el listado
            filasTotales = None
        objetos.append({"nombre": nombre, "tipo": tipo, "columnas": columnas, "filas": filasTotales, "sql": sql})
    return objetos


def explorarBaseDatos(fileBytes, tabla="", limite=FILAS_POR_DEFECTO_BD, desplazamiento=0):
    if not fileBytes:
        raise ValueError("El archivo esta vacio")
    if not fileBytes.startswith(FIRMA_SQLITE):
        raise ValueError("El archivo no es una base de datos SQLite (solo se soporta SQLite: .db, .sqlite, .sqlite3)")

    try:
        limite = int(limite) if str(limite).strip() else FILAS_POR_DEFECTO_BD
        desplazamiento = int(desplazamiento) if str(desplazamiento).strip() else 0
    except (TypeError, ValueError):
        raise ValueError("Limite o desplazamiento invalidos")
    if limite < 1:
        raise ValueError("El limite debe ser mayor que 0")
    if desplazamiento < 0:
        raise ValueError("El desplazamiento no puede ser negativo")
    limite = min(limite, FILAS_MAXIMAS_BD)

    tabla = (tabla or "").strip()
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as temporal:
        temporal.write(fileBytes)
        rutaTemporal = temporal.name
    try:
        try:
            conexion = _abrirBaseDatosSoloLectura(rutaTemporal)
        except sqlite3.Error as error:
            raise ValueError(f"No se pudo abrir la base de datos: {error}")
        try:
            objetos = _listarObjetos(conexion)
            resumen = {
                "tamanoBytes": len(fileBytes),
                "versionSqlite": sqlite3.sqlite_version,
                "objetos": objetos,
            }
            if not tabla:
                return resumen

            # solo se consultan nombres presentes en sqlite_master, nunca la entrada cruda del usuario
            nombresValidos = {objeto["nombre"] for objeto in objetos}
            if tabla not in nombresValidos:
                raise ValueError(f"La tabla o vista '{tabla}' no existe en la base de datos")

            cursor = conexion.execute(f'SELECT * FROM "{tabla}" LIMIT ? OFFSET ?', (limite, desplazamiento))
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = [[_formatearCelda(celda) for celda in fila] for fila in cursor.fetchall()]
            totalFilas = conexion.execute(f'SELECT COUNT(*) FROM "{tabla}"').fetchone()[0]
        except sqlite3.Error as error:
            raise ValueError(f"Error al leer la base de datos: {error}")
        finally:
            conexion.close()
    finally:
        os.unlink(rutaTemporal)

    return {
        **resumen,
        "tabla": tabla,
        "columnas": columnas,
        "filas": filas,
        "totalFilas": totalFilas,
        "limite": limite,
        "desplazamiento": desplazamiento,
        "truncado": desplazamiento + len(filas) < totalFilas,
    }


def analizarFirmaDigital(fileBytes, nombreDeclarado=""):
    if not fileBytes:
        raise ValueError("El archivo esta vacio")
    mimeType = detectarTipoArchivo(fileBytes, nombreDeclarado)["mimeType"]
    if not fileBytes.startswith(b"MZ"):
        return {
            "formato": mimeType,
            "firmado": None,
            "mensaje": "Solo se soporta el analisis de firmas Authenticode en ejecutables PE de Windows (ELF y Mach-O no estan soportados)",
        }

    try:
        import pefile
    except ImportError:
        raise ValueError("El soporte para analizar ejecutables PE (pefile) no esta disponible en el servidor")

    try:
        pe = pefile.PE(data=fileBytes, fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_SECURITY"]])
    except pefile.PEFormatError as error:
        raise ValueError(f"No se pudo analizar el ejecutable PE: {error}")

    # Un PE puede declarar en NumberOfRvaAndSizes menos entradas de directorio de las que hacen
    # falta para llegar a la de seguridad: pasa en ejecutables truncados o mal formados, y ahi
    # indexar a ciegas reventaba con IndexError y devolvia un 500. Sin esa entrada no hay tabla
    # de firmas, que es exactamente lo mismo que un ejecutable sin firmar.
    directorios = pe.OPTIONAL_HEADER.DATA_DIRECTORY
    indiceSeguridad = pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_SECURITY"]
    entradaSeguridad = directorios[indiceSeguridad] if indiceSeguridad < len(directorios) else None

    firmado = entradaSeguridad is not None and entradaSeguridad.VirtualAddress != 0 and entradaSeguridad.Size != 0
    resultado = {
        "formato": "PE",
        "firmado": firmado,
        "tamanoFirmaBytes": entradaSeguridad.Size if firmado else 0,
        "mensaje": (
            "Firma Authenticode presente (no se valida la cadena de confianza ni el certificado)"
            if firmado
            else "No se encontro firma Authenticode en el ejecutable"
        ),
    }
    pe.close()
    return resultado
