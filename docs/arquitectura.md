# Arquitectura técnica

## Componentes

Entrecol se organiza en contenedores con responsabilidades separadas:

| Componente | Ubicación | Responsabilidad |
| --- | --- | --- |
| Navegador | `frontend/` | Inicio de sesión, navegación, reportes y carga de archivos |
| API | `backend/app/` | Validación HTTP, autenticación, autorización y coordinación |
| Base de datos | `database/init/` y MariaDB | Datos operativos, sesiones, auditoría e historial de cargas |
| ETL | `backend/app/etl/` | Lectura, validación, transformación y carga de fuentes |

Docker Compose publica únicamente en `127.0.0.1`:

- API y frontend: puerto `8000`.
- MariaDB: puerto definido por `DB_PORT`.

## Organización del backend

- `api/v1`: contratos HTTP y routing.
- `services`: reglas de consulta y presentación de reportes.
- `repositories`: consultas SQL específicas del dominio.
- `etl`: extractores, transformadores y cargadores por fuente.
- `models`: modelos SQLAlchemy.
- `schemas`: modelos Pydantic de entrada y respuesta.
- `security`: autenticación, sesiones, CSRF, MFA y auditoría.
- `reports`: generación de documentos PDF.
- `core`: configuración y errores compartidos.

## Datos

Los scripts de `database/init/` crean las tablas iniciales de nómina y entretenimiento, además de las tablas de seguridad y cargas. La API utiliza SQLAlchemy y una única sesión por petición.

Las tablas principales se dividen en:

- Nómina y entretenimiento: empleados, novedades, películas y libros.
- Seguridad: cuentas, sesiones, códigos TOTP de recuperación y auditoría.
- Operación: registros de cargas realizadas o fallidas.

## Flujo de autenticación

1. El usuario inicia sesión con correo y contraseña.
2. La contraseña puede exigir cambio obligatorio.
3. Si el usuario no tiene TOTP, se genera una semilla cifrada y se presenta un QR.
4. Tras verificar TOTP, se crea una sesión activa.
5. Las operaciones protegidas exigen sesión vigente, CSRF cuando corresponde y rol autorizado.

Las sesiones tienen límite de inactividad de 30 minutos y límite absoluto configurable de hasta 8 horas por defecto.

## Flujo de carga

1. El usuario administrador selecciona tipo, archivo y período opcional.
2. La API valida sesión, CSRF, rol, extensión y tamaño máximo de 20 MiB.
3. El ETL lee y transforma el contenido en memoria.
4. Una carga correcta registra aceptados y rechazados.
5. Una carga fallida revierte la operación y conserva el intento en el historial.

El archivo original no se guarda en disco ni en la base de datos.

## Flujo de reportes

Los endpoints JSON delegan consultas en repositorios y servicios. Los endpoints PDF usan el mismo resultado de negocio para producir documentos con el mismo criterio de datos.

La interfaz limita visualmente las tablas largas a 100 filas, pero el PDF conserva el reporte completo.

## Endpoints principales

La referencia completa, parámetros y esquemas se encuentran en `/docs` y `/openapi.json`.

| Grupo | Ejemplos |
| --- | --- |
| Salud | `GET /api/v1/health` |
| Autenticación | `/api/v1/auth/login`, `/api/v1/auth/me`, `/api/v1/auth/totp/*` |
| Administración | `/api/v1/auth/admin/users`, `/api/v1/auth/admin/audit` |
| Nómina y personal | `/api/v1/reportes/nomina/*`, `/api/v1/reportes/personal` |
| Entretenimiento | `/api/v1/reportes/entretenimiento/*` |
| PDF | `/api/v1/reportes/**/*` y rutas PDF equivalentes |
| Cargas | `POST/GET /api/v1/cargas` |
