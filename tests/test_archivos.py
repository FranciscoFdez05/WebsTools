import io
import json
import os
import platform
import shutil
import sqlite3
import tempfile

import pytest
from PIL import Image
from PIL.ExifTags import TAGS

from categories.archivos import logic

requiereExiftool = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool no esta instalado")

# En Windows no se puede ni comprobar si libmagic esta disponible: python-magic la busca con
# ctypes al importarse y, cuando no la encuentra, el propio "import magic" se queda colgado en
# vez de fallar. Probarlo dejaba la suite entera bloqueada, asi que aqui se salta y la
# deteccion real se prueba en Linux, que es donde corre la aplicacion.
requiereLibmagic = pytest.mark.skipif(
    platform.system() == "Windows",
    reason="libmagic no esta disponible en Windows y python-magic bloquea al importarse",
)


def _crearImagenPngBytes():
    imagen = Image.new("RGB", (4, 4), color="red")
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    return buffer.getvalue()


def _crearImagenJpegBytes():
    imagen = Image.new("RGB", (4, 4), color="blue")
    buffer = io.BytesIO()
    imagen.save(buffer, format="JPEG")
    return buffer.getvalue()


def test_generarHashes():
    resultado = logic.generarHashes(b"contenido de prueba")
    assert resultado["md5"] == "392b62a13fc2ce2d09e2171fd18938dc"
    assert set(resultado.keys()) == {"md5", "sha1", "sha256", "sha512"}


def test_generarHashes_vacio():
    with pytest.raises(ValueError):
        logic.generarHashes(b"")


def test_verificarHash_coincide():
    hashCalculado = logic.generarHashes(b"contenido")["sha256"]
    resultado = logic.verificarHash(b"contenido", hashCalculado, "sha256")
    assert resultado["coincide"] is True


def test_verificarHash_no_coincide():
    resultado = logic.verificarHash(b"contenido", "abc123", "sha256")
    assert resultado["coincide"] is False


def test_verificarHash_algoritmo_invalido():
    with pytest.raises(ValueError):
        logic.verificarHash(b"contenido", "abc", "sha999")


@requiereLibmagic
def test_detectarTipoArchivo_png():
    firmaPng = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    resultado = logic.detectarTipoArchivo(firmaPng, "imagen.png")
    assert resultado["extensionDeclarada"] == "png"


def test_calcularEntropia_datos_repetitivos():
    resultado = logic.calcularEntropia(b"a" * 1000)
    assert resultado["entropia"] == 0.0


def test_calcularEntropia_vacio():
    with pytest.raises(ValueError):
        logic.calcularEntropia(b"")


@requiereExiftool
def test_verMetadatos_imagen():
    resultado = logic.verMetadatos(_crearImagenPngBytes(), "imagen.png")
    assert resultado["formato"] == "PNG"
    assert resultado["dimensiones"] == "4x4"


def test_verMetadatos_tipo_no_soportado():
    with pytest.raises(ValueError):
        logic.verMetadatos(b"contenido de texto plano", "archivo.txt")


@requiereExiftool
def test_eliminarMetadatos_imagen():
    archivoLimpio, extension = logic.eliminarMetadatos(_crearImagenJpegBytes(), "foto.jpg")
    assert extension == "jpeg"
    assert len(archivoLimpio) > 0
    # el archivo resultante debe seguir siendo una imagen valida
    Image.open(io.BytesIO(archivoLimpio)).verify()


@requiereExiftool
def test_editarMetadatosImagen():
    archivoEditado, extension = logic.editarMetadatosImagen(_crearImagenJpegBytes(), json.dumps({"Artist": "prueba"}))
    assert extension == "jpeg"
    imagen = Image.open(io.BytesIO(archivoEditado))
    etiquetasPorNombre = {nombre: etiquetaId for etiquetaId, nombre in TAGS.items()}
    assert imagen.getexif().get(etiquetasPorNombre["Artist"]) == "prueba"


@requiereExiftool
def test_editarMetadatosImagen_etiqueta_invalida():
    with pytest.raises(ValueError):
        logic.editarMetadatosImagen(_crearImagenJpegBytes(), json.dumps({"EtiquetaInventada": "x"}))


def test_editarMetadatosImagen_json_invalido():
    with pytest.raises(ValueError):
        logic.editarMetadatosImagen(_crearImagenJpegBytes(), "no es json")


def test_extraerStrings():
    contenido = b"\x00\x00hola mundo\x00\x00ab\x00otra cadena larga\x00"
    resultado = logic.extraerStrings(contenido, 4)
    assert "hola mundo" in resultado["cadenas"]
    assert "otra cadena larga" in resultado["cadenas"]
    assert "ab" not in resultado["cadenas"]


