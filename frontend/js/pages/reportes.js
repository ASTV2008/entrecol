const orden = {
  name: "orden",
  label: "Orden alfabético",
  type: "select",
  defaultValue: "asc",
  options: [
    { value: "asc", label: "Ascendente" },
    { value: "desc", label: "Descendente" },
  ],
};

const periodo = (name, label) => ({
  name,
  label,
  type: "text",
  placeholder: "MM/AAAA",
  defaultValue: "03/2022",
  required: true,
  pattern: "(0[1-9]|1[0-2])/\\d{4}",
  title: "Usa el formato MM/AAAA, por ejemplo 03/2022.",
});

const anio = (name, label, required = true) => ({
  name,
  label,
  type: "number",
  min: 1,
  max: 9999,
  defaultValue: required ? "2000" : "",
  required,
});

const entero = (name, label, min, max, defaultValue, required = true) => ({
  name,
  label,
  type: "number",
  min,
  max,
  defaultValue: String(defaultValue),
  required,
});

const reportes = [
  { grupo: "Nómina", nombre: "1a · Cantidad y lista de empleados", ruta: "/nomina/empleados/pdf", campos: [orden] },
  { grupo: "Nómina", nombre: "1b · Empleados por dependencia", ruta: "/nomina/por-dependencia/pdf", campos: [orden] },
  { grupo: "Nómina", nombre: "1c · Empleados por cargo y dependencia", ruta: "/nomina/por-cargo/pdf", campos: [orden] },
  { grupo: "Nómina", nombre: "1d · Gráfico de empleados por dependencia", ruta: "/nomina/grafico-dependencias/pdf" },
  { grupo: "Nómina", nombre: "1e · Gráfico de empleados por cargo", ruta: "/nomina/grafico-cargos/pdf" },
  {
    grupo: "Información personal",
    nombre: "2 · Información personal de empleados",
    ruta: "/personal/pdf",
    campos: [orden, entero("codigo", "Código de empleado (opcional)", 1, 4294967295, "", false)],
  },
  { grupo: "Salud y pensión", nombre: "3a · Frecuencia por EPS", ruta: "/salud-pension/grafico-eps/pdf" },
  { grupo: "Salud y pensión", nombre: "3b · Frecuencia por pensión", ruta: "/salud-pension/grafico-pension/pdf" },
  { grupo: "Salud y pensión", nombre: "3c · EPS por dependencia", ruta: "/salud-pension/grafico-eps-dependencia/pdf" },
  { grupo: "Salud y pensión", nombre: "3d · Pensión por dependencia", ruta: "/salud-pension/grafico-pension-dependencia/pdf" },
  { grupo: "Salud y pensión", nombre: "3e · Empleados por cargo y EPS", ruta: "/salud-pension/por-cargo-eps/pdf", campos: [orden] },
  { grupo: "Salud y pensión", nombre: "3f · Empleados por cargo y pensión", ruta: "/salud-pension/por-cargo-pension/pdf", campos: [orden] },
  {
    grupo: "Novedades",
    nombre: "4a · Empleados con novedades",
    ruta: "/novedades/empleados/pdf",
    campos: [periodo("desde", "Periodo inicial"), periodo("hasta", "Periodo final"), orden],
  },
  {
    grupo: "Novedades",
    nombre: "4b · Resumen de novedades",
    ruta: "/novedades/resumen/pdf",
    campos: [periodo("desde", "Periodo inicial"), periodo("hasta", "Periodo final")],
  },
  {
    grupo: "Entretenimiento",
    nombre: "5a · Películas por género y año",
    ruta: "/entretenimiento/peliculas-por-genero/pdf",
    campos: [anio("desde", "Año inicial"), anio("hasta", "Año final"), orden],
  },
  {
    grupo: "Entretenimiento",
    nombre: "5b · Top de libros",
    ruta: "/entretenimiento/libros/top/pdf",
    campos: [entero("n", "Cantidad de libros", 1, 100, 10), orden, entero("min_calificaciones", "Mínimo de calificaciones", 1, 4294967295, 1)],
  },
  {
    grupo: "Entretenimiento",
    nombre: "5c · Top de libros por año",
    ruta: "/entretenimiento/libros/top-por-anio/pdf",
    campos: [
      anio("desde", "Año inicial (opcional)", false),
      anio("hasta", "Año final (opcional)", false),
      orden,
      entero("min_calificaciones", "Mínimo de calificaciones", 1, 4294967295, 1),
    ],
  },
  {
    grupo: "Entretenimiento",
    nombre: "5d · Películas por número de géneros",
    ruta: "/entretenimiento/peliculas/por-numero-de-generos/pdf",
    campos: [entero("n", "Cantidad de géneros", 0, 30, 1), orden],
  },
  { grupo: "Entretenimiento", nombre: "5e · Gráfico de películas por género", ruta: "/entretenimiento/graficos/peliculas-por-genero/pdf" },
  {
    grupo: "Entretenimiento",
    nombre: "5f · Gráfico de libros por año",
    ruta: "/entretenimiento/graficos/libros-por-anio/pdf",
    campos: [anio("desde", "Año inicial"), anio("hasta", "Año final")],
  },
];

