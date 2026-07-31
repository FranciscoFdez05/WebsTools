import base64
import binascii
import datetime
import hmac
import json
import os

from cryptography import x509
from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.x509.oid import NameOID

TAMANOS_RSA = (2048, 3072, 4096)
TAMANOS_AES = (128, 192, 256)
ALGORITMOS_HMAC = ("sha256", "sha1", "sha512")

# algoritmos JWT soportados para verificacion de firma (HMAC y RSA con PKCS1v15)
ALGORITMOS_JWT_HMAC = {"HS256": "sha256", "HS384": "sha384", "HS512": "sha512"}
ALGORITMOS_JWT_RSA = {"RS256": hashes.SHA256(), "RS384": hashes.SHA384(), "RS512": hashes.SHA512()}


def generarClaveRsa(tamano):
    try:
        tamano = int(tamano)
    except (TypeError, ValueError):
        raise ValueError("Tamano de clave invalido")
    if tamano not in TAMANOS_RSA:
        raise ValueError(f"Tamano de clave no soportado: {tamano}")

    clavePrivada = rsa.generate_private_key(public_exponent=65537, key_size=tamano)
    pemPrivada = clavePrivada.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    pemPublica = clavePrivada.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    return {"tamano": tamano, "clavePrivada": pemPrivada, "clavePublica": pemPublica}


