// Ejecucion y presentacion de una herramienta.
//
// Las APIs devuelven JSON plano (o un archivo). En vez de volcar el JSON tal cual, aqui se
// pinta como fichas legibles -claves como etiquetas, listas de objetos como tablas, booleanos
// como insignias y textos largos en bloques monoespaciados- con el JSON crudo siempre a un
// clic para quien lo prefiera, y con copiar/guardar sobre el resultado completo.

const LIMITE_TEXTO_EN_LINEA = 90;
const MAX_FILAS_TABLA = 250;

// siglas que quedan feas al capitalizarlas como una palabra normal
const SIGLAS = {
    md5: "MD5", sha1: "SHA1", sha256: "SHA256", sha512: "SHA512", crc32: "CRC32",
    ip: "IP", ipv4: "IPv4", ipv6: "IPv6", mac: "MAC", cidr: "CIDR", asn: "ASN", ttl: "TTL",
    dns: "DNS", spf: "SPF", dkim: "DKIM", dmarc: "DMARC", url: "URL", uri: "URI", id: "ID",
    api: "API", jwt: "JWT", hmac: "HMAC", rsa: "RSA", aes: "AES", pem: "PEM", exif: "EXIF",
    qr: "QR", pdf: "PDF", html: "HTML", css: "CSS", js: "JS", xml: "XML", json: "JSON",
    utc: "UTC", iso: "ISO", pe: "PE", sqlite: "SQLite", whois: "WHOIS",
};

