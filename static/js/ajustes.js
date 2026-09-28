document.addEventListener("DOMContentLoaded", () => {
    prepararRecargaDeHerramientas();
    prepararActualizacionDeLaApp();
    prepararActualizacionCompleta();
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
    const botonCompleta = document.getElementById("botonActualizacionCompleta");
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
        botonCompleta.hidden = botonActualizar.hidden;

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
            mensaje += ` No se puede actualizar desde aqui: ${info.motivoNoAplicar} Actualiza en el servidor con ./docker-update.sh (Docker) o ./install.sh --actualizar (systemd).`;
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
                    "Esto solo trae el codigo: si la version trae dependencias nuevas o una ruta API nueva, " +
                    'hace falta reconstruir y reiniciar. Usa "Actualizacion completa" para que lo haga el ' +
                    "vigilante del servidor, o hazlo tu con ./docker-update.sh o ./install.sh --actualizar.",
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

/* --- actualizacion completa: senial + vigilante en el host ---------------------------- */
//
// Este boton no hace el pull el mismo (la app no puede reconstruirse ni reiniciarse a si
// misma sin matarse a mitad de la operacion): solo pide que se apunte la senial y luego hace
// polling del estado hasta que el vigilante del host (tools/actualizador/) la recoge y
// ejecuta docker-update.sh o install.sh --actualizar.

function prepararActualizacionCompleta() {
    const boton = document.getElementById("botonActualizacionCompleta");
    const estado = document.getElementById("estadoActualizacionCompleta");
    const log = document.getElementById("logActualizacionCompleta");
    if (!boton) {
        return;
    }

    const INTERVALO_POLLING_MS = 4000;
    let temporizador = null;

    function detenerPolling() {
        if (temporizador) {
            clearInterval(temporizador);
            temporizador = null;
        }
    }

    function ocultarLog() {
        log.hidden = true;
        log.textContent = "";
    }

    function pintarPanel(panel) {
        estado.hidden = false;

        if (panel.enMarcha) {
            boton.disabled = true;
            ocultarLog();
            const desde = panel.solicitadaHaceSegundos != null ? ` (hace ${panel.solicitadaHaceSegundos}s)` : "";
            let mensaje = `Actualizacion completa en marcha${desde}: reconstruyendo y comprobando que arranca...`;
            if (!panel.vigilanteVisto) {
                mensaje += " El vigilante no ha dado senales de vida todavia: si tarda mucho, puede que " +
                    "no este instalado (sudo ./tools/actualizador/instalar-vigilante.sh en el servidor).";
            }
            pintarEstado(estado, mensaje, false);
            return;
        }

        detenerPolling();
        boton.disabled = false;

        if (!panel.vigilanteVisto) {
            ocultarLog();
            pintarEstado(
                estado,
                "El vigilante no esta instalado, o lleva mas de 5 minutos sin dar senales: ejecuta " +
                    "sudo ./tools/actualizador/instalar-vigilante.sh en el servidor para que este boton funcione.",
                true,
            );
            return;
        }

        if (!panel.ultimoResultado) {
            estado.hidden = true;
            ocultarLog();
            return;
        }

        const ok = panel.ultimoResultado.estado === "ok";
        pintarEstado(
            estado,
            `${ok ? "Actualizacion completa correcta" : "La actualizacion completa fallo"} a las ${panel.ultimoResultado.actualizadoEn}.`,
            !ok,
        );

        if (panel.ultimoResultado.salida) {
            log.textContent = panel.ultimoResultado.salida;
            log.hidden = false;
        } else {
            ocultarLog();
        }
    }

    async function consultarPanel() {
        const { cuerpo, error } = await pedirJson(boton.dataset.estadoUrl);
        if (!cuerpo) {
            detenerPolling();
            boton.disabled = false;
            pintarEstado(estado, error || "No se pudo consultar el estado de la actualizacion", true);
            return;
        }
        pintarPanel(cuerpo);
    }

    boton.addEventListener("click", async () => {
        boton.disabled = true;
        estado.hidden = false;
        pintarEstado(estado, "Pidiendo la actualizacion completa...", false);

        const { cuerpo, error } = await pedirJson(boton.dataset.apiUrl, { method: "POST" });
        if (!cuerpo || cuerpo.enMarcha === undefined) {
            boton.disabled = false;
            pintarEstado(estado, error || "No se pudo pedir la actualizacion completa", true);
            return;
        }

        pintarPanel(cuerpo);
        if (cuerpo.enMarcha) {
            detenerPolling();
            temporizador = setInterval(consultarPanel, INTERVALO_POLLING_MS);
        }
    });
}
