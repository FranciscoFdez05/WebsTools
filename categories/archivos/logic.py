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
import zlib
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


# --- esteganografia -------------------------------------------------------------------------
#
# El archivo secreto se guarda en el bit menos significativo de cada canal R, G y B de la imagen
# portadora, en orden y empezando por el primer pixel. Lo que se oculta es una cabecera fija
# (firma, version, banderas y longitud) seguida del cuerpo: el nombre original y los datos,
# comprimidos si sale a cuenta y cifrados con AES-GCM si se da una contrasena. La imagen se
# entrega siempre en PNG: cualquier formato con perdida (JPEG, WebP) reescribiria esos bits.

FIRMA_ESTEGANOGRAFIA = b"WTSG"
VERSION_ESTEGANOGRAFIA = 1
BANDERA_CIFRADO = 0x01
BANDERA_COMPRIMIDO = 0x02
# firma (4) + version (1) + banderas (1) + longitud del cuerpo (4)
TAMANO_CABECERA_ESTEGANOGRAFIA = 10
TAMANO_SAL_ESTEGANOGRAFIA = 16
TAMANO_NONCE_ESTEGANOGRAFIA = 12
LONGITUD_MAXIMA_NOMBRE_OCULTO = 255
TAMANO_MAXIMO_EXTRAIDO = 200 * 1024 * 1024

# tablas para bytes.translate: poner a cero el bit bajo de cada canal, sacar ese bit como "0"/"1"
# y pasar "0"/"1" a bytes 0/1. Asi el trabajo pesado lo hacen translate y los enteros grandes de
# Python en vez de un bucle bit a bit, que con una foto de varios megapixeles tardaria segundos
_TABLA_LIMPIAR_BIT = bytes(valor & 0xFE for valor in range(256))
_TABLA_BIT_A_ASCII = bytes(0x30 + (valor & 1) for valor in range(256))
_TABLA_ASCII_A_BIT = bytes((valor - 0x30) & 1 for valor in range(256))
_CARACTERES_PROHIBIDOS_NOMBRE = set('"<>:|?*')


def _formatearBytes(cantidad):
    if cantidad < 1024:
        return f"{cantidad} B"
    if cantidad < 1024 * 1024:
        return f"{cantidad / 1024:.1f} KB"
    return f"{cantidad / (1024 * 1024):.2f} MB"


def _derivarClaveEsteganografia(contrasena, sal):
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    return Scrypt(salt=sal, length=32, n=2**15, r=8, p=1).derive(contrasena.encode("utf-8"))


def _abrirPortadora(fileBytes):
    """Abre la imagen y la separa en canales RGB (donde va el mensaje) y alfa (que no se toca)."""
    if not fileBytes:
        raise ValueError("La imagen esta vacia")
    try:
        imagen = Image.open(io.BytesIO(fileBytes))
        imagen.load()
    except Exception:
        raise ValueError("No se pudo abrir la imagen: el archivo no es una imagen valida o el formato no esta soportado")

    tieneAlfa = imagen.mode in ("RGBA", "LA", "PA") or "transparency" in imagen.info
    imagen = imagen.convert("RGBA" if tieneAlfa else "RGB")
    if not tieneAlfa:
        return imagen, None
    return imagen.convert("RGB"), imagen.getchannel("A")


def _incrustarBits(canales, mensaje):
    totalBits = len(mensaje) * 8
    bitsAscii = format(int.from_bytes(mensaje, "big"), f"0{totalBits}b").encode("ascii")
    bits = int.from_bytes(bitsAscii.translate(_TABLA_ASCII_A_BIT), "big")
    limpios = int.from_bytes(canales[:totalBits].translate(_TABLA_LIMPIAR_BIT), "big")
    # los canales limpios son pares y cada byte de bits vale 0 o 1: el OR no arrastra entre bytes
    return (limpios | bits).to_bytes(totalBits, "big") + canales[totalBits:]


def _extraerBits(canales, desplazamiento, longitud):
    if longitud == 0:
        return b""
    tramo = canales[desplazamiento * 8:(desplazamiento + longitud) * 8]
    return int(tramo.translate(_TABLA_BIT_A_ASCII), 2).to_bytes(longitud, "big")


def _nombreSeguro(nombre):
    nombre = os.path.basename((nombre or "").replace("\\", "/"))
    nombre = "".join(caracter for caracter in nombre if caracter.isprintable() and caracter not in _CARACTERES_PROHIBIDOS_NOMBRE)
    return nombre.strip(" .")[:LONGITUD_MAXIMA_NOMBRE_OCULTO] or "archivo-extraido"


