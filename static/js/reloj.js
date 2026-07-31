function actualizarFechaHora() {
    const elemento = document.getElementById("fechaHora");
    if (!elemento) {
        return;
    }
    const ahora = new Date();
    elemento.textContent = ahora.toLocaleString();
}

actualizarFechaHora();
setInterval(actualizarFechaHora, 1000);
