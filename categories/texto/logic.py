import base64
import binascii
import difflib
import html
import json
import math
import random
import secrets
import string
import urllib.parse
import uuid

import zxcvbn

FORMATOS_SOPORTADOS = ("base64", "url", "html", "hex", "binario", "ascii")
VERSIONES_UUID_SOPORTADAS = ("1", "4")
SIMBOLOS_CONTRASENA = "!@#$%^&*()-_=+[]{}"

# wordlist reducida estilo diceware, embebida para no depender de descargas externas
PALABRAS_PASSPHRASE = (
    "abanico", "abrazo", "acero", "acido", "actor", "agenda", "agosto", "aguila", "aire", "alba",
    "alce", "aldea", "alga", "amigo", "ancla", "andar", "anillo", "arbol", "arco", "arena",
    "arpa", "arroz", "astro", "athon", "avion", "azul", "bache", "baile", "banco", "barco",
    "barro", "base", "bello", "besar", "beso", "bicho", "bloque", "boda", "bolsa", "bomba",
    "borde", "bosque", "botella", "brazo", "brillo", "bruma", "buho", "burro", "cable", "cabra",
    "cactus", "cafe", "caja", "calor", "calle", "cama", "campo", "canal", "canela", "cansado",
    "capa", "capital", "carbon", "carga", "carne", "carro", "casa", "cebra", "cedro", "celda",
    "cena", "centro", "cerca", "cereza", "cero", "cesta", "chispa", "cielo", "cima", "cinta",
    "circo", "clavo", "clima", "cobre", "coche", "codigo", "cofre", "cohete", "cola", "collar",
    "color", "coma", "conejo", "copa", "corcho", "coro", "corona", "correa", "corte", "costa",
    "cresta", "cristal", "cruz", "cuadro", "cubo", "cuento", "cuerda", "cueva", "curva", "danza",
    "dardo", "dedo", "delfin", "desierto", "dia", "diamante", "disco", "dolar", "dragon", "duna",
    "eco", "eje", "elefante", "enano", "enero", "escudo", "esfera", "espejo", "estrella", "faro",
    "flauta", "flecha", "flor", "fresa", "fuego", "fuente", "galleta", "ganso", "garra", "gato",
    "gaviota", "gema", "gigante", "girasol", "globo", "golpe", "grano", "grieta", "grillo", "grupo",
)


def generarUuid(version):
    version = str(version).strip()
    if version not in VERSIONES_UUID_SOPORTADAS:
        raise ValueError(f"Version de UUID no soportada: {version}. Usa 1 o 4")
    identificador = uuid.uuid1() if version == "1" else uuid.uuid4()
    return {"version": int(version), "uuid": str(identificador)}


def _esAfirmativo(valor):
    return str(valor).strip().lower() in ("si", "true", "1", "yes", "on")


def generarContrasena(longitud, incluirMayusculas, incluirMinusculas, incluirNumeros, incluirSimbolos):
    try:
        longitud = int(longitud)
    except (TypeError, ValueError):
        raise ValueError("Longitud invalida")
    if not (4 <= longitud <= 128):
        raise ValueError("La longitud debe estar entre 4 y 128")

    conjuntos = []
    if _esAfirmativo(incluirMayusculas):
        conjuntos.append(string.ascii_uppercase)
    if _esAfirmativo(incluirMinusculas):
        conjuntos.append(string.ascii_lowercase)
    if _esAfirmativo(incluirNumeros):
        conjuntos.append(string.digits)
    if _esAfirmativo(incluirSimbolos):
        conjuntos.append(SIMBOLOS_CONTRASENA)
    if not conjuntos:
        raise ValueError("Selecciona al menos un tipo de caracter")
    if longitud < len(conjuntos):
        raise ValueError("La longitud debe ser al menos igual al numero de tipos de caracter seleccionados")

    charsetCompleto = "".join(conjuntos)
    # se garantiza al menos un caracter de cada conjunto elegido, el resto se rellena y se mezcla
    caracteres = [secrets.choice(conjunto) for conjunto in conjuntos]
    caracteres += [secrets.choice(charsetCompleto) for _ in range(longitud - len(conjuntos))]
    random.SystemRandom().shuffle(caracteres)

    return {"contrasena": "".join(caracteres), "longitud": longitud}


