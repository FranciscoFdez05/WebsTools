// Atajo a las ultimas herramientas abiertas. Con 65 en el catalogo, casi siempre se vuelve a
// las mismas pocas, y llegar a ellas obligaba a entrar en la categoria o a buscarlas cada vez.
// Vive entero en el navegador (localStorage): son datos de quien mira, no del servidor, y asi
// cada dispositivo de la LAN tiene los suyos sin que la app guarde nada de nadie.
const CLAVE_RECIENTES = "webstools.recientes";
const MAXIMO_RECIENTES = 6;

document.addEventListener("DOMContentLoaded", () => {
    const datos = document.getElementById("datosHerramienta");
    if (datos) {
        registrarVisita(datos.dataset);
    }

    const lista = document.getElementById("listaRecientes");
    if (lista) {
        pintarRecientes(lista);
    }
});

function leerRecientes() {
    try {
        const guardadas = JSON.parse(localStorage.getItem(CLAVE_RECIENTES) || "[]");
        return Array.isArray(guardadas) ? guardadas.filter((entrada) => entrada && entrada.url && entrada.nombre) : [];
    } catch (error) {
        return [];
    }
}

function registrarVisita({ nombre, categoria, url }) {
    if (!nombre || !url) {
        return;
    }
    // la que se acaba de abrir va primero y no se duplica si ya estaba en la lista
    const recientes = [{ nombre, categoria, url }, ...leerRecientes().filter((entrada) => entrada.url !== url)];
    try {
        localStorage.setItem(CLAVE_RECIENTES, JSON.stringify(recientes.slice(0, MAXIMO_RECIENTES)));
    } catch (error) {
        // almacenamiento no disponible: se pierde el historial, la herramienta funciona igual
    }
}

function pintarRecientes(lista) {
    const recientes = leerRecientes();
    const seccion = document.getElementById("seccionRecientes");
    if (!recientes.length) {
        return;
    }

    lista.textContent = "";
    recientes.forEach((entrada) => {
        const enlace = document.createElement("a");
        enlace.className = "chipReciente";
        enlace.href = entrada.url;

        if (entrada.categoria) {
            const etiqueta = document.createElement("span");
            etiqueta.className = "chipCategoria";
            etiqueta.textContent = entrada.categoria;
            enlace.append(etiqueta);
        }
        // textContent y no innerHTML: el nombre sale de localStorage, que es editable
        enlace.append(document.createTextNode(entrada.nombre));
        lista.append(enlace);
    });

    seccion.hidden = false;

    const borrar = document.getElementById("botonBorrarRecientes");
    if (borrar) {
        borrar.addEventListener("click", () => {
            localStorage.removeItem(CLAVE_RECIENTES);
            seccion.hidden = true;
        });
    }
}
