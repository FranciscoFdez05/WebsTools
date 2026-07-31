from flask import Blueprint, Response, jsonify, render_template, request

from . import logic

archivosBp = Blueprint("archivos", __name__, url_prefix="/archivos")

TOOLS = {
    "verificar-hash": {
        "nombre": "Verificar Hash",
        "descripcion": "Comprueba si el hash de un archivo coincide con el esperado",
        "campos": [
            {"nombre": "archivo", "tipo": "file", "etiqueta": "Archivo"},
            {"nombre": "hashEsperado", "tipo": "text", "etiqueta": "Hash esperado"},
            {"nombre": "algoritmo", "tipo": "select", "etiqueta": "Algoritmo", "opciones": list(logic.ALGORITMOS_HASH)},
        ],
    },
    "generar-hashes": {
        "nombre": "Generar Hashes",
        "descripcion": "Calcula MD5, SHA1, SHA256 y SHA512 de un archivo",
        "campos": [{"nombre": "archivo", "tipo": "file", "etiqueta": "Archivo"}],
    },
    "detectar-tipo": {
        "nombre": "Detectar Tipo Real",
        "descripcion": "Detecta el tipo real de un archivo a partir de su contenido, no de la extension",
        "campos": [{"nombre": "archivo", "tipo": "file", "etiqueta": "Archivo"}],
    },
    "calcular-entropia": {
        "nombre": "Calcular Entropia",
        "descripcion": "Calcula la entropia de Shannon de un archivo para detectar cifrado o empaquetado",
        "campos": [{"nombre": "archivo", "tipo": "file", "etiqueta": "Archivo"}],
    },
    "ver-metadatos": {
        "nombre": "Ver Metadatos",
        "descripcion": "Muestra los metadatos EXIF de una imagen o de un PDF",
        "campos": [{"nombre": "archivo", "tipo": "file", "etiqueta": "Archivo (imagen o PDF)"}],
    },
    "eliminar-metadatos": {
        "nombre": "Eliminar Metadatos",
        "descripcion": "Elimina los metadatos de una imagen o de un PDF y descarga el archivo limpio",
        "campos": [{"nombre": "archivo", "tipo": "file", "etiqueta": "Archivo (imagen o PDF)"}],
    },
    "editar-metadatos": {
        "nombre": "Editar Metadatos",
        "descripcion": "Edita etiquetas EXIF de una imagen y descarga el archivo modificado",
        "campos": [
            {"nombre": "archivo", "tipo": "file", "etiqueta": "Imagen"},
            {"nombre": "metadatosJson", "tipo": "textarea", "etiqueta": "Metadatos a establecer, JSON etiqueta:valor (ej. {\"Artist\": \"nombre\"})"},
        ],
    },
    "extraer-strings": {
        "nombre": "Extraer Strings",
        "descripcion": "Extrae cadenas de texto imprimibles de un archivo (equivalente a strings)",
        "campos": [
            {"nombre": "archivo", "tipo": "file", "etiqueta": "Archivo"},
            {"nombre": "longitudMinima", "tipo": "text", "etiqueta": "Longitud minima (por defecto 4)"},
        ],
    },
    "visor-bd": {
        "nombre": "Visor de Base de Datos",
        "descripcion": "Explora una base de datos SQLite: tablas, vistas, esquema y contenido de sus filas",
        "campos": [
            {"nombre": "archivo", "tipo": "file", "etiqueta": "Base de datos (.db, .sqlite, .sqlite3)"},
            {"nombre": "tabla", "tipo": "text", "etiqueta": "Tabla o vista a mostrar (vacio para listar las disponibles)"},
            {"nombre": "limite", "tipo": "text", "etiqueta": f"Filas a mostrar (por defecto {logic.FILAS_POR_DEFECTO_BD}, maximo {logic.FILAS_MAXIMAS_BD})"},
            {"nombre": "desplazamiento", "tipo": "text", "etiqueta": "Desplazamiento, filas a saltar (por defecto 0)"},
        ],
    },
    "analizar-firma": {
        "nombre": "Analizar Firma Digital",
        "descripcion": "Comprueba si un ejecutable PE de Windows tiene una firma Authenticode",
        "campos": [{"nombre": "archivo", "tipo": "file", "etiqueta": "Ejecutable"}],
    },
}


@archivosBp.route("/")
def index():
    return render_template("categoria.html", categoriaSlug="archivos", categoriaNombre="Analisis Archivos", tools=TOOLS)


