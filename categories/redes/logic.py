import ipaddress
import random


def ipADecimal(ip):
    try:
        return {"ip": ip, "decimal": int(ipaddress.IPv4Address(ip))}
    except ipaddress.AddressValueError as error:
        raise ValueError(f"IP invalida: {error}")


def decimalAIp(decimal):
    try:
        decimal = int(decimal)
        return {"decimal": decimal, "ip": str(ipaddress.IPv4Address(decimal))}
    except (ValueError, ipaddress.AddressValueError):
        raise ValueError("Valor decimal invalido para una IPv4")


def calcularSubred(cidr):
    try:
        red = ipaddress.ip_network(cidr, strict=False)
    except ValueError as error:
        raise ValueError(f"CIDR invalido: {error}")

    hosts = list(red.hosts())
    return {
        "direccionRed": str(red.network_address),
        "mascara": str(red.netmask),
        "broadcast": str(red.broadcast_address),
        "prefijo": red.prefixlen,
        "numHostsUtilizables": max(red.num_addresses - 2, 0) if red.version == 4 else red.num_addresses,
        "primerHost": str(hosts[0]) if hosts else None,
        "ultimoHost": str(hosts[-1]) if hosts else None,
        "version": red.version,
    }


def validarIp(ip):
    try:
        direccion = ipaddress.ip_address(ip)
        return {"ip": ip, "valida": True, "version": direccion.version, "privada": direccion.is_private}
    except ValueError:
        return {"ip": ip, "valida": False, "version": None, "privada": None}


def calcularWildcard(cidr):
    try:
        red = ipaddress.ip_network(cidr, strict=False)
    except ValueError as error:
        raise ValueError(f"CIDR invalido: {error}")
    wildcard = ipaddress.IPv4Address(int(red.hostmask))
    return {"cidr": str(red), "mascara": str(red.netmask), "wildcard": str(wildcard)}


def generarMacAleatoria():
    octetos = [0x02, random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)]
    mac = ":".join(f"{octeto:02x}" for octeto in octetos)
    return {"mac": mac}


def ipv4AIpv6(ipv4):
    try:
        direccion = ipaddress.IPv4Address(ipv4)
    except ipaddress.AddressValueError as error:
        raise ValueError(f"IPv4 invalida: {error}")
    mapeada = ipaddress.IPv6Address(f"::ffff:{direccion}")
    return {"ipv4": str(direccion), "ipv6": str(mapeada)}


def ipv6AIpv4(ipv6):
    try:
        direccion = ipaddress.IPv6Address(ipv6)
    except ipaddress.AddressValueError as error:
        raise ValueError(f"IPv6 invalida: {error}")
    if direccion.ipv4_mapped is None:
        raise ValueError("La direccion IPv6 no es una direccion mapeada IPv4 (::ffff:a.b.c.d)")
    return {"ipv6": str(direccion), "ipv4": str(direccion.ipv4_mapped)}
