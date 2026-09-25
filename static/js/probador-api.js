// Envio en lote para el Probador de API: repite la misma peticion N veces con un intervalo
// configurable, registra cada resultado en una tabla (fila = una peticion) y deja abrir el
// detalle completo de cualquier fila con un clic. Reutiliza crearValor/crearElemento, que
// herramienta.js define como funciones globales.

document.addEventListener("DOMContentLoaded", () => {
    const formulario = document.getElementById("formHerramienta");
    const panelLote = document.getElementById("panelLote");
    if (!formulario || !panelLote) {
        return;
    }

    const campoCantidad = document.getElementById("loteCantidad");
    const campoIntervalo = document.getElementById("loteIntervalo");
    const botonIniciar = document.getElementById("botonIniciarLote");
    const botonDetener = document.getElementById("botonDetenerLote");
    const resumen = document.getElementById("resumenLote");
    const resumenTotal = document.getElementById("resumenTotal");
    const resumenAceptadas = document.getElementById("resumenAceptadas");
    const resumenRechazadas = document.getElementById("resumenRechazadas");
    const resumenOtras = document.getElementById("resumenOtras");
    const contenedorTabla = document.getElementById("contenedorTablaLote");
    const cuerpoTabla = document.getElementById("cuerpoTablaLote");
    const botonEnviarUnico = formulario.querySelector('button[type="submit"]');
    const botonLimpiar = document.getElementById("botonLimpiar");

    const ETIQUETAS_ESTADO = {
        "exito": "Aceptada",
        "rechazada": "Rechazada",
        "no-encontrado": "Endpoint no encontrado",
        "limite-alcanzado": "Limite alcanzado",
        "error-servidor": "Error del servidor",
        "desconocido": "Desconocido",
        "fallo-conexion": "Sin conexion",
    };

    let detenerSolicitado = false;
    let enEjecucion = false;
    let contadores = { aceptadas: 0, rechazadas: 0, otras: 0 };
    let filaDetalleAbierta = null;

    function construirCuerpoJson() {
        const datosFormulario = new FormData(formulario);
        const datos = {};
        datosFormulario.forEach((valor, clave) => {
            if (valor !== "") {
                datos[clave] = valor;
            }
        });
        return JSON.stringify(datos);
    }

    function formularioValido() {
        let valido = true;
        formulario.querySelectorAll("[data-requerido]").forEach((control) => {
            if (control.value.trim() === "") {
                valido = false;
            }
        });
        return valido;
    }

    function claseFila(categoriaEstado) {
        if (categoriaEstado === "exito") {
            return "filaLote--ok";
        }
        if (categoriaEstado === "rechazada" || categoriaEstado === "fallo-conexion") {
            return "filaLote--error";
        }
        return "filaLote--otro";
    }

    function actualizarResumen() {
        const total = contadores.aceptadas + contadores.rechazadas + contadores.otras;
        resumenTotal.textContent = String(total);
        resumenAceptadas.textContent = String(contadores.aceptadas);
        resumenRechazadas.textContent = String(contadores.rechazadas);
        resumenOtras.textContent = String(contadores.otras);
    }

    function contabilizar(categoriaEstado) {
        if (categoriaEstado === "exito") {
            contadores.aceptadas += 1;
        } else if (categoriaEstado === "rechazada" || categoriaEstado === "fallo-conexion") {
            contadores.rechazadas += 1;
        } else {
            contadores.otras += 1;
        }
        actualizarResumen();
    }

    function celda(texto) {
        const elemento = document.createElement("td");
        elemento.textContent = texto;
        return elemento;
    }

    function agregarFila(numero, categoriaEstado, resumenTexto, codigoTexto, duracionTexto, datosDetalle) {
        const fila = document.createElement("tr");
        fila.className = `filaLote ${claseFila(categoriaEstado)}`;

        fila.appendChild(celda(String(numero)));
        fila.appendChild(celda(ETIQUETAS_ESTADO[categoriaEstado] || resumenTexto));
        fila.appendChild(celda(new Date().toLocaleTimeString()));
        fila.appendChild(celda(codigoTexto));
        fila.appendChild(celda(duracionTexto));

        const filaDetalle = document.createElement("tr");
        filaDetalle.className = "filaLoteDetalle";
        filaDetalle.hidden = true;
        const celdaDetalle = document.createElement("td");
        celdaDetalle.colSpan = 5;
        celdaDetalle.appendChild(crearValor(datosDetalle));
        filaDetalle.appendChild(celdaDetalle);

        fila.addEventListener("click", () => {
            const seVaAAbrir = filaDetalle.hidden;
            if (filaDetalleAbierta && filaDetalleAbierta !== filaDetalle) {
                filaDetalleAbierta.hidden = true;
            }
            filaDetalle.hidden = !seVaAAbrir;
            filaDetalleAbierta = seVaAAbrir ? filaDetalle : null;
        });

        cuerpoTabla.appendChild(fila);
        cuerpoTabla.appendChild(filaDetalle);
        contabilizar(categoriaEstado);
    }

    function esperar(ms) {
        return new Promise((resolver) => setTimeout(resolver, ms));
    }

    function alBloquear(activo) {
        botonEnviarUnico.disabled = activo;
        botonLimpiar.disabled = activo;
        campoCantidad.disabled = activo;
        campoIntervalo.disabled = activo;
    }

    async function ejecutarLote() {
        if (!formularioValido()) {
            // reutiliza el marcado de errores del formulario principal
            formulario.requestSubmit();
            return;
        }

        const cantidad = Math.min(Math.max(parseInt(campoCantidad.value, 10) || 1, 1), 100);
        const intervalo = Math.min(Math.max(parseInt(campoIntervalo.value, 10) || 0, 0), 60000);
        const cuerpoPeticion = construirCuerpoJson();

        detenerSolicitado = false;
        enEjecucion = true;
        contadores = { aceptadas: 0, rechazadas: 0, otras: 0 };
        cuerpoTabla.replaceChildren();
        filaDetalleAbierta = null;
        resumen.hidden = false;
        contenedorTabla.hidden = false;
        actualizarResumen();

        botonIniciar.hidden = true;
        botonDetener.hidden = false;
        alBloquear(true);

        for (let numero = 1; numero <= cantidad; numero += 1) {
            if (detenerSolicitado) {
                break;
            }

            const inicio = performance.now();
            try {
                const respuesta = await fetch(formulario.dataset.apiUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: cuerpoPeticion,
                });
                const duracionTexto = `${Math.round(performance.now() - inicio)} ms`;
                const tipoContenido = respuesta.headers.get("Content-Type") || "";

                if (tipoContenido.includes("application/json")) {
                    const datos = await respuesta.json();
                    if (respuesta.ok) {
                        agregarFila(numero, datos.categoriaEstado, datos.resultado, String(datos.codigoEstado), duracionTexto, datos);
                    } else {
                        agregarFila(numero, "desconocido", datos.error, String(respuesta.status), duracionTexto, datos);
                    }
                } else {
                    agregarFila(
                        numero, "desconocido", `Error HTTP ${respuesta.status}`, String(respuesta.status), duracionTexto,
                        { error: `El servidor respondio con el estado ${respuesta.status}` },
                    );
                }
            } catch (error) {
                agregarFila(numero, "fallo-conexion", error.message, "-", "-", { error: error.message });
            }

            if (numero < cantidad && intervalo > 0 && !detenerSolicitado) {
                await esperar(intervalo);
            }
        }

        enEjecucion = false;
        botonIniciar.hidden = false;
        botonDetener.hidden = true;
        alBloquear(false);
    }

    botonIniciar.addEventListener("click", () => {
        if (!enEjecucion) {
            ejecutarLote();
        }
    });

    botonDetener.addEventListener("click", () => {
        detenerSolicitado = true;
    });
});