document.addEventListener("DOMContentLoaded", () => {
    const formulario = document.getElementById("formHerramienta");
    if (!formulario) {
        return;
    }

    const panel = document.getElementById("panelResultado");
    const cuerpo = document.getElementById("cuerpoResultado");
    const estado = document.getElementById("estadoResultado");
    const botonEnviar = formulario.querySelector('button[type="submit"]');
    const botonLimpiar = document.getElementById("botonLimpiar");
    const botonVista = document.getElementById("botonVista");
    const botonCopiar = document.getElementById("botonCopiar");
    const botonDescargar = document.getElementById("botonDescargar");

    let ultimaRespuesta = null;
    let vistaJson = false;
    let urlDescargaActiva = null;

    // --- estado del panel -------------------------------------------------

    function marcarEstado(texto, modificador) {
        estado.textContent = texto;
        estado.className = modificador ? `estadoResultado estadoResultado--${modificador}` : "estadoResultado";
    }

    function mostrarAcciones(visible) {
        [botonVista, botonCopiar, botonDescargar].forEach((boton) => {
            boton.hidden = !visible;
        });
    }

    function liberarDescarga() {
        if (urlDescargaActiva) {
            URL.revokeObjectURL(urlDescargaActiva);
            urlDescargaActiva = null;
        }
    }

    function pintar(...nodos) {
        cuerpo.replaceChildren(...nodos);
    }

    function reiniciarPanel() {
        liberarDescarga();
        ultimaRespuesta = null;
        vistaJson = false;
        botonVista.textContent = "Ver JSON";
        mostrarAcciones(false);
        pintar(crearElemento("p", "vacioResultado", "Los resultados apareceran aqui."));
        marcarEstado("Sin ejecutar", "");
    }

    // --- validacion -------------------------------------------------------

    function marcarErrorCampo(control, mensaje) {
        const contenedor = control.closest(".campoFormulario");
        const aviso = contenedor ? contenedor.querySelector(".errorCampo") : null;
        if (!aviso) {
            return;
        }
        contenedor.classList.toggle("campoFormulario--error", Boolean(mensaje));
        aviso.textContent = mensaje;
        aviso.hidden = !mensaje;
    }

    function validarCampos() {
        let primerFallo = null;
        formulario.querySelectorAll("[data-requerido]").forEach((control) => {
            const vacio = control.type === "file" ? control.files.length === 0 : control.value.trim() === "";
            marcarErrorCampo(control, vacio ? "Este campo es obligatorio" : "");
            if (vacio && !primerFallo) {
                primerFallo = control;
            }
        });

        if (primerFallo) {
            primerFallo.focus();
            marcarEstado("Faltan campos obligatorios", "error");
        }
        return primerFallo === null;
    }

    // --- peticion ---------------------------------------------------------

    // los campos vacios no se envian: asi el servidor aplica el valor por defecto declarado en
    // su ruta en vez de recibir una cadena vacia
    function construirPeticion() {
        const datosFormulario = new FormData(formulario);
        const tieneArchivos = formulario.querySelector('input[type="file"]') !== null;

        if (tieneArchivos) {
            Array.from(datosFormulario.entries()).forEach(([clave, valor]) => {
                if (typeof valor === "string" && valor === "") {
                    datosFormulario.delete(clave);
                }
            });
            return { body: datosFormulario };
        }

        const datos = {};
        datosFormulario.forEach((valor, clave) => {
            if (valor !== "") {
                datos[clave] = valor;
            }
        });
        return { headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos) };
    }

    function bloquear(activo) {
        botonEnviar.disabled = activo;
        botonLimpiar.disabled = activo;
        botonEnviar.textContent = activo ? "Ejecutando..." : "Ejecutar";
        panel.classList.toggle("panelResultado--cargando", activo);
    }

    formulario.addEventListener("submit", async (evento) => {
        evento.preventDefault();
        if (!validarCampos()) {
            return;
        }

        bloquear(true);
        marcarEstado("Ejecutando...", "cargando");
        const inicio = performance.now();

        try {
            const respuesta = await fetch(formulario.dataset.apiUrl, {
                method: "POST",
                ...construirPeticion(),
            });
            await procesarRespuesta(respuesta, Math.round(performance.now() - inicio));
        } catch (error) {
            mostrarAcciones(false);
            pintar(crearAviso("No se pudo contactar con el servidor", error.message));
            marcarEstado("Sin conexion", "error");
        } finally {
            bloquear(false);
        }
    });

    async function procesarRespuesta(respuesta, duracion) {
        const tipoContenido = respuesta.headers.get("Content-Type") || "";

        if (tipoContenido.includes("application/json")) {
            const datos = await respuesta.json();
            guardarRespuesta(datos);
            if (respuesta.ok) {
                dibujarCuerpo();
                marcarEstado(`OK - ${duracion} ms`, "ok");
            } else {
                pintar(crearAviso(tituloDeEstado(respuesta.status), datos.error || mensajeDeEstado(respuesta.status)));
                marcarEstado(`Error ${respuesta.status} - ${duracion} ms`, "error");
            }
            return;
        }

        // el limitador de peticiones y los errores de Flask responden con HTML, no con JSON
        if (!respuesta.ok) {
            mostrarAcciones(false);
            pintar(crearAviso(tituloDeEstado(respuesta.status), mensajeDeEstado(respuesta.status)));
            marcarEstado(`Error ${respuesta.status} - ${duracion} ms`, "error");
            return;
        }

        await pintarDescarga(respuesta, duracion);
    }

    async function pintarDescarga(respuesta, duracion) {
        const disposicion = respuesta.headers.get("Content-Disposition") || "";
        const coincidencia = disposicion.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
        const nombreArchivo = coincidencia ? decodeURIComponent(coincidencia[1]) : "archivo-descargado";
        const blob = await respuesta.blob();

        liberarDescarga();
        ultimaRespuesta = null;
        mostrarAcciones(false);
        urlDescargaActiva = URL.createObjectURL(blob);
        lanzarDescarga(urlDescargaActiva, nombreArchivo);

        const tarjeta = crearElemento("div", "tarjetaArchivo");
        tarjeta.appendChild(crearElemento("p", "tituloArchivo", "Archivo generado y descargado"));
        tarjeta.appendChild(crearListaDatos({
            nombre: nombreArchivo,
            tamano: formatearTamano(blob.size),
            tipo: blob.type || "desconocido",
        }));

        if (blob.type.startsWith("image/")) {
            const imagen = document.createElement("img");
            imagen.className = "previsualizacionArchivo";
            imagen.src = urlDescargaActiva;
            imagen.alt = `Previsualizacion de ${nombreArchivo}`;
            tarjeta.appendChild(imagen);
        }

        const enlace = crearElemento("a", "botonSecundario botonSecundario--pequeno", "Descargar de nuevo");
        enlace.href = urlDescargaActiva;
        enlace.download = nombreArchivo;
        tarjeta.appendChild(enlace);

        pintar(tarjeta);
        marcarEstado(`Archivo listo - ${duracion} ms`, "ok");
    }

    // --- pintado del resultado -------------------------------------------

    function guardarRespuesta(datos) {
        ultimaRespuesta = { valor: datos, texto: JSON.stringify(datos, null, 2) };
        vistaJson = false;
        botonVista.textContent = "Ver JSON";
        mostrarAcciones(true);
    }

    function dibujarCuerpo() {
        if (!ultimaRespuesta) {
            return;
        }
        if (vistaJson) {
            pintar(crearElemento("pre", "bloqueTexto bloqueJson", ultimaRespuesta.texto));
            return;
        }
        pintar(crearValor(ultimaRespuesta.valor));
    }

    // --- acciones ---------------------------------------------------------

    botonVista.addEventListener("click", () => {
        vistaJson = !vistaJson;
        botonVista.textContent = vistaJson ? "Ver resultado" : "Ver JSON";
        dibujarCuerpo();
    });

    botonCopiar.addEventListener("click", async () => {
        if (!ultimaRespuesta) {
            return;
        }
        const copiado = await copiarTexto(ultimaRespuesta.texto);
        confirmarEnBoton(botonCopiar, copiado ? "Copiado" : "No se pudo copiar", "Copiar");
    });

    botonDescargar.addEventListener("click", () => {
        if (!ultimaRespuesta) {
            return;
        }
        const blob = new Blob([ultimaRespuesta.texto], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        lanzarDescarga(url, `${formulario.dataset.toolSlug}-${marcaDeTiempo()}.json`);
        URL.revokeObjectURL(url);
    });

    botonLimpiar.addEventListener("click", () => {
        formulario.reset();
        formulario.querySelectorAll(".campoFormulario--error").forEach((campo) => {
            campo.classList.remove("campoFormulario--error");
            campo.querySelector(".errorCampo").hidden = true;
        });
        formulario.querySelectorAll(".archivoElegido").forEach((etiqueta) => {
            etiqueta.textContent = "";
        });
        reiniciarPanel();
        const primero = formulario.querySelector("input, textarea, select");
        if (primero) {
            primero.focus();
        }
    });

    // clic sobre un valor para copiarlo: hashes, claves y tokens se copian de uno en uno
    cuerpo.addEventListener("click", async (evento) => {
        const objetivo = evento.target.closest(".valorDato, .bloqueTexto");
        if (!objetivo || window.getSelection().toString()) {
            return;
        }
        const copiado = await copiarTexto(objetivo.textContent);
        objetivo.classList.toggle("valorCopiado", copiado);
        setTimeout(() => objetivo.classList.remove("valorCopiado"), 900);
    });

    formulario.addEventListener("input", (evento) => {
        if (evento.target.dataset.requerido) {
            marcarErrorCampo(evento.target, "");
        }
    });

    formulario.addEventListener("change", (evento) => {
        if (evento.target.type !== "file") {
            return;
        }
        const etiqueta = formulario.querySelector(`[data-archivo-de="${evento.target.name}"]`);
        const archivo = evento.target.files[0];
        if (etiqueta) {
            etiqueta.textContent = archivo ? `${archivo.name} (${formatearTamano(archivo.size)})` : "";
        }
    });

    // Ctrl+Enter ejecuta tambien desde un textarea, donde Enter escribe una linea nueva
    formulario.addEventListener("keydown", (evento) => {
        if ((evento.ctrlKey || evento.metaKey) && evento.key === "Enter") {
            evento.preventDefault();
            formulario.requestSubmit();
        }
    });

    const primerCampo = formulario.querySelector("input, textarea, select");
    if (primerCampo) {
        primerCampo.focus({ preventScroll: true });
    }
});

