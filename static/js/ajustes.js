document.addEventListener("DOMContentLoaded", () => {
    prepararRecargaDeHerramientas();
    prepararActualizacionDeLaApp();
});

// El limitador y los fallos inesperados responden {"error": ...}, y un 500 sin manejar puede
// llegar como HTML: las dos secciones necesitan distinguir esos casos de una respuesta buena.
async function pedirJson(url, opciones) {
    const respuesta = await fetch(url, opciones);
    const tipoContenido = respuesta.headers.get("Content-Type") || "";
    if (!tipoContenido.includes("application/json")) {
        return { cuerpo: null, error: `Error ${respuesta.status}: el servidor no respondio JSON` };
    }

    const cuerpo = await respuesta.json();
    if (!respuesta.ok) {
        return { cuerpo, error: cuerpo.error || `Error ${respuesta.status}` };
    }
    return { cuerpo, error: null };
}

function pintarEstado(elemento, mensaje, esError) {
    elemento.textContent = mensaje;
    elemento.classList.toggle("estadoAjustes--error", Boolean(esError));
}

/* --- recargar el catalogo de herramientas desde disco --------------------------------- */

function prepararRecargaDeHerramientas() {
    const boton = document.getElementById("botonActualizarHerramientas");
    const estado = document.getElementById("estadoHerramientas");
    const tabla = document.getElementById("tablaCatalogo");
    if (!boton) {
        return;
    }

    function pintarCatalogo(categorias) {
        categorias.forEach((entrada) => {
            const fila = tabla.querySelector(`tr[data-slug="${entrada.slug}"]`);
            if (!fila) {
                return;
            }
            fila.querySelector(".celdaTotal").textContent = entrada.herramientas;

            const cambios = [];
            if (entrada.nuevas.length) {
                cambios.push(`+ ${entrada.nuevas.join(", ")}`);
            }
            if (entrada.eliminadas.length) {
                cambios.push(`- ${entrada.eliminadas.join(", ")}`);
            }
            const celdaCambios = fila.querySelector(".celdaCambios");
            celdaCambios.textContent = cambios.length ? cambios.join(" / ") : "sin cambios";
            celdaCambios.classList.toggle("celdaCambios--activa", cambios.length > 0);
        });
        document.getElementById("totalHerramientas").textContent =
            categorias.reduce((total, entrada) => total + entrada.herramientas, 0);
    }

    // la comparte el boton de actualizar la app: tras un git pull el catalogo en disco ya es otro
    boton.pintarResultado = (cuerpo) => {
        pintarCatalogo(cuerpo.categorias);

        if (cuerpo.errores.length) {
            const detalle = cuerpo.errores
                .map((fallo) => `${fallo.categoria} (${fallo.modulo}): ${fallo.error}`)
                .join(" | ");
            pintarEstado(estado, `Actualizado con errores a las ${cuerpo.actualizado} - ${detalle}`, true);
            return;
        }
        pintarEstado(
            estado,
            `Catalogo actualizado a las ${cuerpo.actualizado}: ${cuerpo.totalHerramientas} herramientas en ${cuerpo.categorias.length} categorias.`,
            false,
        );
    };

    boton.addEventListener("click", async () => {
        boton.disabled = true;
        pintarEstado(estado, "Actualizando herramientas...", false);

        try {
            const { cuerpo, error } = await pedirJson(boton.dataset.apiUrl, { method: "POST" });
            if (!cuerpo || !cuerpo.categorias) {
                pintarEstado(estado, error || "No se pudo actualizar el catalogo", true);
                return;
            }
            boton.pintarResultado(cuerpo);
        } catch (error) {
            pintarEstado(estado, `Error de red: ${error.message}`, true);
        } finally {
            boton.disabled = false;
        }
    });
}

/* --- comprobar y aplicar la actualizacion de la aplicacion ---------------------------- */

