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
const botonDatos = document.querySelector("#report-data-button");
const panelDatos = document.querySelector("#report-data-panel");
const tituloDatos = document.querySelector("#report-data-title");
const resumenDatos = document.querySelector("#report-data-summary");
const mensajeDatos = document.querySelector("#report-data-message");
const contenidoDatos = document.querySelector("#report-data-content");
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
let solicitudDatos;
let versionVistaPrevia = 0;
let paginaActual = 1;
let zoom = 1;
let temporizadorRedimension = 0;
const formatoNumero = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 2 });
const coloresGrafico = ["#2878a5", "#3a9d83", "#e09b45", "#8a6bb8", "#d66b65", "#4f9baa", "#b07a4f", "#6f8f55", "#c05a8f", "#6574b8"];
const etiquetasCampos = {
  codigo: "Código",
  nombre: "Nombre",
  total: "Total",
  total_peliculas: "Películas distintas",
  tasa_aporte_pension: "Tasa de aporte de pensión",
  dependencia: "Dependencia",
  cargo: "Cargo",
  cantidad: "Cantidad",
  fecha_ingreso: "Fecha de ingreso",
  fecha_inicio: "Fecha de inicio",
  fecha_fin: "Fecha de fin",
  eps: "EPS",
  fondo_pension: "Fondo de pensión",
  aporte_pension: "Aporte de pensión",
  sueldo: "Sueldo",
  novedades: "Novedades",
  dias_trabajados: "Días trabajados",
  desde: "Desde",
  hasta: "Hasta",
  entidad_tipo: "Tipo de entidad",
  entidad: "Entidad",
  genero: "Género",
  n: "Cantidad solicitada",
  posicion: "Posición",
  id_libro: "ID del libro",
  id_pelicula: "ID de la película",
  titulo: "Título",
  calificacion: "Calificación",
  num_calificaciones: "Calificaciones",
  anio: "Año",
  criterio: "Criterio",
  pelicula: "Película",
  generos: "Géneros",
  tipo: "Tipo",
  periodo: "Período",
  dias: "Días",
};

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
  pdfDocumento = null;
}

function cargarReportes(grupo) {
  selector.replaceChildren();
  for (const reporte of reportes.filter((elemento) => elemento.grupo === grupo)) {
    const opcion = document.createElement("option");
    opcion.value = reporte.ruta;
    opcion.textContent = reporte.nombre;
    selector.append(opcion);
  }
}

function seleccionarCategoria(grupo) {
  for (const boton of document.querySelectorAll("[data-report-category]")) {
    boton.setAttribute("aria-pressed", String(boton.dataset.reportCategory === grupo));
  }
  cargarReportes(grupo);
  void actualizarFiltros();
}

function nombreCampo(nombre) {
  return etiquetasCampos[nombre] ?? nombre.replaceAll("_", " ").replace(/^./, (letra) => letra.toLocaleUpperCase("es"));
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") return formatoNumero.format(value);
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "boolean") return value ? "Sí" : "No";
  return String(value);
}

function agregarResumen(data) {
  const campos = ["total", "total_peliculas", "n", "desde", "hasta", "entidad_tipo", "criterio"];
  const estadisticas = campos
    .filter((campo) => data[campo] !== undefined && data[campo] !== null)
    .map((campo) => [nombreCampo(campo), data[campo]]);
  if (!estadisticas.length) return;

  const lista = document.createElement("dl");
  lista.className = "report-stats";
  for (const [label, value] of estadisticas) {
    const tarjeta = document.createElement("div");
    tarjeta.className = "report-stat";
    const termino = document.createElement("dt");
    termino.textContent = label;
    const descripcion = document.createElement("dd");
    descripcion.textContent = formatValue(value);
    tarjeta.append(termino, descripcion);
    lista.append(tarjeta);
  }
  contenidoDatos.append(lista);
}

