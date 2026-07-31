from flask import Blueprint, jsonify, render_template, request

from . import logic

redesBp = Blueprint("redes", __name__, url_prefix="/redes")

TOOLS = {
    "ip-decimal": {
        "nombre": "Conversor IP <-> Decimal",
        "descripcion": "Convierte una IPv4 a su representacion decimal y viceversa",
        "campos": [
            {"nombre": "ip", "tipo": "text", "etiqueta": "IP (ej. 192.168.1.1)"},
            {"nombre": "decimal", "tipo": "text", "etiqueta": "Decimal (ej. 3232235777)"},
        ],
    },
    "cidr": {
        "nombre": "Conversor CIDR",
        "descripcion": "Calcula direccion de red, mascara y broadcast a partir de un CIDR",
        "campos": [{"nombre": "cidr", "tipo": "text", "etiqueta": "CIDR (ej. 192.168.1.0/24)"}],
    },
    "subredes": {
        "nombre": "Calculadora de Subredes",
        "descripcion": "Calcula rango de hosts utilizables de una subred",
        "campos": [{"nombre": "cidr", "tipo": "text", "etiqueta": "CIDR (ej. 192.168.1.0/24)"}],
    },
    "validar-ip": {
        "nombre": "Validar IPv4/IPv6",
        "descripcion": "Comprueba si una direccion IP es valida y de que version",
        "campos": [{"nombre": "ip", "tipo": "text", "etiqueta": "Direccion IP"}],
    },
    "wildcard": {
        "nombre": "Calculadora Wildcard",
        "descripcion": "Calcula la mascara wildcard inversa de un CIDR",
        "campos": [{"nombre": "cidr", "tipo": "text", "etiqueta": "CIDR (ej. 192.168.1.0/24)"}],
    },
    "mac-aleatoria": {
        "nombre": "Generador de MAC Aleatorias",
        "descripcion": "Genera una direccion MAC unicast administrada localmente",
        "campos": [],
    },
    "ipv4-ipv6": {
        "nombre": "Conversor IPv4 <-> IPv6",
        "descripcion": "Convierte una IPv4 a su representacion IPv6 mapeada (::ffff:a.b.c.d) y viceversa",
        "campos": [
            {"nombre": "ipv4", "tipo": "text", "etiqueta": "IPv4 (ej. 192.168.1.1)"},
            {"nombre": "ipv6", "tipo": "text", "etiqueta": "IPv6 (ej. ::ffff:192.168.1.1)"},
        ],
    },
}


@redesBp.route("/")
def index():
    return render_template("categoria.html", categoriaSlug="redes", categoriaNombre="Redes", tools=TOOLS)


@redesBp.route("/<toolSlug>")
def herramienta(toolSlug):
    tool = TOOLS.get(toolSlug)
    if tool is None:
        return render_template("categoria.html", categoriaSlug="redes", categoriaNombre="Redes", tools=TOOLS), 404
    return render_template("herramienta.html", categoriaSlug="redes", toolSlug=toolSlug, tool=tool)


@redesBp.route("/api/ip-decimal", methods=["POST"])
def apiIpDecimal():
    datos = request.get_json(silent=True) or request.form
    try:
        if datos.get("ip"):
            return jsonify(logic.ipADecimal(datos.get("ip")))
        if datos.get("decimal"):
            return jsonify(logic.decimalAIp(datos.get("decimal")))
        return jsonify({"error": "Indica una IP o un valor decimal"}), 400
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@redesBp.route("/api/cidr", methods=["POST"])
def apiCidr():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.calcularSubred(datos.get("cidr", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@redesBp.route("/api/subredes", methods=["POST"])
def apiSubredes():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.calcularSubred(datos.get("cidr", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@redesBp.route("/api/validar-ip", methods=["POST"])
def apiValidarIp():
    datos = request.get_json(silent=True) or request.form
    return jsonify(logic.validarIp(datos.get("ip", "")))


@redesBp.route("/api/wildcard", methods=["POST"])
def apiWildcard():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.calcularWildcard(datos.get("cidr", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@redesBp.route("/api/mac-aleatoria", methods=["POST"])
def apiMacAleatoria():
    return jsonify(logic.generarMacAleatoria())


@redesBp.route("/api/ipv4-ipv6", methods=["POST"])
def apiIpv4Ipv6():
    datos = request.get_json(silent=True) or request.form
    try:
        if datos.get("ipv4"):
            return jsonify(logic.ipv4AIpv6(datos.get("ipv4")))
        if datos.get("ipv6"):
            return jsonify(logic.ipv6AIpv4(datos.get("ipv6")))
        return jsonify({"error": "Indica una IPv4 o una IPv6"}), 400
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
