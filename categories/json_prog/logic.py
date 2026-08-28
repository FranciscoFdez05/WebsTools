import base64
import json
import xml.dom.minidom
import xml.parsers.expat

import cssbeautifier
import jsbeautifier
from bs4 import BeautifulSoup

TECNICAS_OFUSCACION_JS = ("charcode", "base64", "hexadecimal")


def formatearJson(textoJson, indentacion=4):
    try:
        datos = json.loads(textoJson)
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON invalido: {error}")
    return {"resultado": json.dumps(datos, indent=indentacion, ensure_ascii=False, sort_keys=False)}


def validarJson(textoJson):
    try:
        json.loads(textoJson)
        return {"valido": True, "error": None}
    except json.JSONDecodeError as error:
        return {"valido": False, "error": str(error)}


def minificarJson(textoJson):
    try:
        datos = json.loads(textoJson)
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON invalido: {error}")
    return {"resultado": json.dumps(datos, separators=(",", ":"), ensure_ascii=False)}


def beautifyXml(textoXml):
    if not textoXml.strip():
        raise ValueError("Indica un XML")
    try:
        dom = xml.dom.minidom.parseString(textoXml)
    except xml.parsers.expat.ExpatError as error:
        raise ValueError(f"XML invalido: {error}")
    lineas = [linea for linea in dom.toprettyxml(indent="  ").split("\n") if linea.strip()]
    return {"resultado": "\n".join(lineas)}


def beautifyHtml(textoHtml):
    if not textoHtml.strip():
        raise ValueError("Indica un HTML")
    sopa = BeautifulSoup(textoHtml, "html.parser")
    return {"resultado": sopa.prettify()}


def beautifyCss(textoCss):
    if not textoCss.strip():
        raise ValueError("Indica un CSS")
    return {"resultado": cssbeautifier.beautify(textoCss)}


def beautifyJavascript(textoJs):
    if not textoJs.strip():
        raise ValueError("Indica un JavaScript")
    return {"resultado": jsbeautifier.beautify(textoJs)}


def ofuscarJavascript(textoJs, tecnica="charcode"):
    if not textoJs.strip():
        raise ValueError("Indica un JavaScript")
    if tecnica not in TECNICAS_OFUSCACION_JS:
        raise ValueError(f"Tecnica no valida. Usa una de: {', '.join(TECNICAS_OFUSCACION_JS)}")

    if tecnica == "charcode":
        codigos = ",".join(str(ord(caracter)) for caracter in textoJs)
        resultado = f"eval(String.fromCharCode({codigos}));"
    elif tecnica == "hexadecimal":
        escapado = "".join(f"\\x{byte:02x}" for byte in textoJs.encode("utf-8"))
        resultado = f'eval(decodeURIComponent(escape("{escapado}")));'
    else:  # base64
        codificado = base64.b64encode(textoJs.encode("utf-8")).decode("ascii")
        resultado = f'eval(decodeURIComponent(escape(atob("{codificado}"))));'

    return {"resultado": resultado}