def generarClaveAes(tamano):
    try:
        tamano = int(tamano)
    except (TypeError, ValueError):
        raise ValueError("Tamano de clave invalido")
    if tamano not in TAMANOS_AES:
        raise ValueError(f"Tamano de clave no soportado: {tamano}")

    claveBytes = os.urandom(tamano // 8)
    return {"tamano": tamano, "claveBase64": base64.b64encode(claveBytes).decode("ascii"), "claveHex": claveBytes.hex()}


def _decodificarClaveAesBase64(claveBase64):
    try:
        claveBytes = base64.b64decode(claveBase64, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("Clave Base64 invalida")
    if len(claveBytes) not in (16, 24, 32):
        raise ValueError("La clave debe tener 16, 24 o 32 bytes (128/192/256 bits) tras decodificar")
    return claveBytes


def cifrarAes(texto, claveBase64):
    if not texto:
        raise ValueError("Indica un texto a cifrar")
    claveBytes = _decodificarClaveAesBase64(claveBase64)

    nonce = os.urandom(12)
    aesgcm = AESGCM(claveBytes)
    textoCifrado = aesgcm.encrypt(nonce, texto.encode("utf-8"), None)
    return {
        "nonceBase64": base64.b64encode(nonce).decode("ascii"),
        "textoCifradoBase64": base64.b64encode(textoCifrado).decode("ascii"),
    }


def descifrarAes(claveBase64, nonceBase64, textoCifradoBase64):
    claveBytes = _decodificarClaveAesBase64(claveBase64)
    try:
        nonce = base64.b64decode(nonceBase64, validate=True)
        textoCifrado = base64.b64decode(textoCifradoBase64, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("Nonce o texto cifrado en Base64 invalido")

    aesgcm = AESGCM(claveBytes)
    try:
        textoPlano = aesgcm.decrypt(nonce, textoCifrado, None)
    except InvalidTag:
        raise ValueError("No se pudo descifrar: clave, nonce o texto cifrado incorrectos")
    return {"textoPlano": textoPlano.decode("utf-8")}


def cifrarRsa(texto, clavePublicaPem):
    if not texto:
        raise ValueError("Indica un texto a cifrar")
    try:
        clavePublica = serialization.load_pem_public_key(clavePublicaPem.encode("utf-8"))
    except (ValueError, TypeError) as error:
        raise ValueError(f"Clave publica invalida: {error}")

    try:
        textoCifrado = clavePublica.encrypt(
            texto.encode("utf-8"),
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
        )
    except ValueError as error:
        raise ValueError(f"No se pudo cifrar: {error}")
    return {"textoCifradoBase64": base64.b64encode(textoCifrado).decode("ascii")}


def descifrarRsa(textoCifradoBase64, clavePrivadaPem):
    try:
        textoCifrado = base64.b64decode(textoCifradoBase64, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("Texto cifrado en Base64 invalido")
    try:
        clavePrivada = serialization.load_pem_private_key(clavePrivadaPem.encode("utf-8"), password=None)
    except (ValueError, TypeError) as error:
        raise ValueError(f"Clave privada invalida: {error}")

    try:
        textoPlano = clavePrivada.decrypt(
            textoCifrado,
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
        )
    except ValueError:
        raise ValueError("No se pudo descifrar: clave o texto cifrado incorrectos")
    return {"textoPlano": textoPlano.decode("utf-8")}


def generarHmac(texto, claveSecreta, algoritmo):
    algoritmo = algoritmo.lower()
    if algoritmo not in ALGORITMOS_HMAC:
        raise ValueError(f"Algoritmo no soportado: {algoritmo}")
    if not claveSecreta:
        raise ValueError("Indica una clave secreta")

    firma = hmac.new(claveSecreta.encode("utf-8"), texto.encode("utf-8"), algoritmo).hexdigest()
    return {"algoritmo": algoritmo, "hmac": firma}


def _decodificarSegmentoJwt(segmento):
    relleno = "=" * (-len(segmento) % 4)
    datosDecodificados = base64.urlsafe_b64decode(segmento + relleno)
    return json.loads(datosDecodificados)


def inspeccionarJwt(token, secretoOClavePublica):
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

    algoritmoToken = cabecera.get("alg", "")
    resultado = {
        "cabecera": cabecera,
        "cuerpo": cuerpo,
        "algoritmo": algoritmoToken,
        "firmaValida": None,
        "mensaje": "No se aporto clave/secreto, solo se decodifico sin verificar",
    }

    secretoOClavePublica = (secretoOClavePublica or "").strip()
    if not secretoOClavePublica:
        return resultado

    mensajeFirmado = f"{partes[0]}.{partes[1]}".encode("ascii")
    relleno = "=" * (-len(partes[2]) % 4)
    try:
        firmaBytes = base64.urlsafe_b64decode(partes[2] + relleno)
    except binascii.Error as error:
        raise ValueError(f"Firma invalida: {error}")

    if algoritmoToken in ALGORITMOS_JWT_HMAC:
        firmaEsperada = hmac.new(secretoOClavePublica.encode("utf-8"), mensajeFirmado, ALGORITMOS_JWT_HMAC[algoritmoToken]).digest()
        resultado["firmaValida"] = hmac.compare_digest(firmaEsperada, firmaBytes)
        resultado["mensaje"] = "Firma verificada con HMAC"
    elif algoritmoToken in ALGORITMOS_JWT_RSA:
        try:
            clavePublica = serialization.load_pem_public_key(secretoOClavePublica.encode("utf-8"))
        except (ValueError, TypeError) as error:
            raise ValueError(f"Clave publica invalida: {error}")
        try:
            clavePublica.verify(firmaBytes, mensajeFirmado, padding.PKCS1v15(), ALGORITMOS_JWT_RSA[algoritmoToken])
            resultado["firmaValida"] = True
            resultado["mensaje"] = "Firma verificada con RSA"
        except InvalidSignature:
            resultado["firmaValida"] = False
            resultado["mensaje"] = "Firma RSA invalida"
    else:
        resultado["mensaje"] = f"Algoritmo no soportado para verificacion de firma: {algoritmoToken}"

    return resultado


def generarCertificadoAutofirmado(nombreComun, diasValidez, tamanoClave):
    nombreComun = nombreComun.strip()
    if not nombreComun:
        raise ValueError("Indica un nombre comun (CN)")
    try:
        diasValidez = int(diasValidez)
    except (TypeError, ValueError):
        raise ValueError("Dias de validez invalidos")
    if diasValidez <= 0:
        raise ValueError("Los dias de validez deben ser mayores que 0")
    try:
        tamanoClave = int(tamanoClave)
    except (TypeError, ValueError):
        raise ValueError("Tamano de clave invalido")
    if tamanoClave not in TAMANOS_RSA:
        raise ValueError(f"Tamano de clave no soportado: {tamanoClave}")

    clavePrivada = rsa.generate_private_key(public_exponent=65537, key_size=tamanoClave)
    nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nombreComun)])
    ahora = datetime.datetime.now(datetime.timezone.utc)
    certificado = (
        x509.CertificateBuilder()
        .subject_name(nombre)
        .issuer_name(nombre)
        .public_key(clavePrivada.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ahora)
        .not_valid_after(ahora + datetime.timedelta(days=diasValidez))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(nombreComun)]), critical=False)
        .sign(clavePrivada, hashes.SHA256())
    )

    pemCertificado = certificado.public_bytes(serialization.Encoding.PEM).decode("ascii")
    pemClavePrivada = clavePrivada.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    return {
        "certificadoPem": pemCertificado,
        "clavePrivadaPem": pemClavePrivada,
        "nombreComun": nombreComun,
        "diasValidez": diasValidez,
    }
