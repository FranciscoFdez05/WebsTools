// Aviso de version nueva en la cabecera, para no tener que entrar a /ajustes a mirar.
// La comprobacion sale a GitHub, asi que el resultado se guarda una hora en el navegador:
// sin eso, cada cambio de pagina gastaria una peticion del cupo de /api/ajustes/version.
const CLAVE_CACHE = "webstools.avisoVersion";
const HORA_EN_MS = 60 * 60 * 1000;

document.addEventListener("DOMContentLoaded", () => {
    const aviso = document.getElementById("avisoActualizacion");
    if (!aviso) {
        return;
    }
    comprobar(aviso);
});

function leerCache() {
    try {
        const guardado = JSON.parse(localStorage.getItem(CLAVE_CACHE) || "null");
        if (guardado && Date.now() - guardado.momento < HORA_EN_MS) {
            return guardado;
        }
    } catch (error) {
        // localStorage puede estar bloqueado o traer basura de una version anterior:
        // no es motivo para dejar de comprobar, solo se pierde la cache
    }
    return null;
}

function guardarCache(version) {
    try {
        localStorage.setItem(CLAVE_CACHE, JSON.stringify({ momento: Date.now(), version }));
    } catch (error) {
        // navegacion privada o almacenamiento lleno: se comprobara otra vez, nada mas
    }
}

function pintar(aviso, version) {
    if (!version) {
        return;
    }
    aviso.title = `Hay una version nueva disponible: v${version}`;
    aviso.hidden = false;
}

async function comprobar(aviso) {
    const guardado = leerCache();
    if (guardado) {
        pintar(aviso, guardado.version);
        return;
    }

    try {
        const respuesta = await fetch(aviso.dataset.apiUrl);
        if (!respuesta.ok) {
            return;
        }
        const info = await respuesta.json();
        const version = info.hayActualizacion ? info.versionDisponible : null;
        guardarCache(version);
        pintar(aviso, version);
    } catch (error) {
        // sin red, o GitHub caido: el aviso simplemente no aparece. Es informativo, no
        // hay nada que contarle al usuario aqui; /ajustes si explica que ha fallado
    }
}

/* --- popup de la version en la cabecera ------------------------------------------------ */
// Comprobar es publico; "Actualizar ahora" pide la actualizacion completa (la misma que el
// boton de /ajustes), asi que puede pedir la contrasena de ajustes si esta configurada.

document.addEventListener("DOMContentLoaded", () => {
    const boton = document.getElementById("botonVersion");
    const popup = document.getElementById("popupVersion");
    if (!boton || !popup) {
        return;
    }

    const ultima = document.getElementById("popupVersionUltima");
    const etiqueta = document.getElementById("popupVersionEtiqueta");
    const estado = document.getElementById("popupVersionEstado");
    const botonActualizar = document.getElementById("popupVersionActualizar");
    const botonComprobar = document.getElementById("popupVersionComprobar");
    const INTERVALO_MS = 4000;
    let temporizador = null;
    let comprobado = false;

    function pintarEstado(mensaje, esError) {
        estado.textContent = mensaje;
        estado.classList.toggle("estadoPopupVersion--error", Boolean(esError));
    }

    function abrir(abierto) {
        popup.hidden = !abierto;
        boton.setAttribute("aria-expanded", String(abierto));
        if (abierto && !comprobado) {
            comprobar();
        }
    }

    async function pedirJson(url, opciones) {
        const respuesta = await fetch(url, opciones);
        const tipo = respuesta.headers.get("Content-Type") || "";
        if (!tipo.includes("application/json")) {
            return { cuerpo: null, error: `Error ${respuesta.status}` };
        }
        const cuerpo = await respuesta.json();
        return { cuerpo, error: respuesta.ok ? null : cuerpo.error || `Error ${respuesta.status}` };
    }

    async function comprobar() {
        botonComprobar.disabled = true;
        pintarEstado("Comprobando...", false);
        try {
            const { cuerpo, error } = await pedirJson(popup.dataset.apiUrl);
            if (!cuerpo || cuerpo.versionInstalada === undefined) {
                pintarEstado(error || "No se pudo comprobar la version", true);
                return;
            }
            comprobado = true;
            ultima.textContent = cuerpo.versionDisponible ? `v${cuerpo.versionDisponible}` : "-";
            etiqueta.hidden = Boolean(cuerpo.error);
            etiqueta.textContent = cuerpo.hayActualizacion ? "Nueva" : "Al dia";
            botonActualizar.hidden = !(cuerpo.hayActualizacion && cuerpo.puedeAplicar);

            if (cuerpo.error) {
                pintarEstado(cuerpo.error, true);
            } else if (cuerpo.hayActualizacion && !cuerpo.puedeAplicar) {
                pintarEstado(`No se puede actualizar desde aqui: ${cuerpo.motivoNoAplicar}`, true);
            } else {
                pintarEstado("", false);
            }
        } catch (error) {
            pintarEstado(`Error de red: ${error.message}`, true);
        } finally {
            botonComprobar.disabled = false;
        }
    }

    function detenerPolling() {
        if (temporizador) {
            clearInterval(temporizador);
            temporizador = null;
        }
    }

    function pintarPanel(panel) {
        if (panel.enMarcha) {
            botonActualizar.disabled = true;
            pintarEstado("Actualizando: reconstruyendo y reiniciando...", false);
            return;
        }
        detenerPolling();
        botonActualizar.disabled = false;
        if (!panel.vigilanteVisto) {
            pintarEstado("El vigilante del servidor no esta activo: ver /ajustes.", true);
        } else if (panel.ultimoResultado) {
            const ok = panel.ultimoResultado.estado === "ok";
            pintarEstado(ok ? "Actualizacion completada. Recarga la pagina." : "La actualizacion fallo: ver /ajustes.", !ok);
        }
    }

    async function consultarPanel() {
        try {
            const { cuerpo } = await pedirJson(popup.dataset.estadoUrl);
            if (cuerpo) {
                pintarPanel(cuerpo);
            }
        } catch (error) {
            // el servidor se reinicia durante la actualizacion: el siguiente intento lo resolvera
        }
    }

    async function actualizar() {
        botonActualizar.disabled = true;
        pintarEstado("Pidiendo la actualizacion...", false);
        try {
            const { cuerpo, error } = await pedirJson(popup.dataset.actualizarUrl, { method: "POST" });
            if (!cuerpo || cuerpo.enMarcha === undefined) {
                botonActualizar.disabled = false;
                pintarEstado(error || "No se pudo pedir la actualizacion", true);
                return;
            }
            pintarPanel(cuerpo);
            if (cuerpo.enMarcha) {
                detenerPolling();
                temporizador = setInterval(consultarPanel, INTERVALO_MS);
            }
        } catch (error) {
            botonActualizar.disabled = false;
            pintarEstado(`Error de red: ${error.message}`, true);
        }
    }

    boton.addEventListener("click", (evento) => {
        evento.stopPropagation();
        abrir(popup.hidden);
    });
    popup.addEventListener("click", (evento) => evento.stopPropagation());
    document.addEventListener("click", () => abrir(false));
    document.addEventListener("keydown", (evento) => {
        if (evento.key === "Escape") {
            abrir(false);
        }
    });
    botonComprobar.addEventListener("click", comprobar);
    botonActualizar.addEventListener("click", actualizar);
});
