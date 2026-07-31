import ipaddress
import json
import socket
import urllib.parse
import urllib.request

import dns.resolver
import dns.reversename
import whois

from config import Config

TIPOS_REGISTRO_SOPORTADOS = ("A", "AAAA", "MX", "TXT", "NS", "CNAME", "SOA")

# rangos IP publicados por Cloudflare (https://www.cloudflare.com/ips/), snapshot estatico
RANGOS_CLOUDFLARE_IPV4 = (
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
    "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
    "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
    "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
)
RANGOS_CLOUDFLARE_IPV6 = (
    "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32",
    "2405:8100::/32", "2a06:98c0::/29", "2c0f:f248::/32",
)

# crt.sh no requiere API key pero no publica un limite oficial; en la practica banea temporalmente
# IPs que hagan demasiadas consultas seguidas, por eso se usa un timeout generoso y una sola peticion
TIMEOUT_CRTSH_SEGUNDOS = 10

RESOLVERS_PUBLICOS = {
    "google": "8.8.8.8",
    "cloudflare": "1.1.1.1",
    "quad9": "9.9.9.9",
    "opendns": "208.67.222.222",
}


def whoisLookup(dominio):
    dominio = dominio.strip()
    if not dominio:
        raise ValueError("Indica un dominio")
    try:
        datos = whois.whois(dominio)
    except Exception as error:
        raise ValueError(f"No se pudo consultar el WHOIS: {error}")
    if not datos or not datos.get("domain_name"):
        raise ValueError("No se encontraron datos WHOIS para ese dominio")
    return {
        "dominio": dominio,
        "registrador": datos.get("registrar"),
        "fechaCreacion": str(datos.get("creation_date")),
        "fechaExpiracion": str(datos.get("expiration_date")),
        "servidoresNombre": datos.get("name_servers"),
        "estado": datos.get("status"),
    }


def dnsLookup(dominio, tipoRegistro):
    dominio = dominio.strip()
    tipoRegistro = tipoRegistro.upper()
    if not dominio:
        raise ValueError("Indica un dominio")
    if tipoRegistro not in TIPOS_REGISTRO_SOPORTADOS:
        raise ValueError(f"Tipo de registro no soportado: {tipoRegistro}")
    try:
        respuestas = dns.resolver.resolve(dominio, tipoRegistro)
    except dns.resolver.NXDOMAIN:
        raise ValueError("El dominio no existe")
    except dns.resolver.NoAnswer:
        return {"dominio": dominio, "tipoRegistro": tipoRegistro, "registros": []}
    except dns.exception.DNSException as error:
        raise ValueError(f"Error DNS: {error}")

    registros = [respuesta.to_text() for respuesta in respuestas]
    return {"dominio": dominio, "tipoRegistro": tipoRegistro, "registros": registros}


def reverseDnsLookup(ip):
    ip = ip.strip()
    if not ip:
        raise ValueError("Indica una IP")
    try:
        nombreHost, _, _ = socket.gethostbyaddr(ip)
        return {"ip": ip, "nombreHost": nombreHost}
    except socket.herror:
        raise ValueError("No se encontro registro PTR para esa IP")
    except socket.gaierror as error:
        raise ValueError(f"IP invalida: {error}")


def geolocalizarIp(ip):
    ip = ip.strip()
    if not ip:
        raise ValueError("Indica una IP")
    url = f"{Config.geolocalizacionUrl}{ip}?fields=status,message,country,regionName,city,lat,lon,isp,org,as,query"
    try:
        with urllib.request.urlopen(url, timeout=Config.osintTimeoutSegundos) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except Exception as error:
        raise ValueError(f"No se pudo consultar la geolocalizacion: {error}")

    if datos.get("status") != "success":
        raise ValueError(datos.get("message", "No se pudo geolocalizar la IP"))

    return {
        "ip": datos.get("query"),
        "pais": datos.get("country"),
        "region": datos.get("regionName"),
        "ciudad": datos.get("city"),
        "latitud": datos.get("lat"),
        "longitud": datos.get("lon"),
        "isp": datos.get("isp"),
        "organizacion": datos.get("org"),
        "asn": datos.get("as"),
    }


def _juntarRegistroTxt(respuestaTxt):
    return "".join(parte.decode("utf-8") if isinstance(parte, bytes) else parte for parte in respuestaTxt.strings)


def comprobarSpf(dominio):
    dominio = dominio.strip()
    if not dominio:
        raise ValueError("Indica un dominio")
    try:
        respuestas = dns.resolver.resolve(dominio, "TXT")
    except dns.resolver.NXDOMAIN:
        raise ValueError("El dominio no existe")
    except dns.resolver.NoAnswer:
        return {"dominio": dominio, "spfEncontrado": False, "registro": None}
    except dns.exception.DNSException as error:
        raise ValueError(f"Error DNS: {error}")

    registrosSpf = [_juntarRegistroTxt(r) for r in respuestas if _juntarRegistroTxt(r).lower().startswith("v=spf1")]
    if not registrosSpf:
        return {"dominio": dominio, "spfEncontrado": False, "registro": None}
    return {"dominio": dominio, "spfEncontrado": True, "registro": registrosSpf[0]}


