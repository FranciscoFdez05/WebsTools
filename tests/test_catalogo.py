import catalogo


def test_obtenerCatalogo_incluyeTodasLasCategorias():
    entradas = catalogo.obtenerCatalogo()
    assert [entrada["slug"] for entrada in entradas] == [c["slug"] for c in catalogo.CATEGORIAS]
    assert all(entrada["herramientas"] > 0 for entrada in entradas)
    assert all(len(entrada["slugs"]) == entrada["herramientas"] for entrada in entradas)


def test_recargarHerramientas_sinCambiosEnDisco():
    antes = catalogo.obtenerCatalogo()
    resultado = catalogo.recargarHerramientas()

    assert resultado["errores"] == []
    assert resultado["totalHerramientas"] == sum(entrada["herramientas"] for entrada in antes)
    assert all(entrada["nuevas"] == [] and entrada["eliminadas"] == [] for entrada in resultado["categorias"])
    assert resultado["actualizado"]


def test_recargarHerramientas_detectaHerramientaNueva(monkeypatch):
    # se anade a la copia en memoria: la recarga la borra al releer el modulo desde disco,
    # asi que debe aparecer como eliminada
    from categories.redes import routes

    monkeypatch.setitem(routes.TOOLS, "herramienta-inventada", {"nombre": "x", "descripcion": "x", "campos": []})
    resultado = catalogo.recargarHerramientas()

    redes = next(entrada for entrada in resultado["categorias"] if entrada["slug"] == "redes")
    assert redes["eliminadas"] == ["herramienta-inventada"]
    assert "herramienta-inventada" not in routes.TOOLS


def test_recargarHerramientas_informaDeModuloRoto(monkeypatch):
    def reloadQueFalla(modulo):
        raise SyntaxError("modulo invalido")

    monkeypatch.setattr(catalogo.importlib, "reload", reloadQueFalla)
    resultado = catalogo.recargarHerramientas()

    assert len(resultado["errores"]) == len(catalogo.CATEGORIAS)
    assert all(fallo["modulo"] == "logic" for fallo in resultado["errores"])
    assert "SyntaxError" in resultado["errores"][0]["error"]


def test_obtenerHerramientas_aplanaTodasLasCategorias():
    herramientas = catalogo.obtenerHerramientas()
    catalogoPorCategoria = catalogo.obtenerCatalogo()

    assert len(herramientas) == sum(entrada["herramientas"] for entrada in catalogoPorCategoria)
    assert all({"slug", "nombre", "descripcion", "categoriaSlug", "blueprint"} <= set(h) for h in herramientas)
    assert {h["categoriaSlug"] for h in herramientas} == {c["slug"] for c in catalogo.CATEGORIAS}


def test_nombreCategoria():
    assert catalogo.nombreCategoria("json-prog") == "JSON y Programacion"
    assert catalogo.nombreCategoria("inexistente") == "inexistente"


def test_normalizarCampos_separaEjemploYAyudaDeLaEtiqueta():
    campos = catalogo.normalizarCampos([
        {"nombre": "cidr", "tipo": "text", "etiqueta": "CIDR (ej. 192.168.1.0/24)"},
        {"nombre": "longitud", "tipo": "text", "etiqueta": "Longitud (4-128)"},
    ])

    assert campos[0]["etiqueta"] == "CIDR"
    assert campos[0]["placeholder"] == "192.168.1.0/24"
    assert "ayuda" not in campos[0]

    assert campos[1]["etiqueta"] == "Longitud"
    assert campos[1]["ayuda"] == "4-128"
    assert "placeholder" not in campos[1]


def test_normalizarCampos_marcaObligatorioSoloElCampoUnico():
    unico = catalogo.normalizarCampos([{"nombre": "ip", "tipo": "text", "etiqueta": "Direccion IP"}])
    varios = catalogo.normalizarCampos([
        {"nombre": "ip", "tipo": "text", "etiqueta": "IP"},
        {"nombre": "decimal", "tipo": "text", "etiqueta": "Decimal"},
    ])

    assert unico[0]["requerido"] is True
    assert [campo["requerido"] for campo in varios] == [False, False]


def test_normalizarCampos_respetaLoQueDeclaraLaHerramienta():
    campos = catalogo.normalizarCampos([
        {"nombre": "dominio", "tipo": "text", "etiqueta": "Dominio (ej. ejemplo.com)",
         "placeholder": "midominio.com", "requerido": True},
        {"nombre": "selector", "tipo": "text", "etiqueta": "Selector", "requerido": True},
    ])

    assert campos[0]["placeholder"] == "midominio.com"
    assert campos[0]["etiqueta"] == "Dominio"
    assert all(campo["requerido"] is True for campo in campos)


def test_normalizarCampos_noModificaElOriginal():
    original = [{"nombre": "ip", "tipo": "text", "etiqueta": "IP (ej. 1.1.1.1)"}]
    catalogo.normalizarCampos(original)

    assert original == [{"nombre": "ip", "tipo": "text", "etiqueta": "IP (ej. 1.1.1.1)"}]


def test_normalizarCampos_marcaObligatorioLosArchivos():
    campos = catalogo.normalizarCampos([
        {"nombre": "archivo", "tipo": "file", "etiqueta": "Archivo"},
        {"nombre": "hashEsperado", "tipo": "text", "etiqueta": "Hash esperado"},
    ])

    assert campos[0]["requerido"] is True
    assert campos[1]["requerido"] is False