function crearSvgElemento(nombre, atributos = {}, texto = "") {
  const elemento = document.createElementNS("http://www.w3.org/2000/svg", nombre);
  for (const [clave, valor] of Object.entries(atributos)) elemento.setAttribute(clave, String(valor));
  if (texto) elemento.textContent = texto;
  return elemento;
}

function agregarLeyenda(contenedor, items) {
  const leyenda = document.createElement("ul");
  leyenda.className = "report-chart-legend";
  for (const [indice, item] of items.entries()) {
    const fila = document.createElement("li");
    const muestra = document.createElement("span");
    muestra.className = `chart-swatch chart-swatch-${indice % coloresGrafico.length}`;
    muestra.setAttribute("aria-hidden", "true");
    const texto = document.createElement("span");
    texto.textContent = item;
    fila.append(muestra, texto);
    leyenda.append(fila);
  }
  contenedor.append(leyenda);
}

function mostrarSinDatos(contenedor) {
  const texto = document.createElement("p");
  texto.className = "report-table-note";
  texto.textContent = "No hay datos disponibles para mostrar en este reporte.";
  contenedor.append(texto);
}

function renderizarTorta(datos, contenedor) {
  const serie = datos.series[0];
  const elementos = datos.etiquetas.map((etiqueta, indice) => ({
    etiqueta,
    valor: Number(serie?.valores?.[indice] ?? 0),
  })).filter((item) => Number.isFinite(item.valor) && item.valor > 0);
  const total = elementos.reduce((acumulado, item) => acumulado + item.valor, 0);
  if (!elementos.length || total <= 0) {
    mostrarSinDatos(contenedor);
    return;
  }

  const envoltura = document.createElement("div");
  envoltura.className = "report-chart-wrap";
  const svg = crearSvgElemento("svg", {
    class: "report-chart",
    viewBox: "0 0 320 260",
    role: "img",
    "aria-label": datos.titulo,
  });
  svg.append(crearSvgElemento("title", {}, datos.titulo));
  const cx = 130;
  const cy = 128;
  const radio = 102;

  if (elementos.length === 1) {
    svg.append(crearSvgElemento("circle", {
      cx, cy, r: radio, fill: coloresGrafico[0],
    }));
  } else {
    let inicio = -Math.PI / 2;
    for (const [indice, item] of elementos.entries()) {
      const fin = inicio + (item.valor / total) * Math.PI * 2;
      const puntoInicio = [cx + radio * Math.cos(inicio), cy + radio * Math.sin(inicio)];
      const puntoFin = [cx + radio * Math.cos(fin), cy + radio * Math.sin(fin)];
      const arcoGrande = fin - inicio > Math.PI ? 1 : 0;
      const ruta = [
        `M ${cx} ${cy}`,
        `L ${puntoInicio[0]} ${puntoInicio[1]}`,
        `A ${radio} ${radio} 0 ${arcoGrande} 1 ${puntoFin[0]} ${puntoFin[1]}`,
        "Z",
      ].join(" ");
      svg.append(crearSvgElemento("path", {
        d: ruta,
        fill: coloresGrafico[indice % coloresGrafico.length],
        stroke: "#fff",
        "stroke-width": 1,
      }));
      inicio = fin;
    }
  }
  envoltura.append(svg);
  contenedor.append(envoltura);
  agregarLeyenda(contenedor, elementos.map((item) =>
    `${item.etiqueta}: ${formatValue(item.valor)} (${formatoNumero.format(item.valor / total * 100)}%)`));
}