@archivosBp.route("/<toolSlug>")
def herramienta(toolSlug):
    tool = TOOLS.get(toolSlug)
    if tool is None:
        return render_template("categoria.html", categoriaSlug="archivos", categoriaNombre="Analisis Archivos", tools=TOOLS), 404
    return render_template("herramienta.html", categoriaSlug="archivos", toolSlug=toolSlug, tool=tool)


@archivosBp.route("/api/verificar-hash", methods=["POST"])
def apiVerificarHash():
    archivo = request.files.get("archivo")
    if archivo is None:
        return jsonify({"error": "Falta el archivo"}), 400
    try:
        resultado = logic.verificarHash(archivo.read(), request.form.get("hashEsperado", ""), request.form.get("algoritmo", "sha256"))
        return jsonify(resultado)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@archivosBp.route("/api/generar-hashes", methods=["POST"])
def apiGenerarHashes():
    archivo = request.files.get("archivo")
    if archivo is None:
        return jsonify({"error": "Falta el archivo"}), 400
    try:
        resultado = logic.generarHashes(archivo.read())
        return jsonify(resultado)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@archivosBp.route("/api/detectar-tipo", methods=["POST"])
def apiDetectarTipo():
    archivo = request.files.get("archivo")
    if archivo is None:
        return jsonify({"error": "Falta el archivo"}), 400
    try:
        resultado = logic.detectarTipoArchivo(archivo.read(), archivo.filename or "")
        return jsonify(resultado)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@archivosBp.route("/api/calcular-entropia", methods=["POST"])
def apiCalcularEntropia():
    archivo = request.files.get("archivo")
    if archivo is None:
        return jsonify({"error": "Falta el archivo"}), 400
    try:
        resultado = logic.calcularEntropia(archivo.read())
        return jsonify(resultado)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@archivosBp.route("/api/ver-metadatos", methods=["POST"])
def apiVerMetadatos():
    archivo = request.files.get("archivo")
    if archivo is None:
        return jsonify({"error": "Falta el archivo"}), 400
    try:
        resultado = logic.verMetadatos(archivo.read(), archivo.filename or "")
        return jsonify(resultado)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@archivosBp.route("/api/eliminar-metadatos", methods=["POST"])
def apiEliminarMetadatos():
    archivo = request.files.get("archivo")
    if archivo is None:
        return jsonify({"error": "Falta el archivo"}), 400
    try:
        archivoLimpio, extension = logic.eliminarMetadatos(archivo.read(), archivo.filename or "")
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    nombreSalida = f"sin-metadatos.{extension}"
    return Response(
        archivoLimpio,
        mimetype="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{nombreSalida}"'},
    )


@archivosBp.route("/api/editar-metadatos", methods=["POST"])
def apiEditarMetadatos():
    archivo = request.files.get("archivo")
    if archivo is None:
        return jsonify({"error": "Falta el archivo"}), 400
    try:
        archivoEditado, extension = logic.editarMetadatosImagen(archivo.read(), request.form.get("metadatosJson", ""), archivo.filename or "")
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    nombreSalida = f"metadatos-editados.{extension}"
    return Response(
        archivoEditado,
        mimetype="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{nombreSalida}"'},
    )


@archivosBp.route("/api/extraer-strings", methods=["POST"])
def apiExtraerStrings():
    archivo = request.files.get("archivo")
    if archivo is None:
        return jsonify({"error": "Falta el archivo"}), 400
    try:
        resultado = logic.extraerStrings(archivo.read(), request.form.get("longitudMinima", 4))
        return jsonify(resultado)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@archivosBp.route("/api/visor-bd", methods=["POST"])
def apiVisorBd():
    archivo = request.files.get("archivo")
    if archivo is None:
        return jsonify({"error": "Falta el archivo"}), 400
    try:
        resultado = logic.explorarBaseDatos(
            archivo.read(),
            request.form.get("tabla", ""),
            request.form.get("limite", logic.FILAS_POR_DEFECTO_BD),
            request.form.get("desplazamiento", 0),
        )
        return jsonify(resultado)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@archivosBp.route("/api/analizar-firma", methods=["POST"])
def apiAnalizarFirma():
    archivo = request.files.get("archivo")
    if archivo is None:
        return jsonify({"error": "Falta el archivo"}), 400
    try:
        resultado = logic.analizarFirmaDigital(archivo.read(), archivo.filename or "")
        return jsonify(resultado)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