const form = document.querySelector("#report-form");
const selector = document.querySelector("#report-select");
const filtros = document.querySelector("#report-filters");
const mensaje = document.querySelector("#form-message");
const vistaPrevia = document.querySelector("#pdf-preview");
const espacioVacio = document.querySelector("#preview-empty");
const botonDescarga = document.querySelector("#download-button");
const botonVistaPrevia = form.querySelector('button[type="submit"]');
const lienzo = document.querySelector("#pdf-canvas");
const contextoLienzo = lienzo.getContext("2d");
const indicadorPagina = document.querySelector("#page-indicator");
const indicadorZoom = document.querySelector("#zoom-indicator");
const botonAnterior = document.querySelector("#previous-page");
const botonSiguiente = document.querySelector("#next-page");
const botonZoomMenos = document.querySelector("#zoom-out");
const botonZoomMas = document.querySelector("#zoom-in");

let pdfjsPromise;
let pdfDocumento;
let tareaCargaPdf;
let tareaRenderizado;
let solicitudVistaPrevia;
let versionVistaPrevia = 0;
let paginaActual = 1;
let zoom = 1;
let temporizadorRedimension = 0;

function cargarPdfJs() {
  if (!pdfjsPromise) {
    pdfjsPromise = import("/js/vendor/pdf.min.mjs").then((pdfjs) => {
      pdfjs.GlobalWorkerOptions.workerSrc = "/js/vendor/pdf.worker.min.mjs?v=6";
      return pdfjs;
    });
  }
  return pdfjsPromise;
}

async function liberarDocumento() {
  if (tareaRenderizado) {
    tareaRenderizado.cancel();
    tareaRenderizado = null;
  }
  if (tareaCargaPdf) {
    const tarea = tareaCargaPdf;
    tareaCargaPdf = null;
    await tarea.destroy();
  }
  if (pdfDocumento) {
    const documento = pdfDocumento;
    pdfDocumento = null;
    await documento.destroy();
  }
}

function cargarReportes() {
  const grupos = new Map();
  for (const reporte of reportes) {
    if (!grupos.has(reporte.grupo)) {
      const grupo = document.createElement("optgroup");
      grupo.label = reporte.grupo;
      grupos.set(reporte.grupo, grupo);
      selector.append(grupo);
    }
    const opcion = document.createElement("option");
    opcion.value = reporte.ruta;
    opcion.textContent = reporte.nombre;
    grupos.get(reporte.grupo).append(opcion);
  }
}

function crearControl(campo) {
  const contenedor = document.createElement("div");
  contenedor.className = "field";
  const etiqueta = document.createElement("label");
  etiqueta.htmlFor = `filter-${campo.name}`;
  etiqueta.textContent = campo.label;
  contenedor.append(etiqueta);

  let control;
  if (campo.type === "select") {
    control = document.createElement("select");
    for (const opcion of campo.options) {
      const elemento = document.createElement("option");
      elemento.value = opcion.value;
      elemento.textContent = opcion.label;
      control.append(elemento);
    }
  } else {
    control = document.createElement("input");
    control.type = campo.type;
    if (campo.min !== undefined) control.min = String(campo.min);
    if (campo.max !== undefined) control.max = String(campo.max);
    if (campo.pattern) control.pattern = campo.pattern;
    if (campo.placeholder) control.placeholder = campo.placeholder;
    if (campo.title) control.title = campo.title;
  }
  control.id = `filter-${campo.name}`;
  control.name = campo.name;
  control.required = Boolean(campo.required);
  control.value = campo.defaultValue ?? "";
  contenedor.append(control);
  return contenedor;
}