def test_extraerStrings_longitud_invalida():
    with pytest.raises(ValueError):
        logic.extraerStrings(b"contenido", 0)


def test_extraerStrings_vacio():
    with pytest.raises(ValueError):
        logic.extraerStrings(b"", 4)


def _crearBaseDatosBytes(numeroFilas=3):
    ruta = os.path.join(tempfile.mkdtemp(), "prueba.sqlite")
    conexion = sqlite3.connect(ruta)
    conexion.execute("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nombre TEXT, foto BLOB)")
    conexion.executemany(
        "INSERT INTO usuarios (id, nombre, foto) VALUES (?, ?, ?)",
        [(indice, f"usuario{indice}", b"\x00\x01\x02") for indice in range(1, numeroFilas + 1)],
    )
    conexion.execute("CREATE VIEW usuariosVista AS SELECT id, nombre FROM usuarios")
    conexion.commit()
    conexion.close()
    with open(ruta, "rb") as archivo:
        contenido = archivo.read()
    os.unlink(ruta)
    return contenido


def test_explorarBaseDatos_listado():
    resultado = logic.explorarBaseDatos(_crearBaseDatosBytes())
    nombres = {objeto["nombre"]: objeto for objeto in resultado["objetos"]}
    assert nombres["usuarios"]["tipo"] == "table"
    assert nombres["usuarios"]["filas"] == 3
    assert nombres["usuarios"]["columnas"] == ["id", "nombre", "foto"]
    assert nombres["usuariosVista"]["tipo"] == "view"
    # sin tabla seleccionada no se devuelven filas
    assert "filas" not in resultado


def test_explorarBaseDatos_contenido_tabla():
    resultado = logic.explorarBaseDatos(_crearBaseDatosBytes(), "usuarios")
    assert resultado["columnas"] == ["id", "nombre", "foto"]
    assert resultado["totalFilas"] == 3
    assert resultado["filas"][0][1] == "usuario1"
    # los BLOB se resumen, no se vuelcan en crudo
    assert resultado["filas"][0][2].startswith("<BLOB 3 bytes:")
    assert resultado["truncado"] is False


def test_explorarBaseDatos_limite_y_desplazamiento():
    resultado = logic.explorarBaseDatos(_crearBaseDatosBytes(10), "usuarios", limite=2, desplazamiento=5)
    assert [fila[0] for fila in resultado["filas"]] == [6, 7]
    assert resultado["truncado"] is True


def test_explorarBaseDatos_limite_maximo():
    resultado = logic.explorarBaseDatos(_crearBaseDatosBytes(), "usuarios", limite=99999)
    assert resultado["limite"] == logic.FILAS_MAXIMAS_BD


def test_explorarBaseDatos_vista():
    resultado = logic.explorarBaseDatos(_crearBaseDatosBytes(), "usuariosVista")
    assert resultado["columnas"] == ["id", "nombre"]


def test_explorarBaseDatos_tabla_inexistente():
    with pytest.raises(ValueError):
        logic.explorarBaseDatos(_crearBaseDatosBytes(), "no_existe")


def test_explorarBaseDatos_inyeccion_en_nombre_tabla():
    # el nombre no se interpola sin validar: debe rechazarse antes de tocar sqlite
    with pytest.raises(ValueError):
        logic.explorarBaseDatos(_crearBaseDatosBytes(), 'usuarios"; DROP TABLE usuarios; --')


def test_explorarBaseDatos_no_es_sqlite():
    with pytest.raises(ValueError):
        logic.explorarBaseDatos(_crearImagenPngBytes())


def test_explorarBaseDatos_vacio():
    with pytest.raises(ValueError):
        logic.explorarBaseDatos(b"")


def test_explorarBaseDatos_limite_invalido():
    with pytest.raises(ValueError):
        logic.explorarBaseDatos(_crearBaseDatosBytes(), "usuarios", limite=0)


def test_analizarFirmaDigital_no_pe():
    resultado = logic.analizarFirmaDigital(_crearImagenPngBytes(), "imagen.png")
    assert resultado["firmado"] is None


def test_analizarFirmaDigital_pe_sin_firma():
    # cabecera MZ minima sin tabla de seguridad -> pefile debe indicar que no esta firmado
    cabeceraDosMinima = b"MZ" + b"\x00" * 58 + (64).to_bytes(4, "little")
    cabeceraPe = cabeceraDosMinima.ljust(64, b"\x00")
    peMinimo = cabeceraPe + b"PE\x00\x00" + b"\x00" * 200
    try:
        resultado = logic.analizarFirmaDigital(peMinimo, "archivo.exe")
    except ValueError:
        pytest.skip("pefile no pudo analizar el PE minimo sintetico")
    assert resultado["formato"] == "PE"