// --- ayudantes de presentacion --------------------------------------------

function crearElemento(etiqueta, clase, texto) {
    const elemento = document.createElement(etiqueta);
    if (clase) {
        elemento.className = clase;
    }
    if (texto !== undefined) {
        elemento.textContent = texto;
    }
    return elemento;
}

function crearAviso(titulo, detalle) {
    const aviso = crearElemento("div", "avisoError");
    aviso.appendChild(crearElemento("p", "tituloAviso", titulo));
    if (detalle) {
        aviso.appendChild(crearElemento("p", "detalleAviso", detalle));
    }
    return aviso;
}

function humanizarClave(clave) {
    const palabras = String(clave)
        .replace(/[_-]+/g, " ")
        .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
        .toLowerCase()
        .split(/\s+/)
        .filter(Boolean);

    return palabras
        .map((palabra, indice) => {
            if (SIGLAS[palabra]) {
                return SIGLAS[palabra];
            }
            return indice === 0 ? palabra.charAt(0).toUpperCase() + palabra.slice(1) : palabra;
        })
        .join(" ");
}

function esObjetoPlano(valor) {
    return valor !== null && typeof valor === "object" && !Array.isArray(valor);
}

// un valor "de bloque" (tabla, lista, texto largo, objeto anidado) ocupa el ancho completo de
// la fila en vez de colocarse al lado de su etiqueta
function esValorDeBloque(valor) {
    if (Array.isArray(valor)) {
        return valor.length > 0;
    }
    if (esObjetoPlano(valor)) {
        return Object.keys(valor).length > 0;
    }
    return typeof valor === "string" && (valor.includes("\n") || valor.length > LIMITE_TEXTO_EN_LINEA);
}

