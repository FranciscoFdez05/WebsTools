import importlib
import re
from datetime import datetime

# registro central de categorias, usado por la pantalla principal y por los ajustes
CATEGORIAS = [
    {"slug": "archivos", "blueprint": "archivos", "nombre": "Analisis Archivos", "descripcion": "Hashes, metadatos, entropia y tipo real de archivo"},
    {"slug": "criptografia", "blueprint": "criptografia", "nombre": "Criptografia", "descripcion": "Claves RSA/AES, cifrado, JWT, certificados"},
    {"slug": "osint", "blueprint": "osint", "nombre": "OSINT", "descripcion": "WHOIS, DNS, geolocalizacion, subdominios"},
    {"slug": "redes", "blueprint": "redes", "nombre": "Redes", "descripcion": "Subredes, CIDR, validacion IP, direcciones MAC"},
    {"slug": "utilidades", "blueprint": "utilidades", "nombre": "Utilidades", "descripcion": "Conversores, generadores y herramientas varias"},
    {"slug": "texto", "blueprint": "texto", "nombre": "Texto", "descripcion": "Codificacion, generadores y comparador de texto"},
    {"slug": "json-prog", "blueprint": "json_prog", "nombre": "JSON y Programacion", "descripcion": "Formateo y validacion de JSON, XML, HTML, CSS, JS"},
]


def _modulo(categoria, sufijo):
    return importlib.import_module(f"categories.{categoria['blueprint']}.{sufijo}")


def obtenerCatalogo():
    """Herramientas registradas ahora mismo por categoria, leyendo el TOOLS de cada modulo."""
    catalogo = []
    for categoria in CATEGORIAS:
        tools = getattr(_modulo(categoria, "routes"), "TOOLS", {})
        catalogo.append({
            "slug": categoria["slug"],
            "nombre": categoria["nombre"],
            "herramientas": len(tools),
            "slugs": sorted(tools),
        })
    return catalogo


def nombreCategoria(slug):
    """Nombre legible de una categoria a partir de su slug, para cabeceras y enlaces."""
    for categoria in CATEGORIAS:
        if categoria["slug"] == slug:
            return categoria["nombre"]
    return slug


def obtenerHerramientas():
    """Todas las herramientas de todas las categorias en una lista plana.

    La usa el buscador de la pantalla principal, que necesita nombre, descripcion y a que
    categoria pertenece cada herramienta para poder filtrarlas y enlazarlas.
    """
    herramientas = []
    for categoria in CATEGORIAS:
        tools = getattr(_modulo(categoria, "routes"), "TOOLS", {})
        for slug, tool in sorted(tools.items(), key=lambda par: par[1]["nombre"].lower()):
            herramientas.append({
                "slug": slug,
                "nombre": tool["nombre"],
                "descripcion": tool["descripcion"],
                "categoriaSlug": categoria["slug"],
                "categoriaNombre": categoria["nombre"],
                "blueprint": categoria["blueprint"],
            })
    return herramientas


def recargarHerramientas():
    """Relee desde disco el TOOLS de cada categoria sin reiniciar el servidor.

    importlib.reload reutiliza el diccionario de globales del modulo, asi que las vistas
    que Flask ya tiene registradas ven el TOOLS nuevo: editar nombres, descripciones o
    campos de una herramienta se refleja al instante. Anadir una herramienta con una ruta
    API nueva si exige reiniciar, porque Flask no admite registrar vistas despues de arrancar.
    """
    anterior = {entrada["slug"]: set(entrada["slugs"]) for entrada in obtenerCatalogo()}
    errores = []

    for categoria in CATEGORIAS:
        # logic primero: el TOOLS de routes usa constantes de logic al construirse
        for sufijo in ("logic", "routes"):
            try:
                importlib.reload(_modulo(categoria, sufijo))
            except Exception as error:
                # recargar modulos ejecuta codigo arbitrario del disco: se informa del fallo
                # y se sigue con el resto de categorias en vez de tumbar la peticion
                errores.append({
                    "categoria": categoria["slug"],
                    "modulo": sufijo,
                    "error": f"{type(error).__name__}: {error}",
                })
                break

    catalogo = obtenerCatalogo()
    for entrada in catalogo:
        previas = anterior.get(entrada["slug"], set())
        actuales = set(entrada["slugs"])
        entrada["nuevas"] = sorted(actuales - previas)
        entrada["eliminadas"] = sorted(previas - actuales)

    return {
        "actualizado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "totalHerramientas": sum(entrada["herramientas"] for entrada in catalogo),
        "categorias": catalogo,
        "errores": errores,
    }


# pista entre parentesis al final de una etiqueta: "CIDR (ej. 192.168.1.0/24)", "Longitud (4-128)"
_PISTA_ETIQUETA = re.compile(r"^(?P<etiqueta>.+?)\s*\((?P<pista>[^()]+)\)\s*$")
_MARCA_EJEMPLO = re.compile(r"^(ej\.|ej:|ejemplo:?)\s*", re.IGNORECASE)


def normalizarCampos(campos):
    """Completa los campos de una herramienta con lo que necesita el formulario.

    Cada herramienta declara lo minimo (nombre, tipo, etiqueta) y suele meter la pista dentro
    de la propia etiqueta. Aqui se separa: los ejemplos pasan a placeholder y el resto a texto
    de ayuda bajo el campo, para que la etiqueta quede corta y legible. Una herramienta de un
    solo campo lo marca obligatorio, igual que cualquier campo de archivo; los demas pueden
    declararlo con "requerido": True. Lo que declara la herramienta manda sobre lo deducido.
    """
    normalizados = []
    for campo in campos:
        normalizado = dict(campo)
        etiqueta = normalizado.get("etiqueta", normalizado["nombre"])

        coincidencia = _PISTA_ETIQUETA.match(etiqueta)
        if coincidencia:
            pista = coincidencia.group("pista").strip()
            if _MARCA_EJEMPLO.match(pista):
                normalizado.setdefault("placeholder", _MARCA_EJEMPLO.sub("", pista))
            else:
                normalizado.setdefault("ayuda", pista)
            etiqueta = coincidencia.group("etiqueta").strip()

        normalizado["etiqueta"] = etiqueta
        # un archivo siempre hace falta (las rutas responden "Falta el archivo" si no llega) y
        # una herramienta de un solo campo no puede ejecutarse vacia
        normalizado.setdefault("requerido", len(campos) == 1 or normalizado.get("tipo") == "file")
        normalizados.append(normalizado)
    return normalizados