async function actualizarFiltros() {
  versionVistaPrevia += 1;
  solicitudVistaPrevia?.abort();
  await liberarDocumento();
  filtros.replaceChildren();
  const reporte = reportes.find((elemento) => elemento.ruta === selector.value);
  for (const campo of reporte?.campos ?? []) {
    filtros.append(crearControl(campo));
  }
  mensaje.textContent = "";
  vistaPrevia.hidden = true;
  espacioVacio.hidden = false;
  espacioVacio.querySelector("p").textContent = "Elige un reporte y selecciona Ver vista previa.";
  indicadorPagina.textContent = "Página 0 de 0";
  lienzo.width = 0;
  lienzo.height = 0;
  paginaActual = 1;
  zoom = 1;
  actualizarControles();
}

function crearUrl(descargar = false) {
  const url = new URL(`/api/v1/reportes${selector.value}`, window.location.origin);
  for (const [clave, valor] of new FormData(form)) {
    if (clave !== "reporte" && String(valor).trim()) {
      url.searchParams.set(clave, String(valor).trim());
    }
  }
  if (descargar) url.searchParams.set("descargar", "true");
  return url;
}

function actualizarControles() {
  const totalPaginas = pdfDocumento?.numPages ?? 0;
  indicadorPagina.textContent = `Página ${pdfDocumento ? paginaActual : 0} de ${totalPaginas}`;
  indicadorZoom.textContent = `${Math.round(zoom * 100)}%`;
  botonAnterior.disabled = !pdfDocumento || paginaActual <= 1;
  botonSiguiente.disabled = !pdfDocumento || paginaActual >= totalPaginas;
  botonZoomMenos.disabled = !pdfDocumento || zoom <= 0.6;
  botonZoomMas.disabled = !pdfDocumento || zoom >= 2;
}

async function renderizarPagina(version) {
  if (!pdfDocumento) return;
  if (tareaRenderizado) tareaRenderizado.cancel();

  const documento = pdfDocumento;
  const pagina = await documento.getPage(paginaActual);
  if (version !== versionVistaPrevia || documento !== pdfDocumento) return;

  const escalaBase = pagina.getViewport({ scale: 1 });
  const anchoDisponible = Math.max(240, vistaPrevia.clientWidth - 48);
  const escalaAjuste = Math.min(1.35, anchoDisponible / escalaBase.width);
  const viewport = pagina.getViewport({ scale: escalaAjuste * zoom });
  const resolucion = Math.min(window.devicePixelRatio || 1, 2);

  lienzo.width = Math.floor(viewport.width * resolucion);
  lienzo.height = Math.floor(viewport.height * resolucion);
  lienzo.style.width = `${viewport.width}px`;
  lienzo.style.height = `${viewport.height}px`;
  contextoLienzo.clearRect(0, 0, lienzo.width, lienzo.height);
  lienzo.setAttribute("aria-label", `Página ${paginaActual} de ${documento.numPages}`);

  const tarea = pagina.render({
    canvasContext: contextoLienzo,
    viewport,
    transform: resolucion === 1 ? null : [resolucion, 0, 0, resolucion, 0, 0],
  });
  tareaRenderizado = tarea;
  try {
    await tarea.promise;
  } catch (error) {
    if (error.name !== "RenderingCancelledException") throw error;
  } finally {
    if (tareaRenderizado === tarea) tareaRenderizado = null;
  }
  if (version === versionVistaPrevia && documento === pdfDocumento) actualizarControles();
}

