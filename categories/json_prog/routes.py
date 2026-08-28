from flask import Blueprint, jsonify, render_template, request

from . import logic

jsonProgBp = Blueprint("json_prog", __name__, url_prefix="/json-prog")

TOOLS = {
    "formatear": {
        "nombre": "Formatear JSON",
        "descripcion": "Indenta y da formato legible a un JSON",
        "campos": [{"nombre": "textoJson", "tipo": "textarea", "etiqueta": "JSON"}],
    },
    "validar": {
        "nombre": "Validar JSON",
        "descripcion": "Comprueba si un texto es JSON valido",
        "campos": [{"nombre": "textoJson", "tipo": "textarea", "etiqueta": "JSON"}],
    },
    "minificar": {
        "nombre": "Minificar JSON",
        "descripcion": "Elimina espacios y saltos de linea innecesarios de un JSON",
        "campos": [{"nombre": "textoJson", "tipo": "textarea", "etiqueta": "JSON"}],
    },
    "beautify-xml": {
        "nombre": "Beautify XML",
        "descripcion": "Indenta y da formato legible a un XML",
        "campos": [{"nombre": "textoXml", "tipo": "textarea", "etiqueta": "XML"}],
    },
    "beautify-html": {
        "nombre": "Beautify HTML",
        "descripcion": "Indenta y da formato legible a un HTML",
        "campos": [{"nombre": "textoHtml", "tipo": "textarea", "etiqueta": "HTML"}],
    },
    "beautify-css": {
        "nombre": "Beautify CSS",
        "descripcion": "Indenta y da formato legible a un CSS",
        "campos": [{"nombre": "textoCss", "tipo": "textarea", "etiqueta": "CSS"}],
    },
    "beautify-js": {
        "nombre": "Beautify JavaScript",
        "descripcion": "Indenta y da formato legible a un JavaScript",
        "campos": [{"nombre": "textoJs", "tipo": "textarea", "etiqueta": "JavaScript"}],
    },
    "ofuscar-js": {
        "nombre": "Ofuscar JavaScript",
        "descripcion": "Ofusca codigo JavaScript para dificultar su lectura manteniendolo ejecutable",
        "campos": [
            {"nombre": "textoJs", "tipo": "textarea", "etiqueta": "JavaScript"},
            {"nombre": "tecnica", "tipo": "select", "etiqueta": "Tecnica", "opciones": list(logic.TECNICAS_OFUSCACION_JS)},
        ],
    },
}


@jsonProgBp.route("/")
def index():
    return render_template("categoria.html", categoriaSlug="json-prog", categoriaNombre="JSON y Programacion", tools=TOOLS)


@jsonProgBp.route("/<toolSlug>")
def herramienta(toolSlug):
    tool = TOOLS.get(toolSlug)
    if tool is None:
        return render_template("categoria.html", categoriaSlug="json-prog", categoriaNombre="JSON y Programacion", tools=TOOLS), 404
    return render_template("herramienta.html", categoriaSlug="json-prog", toolSlug=toolSlug, tool=tool)


@jsonProgBp.route("/api/formatear", methods=["POST"])
def apiFormatear():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.formatearJson(datos.get("textoJson", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@jsonProgBp.route("/api/validar", methods=["POST"])
def apiValidar():
    datos = request.get_json(silent=True) or request.form
    return jsonify(logic.validarJson(datos.get("textoJson", "")))


@jsonProgBp.route("/api/minificar", methods=["POST"])
def apiMinificar():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.minificarJson(datos.get("textoJson", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@jsonProgBp.route("/api/beautify-xml", methods=["POST"])
def apiBeautifyXml():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.beautifyXml(datos.get("textoXml", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@jsonProgBp.route("/api/beautify-html", methods=["POST"])
def apiBeautifyHtml():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.beautifyHtml(datos.get("textoHtml", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@jsonProgBp.route("/api/beautify-css", methods=["POST"])
def apiBeautifyCss():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.beautifyCss(datos.get("textoCss", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@jsonProgBp.route("/api/beautify-js", methods=["POST"])
def apiBeautifyJs():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.beautifyJavascript(datos.get("textoJs", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@jsonProgBp.route("/api/ofuscar-js", methods=["POST"])
def apiOfuscarJs():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.ofuscarJavascript(datos.get("textoJs", ""), datos.get("tecnica", "charcode")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