function renderizarBarras(datos, contenedor) {
  const series = datos.series.map((serie) => ({
    nombre: serie.nombre,
    valores: datos.etiquetas.map((_, indice) => Number(serie.valores[indice] ?? 0)),
  }));
  const maximo = Math.max(0, ...series.flatMap((serie) => serie.valores.filter(Number.isFinite)));
  if (!datos.etiquetas.length || !series.length || maximo <= 0) {
    mostrarSinDatos(contenedor);
    return;
  }

  const ancho = 920;
  const margenIzquierdo = 230;
  const margenDerecho = 54;
  const altoFila = Math.max(34, series.length * 17 + 10);
  const alto = Math.max(150, 44 + datos.etiquetas.length * altoFila);
  const anchoBarras = ancho - margenIzquierdo - margenDerecho;
  const altoBarra = Math.max(7, Math.min(15, (altoFila - 8) / series.length));
  const envoltura = document.createElement("div");
  envoltura.className = "report-chart-wrap";
  const svg = crearSvgElemento("svg", {
    class: "report-chart report-chart-bars",
    viewBox: `0 0 ${ancho} ${alto}`,
    role: "img",
    "aria-label": datos.titulo,
  });
  svg.append(crearSvgElemento("title", {}, datos.titulo));

  for (let tick = 0; tick <= 4; tick += 1) {
    const x = margenIzquierdo + (anchoBarras * tick) / 4;
    svg.append(crearSvgElemento("line", {
      x1: x, y1: 28, x2: x, y2: alto - 8, stroke: "#e1e8ec", "stroke-width": 1,
    }));
    svg.append(crearSvgElemento("text", {
      x, y: 20, fill: "#627582", "font-size": 11, "text-anchor": "middle",
    }, formatValue((maximo * tick) / 4)));
  }

  datos.etiquetas.forEach((etiqueta, indiceEtiqueta) => {
    const inicioFila = 36 + indiceEtiqueta * altoFila;
    const grupo = datos.grupos?.[indiceEtiqueta];
    const rotulo = grupo ? `${etiqueta} · ${grupo}` : etiqueta;
    const texto = rotulo.length > 32 ? `${rotulo.slice(0, 29)}…` : rotulo;
    const textoSvg = crearSvgElemento("text", {
      x: margenIzquierdo - 12,
      y: inicioFila + altoFila / 2 + 4,
      fill: "#334d5f",
      "font-size": 11,
      "text-anchor": "end",
    }, texto);
    textoSvg.append(crearSvgElemento("title", {}, rotulo));
    svg.append(textoSvg);

    series.forEach((serie, indiceSerie) => {
      const valor = serie.valores[indiceEtiqueta];
      if (!Number.isFinite(valor) || valor <= 0) return;
      const y = inicioFila + indiceSerie * (altoBarra + 3);
      const barraAncho = (valor / maximo) * anchoBarras;
      svg.append(crearSvgElemento("rect", {
        x: margenIzquierdo,
        y,
        width: barraAncho,
        height: altoBarra,
        rx: 3,
        fill: coloresGrafico[indiceSerie % coloresGrafico.length],
      }));
      svg.append(crearSvgElemento("text", {
        x: Math.min(ancho - 6, margenIzquierdo + barraAncho + 5),
        y: y + altoBarra - 1,
        fill: "#334d5f",
        "font-size": 10,
      }, formatValue(valor)));
    });
  });

  envoltura.append(svg);
  contenedor.append(envoltura);
  if (series.length > 1) agregarLeyenda(contenedor, series.map((serie) => serie.nombre));
}