def comprobarDkim(dominio, selector):
    dominio = dominio.strip()
    selector = (selector or "default").strip()
    if not dominio:
        raise ValueError("Indica un dominio")
    if not selector:
        raise ValueError("Indica un selector DKIM")

    nombreConsulta = f"{selector}._domainkey.{dominio}"
    try:
        respuestas = dns.resolver.resolve(nombreConsulta, "TXT")
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return {"dominio": dominio, "selector": selector, "dkimEncontrado": False, "registro": None}
    except dns.exception.DNSException as error:
        raise ValueError(f"Error DNS: {error}")

    return {"dominio": dominio, "selector": selector, "dkimEncontrado": True, "registro": _juntarRegistroTxt(respuestas[0])}


def comprobarDmarc(dominio):
    dominio = dominio.strip()
    if not dominio:
        raise ValueError("Indica un dominio")

    nombreConsulta = f"_dmarc.{dominio}"
    try:
        respuestas = dns.resolver.resolve(nombreConsulta, "TXT")
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return {"dominio": dominio, "dmarcEncontrado": False, "registro": None}
    except dns.exception.DNSException as error:
        raise ValueError(f"Error DNS: {error}")

    registrosDmarc = [_juntarRegistroTxt(r) for r in respuestas if _juntarRegistroTxt(r).lower().startswith("v=dmarc1")]
    if not registrosDmarc:
        return {"dominio": dominio, "dmarcEncontrado": False, "registro": None}
    return {"dominio": dominio, "dmarcEncontrado": True, "registro": registrosDmarc[0]}


def buscarAsn(ip):
    ip = ip.strip()
    if not ip:
        raise ValueError("Indica una IP")
    url = f"{Config.geolocalizacionUrl}{ip}?fields=status,message,as,asname,isp,org,query"
    try:
        with urllib.request.urlopen(url, timeout=Config.osintTimeoutSegundos) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except Exception as error:
        raise ValueError(f"No se pudo consultar el ASN: {error}")

    if datos.get("status") != "success":
        raise ValueError(datos.get("message", "No se pudo obtener el ASN"))

    return {
        "ip": datos.get("query"),
        "asn": datos.get("as"),
        "nombreAsn": datos.get("asname"),
        "isp": datos.get("isp"),
        "organizacion": datos.get("org"),
    }


def esIpCloudflare(ip):
    ip = ip.strip()
    if not ip:
        raise ValueError("Indica una IP")
    try:
        direccion = ipaddress.ip_address(ip)
    except ValueError:
        raise ValueError("Direccion IP invalida")

    rangos = RANGOS_CLOUDFLARE_IPV4 if direccion.version == 4 else RANGOS_CLOUDFLARE_IPV6
    for rango in rangos:
        if direccion in ipaddress.ip_network(rango):
            return {"ip": ip, "esCloudflare": True, "rango": rango}
    return {"ip": ip, "esCloudflare": False, "rango": None}


def buscarSubdominios(dominio):
    dominio = dominio.strip().lower()
    if not dominio:
        raise ValueError("Indica un dominio")

    url = f"https://crt.sh/?q=%25.{urllib.parse.quote(dominio)}&output=json"
    peticion = urllib.request.Request(url, headers={"User-Agent": "WebTools-SubdomainFinder/1.0"})
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT_CRTSH_SEGUNDOS) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except Exception as error:
        raise ValueError(f"No se pudo consultar crt.sh: {error}")

    subdominios = set()
    for entrada in datos:
        for linea in entrada.get("name_value", "").split("\n"):
            linea = linea.strip().lower()
            if linea and linea.endswith(dominio):
                subdominios.add(linea)

    return {"dominio": dominio, "totalEncontrados": len(subdominios), "subdominios": sorted(subdominios)}


def comprobarPropagacionDns(dominio, tipoRegistro):
    dominio = dominio.strip()
    tipoRegistro = tipoRegistro.upper()
    if not dominio:
        raise ValueError("Indica un dominio")
    if tipoRegistro not in TIPOS_REGISTRO_SOPORTADOS:
        raise ValueError(f"Tipo de registro no soportado: {tipoRegistro}")

    resultadosPorResolver = {}
    for nombreResolver, ipResolver in RESOLVERS_PUBLICOS.items():
        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = [ipResolver]
        resolver.timeout = Config.osintTimeoutSegundos
        resolver.lifetime = Config.osintTimeoutSegundos
        try:
            respuestas = resolver.resolve(dominio, tipoRegistro)
            resultadosPorResolver[nombreResolver] = sorted(respuesta.to_text() for respuesta in respuestas)
        except dns.resolver.NXDOMAIN:
            resultadosPorResolver[nombreResolver] = []
        except dns.exception.DNSException as error:
            resultadosPorResolver[nombreResolver] = [f"error: {error}"]

    valoresConExito = [tuple(valor) for valor in resultadosPorResolver.values() if valor and not str(valor[0]).startswith("error:")]
    propagado = len(set(valoresConExito)) <= 1 and len(valoresConExito) == len(RESOLVERS_PUBLICOS)

    return {"dominio": dominio, "tipoRegistro": tipoRegistro, "resultadosPorResolver": resultadosPorResolver, "propagado": propagado}
