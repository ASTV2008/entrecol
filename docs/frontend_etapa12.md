# Etapa 12: interfaz de usuario

## Alcance

La aplicación ofrece una interfaz de inicio de sesión con MFA y un espacio autenticado para consultar reportes, cargar fuentes y administrar la cuenta. Las opciones de administración, auditoría y carga de archivos están disponibles únicamente para administradores.

## Cinco áreas de consulta

En **Consultas**, las áreas se muestran separadas para facilitar la navegación:

1. **Nómina**: listas y agrupaciones de empleados, además de gráficos por dependencia y cargo.
2. **Información personal**: fichas y novedades de cada empleado.
3. **Salud y pensión**: distribuciones por entidad y comparaciones por dependencia.
4. **Novedades**: empleados y resúmenes para un intervalo de períodos.
5. **Entretenimiento**: reportes de películas y libros.

El botón **Consultar datos** usa la ruta JSON correspondiente y presenta tablas o gráficos en la página. Las tablas de pantalla se limitan a 100 filas cuando el resultado es mayor; el PDF conserva el reporte completo. **Vista previa del PDF** renderiza el documento en el panel integrado, con controles de página y zoom; **Descargar PDF** guarda el mismo reporte.

## Carga de archivos

En **Carga de archivos**, un administrador puede seleccionar películas (`.dat`), libros (`.json`) o nómina (`.xlsx`). Nómina requiere el período `AAAA-MM`. La estructura la valida el ETL existente y la API aplica el límite de tamaño; la pantalla muestra el resultado y el historial de cargas.

## Uso local

La interfaz se sirve desde el mismo origen que la API. Inicia sesión con una cuenta habilitada y completa el flujo MFA. Los datos se consultan desde la API autenticada; el navegador no guarda archivos de carga ni credenciales de sesión en almacenamiento local.