function crearValor(valor) {
    if (valor === null || valor === undefined) {
        return crearElemento("span", "valorNulo", "sin dato");
    }
    if (typeof valor === "boolean") {
        return crearElemento("span", `insignia insignia--${valor ? "si" : "no"}`, valor ? "Si" : "No");
    }
    if (typeof valor === "number") {
        return crearElemento("span", "valorDato valorDato--numero", String(valor));
    }
    if (Array.isArray(valor)) {
        return crearLista(valor);
    }
    if (typeof valor === "object") {
        return crearListaDatos(valor);
    }
    return crearTexto(String(valor));
}

function crearTexto(texto) {
    if (texto === "") {
        return crearElemento("span", "valorNulo", "vacio");
    }

    if (/^https?:\/\/\S+$/i.test(texto)) {
        const enlace = crearElemento("a", "enlaceValor", texto);
        enlace.href = texto;
        enlace.target = "_blank";
        enlace.rel = "noopener noreferrer";
        return enlace;
    }

    if (texto.includes("\n") || texto.length > LIMITE_TEXTO_EN_LINEA) {
        const bloque = crearElemento("pre", "bloqueTexto", texto);
        bloque.title = "Clic para copiar";
        return bloque;
    }

    const valor = crearElemento("span", "valorDato", texto);
    valor.title = "Clic para copiar";
    return valor;
}

function crearLista(lista) {
    if (lista.length === 0) {
        return crearElemento("span", "valorNulo", "sin resultados");
    }
    if (lista.every(esObjetoPlano)) {
        return crearTabla(lista);
    }

    const listaHtml = crearElemento("ul", "listaValores");
    lista.forEach((elemento) => {
        const item = document.createElement("li");
        item.appendChild(crearValor(elemento));
        listaHtml.appendChild(item);
    });
    return listaHtml;
}

