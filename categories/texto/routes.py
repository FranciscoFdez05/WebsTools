from flask import Blueprint, jsonify, render_template, request

from . import logic

textoBp = Blueprint("texto", __name__, url_prefix="/texto")

TOOLS = {
    "codificar": {
        "nombre": "Codificar Texto",
        "descripcion": "Codifica texto a Base64, URL Encode, HTML Encode, Hex, Binario o ASCII",
        "campos": [
            {"nombre": "texto", "tipo": "textarea", "etiqueta": "Texto"},
            {"nombre": "formato", "tipo": "select", "etiqueta": "Formato", "opciones": list(logic.FORMATOS_SOPORTADOS)},
        ],
    },
    "decodificar": {
        "nombre": "Decodificar Texto",
        "descripcion": "Decodifica texto desde Base64, URL Encode, HTML Encode, Hex, Binario o ASCII",
        "campos": [
            {"nombre": "texto", "tipo": "textarea", "etiqueta": "Texto codificado"},
            {"nombre": "formato", "tipo": "select", "etiqueta": "Formato", "opciones": list(logic.FORMATOS_SOPORTADOS)},
        ],
    },
    "jwt-decoder": {
        "nombre": "JWT Decoder",
        "descripcion": "Decodifica la cabecera y el cuerpo de un token JWT sin verificar la firma",
        "campos": [{"nombre": "token", "tipo": "textarea", "etiqueta": "Token JWT"}],
    },
    "generar-uuid": {
        "nombre": "Generador de UUID",
        "descripcion": "Genera un identificador UUID version 1 o version 4",
        "campos": [{"nombre": "version", "tipo": "select", "etiqueta": "Version", "opciones": list(logic.VERSIONES_UUID_SOPORTADAS)}],
    },
    "generar-contrasena": {
        "nombre": "Generador de Contrasenas",
        "descripcion": "Genera una contrasena aleatoria con longitud y conjuntos de caracteres configurables",
        "campos": [
            {"nombre": "longitud", "tipo": "text", "etiqueta": "Longitud (4-128)"},
            {"nombre": "incluirMayusculas", "tipo": "select", "etiqueta": "Incluir mayusculas", "opciones": ["si", "no"]},
            {"nombre": "incluirMinusculas", "tipo": "select", "etiqueta": "Incluir minusculas", "opciones": ["si", "no"]},
            {"nombre": "incluirNumeros", "tipo": "select", "etiqueta": "Incluir numeros", "opciones": ["si", "no"]},
            {"nombre": "incluirSimbolos", "tipo": "select", "etiqueta": "Incluir simbolos", "opciones": ["si", "no"]},
        ],
    },
    "generar-passphrase": {
        "nombre": "Generador de Passphrase",
        "descripcion": "Genera una passphrase estilo diceware a partir de una wordlist embebida",
        "campos": [
            {"nombre": "numPalabras", "tipo": "text", "etiqueta": "Numero de palabras (3-12)"},
            {"nombre": "separador", "tipo": "text", "etiqueta": "Separador (por defecto '-')"},
        ],
    },
    "comprobar-fortaleza": {
        "nombre": "Comprobar Fortaleza de Contrasena",
        "descripcion": "Analiza la fortaleza de una contrasena con la libreria zxcvbn",
        "campos": [{"nombre": "contrasena", "tipo": "text", "etiqueta": "Contrasena"}],
    },
    "comparar-textos": {
        "nombre": "Comparador de Textos (Diff)",
        "descripcion": "Compara dos textos y muestra las diferencias linea a linea",
        "campos": [
            {"nombre": "textoA", "tipo": "textarea", "etiqueta": "Texto A"},
            {"nombre": "textoB", "tipo": "textarea", "etiqueta": "Texto B"},
        ],
    },
}


@textoBp.route("/")
def index():
    return render_template("categoria.html", categoriaSlug="texto", categoriaNombre="Texto", tools=TOOLS)


@textoBp.route("/<toolSlug>")
def herramienta(toolSlug):
    tool = TOOLS.get(toolSlug)
    if tool is None:
        return render_template("categoria.html", categoriaSlug="texto", categoriaNombre="Texto", tools=TOOLS), 404
    return render_template("herramienta.html", categoriaSlug="texto", toolSlug=toolSlug, tool=tool)


@textoBp.route("/api/codificar", methods=["POST"])
def apiCodificar():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.codificar(datos.get("texto", ""), datos.get("formato", "base64")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@textoBp.route("/api/decodificar", methods=["POST"])
def apiDecodificar():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.decodificar(datos.get("texto", ""), datos.get("formato", "base64")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@textoBp.route("/api/jwt-decoder", methods=["POST"])
def apiJwtDecoder():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.decodificarJwt(datos.get("token", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@textoBp.route("/api/generar-uuid", methods=["POST"])
def apiGenerarUuid():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.generarUuid(datos.get("version", "4")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@textoBp.route("/api/generar-contrasena", methods=["POST"])
def apiGenerarContrasena():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.generarContrasena(
            datos.get("longitud", 16),
            datos.get("incluirMayusculas", "si"),
            datos.get("incluirMinusculas", "si"),
            datos.get("incluirNumeros", "si"),
            datos.get("incluirSimbolos", "no"),
        ))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@textoBp.route("/api/generar-passphrase", methods=["POST"])
def apiGenerarPassphrase():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.generarPassphrase(datos.get("numPalabras", 5), datos.get("separador", "-")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@textoBp.route("/api/comprobar-fortaleza", methods=["POST"])
def apiComprobarFortaleza():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.comprobarFortalezaContrasena(datos.get("contrasena", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@textoBp.route("/api/comparar-textos", methods=["POST"])
def apiCompararTextos():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.compararTextos(datos.get("textoA", ""), datos.get("textoB", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
