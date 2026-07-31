from flask import Blueprint, jsonify, render_template, request

from . import logic

osintBp = Blueprint("osint", __name__, url_prefix="/osint")

TOOLS = {
    "whois": {
        "nombre": "WHOIS",
        "descripcion": "Consulta los datos de registro publico de un dominio",
        "campos": [{"nombre": "dominio", "tipo": "text", "etiqueta": "Dominio (ej. example.com)"}],
    },
    "dns-lookup": {
        "nombre": "DNS Lookup",
        "descripcion": "Consulta registros DNS de un dominio",
        "campos": [
            {"nombre": "dominio", "tipo": "text", "etiqueta": "Dominio"},
            {"nombre": "tipoRegistro", "tipo": "select", "etiqueta": "Tipo de registro", "opciones": list(logic.TIPOS_REGISTRO_SOPORTADOS)},
        ],
    },
    "reverse-dns": {
        "nombre": "Reverse DNS",
        "descripcion": "Obtiene el nombre de host asociado a una IP",
        "campos": [{"nombre": "ip", "tipo": "text", "etiqueta": "Direccion IP"}],
    },
    "geolocalizacion": {
        "nombre": "Geolocalizacion IP",
        "descripcion": "Obtiene la ubicacion aproximada de una direccion IP",
        "campos": [{"nombre": "ip", "tipo": "text", "etiqueta": "Direccion IP"}],
    },
    "spf": {
        "nombre": "Comprobar SPF",
        "descripcion": "Comprueba si un dominio tiene un registro SPF publicado",
        "campos": [{"nombre": "dominio", "tipo": "text", "etiqueta": "Dominio"}],
    },
    "dkim": {
        "nombre": "Comprobar DKIM",
        "descripcion": "Comprueba si un dominio tiene un registro DKIM publicado para un selector",
        "campos": [
            {"nombre": "dominio", "tipo": "text", "etiqueta": "Dominio"},
            {"nombre": "selector", "tipo": "text", "etiqueta": "Selector (por defecto 'default')"},
        ],
    },
    "dmarc": {
        "nombre": "Comprobar DMARC",
        "descripcion": "Comprueba si un dominio tiene un registro DMARC publicado",
        "campos": [{"nombre": "dominio", "tipo": "text", "etiqueta": "Dominio"}],
    },
    "asn-lookup": {
        "nombre": "ASN Lookup",
        "descripcion": "Obtiene el sistema autonomo (ASN) al que pertenece una IP",
        "campos": [{"nombre": "ip", "tipo": "text", "etiqueta": "Direccion IP"}],
    },
    "cloudflare-ip": {
        "nombre": "Comprobar IP Cloudflare",
        "descripcion": "Comprueba si una IP pertenece a los rangos publicados por Cloudflare",
        "campos": [{"nombre": "ip", "tipo": "text", "etiqueta": "Direccion IP"}],
    },
    "subdominios": {
        "nombre": "Buscar Subdominios",
        "descripcion": "Busca subdominios conocidos a partir de certificados publicos (Certificate Transparency via crt.sh)",
        "campos": [{"nombre": "dominio", "tipo": "text", "etiqueta": "Dominio (ej. example.com)"}],
    },
    "dns-propagation": {
        "nombre": "DNS Propagation",
        "descripcion": "Consulta un registro DNS contra varios resolvers publicos para comprobar su propagacion",
        "campos": [
            {"nombre": "dominio", "tipo": "text", "etiqueta": "Dominio"},
            {"nombre": "tipoRegistro", "tipo": "select", "etiqueta": "Tipo de registro", "opciones": list(logic.TIPOS_REGISTRO_SOPORTADOS)},
        ],
    },
}


@osintBp.route("/")
def index():
    return render_template("categoria.html", categoriaSlug="osint", categoriaNombre="OSINT", tools=TOOLS)


@osintBp.route("/<toolSlug>")
def herramienta(toolSlug):
    tool = TOOLS.get(toolSlug)
    if tool is None:
        return render_template("categoria.html", categoriaSlug="osint", categoriaNombre="OSINT", tools=TOOLS), 404
    return render_template("herramienta.html", categoriaSlug="osint", toolSlug=toolSlug, tool=tool)


@osintBp.route("/api/whois", methods=["POST"])
def apiWhois():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.whoisLookup(datos.get("dominio", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@osintBp.route("/api/dns-lookup", methods=["POST"])
def apiDnsLookup():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.dnsLookup(datos.get("dominio", ""), datos.get("tipoRegistro", "A")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@osintBp.route("/api/reverse-dns", methods=["POST"])
def apiReverseDns():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.reverseDnsLookup(datos.get("ip", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@osintBp.route("/api/geolocalizacion", methods=["POST"])
def apiGeolocalizacion():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.geolocalizarIp(datos.get("ip", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@osintBp.route("/api/spf", methods=["POST"])
def apiSpf():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.comprobarSpf(datos.get("dominio", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@osintBp.route("/api/dkim", methods=["POST"])
def apiDkim():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.comprobarDkim(datos.get("dominio", ""), datos.get("selector", "default")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@osintBp.route("/api/dmarc", methods=["POST"])
def apiDmarc():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.comprobarDmarc(datos.get("dominio", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@osintBp.route("/api/asn-lookup", methods=["POST"])
def apiAsnLookup():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.buscarAsn(datos.get("ip", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@osintBp.route("/api/cloudflare-ip", methods=["POST"])
def apiCloudflareIp():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.esIpCloudflare(datos.get("ip", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@osintBp.route("/api/subdominios", methods=["POST"])
def apiSubdominios():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.buscarSubdominios(datos.get("dominio", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@osintBp.route("/api/dns-propagation", methods=["POST"])
def apiDnsPropagation():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(logic.comprobarPropagacionDns(datos.get("dominio", ""), datos.get("tipoRegistro", "A")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