async function generarVistaPrevia() {
  const version = ++versionVistaPrevia;
  solicitudVistaPrevia?.abort();
  solicitudVistaPrevia = new AbortController();
  botonVistaPrevia.disabled = true;
  mensaje.textContent = "Generando el PDF…";
  espacioVacio.hidden = false;
  espacioVacio.querySelector("p").textContent = "Generando la vista previa…";
  vistaPrevia.hidden = true;

  try {
    await liberarDocumento();
    const respuesta = await fetch(crearUrl(), { signal: solicitudVistaPrevia.signal });
    if (respuesta.status === 401) {
      window.location.replace("/login.html");
      return;
    }
    if (!respuesta.ok) {
      const cuerpo = await respuesta.text();
      let detalle = cuerpo || `Error HTTP ${respuesta.status}`;
      try {
        detalle = JSON.parse(cuerpo).detail ?? detalle;
      } catch {
        detalle = cuerpo || `Error HTTP ${respuesta.status}`;
      }
      throw new Error(detalle);
    }

    const pdfjs = await cargarPdfJs();
    const datos = new Uint8Array(await respuesta.arrayBuffer());
    const tarea = pdfjs.getDocument({ data: datos, isEvalSupported: false });
    tareaCargaPdf = tarea;
    const documento = await tarea.promise;
    if (version !== versionVistaPrevia) {
      await documento.destroy();
      return;
    }

    pdfDocumento = documento;
    tareaCargaPdf = null;
    paginaActual = 1;
    zoom = 1;
    vistaPrevia.hidden = false;
    espacioVacio.hidden = true;
    mensaje.textContent = "";
    actualizarControles();
    await renderizarPagina(version);
  } catch (error) {
    if (error.name === "AbortError" || version !== versionVistaPrevia) return;
    vistaPrevia.hidden = true;
    espacioVacio.hidden = false;
    espacioVacio.querySelector("p").textContent = "No se pudo cargar la vista previa.";
    mensaje.textContent = error.message || "Ocurrió un error al generar el PDF.";
  } finally {
    if (version === versionVistaPrevia) botonVistaPrevia.disabled = false;
  }
}

async function cambiarPagina(delta) {
  if (!pdfDocumento) return;
  paginaActual = Math.min(pdfDocumento.numPages, Math.max(1, paginaActual + delta));
  actualizarControles();
  try {
    await renderizarPagina(versionVistaPrevia);
  } catch (error) {
    mensaje.textContent = error.message || "No se pudo dibujar la página.";
  }
}

async function cambiarZoom(delta) {
  if (!pdfDocumento) return;
  zoom = Math.min(2, Math.max(0.6, Math.round((zoom + delta) * 10) / 10));
  actualizarControles();
  try {
    await renderizarPagina(versionVistaPrevia);
  } catch (error) {
    mensaje.textContent = error.message || "No se pudo ajustar el zoom.";
  }
}

form.addEventListener("submit", (evento) => {
  evento.preventDefault();
  mensaje.textContent = "";
  if (!form.reportValidity()) return;
  void generarVistaPrevia();
});

selector.addEventListener("change", () => {
  void actualizarFiltros();
});

botonAnterior.addEventListener("click", () => void cambiarPagina(-1));
botonSiguiente.addEventListener("click", () => void cambiarPagina(1));
botonZoomMenos.addEventListener("click", () => void cambiarZoom(-0.1));
botonZoomMas.addEventListener("click", () => void cambiarZoom(0.1));

window.addEventListener("resize", () => {
  window.clearTimeout(temporizadorRedimension);
  temporizadorRedimension = window.setTimeout(() => {
    if (pdfDocumento) void renderizarPagina(versionVistaPrevia);
  }, 150);
});

botonDescarga.addEventListener("click", async () => {
  mensaje.textContent = "";
  if (!form.reportValidity()) return;

  botonDescarga.disabled = true;
  try {
    const respuesta = await fetch(crearUrl(true));
    if (respuesta.status === 401) {
      window.location.replace("/login.html");
      return;
    }
    if (!respuesta.ok) {
      const cuerpo = await respuesta.text();
      let detalle = cuerpo || `Error HTTP ${respuesta.status}`;
      try {
        detalle = JSON.parse(cuerpo).detail ?? detalle;
      } catch {
        detalle = cuerpo || `Error HTTP ${respuesta.status}`;
      }
      throw new Error(detalle);
    }
    const archivo = URL.createObjectURL(await respuesta.blob());
    const enlace = document.createElement("a");
    enlace.href = archivo;
    enlace.download = respuesta.headers.get("Content-Disposition")?.match(/filename="?([^";]+)"?/i)?.[1] ?? "reporte.pdf";
    enlace.hidden = true;
    document.body.append(enlace);
    enlace.click();
    enlace.remove();
    window.setTimeout(() => URL.revokeObjectURL(archivo), 1000);
  } catch (error) {
    mensaje.textContent = error.message || "No se pudo descargar el PDF.";
  } finally {
    botonDescarga.disabled = false;
  }
});

cargarReportes();
void actualizarFiltros();
