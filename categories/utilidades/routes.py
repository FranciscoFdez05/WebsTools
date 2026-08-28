import urllib.parse

from flask import Blueprint, Response, jsonify, render_template, request

from . import logic

utilidadesBp = Blueprint("utilidades", __name__, url_prefix="/utilidades")

TOOLS = {
    "timestamp-fecha": {
        "nombre": "Conversor Timestamp <-> Fecha",
        "descripcion": "Convierte un timestamp Unix a fecha ISO 8601 y viceversa",
        "campos": [
            {"nombre": "timestampUnix", "tipo": "text", "etiqueta": "Timestamp Unix (segundos)"},
            {"nombre": "fechaIso", "tipo": "text", "etiqueta": "Fecha ISO 8601 (ej. 2026-07-29T12:00:00)"},
        ],
    },
    "unix-time": {
        "nombre": "Conversor Unix Time",
        "descripcion": "Convierte entre segundos y milisegundos Unix; en blanco usa la hora actual",
        "campos": [
            {"nombre": "valor", "tipo": "text", "etiqueta": "Valor (vacio = ahora)"},
            {"nombre": "unidad", "tipo": "select", "etiqueta": "Unidad del valor", "opciones": ["segundos", "milisegundos"]},
        ],
    },
    "conversor-unidades": {
        "nombre": "Conversor de Unidades",
        "descripcion": "Convierte valores entre unidades de longitud, peso, datos o temperatura",
        "campos": [
            {"nombre": "categoria", "tipo": "select", "etiqueta": "Categoria", "opciones": ["longitud", "peso", "datos", "temperatura"]},
            {"nombre": "valor", "tipo": "text", "etiqueta": "Valor"},
            {"nombre": "unidadOrigen", "tipo": "text", "etiqueta": "Unidad origen (ej. km, kg, gb, c)"},
            {"nombre": "unidadDestino", "tipo": "text", "etiqueta": "Unidad destino (ej. mi, lb, mb, f)"},
        ],
    },
    "generador-clave-api": {
        "nombre": "Generador de Claves API",
        "descripcion": "Genera una clave API aleatoria criptograficamente segura",
        "campos": [
            {"nombre": "longitudBytes", "tipo": "text", "etiqueta": "Longitud en bytes (8-128, por defecto 32)"},
            {"nombre": "formato", "tipo": "select", "etiqueta": "Formato", "opciones": list(logic.FORMATOS_CLAVE_API)},
        ],
    },
    "internet-downloader": {
        "nombre": "Internet Downloader",
        "descripcion": "Descarga un archivo desde una URL publica (solo http/https, IPs privadas bloqueadas)",
        "campos": [{"nombre": "url", "tipo": "text", "etiqueta": "URL (http:// o https://)"}],
    },
    "qr-generator": {
        "nombre": "QR Generator",
        "descripcion": "Genera un codigo QR a partir de un texto o URL y lo descarga como PNG",
        "campos": [{"nombre": "texto", "tipo": "textarea", "etiqueta": "Texto o URL"}],
    },
    "qr-reader": {
        "nombre": "QR Reader",
        "descripcion": "Lee el contenido de uno o varios codigos QR en una imagen",
        "campos": [{"nombre": "archivo", "tipo": "file", "etiqueta": "Imagen con codigo QR"}],
    },
    "lorem-ipsum": {
        "nombre": "Generador de Lorem Ipsum",
        "descripcion": "Genera parrafos de texto de relleno Lorem Ipsum",
        "campos": [
            {"nombre": "numParrafos", "tipo": "text", "etiqueta": "Numero de parrafos (1-20)"},
            {"nombre": "numFrasesPorParrafo", "tipo": "text", "etiqueta": "Frases por parrafo (1-20)"},
        ],
    },
    "nombres-aleatorios": {
        "nombre": "Generador de Nombres Aleatorios",
        "descripcion": "Genera nombres y apellidos aleatorios",
        "campos": [
            {"nombre": "cantidad", "tipo": "text", "etiqueta": "Cantidad (1-50)"},
            {"nombre": "genero", "tipo": "select", "etiqueta": "Genero", "opciones": ["aleatorio", "masculino", "femenino"]},
        ],
    },
    "generador-user-agent": {
        "nombre": "Generador de User-Agent",
        "descripcion": "Devuelve un User-Agent real de una lista curada por navegador",
        "campos": [
            {"nombre": "navegador", "tipo": "select", "etiqueta": "Navegador", "opciones": ["aleatorio", "chrome", "firefox", "safari", "edge"]},
        ],
    },
    "descargador-video": {
        "nombre": "Descargador de Video/Audio",
        "descripcion": "Descarga video (MP4) o audio (MP3) desde YouTube, Twitter/X, TikTok y otras webs compatibles",
        "campos": [
            {"nombre": "url", "tipo": "text", "etiqueta": "URL del video"},
            {"nombre": "formato", "tipo": "select", "etiqueta": "Formato", "opciones": list(logic.FORMATOS_DESCARGA_PERMITIDOS)},
            {
                "nombre": "calidad",
                "tipo": "select",
                "etiqueta": "Calidad (video: resolucion, audio: bitrate)",
                "opciones": list(logic.CALIDADES_VIDEO_DESCARGA) + list(logic.CALIDADES_AUDIO_DESCARGA),
            },
        ],
    },
    "url-directa-video": {
        "nombre": "URL Directa de Video (VLC)",
        "descripcion": "Devuelve la URL directa del stream para abrirla en VLC u otro reproductor, sin descargar el archivo",
        "campos": [
            {"nombre": "url", "tipo": "text", "etiqueta": "URL del video"},
            {
                "nombre": "calidad",
                "tipo": "select",
                "etiqueta": "Calidad (resolucion maxima)",
                "opciones": list(logic.CALIDADES_VIDEO_DESCARGA),
            },
        ],
    },
}


