
//---ESTE CODIGO ABRE Y CIERRA EL PANEL DE NAVEGACIÓN-----------------------------//
const navigationButton = document.getElementById("navigationButton");
const layout = document.querySelector(".layout");

navigationButton.addEventListener("click", function(){
    layout.classList.toggle("panel-collapsed");
});

//---ESTE CODIGO MANEJA EL INSERTO DE TROZOS DE HTML PARA MOSTRAR EN MAIN

const mainContent = document.getElementById("mainContent");
const noteLinks = document.querySelectorAll(".note-link");

noteLinks.forEach(function(noteLink){
    noteLink.addEventListener("click", function(event){
        event.preventDefault();
        
        const notePath = noteLink.getAttribute("href");

        fetch(notePath)
            .then(function(response){
                return response.text();
            })
            .then(function (noteContent){
                mainContent.innerHTML = noteContent;

                if (smallScreen.matches) {
                    layout.classList.add("panel-collapsed");
                }
            });
    });
});

//---COMPORTAMIENTO DEL OVERLAY----------------------------------------//

const panelOverlay =
    document.getElementById("panelOverlay");

const navigationPanel =
    document.getElementById("sidebar");

const smallScreen =
    window.matchMedia("(max-width: 768px)");
//---CERRAR AL TOCAR OVERLAY
if (smallScreen.matches) {
    layout.classList.add("panel-collapsed");
}

panelOverlay.addEventListener("click", function () {
    layout.classList.add("panel-collapsed");
});
//---CERRAR AL SELECCIONAR UN ENLACE DEL PANEL
const navigationLinks =
    navigationPanel.querySelectorAll("a");

navigationLinks.forEach(function (link) {
    link.addEventListener("click", function () {
        if (smallScreen.matches) {
            layout.classList.add("panel-collapsed");
        }
    });
});