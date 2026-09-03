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