function construirFilas(data) {
  switch (selector.value) {
    case "/nomina/empleados/pdf":
      return data.empleados.map(({ codigo, nombre }) => ({ codigo, nombre }));
    case "/nomina/por-dependencia/pdf":
      return data.dependencias.map(({ dependencia, cantidad }) => ({ dependencia, cantidad }));
    case "/nomina/por-cargo/pdf":
      return data.dependencias.flatMap((item) =>
        item.cargos.map(({ cargo, cantidad }) => ({ dependencia: item.dependencia, cargo, cantidad })));
    case "/personal/pdf":
      return data.empleados.map((item) => ({
        codigo: item.codigo,
        nombre: item.nombre,
        dependencia: item.dependencia,
        cargo: item.cargo,
        fecha_ingreso: item.fecha_ingreso,
        eps: item.eps,
        fondo_pension: item.fondo_pension,
        aporte_pension: item.aporte_pension,
        sueldo: item.sueldo,
        novedades: item.novedades.length,
      }));
    case "/salud-pension/por-cargo-eps/pdf":
    case "/salud-pension/por-cargo-pension/pdf":
      return data.cargos.flatMap((item) =>
        item.entidades.map(({ entidad, cantidad }) => ({ cargo: item.cargo, entidad, cantidad })));
    case "/novedades/empleados/pdf":
      return data.empleados.map((item) => ({
        codigo: item.codigo,
        nombre: item.nombre,
        dependencia: item.dependencia,
        cargo: item.cargo,
        novedades: item.novedades.length,
      }));
    case "/novedades/resumen/pdf":
      return data.dependencias.flatMap((item) =>
        item.cargos.map(({ cargo, cantidad }) => ({ dependencia: item.dependencia, cargo, cantidad })));
    case "/entretenimiento/peliculas-por-genero/pdf":
      return data.generos.map(({ genero, cantidad }) => ({ genero, cantidad }));
    case "/entretenimiento/libros/top/pdf":
      return data.libros.map((item) => ({
        posicion: item.posicion,
        titulo: item.titulo,
        calificacion: item.calificacion,
        num_calificaciones: item.num_calificaciones,
        anio: item.anio,
      }));
    case "/entretenimiento/libros/top-por-anio/pdf":
      return data.anios.flatMap((item) => [
        ...item.mejores.map((libro) => ({ anio: item.anio, criterio: "Mejores", ...libro })),
        ...item.peores.map((libro) => ({ anio: item.anio, criterio: "Peores", ...libro })),
      ]);
    case "/entretenimiento/peliculas/por-numero-de-generos/pdf":
      return data.peliculas.map((item) => ({
        id_pelicula: item.id_pelicula,
        titulo: item.titulo,
        anio: item.anio,
        generos: item.generos,
      }));
    default:
      return [];
  }
}

function renderizarTabla(data, contenedor) {
  const filas = construirFilas(data);
  if (!filas.length) {
    mostrarSinDatos(contenedor);
    return;
  }

  const maxFilas = 100;
  const visibles = filas.slice(0, maxFilas);
  const columnas = [...new Set(visibles.flatMap((fila) => Object.keys(fila)))];
  const envoltura = document.createElement("div");
  envoltura.className = "report-table-wrap";
  const tabla = document.createElement("table");
  tabla.className = "report-data-table";
  const encabezado = document.createElement("thead");
  const filaEncabezado = document.createElement("tr");
  for (const columna of columnas) {
    const celda = document.createElement("th");
    celda.scope = "col";
    celda.textContent = nombreCampo(columna);
    filaEncabezado.append(celda);
  }
  encabezado.append(filaEncabezado);
  tabla.append(encabezado);
  const cuerpo = document.createElement("tbody");
  for (const fila of visibles) {
    const filaTabla = document.createElement("tr");
    for (const columna of columnas) {
      const celda = document.createElement("td");
      celda.textContent = formatValue(fila[columna]);
      filaTabla.append(celda);
    }
    cuerpo.append(filaTabla);
  }
  tabla.append(cuerpo);
  envoltura.append(tabla);
  contenedor.append(envoltura);
  if (filas.length > maxFilas) {
    const nota = document.createElement("p");
    nota.className = "report-table-note";
    nota.textContent = `Se muestran ${maxFilas} de ${formatValue(filas.length)} filas. Usa la vista previa o descarga el PDF para consultar el reporte completo.`;
    contenedor.append(nota);
  }
}