def ocultarArchivoEnImagen(imagenBytes, secretoBytes, nombreSecreto="", contrasena=""):
    """Oculta un archivo cualquiera dentro de una imagen y devuelve la imagen resultante en PNG."""
    if not secretoBytes:
        raise ValueError("El archivo a ocultar esta vacio")
    rgb, alfa = _abrirPortadora(imagenBytes)
    canales = rgb.tobytes()

    nombre = _nombreSeguro(nombreSecreto).encode("utf-8")[:LONGITUD_MAXIMA_NOMBRE_OCULTO]
    banderas = 0
    datos = secretoBytes
    comprimidos = zlib.compress(secretoBytes, 9)
    if len(comprimidos) < len(secretoBytes):
        datos = comprimidos
        banderas |= BANDERA_COMPRIMIDO

    cuerpo = len(nombre).to_bytes(2, "big") + nombre + datos
    if contrasena:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        banderas |= BANDERA_CIFRADO
        sal = os.urandom(TAMANO_SAL_ESTEGANOGRAFIA)
        nonce = os.urandom(TAMANO_NONCE_ESTEGANOGRAFIA)
        # la firma, la version y las banderas van como datos asociados: si alguien las altera
        # (por ejemplo, quita la bandera de cifrado) el descifrado falla en vez de dar basura
        asociados = FIRMA_ESTEGANOGRAFIA + bytes([VERSION_ESTEGANOGRAFIA, banderas])
        cuerpo = sal + nonce + AESGCM(_derivarClaveEsteganografia(contrasena, sal)).encrypt(nonce, cuerpo, asociados)

    mensaje = FIRMA_ESTEGANOGRAFIA + bytes([VERSION_ESTEGANOGRAFIA, banderas]) + len(cuerpo).to_bytes(4, "big") + cuerpo
    capacidad = len(canales) // 8
    if len(mensaje) > capacidad:
        raise ValueError(
            f"El archivo no cabe en la imagen: hacen falta {_formatearBytes(len(mensaje))} y la imagen "
            f"({rgb.width}x{rgb.height}) solo admite {_formatearBytes(capacidad)}. Usa una imagen mas grande"
        )

    resultado = Image.frombytes("RGB", rgb.size, _incrustarBits(canales, mensaje))
    if alfa is not None:
        resultado.putalpha(alfa)
    buffer = io.BytesIO()
    resultado.save(buffer, format="PNG")
    return buffer.getvalue()


def extraerArchivoDeImagen(imagenBytes, contrasena=""):
    """Recupera el archivo oculto con ocultarArchivoEnImagen. Devuelve (nombre, datos)."""
    rgb, _ = _abrirPortadora(imagenBytes)
    canales = rgb.tobytes()
    capacidad = len(canales) // 8

    if capacidad < TAMANO_CABECERA_ESTEGANOGRAFIA:
        raise ValueError("La imagen es demasiado pequena para contener datos ocultos")
    cabecera = _extraerBits(canales, 0, TAMANO_CABECERA_ESTEGANOGRAFIA)
    if cabecera[:4] != FIRMA_ESTEGANOGRAFIA:
        raise ValueError(
            "La imagen no contiene un archivo oculto con esta herramienta (si se convirtio a JPEG u "
            "otro formato con perdida, o se redimensiono, los datos ocultos se han perdido)"
        )
    version, banderas = cabecera[4], cabecera[5]
    if version != VERSION_ESTEGANOGRAFIA:
        raise ValueError(f"Version de datos ocultos no soportada ({version})")
    longitud = int.from_bytes(cabecera[6:10], "big")
    if longitud > capacidad - TAMANO_CABECERA_ESTEGANOGRAFIA:
        raise ValueError("Los datos ocultos estan danados: su longitud no cabe en la imagen")

    cuerpo = _extraerBits(canales, TAMANO_CABECERA_ESTEGANOGRAFIA, longitud)
    if banderas & BANDERA_CIFRADO:
        if not contrasena:
            raise ValueError("El archivo oculto esta protegido con contrasena: introducela para extraerlo")
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        sal = cuerpo[:TAMANO_SAL_ESTEGANOGRAFIA]
        nonce = cuerpo[TAMANO_SAL_ESTEGANOGRAFIA:TAMANO_SAL_ESTEGANOGRAFIA + TAMANO_NONCE_ESTEGANOGRAFIA]
        cifrado = cuerpo[TAMANO_SAL_ESTEGANOGRAFIA + TAMANO_NONCE_ESTEGANOGRAFIA:]
        try:
            cuerpo = AESGCM(_derivarClaveEsteganografia(contrasena, sal)).decrypt(nonce, cifrado, cabecera[:6])
        except (InvalidTag, ValueError):
            raise ValueError("Contrasena incorrecta o datos ocultos danados")

    if len(cuerpo) < 2:
        raise ValueError("Los datos ocultos estan danados")
    longitudNombre = int.from_bytes(cuerpo[:2], "big")
    nombre = _nombreSeguro(cuerpo[2:2 + longitudNombre].decode("utf-8", errors="replace"))
    datos = cuerpo[2 + longitudNombre:]
    if banderas & BANDERA_COMPRIMIDO:
        # con tope: una imagen preparada a mano podria llevar unos pocos KB que se inflan a GB
        descompresor = zlib.decompressobj()
        try:
            datos = descompresor.decompress(datos, TAMANO_MAXIMO_EXTRAIDO)
        except zlib.error:
            raise ValueError("Los datos ocultos estan danados: no se pudieron descomprimir")
        if descompresor.unconsumed_tail:
            raise ValueError(f"El archivo oculto supera el maximo extraible ({_formatearBytes(TAMANO_MAXIMO_EXTRAIDO)})")
    return nombre, datos