function prepararActualizacionDeLaApp() {
    const botonComprobar = document.getElementById("botonComprobarVersion");
    const botonActualizar = document.getElementById("botonActualizarApp");
    const estado = document.getElementById("estadoVersion");
    const notas = document.getElementById("notasVersion");
    if (!botonComprobar) {
        return;
    }

    function pintarNotas(titulo, lineas, url) {
        notas.textContent = "";
        if (!lineas.length && !url) {
            notas.hidden = true;
            return;
        }

        const encabezado = document.createElement("h3");
        encabezado.className = "tituloNotas";
        encabezado.textContent = titulo;
        notas.append(encabezado);

        if (lineas.length) {
            const bloque = document.createElement("pre");
            bloque.className = "bloqueTexto bloqueNotas";
            // textContent y no innerHTML: el texto viene de la release de GitHub
            bloque.textContent = lineas.join("\n");
            notas.append(bloque);
        }

        if (url) {
            const enlace = document.createElement("a");
            enlace.className = "enlaceNotas";
            enlace.href = url;
            enlace.target = "_blank";
            enlace.rel = "noopener noreferrer";
            enlace.textContent = "Ver la release en GitHub";
            notas.append(enlace);
        }
        notas.hidden = false;
    }

    function pintarComprobacion(info) {
        botonActualizar.hidden = !(info.hayActualizacion && info.puedeAplicar);

        if (info.error) {
            pintarEstado(estado, info.error, true);
            pintarNotas("", [], info.url);
            return;
        }

        if (!info.hayActualizacion) {
            pintarEstado(estado, `Estas en la ultima version publicada (v${info.versionInstalada}).`, false);
            notas.hidden = true;
            return;
        }

        const publicada = info.publicada ? `, publicada el ${info.publicada}` : "";
        let mensaje = `Hay una version nueva: v${info.versionDisponible}${publicada}. Tienes la v${info.versionInstalada}.`;
        if (!info.puedeAplicar) {
            // sin git, con cambios locales o desactivado en config: queda el camino manual
            mensaje += ` No se puede actualizar desde aqui: ${info.motivoNoAplicar} Actualiza en el servidor con ./docker-update.sh.`;
        }
        pintarEstado(estado, mensaje, !info.puedeAplicar);
        pintarNotas(`Novedades de la v${info.versionDisponible}`, info.notas ? [info.notas] : [], info.url);
    }

    async function comprobar() {
        botonComprobar.disabled = true;
        pintarEstado(estado, "Comprobando si hay actualizaciones...", false);

        try {
            const { cuerpo, error } = await pedirJson(botonComprobar.dataset.apiUrl);
            if (!cuerpo || cuerpo.versionInstalada === undefined) {
                pintarEstado(estado, error || "No se pudo comprobar la version", true);
                return;
            }
            pintarComprobacion(cuerpo);
        } catch (error) {
            pintarEstado(estado, `Error de red: ${error.message}`, true);
        } finally {
            botonComprobar.disabled = false;
        }
    }

    async function actualizar() {
        botonActualizar.disabled = true;
        botonComprobar.disabled = true;
        pintarEstado(estado, "Trayendo los cambios desde GitHub...", false);

        try {
            const { cuerpo, error } = await pedirJson(botonActualizar.dataset.apiUrl, { method: "POST" });
            if (!cuerpo || cuerpo.aplicado === undefined) {
                pintarEstado(estado, error || "No se pudo actualizar la aplicacion", true);
                return;
            }
            if (cuerpo.error) {
                pintarEstado(estado, cuerpo.error, true);
                return;
            }

            if (!cuerpo.aplicado) {
                pintarEstado(estado, "El codigo ya estaba al dia: no habia nada que traer.", false);
                return;
            }

            botonActualizar.hidden = true;
            pintarEstado(
                estado,
                `Actualizado a las ${cuerpo.actualizado} (${cuerpo.commitAnterior} -> ${cuerpo.commitNuevo}). ` +
                    "Reinicia para que entren las rutas nuevas y la version: docker compose restart webtools. " +
                    "Si la version trae dependencias nuevas, hace falta ./docker-update.sh en el servidor.",
                false,
            );
            pintarNotas(`${cuerpo.cambios.length} commits nuevos`, cuerpo.cambios, null);

            // el pull cambia el catalogo en disco; la app ya lo ha recargado, se refleja en la tabla
            const botonHerramientas = document.getElementById("botonActualizarHerramientas");
            if (cuerpo.catalogo && botonHerramientas) {
                botonHerramientas.pintarResultado(cuerpo.catalogo);
            }
        } catch (error) {
            pintarEstado(estado, `Error de red: ${error.message}`, true);
        } finally {
            botonActualizar.disabled = false;
            botonComprobar.disabled = false;
        }
    }

    botonComprobar.addEventListener("click", comprobar);
    botonActualizar.addEventListener("click", actualizar);
    comprobar();
}
