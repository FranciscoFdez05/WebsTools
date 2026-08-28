document.addEventListener("DOMContentLoaded", () => {
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
    }

    function mostrarError(mensaje) {
        estado.textContent = mensaje;
        estado.classList.add("estadoAjustes--error");
    }

    boton.addEventListener("click", async () => {
        boton.disabled = true;
        estado.classList.remove("estadoAjustes--error");
        estado.textContent = "Actualizando herramientas...";

        try {
            const respuesta = await fetch(boton.dataset.apiUrl, { method: "POST" });
            const tipoContenido = respuesta.headers.get("Content-Type") || "";
            if (!tipoContenido.includes("application/json")) {
                mostrarError(`Error ${respuesta.status}: no se pudo actualizar el catalogo`);
                return;
            }

            const cuerpo = await respuesta.json();
            if (!cuerpo.categorias) {
                // el limitador y los fallos inesperados responden {"error": ...} sin catalogo
                mostrarError(cuerpo.error || `Error ${respuesta.status}: no se pudo actualizar el catalogo`);
                return;
            }

            pintarCatalogo(cuerpo.categorias);
            document.getElementById("totalHerramientas").textContent = cuerpo.totalHerramientas;

            if (cuerpo.errores.length) {
                const detalle = cuerpo.errores
                    .map((fallo) => `${fallo.categoria} (${fallo.modulo}): ${fallo.error}`)
                    .join(" | ");
                mostrarError(`Actualizado con errores a las ${cuerpo.actualizado} - ${detalle}`);
            } else {
                estado.textContent =
                    `Catalogo actualizado a las ${cuerpo.actualizado}: ${cuerpo.totalHerramientas} herramientas en ${cuerpo.categorias.length} categorias.`;
            }
        } catch (error) {
            mostrarError(`Error de red: ${error.message}`);
        } finally {
            boton.disabled = false;
        }
    });
});