function renderizarDatos(data) {
  contenidoDatos.replaceChildren();
  tituloDatos.textContent = data.titulo || selector.selectedOptions[0].textContent;
  resumenDatos.textContent = Array.isArray(data.etiquetas)
    ? `${formatValue(data.etiquetas.length)} categorías`
    : `${formatValue(data.total ?? data.total_peliculas ?? construirFilas(data).length)} registros`;
  agregarResumen(data);

  if (Array.isArray(data.etiquetas) && Array.isArray(data.series)) {
    if (data.tipo === "torta") renderizarTorta(data, contenidoDatos);
    else if (data.tipo === "barras") renderizarBarras(data, contenidoDatos);
    else renderizarTabla(data, contenidoDatos);
    if (data.nota) {
      const nota = document.createElement("p");
      nota.className = "report-chart-note";
      nota.textContent = data.nota;
      contenidoDatos.append(nota);
    }
  } else {
    renderizarTabla(data, contenidoDatos);
  }
  panelDatos.hidden = false;
}

function invalidarDatos() {
  solicitudDatos?.abort();
  solicitudDatos = null;
  botonDatos.disabled = false;
  panelDatos.hidden = true;
  resumenDatos.textContent = "";
  mensajeDatos.textContent = "";
  contenidoDatos.replaceChildren();
}

function errorDeRespuesta(cuerpo, status) {
  const predeterminado = cuerpo || `Error HTTP ${status}`;
  try {
    const detalle = JSON.parse(cuerpo).detail;
    if (typeof detalle === "string") return detalle;
    if (Array.isArray(detalle)) {
      return detalle.map((item) => item.msg || String(item)).join("; ");
    }
  } catch {
    return predeterminado;
  }
  return predeterminado;
}

async function consultarDatos() {
  if (!form.reportValidity()) return;
  solicitudDatos?.abort();
  const controlador = new AbortController();
  solicitudDatos = controlador;
  botonDatos.disabled = true;
  panelDatos.hidden = false;
  tituloDatos.textContent = selector.selectedOptions[0].textContent;
  resumenDatos.textContent = "";
  contenidoDatos.replaceChildren();
  mensajeDatos.textContent = "Consultando los datos del reporte…";
  try {
    const ruta = selector.value.replace(/\/pdf$/, "");
    const url = new URL(`/api/v1/reportes${ruta}`, window.location.origin);
    for (const [clave, valor] of new FormData(form)) {
      if (clave !== "reporte" && String(valor).trim()) url.searchParams.set(clave, String(valor).trim());
    }
    const respuesta = await fetch(url, { signal: controlador.signal, credentials: "same-origin" });
    if (respuesta.status === 401) {
      window.location.replace("/login.html");
      return;
    }
    if (!respuesta.ok) throw new Error(errorDeRespuesta(await respuesta.text(), respuesta.status));
    const data = await respuesta.json();
    if (solicitudDatos !== controlador) return;
    renderizarDatos(data);
    mensajeDatos.textContent = "";
  } catch (error) {
    if (error.name === "AbortError") return;
    contenidoDatos.replaceChildren();
    mensajeDatos.textContent = error.message || "No se pudieron consultar los datos.";
  } finally {
    if (solicitudDatos === controlador) {
      solicitudDatos = null;
      botonDatos.disabled = false;
    }
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
  solicitudDatos?.abort();
  solicitudDatos = null;
  botonVistaPrevia.disabled = false;
  botonDatos.disabled = false;
  panelDatos.hidden = true;
  mensajeDatos.textContent = "";
  contenidoDatos.replaceChildren();
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
      await tarea.destroy();
      if (tareaCargaPdf === tarea) tareaCargaPdf = null;
      return;
    }

    pdfDocumento = documento;
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

botonDatos.addEventListener("click", () => void consultarDatos());
for (const boton of document.querySelectorAll("[data-report-category]")) {
  boton.addEventListener("click", () => seleccionarCategoria(boton.dataset.reportCategory));
}

selector.addEventListener("change", () => {
  void actualizarFiltros();
});

filtros.addEventListener("input", invalidarDatos);
filtros.addEventListener("change", invalidarDatos);

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

cargarReportes("Nómina");
void actualizarFiltros();