@utilidadesBp.route("/")
def index():
    return render_template("categoria.html", categoriaSlug="utilidades", categoriaNombre="Utilidades", tools=TOOLS)


@utilidadesBp.route("/<toolSlug>")
def herramienta(toolSlug):
    tool = TOOLS.get(toolSlug)
    if tool is None:
        return render_template("categoria.html", categoriaSlug="utilidades", categoriaNombre="Utilidades", tools=TOOLS), 404
    return render_template("herramienta.html", categoriaSlug="utilidades", toolSlug=toolSlug, tool=tool)


@utilidadesBp.route("/api/timestamp-fecha", methods=["POST"])
def apiTimestampFecha():
    datos = request.get_json(silent=True) or request.form
    try:
        if datos.get("timestampUnix"):
            return jsonify(logic.timestampAFecha(datos.get("timestampUnix")))
        if datos.get("fechaIso"):
            return jsonify(logic.fechaATimestamp(datos.get("fechaIso")))
        return jsonify({"error": "Indica un timestamp o una fecha ISO 8601"}), 400
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@utilidadesBp.route("/api/unix-time", methods=["POST"])
def apiUnixTime():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.convertirUnixTime(datos.get("valor"), datos.get("unidad", "segundos")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@utilidadesBp.route("/api/conversor-unidades", methods=["POST"])
def apiConversorUnidades():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.convertirUnidades(
            datos.get("categoria", ""), datos.get("valor", ""), datos.get("unidadOrigen", ""), datos.get("unidadDestino", "")
        ))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@utilidadesBp.route("/api/generador-clave-api", methods=["POST"])
def apiGeneradorClaveApi():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.generarClaveApi(datos.get("longitudBytes") or 32, datos.get("formato", "hex")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@utilidadesBp.route("/api/internet-downloader", methods=["POST"])
def apiInternetDownloader():
    datos = request.get_json(silent=True) or request.form
    try:
        resultado = logic.descargarUrlSegura(datos.get("url", ""))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    rutaUrl = urllib.parse.urlparse(resultado["urlFinal"]).path
    nombreArchivo = rutaUrl.rsplit("/", 1)[-1] or "descarga"
    return Response(
        resultado["contenido"],
        mimetype=resultado["tipoContenido"] or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{nombreArchivo}"'},
    )


@utilidadesBp.route("/api/qr-generator", methods=["POST"])
def apiQrGenerator():
    datos = request.get_json(silent=True) or request.form
    try:
        imagenPng = logic.generarQr(datos.get("texto", ""))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return Response(imagenPng, mimetype="image/png", headers={"Content-Disposition": 'attachment; filename="qr.png"'})


@utilidadesBp.route("/api/qr-reader", methods=["POST"])
def apiQrReader():
    archivo = request.files.get("archivo")
    if archivo is None:
        return jsonify({"error": "Falta el archivo"}), 400
    try:
        return jsonify(logic.leerQr(archivo.read()))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@utilidadesBp.route("/api/lorem-ipsum", methods=["POST"])
def apiLoremIpsum():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.generarLoremIpsum(datos.get("numParrafos", 3), datos.get("numFrasesPorParrafo", 5)))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@utilidadesBp.route("/api/nombres-aleatorios", methods=["POST"])
def apiNombresAleatorios():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.generarNombresAleatorios(datos.get("cantidad", 5), datos.get("genero", "aleatorio")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@utilidadesBp.route("/api/generador-user-agent", methods=["POST"])
def apiGeneradorUserAgent():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.generarUserAgent(datos.get("navegador", "aleatorio")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@utilidadesBp.route("/api/url-directa-video", methods=["POST"])
def apiUrlDirectaVideo():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.obtenerUrlDirecta(datos.get("url", ""), datos.get("calidad", "mejor")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@utilidadesBp.route("/api/descargador-video", methods=["POST"])
def apiDescargadorVideo():
    datos = request.get_json(silent=True) or request.form
    try:
        resultado = logic.descargarMedia(datos.get("url", ""), datos.get("formato", "mp4"), datos.get("calidad", "mejor"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return Response(
        resultado["contenido"],
        mimetype=resultado["tipoContenido"],
        headers={"Content-Disposition": f'attachment; filename="{resultado["nombreArchivo"]}"'},
    )
