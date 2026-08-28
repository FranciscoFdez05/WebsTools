// Filtro en vivo de tarjetas de herramienta. Cada buscador se declara en la plantilla con
// data-buscador y apunta con selectores al contenedor de resultados, al contador, al mensaje
// de "sin resultados" y, opcionalmente, al bloque alternativo que se muestra sin busqueda.
document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-buscador]").forEach(prepararBuscador);
    prepararAtajoBusqueda();
});

// las herramientas estan escritas sin tildes, pero el usuario puede escribirlas: se comparan
// ambos lados sin acentos y en minusculas
function normalizarTexto(texto) {
    return texto
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");
}

function prepararBuscador(entrada) {
    const resultados = document.querySelector(entrada.dataset.resultados);
    if (!resultados) {
        return;
    }

    const alternativo = entrada.dataset.alternativo ? document.querySelector(entrada.dataset.alternativo) : null;
    const contador = entrada.dataset.contador ? document.querySelector(entrada.dataset.contador) : null;
    const vacio = entrada.dataset.vacio ? document.querySelector(entrada.dataset.vacio) : null;

    const tarjetas = Array.from(resultados.querySelectorAll("[data-buscable]")).map((elemento) => ({
        elemento,
        texto: normalizarTexto(elemento.dataset.buscable),
    }));

    function filtrar() {
        const consulta = normalizarTexto(entrada.value.trim());
        const terminos = consulta.split(/\s+/).filter(Boolean);

        let visibles = 0;
        tarjetas.forEach((tarjeta) => {
            const coincide = terminos.every((termino) => tarjeta.texto.includes(termino));
            tarjeta.elemento.hidden = !coincide;
            visibles += coincide ? 1 : 0;
        });

        // en la pantalla principal la cuadricula de categorias sustituye a los resultados
        // mientras no se busca nada; en una categoria no hay alternativo y la lista se queda
        const buscando = terminos.length > 0;
        if (alternativo) {
            alternativo.hidden = buscando;
            resultados.hidden = !buscando;
        }

        if (vacio) {
            vacio.hidden = !(buscando && visibles === 0);
        }
        if (contador) {
            contador.textContent = buscando ? `${visibles} de ${tarjetas.length}` : "";
        }
    }

    entrada.addEventListener("input", filtrar);
    entrada.addEventListener("keydown", (evento) => {
        if (evento.key === "Escape") {
            entrada.value = "";
            filtrar();
        }
        // Enter abre la primera coincidencia: buscar y entrar sin tocar el raton
        if (evento.key === "Enter") {
            evento.preventDefault();
            const primera = tarjetas.find((tarjeta) => !tarjeta.elemento.hidden);
            if (primera && entrada.value.trim()) {
                primera.elemento.click();
            }
        }
    });

    filtrar();
}

// "/" enfoca el buscador desde cualquier punto de la pagina, salvo si ya se esta escribiendo
function prepararAtajoBusqueda() {
    const entrada = document.querySelector("[data-buscador]");
    if (!entrada) {
        return;
    }

    document.addEventListener("keydown", (evento) => {
        const escribiendo = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName);
        if (evento.key === "/" && !escribiendo) {
            evento.preventDefault();
            entrada.focus();
        }
    });
}
