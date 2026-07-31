from flask import Blueprint, jsonify, render_template, request

from . import logic

criptografiaBp = Blueprint("criptografia", __name__, url_prefix="/criptografia")

TOOLS = {
    "generar-rsa": {
        "nombre": "Generar Claves RSA",
        "descripcion": "Genera un par de claves RSA (privada y publica) en formato PEM",
        "campos": [{"nombre": "tamano", "tipo": "select", "etiqueta": "Tamano de clave (bits)", "opciones": list(logic.TAMANOS_RSA)}],
    },
    "generar-aes": {
        "nombre": "Generar Clave AES",
        "descripcion": "Genera una clave AES aleatoria en Base64 y Hex",
        "campos": [{"nombre": "tamano", "tipo": "select", "etiqueta": "Tamano de clave (bits)", "opciones": list(logic.TAMANOS_AES)}],
    },
    "aes-cifrar": {
        "nombre": "Cifrar AES-GCM",
        "descripcion": "Cifra un texto con AES en modo GCM usando una clave Base64",
        "campos": [
            {"nombre": "texto", "tipo": "textarea", "etiqueta": "Texto"},
            {"nombre": "claveBase64", "tipo": "text", "etiqueta": "Clave AES (Base64)"},
        ],
    },
    "aes-descifrar": {
        "nombre": "Descifrar AES-GCM",
        "descripcion": "Descifra un texto cifrado con AES-GCM",
        "campos": [
            {"nombre": "claveBase64", "tipo": "text", "etiqueta": "Clave AES (Base64)"},
            {"nombre": "nonceBase64", "tipo": "text", "etiqueta": "Nonce (Base64)"},
            {"nombre": "textoCifradoBase64", "tipo": "textarea", "etiqueta": "Texto cifrado (Base64)"},
        ],
    },
    "rsa-cifrar": {
        "nombre": "Cifrar RSA",
        "descripcion": "Cifra un texto con una clave publica RSA (OAEP-SHA256)",
        "campos": [
            {"nombre": "texto", "tipo": "textarea", "etiqueta": "Texto"},
            {"nombre": "clavePublicaPem", "tipo": "textarea", "etiqueta": "Clave publica RSA (PEM)"},
        ],
    },
    "rsa-descifrar": {
        "nombre": "Descifrar RSA",
        "descripcion": "Descifra un texto con una clave privada RSA (OAEP-SHA256)",
        "campos": [
            {"nombre": "textoCifradoBase64", "tipo": "textarea", "etiqueta": "Texto cifrado (Base64)"},
            {"nombre": "clavePrivadaPem", "tipo": "textarea", "etiqueta": "Clave privada RSA (PEM)"},
        ],
    },
    "generar-hmac": {
        "nombre": "Generar HMAC",
        "descripcion": "Calcula el HMAC de un texto con una clave secreta",
        "campos": [
            {"nombre": "texto", "tipo": "textarea", "etiqueta": "Texto"},
            {"nombre": "claveSecreta", "tipo": "text", "etiqueta": "Clave secreta"},
            {"nombre": "algoritmo", "tipo": "select", "etiqueta": "Algoritmo", "opciones": list(logic.ALGORITMOS_HMAC)},
        ],
    },
    "jwt-inspector": {
        "nombre": "JWT Inspector",
        "descripcion": "Decodifica un token JWT y valida su firma si se aporta la clave o secreto",
        "campos": [
            {"nombre": "token", "tipo": "textarea", "etiqueta": "Token JWT"},
            {"nombre": "secretoOClavePublica", "tipo": "textarea", "etiqueta": "Secreto HMAC o clave publica RSA (opcional)"},
        ],
    },
    "generar-certificado": {
        "nombre": "Generar Certificado Autofirmado",
        "descripcion": "Genera un certificado X.509 autofirmado junto con su clave privada",
        "campos": [
            {"nombre": "nombreComun", "tipo": "text", "etiqueta": "Nombre comun (CN)"},
            {"nombre": "diasValidez", "tipo": "text", "etiqueta": "Dias de validez"},
            {"nombre": "tamanoClave", "tipo": "select", "etiqueta": "Tamano de clave (bits)", "opciones": list(logic.TAMANOS_RSA)},
        ],
    },
}


@criptografiaBp.route("/")
def index():
    return render_template("categoria.html", categoriaSlug="criptografia", categoriaNombre="Criptografia", tools=TOOLS)


@criptografiaBp.route("/<toolSlug>")
def herramienta(toolSlug):
    tool = TOOLS.get(toolSlug)
    if tool is None:
        return render_template("categoria.html", categoriaSlug="criptografia", categoriaNombre="Criptografia", tools=TOOLS), 404
    return render_template("herramienta.html", categoriaSlug="criptografia", toolSlug=toolSlug, tool=tool)


@criptografiaBp.route("/api/generar-rsa", methods=["POST"])
def apiGenerarRsa():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.generarClaveRsa(datos.get("tamano", 2048)))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@criptografiaBp.route("/api/generar-aes", methods=["POST"])
def apiGenerarAes():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.generarClaveAes(datos.get("tamano", 256)))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@criptografiaBp.route("/api/aes-cifrar", methods=["POST"])
def apiAesCifrar():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.cifrarAes(datos.get("texto", ""), datos.get("claveBase64", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@criptografiaBp.route("/api/aes-descifrar", methods=["POST"])
def apiAesDescifrar():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.descifrarAes(datos.get("claveBase64", ""), datos.get("nonceBase64", ""), datos.get("textoCifradoBase64", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@criptografiaBp.route("/api/rsa-cifrar", methods=["POST"])
def apiRsaCifrar():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.cifrarRsa(datos.get("texto", ""), datos.get("clavePublicaPem", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@criptografiaBp.route("/api/rsa-descifrar", methods=["POST"])
def apiRsaDescifrar():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.descifrarRsa(datos.get("textoCifradoBase64", ""), datos.get("clavePrivadaPem", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@criptografiaBp.route("/api/generar-hmac", methods=["POST"])
def apiGenerarHmac():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.generarHmac(datos.get("texto", ""), datos.get("claveSecreta", ""), datos.get("algoritmo", "sha256")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@criptografiaBp.route("/api/jwt-inspector", methods=["POST"])
def apiJwtInspector():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.inspeccionarJwt(datos.get("token", ""), datos.get("secretoOClavePublica", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@criptografiaBp.route("/api/generar-certificado", methods=["POST"])
def apiGenerarCertificado():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.generarCertificadoAutofirmado(datos.get("nombreComun", ""), datos.get("diasValidez", 365), datos.get("tamanoClave", 2048)))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