def generarPassphrase(numPalabras, separador):
    try:
        numPalabras = int(numPalabras)
    except (TypeError, ValueError):
        raise ValueError("Numero de palabras invalido")
    if not (3 <= numPalabras <= 12):
        raise ValueError("El numero de palabras debe estar entre 3 y 12")
    separador = separador if separador else "-"

    palabras = [secrets.choice(PALABRAS_PASSPHRASE) for _ in range(numPalabras)]
    entropiaBits = round(numPalabras * math.log2(len(PALABRAS_PASSPHRASE)), 2)
    return {"passphrase": separador.join(palabras), "numPalabras": numPalabras, "entropiaBits": entropiaBits}


def comprobarFortalezaContrasena(contrasena):
    if not contrasena:
        raise ValueError("Indica una contrasena")
    # se usa la libreria zxcvbn (puerto puro Python de la libreria de Dropbox)
    resultado = zxcvbn.zxcvbn(contrasena)
    return {
        "puntuacion": resultado["score"],
        "tiempoCrackeoOffline": resultado["crack_times_display"]["offline_fast_hashing_1e10_per_second"],
        "tiempoCrackeoOnline": resultado["crack_times_display"]["online_no_throttling_10_per_second"],
        "advertencia": resultado["feedback"]["warning"] or None,
        "sugerencias": resultado["feedback"]["suggestions"],
    }


def compararTextos(textoA, textoB):
    if textoA is None or textoB is None:
        raise ValueError("Indica ambos textos a comparar")

    diferencias = list(difflib.unified_diff(textoA.splitlines(), textoB.splitlines(), lineterm=""))
    similitud = round(difflib.SequenceMatcher(None, textoA, textoB).ratio() * 100, 2)
    return {"diff": "\n".join(diferencias), "similitud": similitud, "identicos": textoA == textoB}


def codificar(texto, formato):
    formato = formato.lower()
    if formato not in FORMATOS_SOPORTADOS:
        raise ValueError(f"Formato no soportado: {formato}")

    if formato == "base64":
        resultado = base64.b64encode(texto.encode("utf-8")).decode("ascii")
    elif formato == "url":
        resultado = urllib.parse.quote(texto)
    elif formato == "html":
        resultado = html.escape(texto)
    elif formato == "hex":
        resultado = texto.encode("utf-8").hex()
    elif formato == "binario":
        resultado = " ".join(format(byte, "08b") for byte in texto.encode("utf-8"))
    elif formato == "ascii":
        resultado = " ".join(str(byte) for byte in texto.encode("utf-8"))

    return {"entrada": texto, "formato": formato, "resultado": resultado}


def decodificar(texto, formato):
    formato = formato.lower()
    if formato not in FORMATOS_SOPORTADOS:
        raise ValueError(f"Formato no soportado: {formato}")

    try:
        if formato == "base64":
            resultado = base64.b64decode(texto).decode("utf-8")
        elif formato == "url":
            resultado = urllib.parse.unquote(texto)
        elif formato == "html":
            resultado = html.unescape(texto)
        elif formato == "hex":
            resultado = bytes.fromhex(texto.replace(" ", "")).decode("utf-8")
        elif formato == "binario":
            bytesDatos = bytes(int(grupo, 2) for grupo in texto.split())
            resultado = bytesDatos.decode("utf-8")
        elif formato == "ascii":
            bytesDatos = bytes(int(codigo) for codigo in texto.split())
            resultado = bytesDatos.decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError) as error:
        raise ValueError(f"No se pudo decodificar como {formato}: {error}")

    return {"entrada": texto, "formato": formato, "resultado": resultado}


def _decodificarSegmentoJwt(segmento):
    relleno = "=" * (-len(segmento) % 4)
    datosDecodificados = base64.urlsafe_b64decode(segmento + relleno)
    return json.loads(datosDecodificados)


def decodificarJwt(token):
    token = token.strip()
    if not token:
        raise ValueError("Indica un token JWT")

    partes = token.split(".")
    if len(partes) != 3:
        raise ValueError("El token JWT debe tener 3 partes separadas por puntos")

    try:
        cabecera = _decodificarSegmentoJwt(partes[0])
        cuerpo = _decodificarSegmentoJwt(partes[1])
    except (ValueError, json.JSONDecodeError, binascii.Error) as error:
        raise ValueError(f"No se pudo decodificar el token: {error}")

    return {"cabecera": cabecera, "cuerpo": cuerpo, "firma": partes[2]}
