document.addEventListener("DOMContentLoaded", () => {
    const formulario = document.getElementById("formHerramienta");
    const resultado = document.getElementById("resultadoHerramienta");
    if (!formulario) {
        return;
    }

    const botonEnviar = formulario.querySelector('button[type="submit"]');

    formulario.addEventListener("submit", async (evento) => {
        evento.preventDefault();
        resultado.classList.remove("resultadoHerramienta--error");
        resultado.textContent = "Procesando...";
        if (botonEnviar) {
            botonEnviar.disabled = true;
        }

        const apiUrl = formulario.dataset.apiUrl;
        const tieneArchivos = formulario.querySelector('input[type="file"]') !== null;

        try {
            let respuesta;
            if (tieneArchivos) {
                const formData = new FormData(formulario);
                respuesta = await fetch(apiUrl, { method: "POST", body: formData });
            } else {
                const datos = {};
                new FormData(formulario).forEach((valor, clave) => {
                    datos[clave] = valor;
                });
                respuesta = await fetch(apiUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(datos),
                });
            }

            const tipoContenido = respuesta.headers.get("Content-Type") || "";
            if (tipoContenido.includes("application/json")) {
                const cuerpo = await respuesta.json();
                resultado.textContent = JSON.stringify(cuerpo, null, 2);
                if (!respuesta.ok) {
                    resultado.classList.add("resultadoHerramienta--error");
                }
            } else {
                const disposicion = respuesta.headers.get("Content-Disposition") || "";
                const coincidencia = disposicion.match(/filename="?([^";]+)"?/);
                const nombreArchivo = coincidencia ? coincidencia[1] : "archivo-descargado";
                const blob = await respuesta.blob();
                const urlDescarga = URL.createObjectURL(blob);
                const enlace = document.createElement("a");
                enlace.href = urlDescarga;
                enlace.download = nombreArchivo;
                document.body.appendChild(enlace);
                enlace.click();
                enlace.remove();
                URL.revokeObjectURL(urlDescarga);
                resultado.textContent = `Archivo descargado: ${nombreArchivo}`;
            }
        } catch (error) {
            resultado.textContent = `Error de red: ${error.message}`;
            resultado.classList.add("resultadoHerramienta--error");
        } finally {
            if (botonEnviar) {
                botonEnviar.disabled = false;
            }
        }
    });
});