function crearTabla(filas) {
    const columnas = [];
    filas.forEach((fila) => {
        Object.keys(fila).forEach((columna) => {
            if (!columnas.includes(columna)) {
                columnas.push(columna);
            }
        });
    });

    const tabla = crearElemento("table", "tablaResultado");
    const cabecera = tabla.createTHead().insertRow();
    columnas.forEach((columna) => {
        const celda = document.createElement("th");
        celda.textContent = humanizarClave(columna);
        cabecera.appendChild(celda);
    });

    const cuerpoTabla = tabla.createTBody();
    filas.slice(0, MAX_FILAS_TABLA).forEach((fila) => {
        const filaHtml = cuerpoTabla.insertRow();
        columnas.forEach((columna) => {
            filaHtml.insertCell().appendChild(crearValor(fila[columna] === undefined ? null : fila[columna]));
        });
    });

    const contenedor = crearElemento("div", "contenedorTabla");
    contenedor.appendChild(tabla);
    if (filas.length > MAX_FILAS_TABLA) {
        contenedor.appendChild(crearElemento(
            "p",
            "notaTabla",
            `Mostrando ${MAX_FILAS_TABLA} de ${filas.length} filas. Usa "Ver JSON" o "Guardar .json" para el resto.`,
        ));
    }
    return contenedor;
}

function crearListaDatos(objeto) {
    const entradas = Object.entries(objeto);
    if (entradas.length === 0) {
        return crearElemento("span", "valorNulo", "sin datos");
    }

    const lista = crearElemento("dl", "listaDatos");
    entradas.forEach(([clave, valor]) => {
        const fila = crearElemento("div", esValorDeBloque(valor) ? "filaDato filaDato--bloque" : "filaDato");
        fila.appendChild(crearElemento("dt", null, humanizarClave(clave)));
        const contenido = document.createElement("dd");
        contenido.appendChild(crearValor(valor));
        fila.appendChild(contenido);
        lista.appendChild(fila);
    });
    return lista;
}

// --- ayudantes varios ------------------------------------------------------

function tituloDeEstado(codigo) {
    if (codigo === 429) {
        return "Limite de peticiones alcanzado";
    }
    if (codigo === 413) {
        return "Archivo demasiado grande";
    }
    return `La herramienta devolvio un error (${codigo})`;
}

function mensajeDeEstado(codigo) {
    const mensajes = {
        400: "La peticion no es valida: revisa los datos introducidos.",
        404: "La ruta de esta herramienta no existe. Si acabas de anadirla, reinicia la aplicacion.",
        413: "El archivo supera el tamano maximo permitido (config.ini, [app] maxUploadMb).",
        429: "Has superado el limite de peticiones por minuto. Espera un momento y vuelve a intentarlo.",
        500: "La herramienta ha fallado en el servidor. Revisa los logs del contenedor.",
    };
    return mensajes[codigo] || `El servidor respondio con el estado ${codigo}.`;
}

function formatearTamano(bytes) {
    if (bytes < 1024) {
        return `${bytes} B`;
    }
    if (bytes < 1024 * 1024) {
        return `${(bytes / 1024).toFixed(1)} KB`;
    }
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function marcaDeTiempo() {
    return new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
}

function lanzarDescarga(url, nombreArchivo) {
    const enlace = document.createElement("a");
    enlace.href = url;
    enlace.download = nombreArchivo;
    document.body.appendChild(enlace);
    enlace.click();
    enlace.remove();
}

async function copiarTexto(texto) {
    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(texto);
            return true;
        }
    } catch (error) {
        // servida por http en la LAN no hay Clipboard API: se cae al metodo antiguo
    }

    const area = document.createElement("textarea");
    area.value = texto;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    const copiado = document.execCommand("copy");
    area.remove();
    return copiado;
}

function confirmarEnBoton(boton, mensaje, textoOriginal) {
    boton.textContent = mensaje;
    boton.disabled = true;
    setTimeout(() => {
        boton.textContent = textoOriginal;
        boton.disabled = false;
    }, 1200);
}
