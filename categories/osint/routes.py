from flask import Blueprint, jsonify, render_template, request

from . import logic, recon

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
    "buscar-usuario": {
        "nombre": "Buscar Usuario (Sherlock)",
        "descripcion": "Busca un nombre de usuario en cientos de redes sociales y sitios web, con la lista de sitios del proyecto Sherlock",
        "campos": [
            {"nombre": "usuario", "tipo": "text", "etiqueta": "Nombre de usuario (ej. torvalds)"},
            {"nombre": "alcance", "tipo": "select", "etiqueta": "Sitios (populares: unos 80, rapido; todos: mas de 400, tarda medio minuto)", "opciones": list(recon.ALCANCES_SHERLOCK)},
        ],
    },
    "comprobar-email": {
        "nombre": "Comprobar Email (Holehe)",
        "descripcion": "Comprueba en que servicios esta registrado un email sin avisar a su dueno, con los modulos de holehe",
        "campos": [{"nombre": "email", "tipo": "text", "etiqueta": "Email (ej. usuario@example.com)"}],
    },
    "cabeceras-http": {
        "nombre": "Analizar Cabeceras HTTP",
        "descripcion": "Cabeceras de respuesta de un sitio, redirecciones, cookies, tecnologias detectadas y cabeceras de seguridad que faltan",
        "campos": [{"nombre": "url", "tipo": "text", "etiqueta": "URL (ej. https://example.com)"}],
    },
    "escaner-puertos": {
        "nombre": "Escaner de Puertos",
        "descripcion": "Comprueba que puertos TCP acepta conexiones un host: los mas habituales o los que indiques",
        "campos": [
            {"nombre": "host", "tipo": "text", "etiqueta": "Host o IP (ej. 192.168.1.1)"},
            {"nombre": "puertos", "tipo": "text", "etiqueta": f"Puertos (vacio: {len(recon.PUERTOS_COMUNES)} habituales; o 22,80,8000-8100; maximo {recon.MAX_PUERTOS_ESCANEO})"},
        ],
    },
    "transferencia-zona": {
        "nombre": "Transferencia de Zona DNS (AXFR)",
        "descripcion": "Pide la zona completa a cada servidor de nombres del dominio: si alguno la entrega, expone todos sus registros",
        "campos": [{"nombre": "dominio", "tipo": "text", "etiqueta": "Dominio (ej. zonetransfer.me)"}],
    },
    "wayback": {
        "nombre": "Wayback Machine",
        "descripcion": "Capturas historicas de una URL en archive.org: primera, ultimas y anos con capturas",
        "campos": [{"nombre": "url", "tipo": "text", "etiqueta": "URL (ej. example.com)"}],
    },
    "extraer-datos-web": {
        "nombre": "Extraer Datos de una Pagina",
        "descripcion": "Emails, telefonos, perfiles en redes sociales, dominios enlazados, scripts externos y comentarios HTML de una pagina",
        "campos": [{"nombre": "url", "tipo": "text", "etiqueta": "URL (ej. https://example.com)"}],
    },
    "robots-sitemap": {
        "nombre": "robots.txt y Sitemap",
        "descripcion": "Rutas que un sitio pide no indexar y URLs que publica en su sitemap",
        "campos": [{"nombre": "url", "tipo": "text", "etiqueta": "Sitio (ej. example.com)"}],
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


@osintBp.route("/api/buscar-usuario", methods=["POST"])
def apiBuscarUsuario():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(recon.buscarUsuario(datos.get("usuario", ""), datos.get("alcance", "populares")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@osintBp.route("/api/comprobar-email", methods=["POST"])
def apiComprobarEmail():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(recon.comprobarEmail(datos.get("email", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@osintBp.route("/api/cabeceras-http", methods=["POST"])
def apiCabecerasHttp():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(recon.analizarCabecerasHttp(datos.get("url", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@osintBp.route("/api/escaner-puertos", methods=["POST"])
def apiEscanerPuertos():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(recon.escanearPuertos(datos.get("host", ""), datos.get("puertos", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@osintBp.route("/api/transferencia-zona", methods=["POST"])
def apiTransferenciaZona():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(recon.comprobarTransferenciaZona(datos.get("dominio", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@osintBp.route("/api/wayback", methods=["POST"])
def apiWayback():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(recon.consultarWayback(datos.get("url", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@osintBp.route("/api/extraer-datos-web", methods=["POST"])
def apiExtraerDatosWeb():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(recon.extraerDatosPagina(datos.get("url", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@osintBp.route("/api/robots-sitemap", methods=["POST"])
def apiRobotsSitemap():
    datos = request.get_json(silent=True) or request.form
    try:
        return jsonify(recon.analizarRobotsSitemap(datos.get("url", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
