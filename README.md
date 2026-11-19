# Entrecol

**Entrecol 1.0.0** es una aplicación web para consultar información de nómina y entretenimiento y administrar sus fuentes de datos. Integrado en un mismo origen, incluye frontend estático, API FastAPI, ETL para tres formatos y MariaDB.

## Funcionalidades

- Reportes de nómina, personal, salud y pensión y novedades.
- Reportes de películas y libros, con salida JSON y PDF.
- Autenticación multifactor obligatoria, sesiones revocables y roles `admin` y `report_reader`.
- Auditoría de autenticación, administración, cargas y accesos a reportes.
- Carga validada de películas (`.dat`), libros (`.json`) y nómina (`.xlsx`).
- Ejecución de API y base de datos en contenedores Docker.

## Arquitectura resumida

```text
Navegador -> Frontend estático -> API FastAPI -> Servicios/repositorios -> MariaDB
                                      |
                                      +-> Motores ETL
                                      +-> Generación de PDF
                                      +-> Sesiones y auditoría
```

La API monta el frontend en `/`, expone la documentación interactiva en `/docs` y agrupa sus servicios bajo `/api/v1`. La especificación OpenAPI completa también está disponible en `/openapi.json`.

## Requisitos

| Componente | Uso |
| --- | --- |
| Docker Engine + Docker Compose v2 | Ejecución recomendada |
| Python 3.12 | Pruebas locales |
| MariaDB 11.4 | Motor de datos del Compose |
| `curl` | Comprobaciones manuales |

## Inicio rápido

1. Copia la plantilla sin sobrescribir una configuración existente:

   ```sh
   if [ ! -f .env ]; then cp .env.example .env; fi
   ```

2. Cambia todas las contraseñas de ejemplo en `.env` y genera las claves criptográficas:

   ```sh
   python3 -c 'import secrets; print(secrets.token_hex(32))'
   python3 -c 'import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())'
   ```

   Usa la primera salida como `SECRET_KEY` y la segunda como `TOTP_ENCRYPTION_KEY`. No publiques ni confirmes `.env`.

3. Construye e inicia todos los servicios:

   ```sh
   docker compose up -d --build
   docker compose ps
   ```

4. Comprueba la salud de la aplicación:

   ```sh
   curl -fsS http://127.0.0.1:8000/api/v1/health
   ```

   La respuesta esperada es `{"status":"ok","database":"up"}`.

5. Crea el primer administrador:

   ```sh
   docker compose exec api python -m app.security.cli create-admin
   ```

   El correo y la contraseña se solicitan de forma interactiva. No existen credenciales iniciales ni auto-registro.

6. Abre `http://127.0.0.1:8000`, inicia sesión y configura TOTP.

Al modificar código o recursos del frontend, reconstruye el servicio API:

```sh
docker compose up -d --build api
```

## Configuración

Las variables principales se leen desde `.env`:

| Variable | Propósito |
| --- | --- |
| `DB_ROOT_PASSWORD` | Usuario root usado por MariaDB al inicializar el volumen |
| `DB_NAME` | Nombre de la base principal |
| `DB_USER` | Usuario de aplicación |
| `DB_PASSWORD` | Contraseña de la aplicación |
| `DB_PORT` | Puerto publicado en el host |
| `SECRET_KEY` | Firma de tokens CSRF; mínimo 32 bytes |
| `TOTP_ENCRYPTION_KEY` | Clave Fernet para semillas TOTP |

API y MariaDB se publican únicamente en `127.0.0.1`. Para una instalación accesible desde otro equipo, coloca TLS y controles de acceso delante de la API. El contenedor API se ejecuta como el usuario sin privilegios `entrecol` (UID 10001).

## Datos y actualizaciones

En una instalación nueva, MariaDB ejecuta automáticamente `database/init/01_nomina.sql`, `02_entretenimiento.sql`, `03_seguridad.sql` y `04_cargas.sql` al crear el volumen.

Si el volumen ya existe, los scripts de inicialización no vuelven a ejecutarse. Los scripts `03_seguridad.sql` y `04_cargas.sql` son idempotentes y pueden aplicarse manualmente; consulta las instrucciones de [seguridad](docs/seguridad_etapa10.md) y [cargas](docs/cargas_archivos_etapa11.md).

No uses `docker compose down -v` salvo que quieras eliminar deliberadamente todos los datos de MariaDB. Antes de actualizar o cambiar claves, realiza un respaldo de:

- El volumen `db_data`.
- Las variables `SECRET_KEY` y `TOTP_ENCRYPTION_KEY`.
- Los scripts y datos de carga originales.

Perder `TOTP_ENCRYPTION_KEY` impide descifrar las semillas TOTP existentes.

## Uso

- Los administradores gestionan cuentas, auditoría y cargas.
- Los lectores consultan y descargan reportes, pero no administran cuentas ni cargan datos.
- Toda cuenta activa requiere TOTP.
- Los archivos cargados no se conservan en disco; sí se conserva su nombre, tamaño, fecha, hash SHA-256 y resultado.

Consulta las guías funcionales:

- [Guía de seguridad y auditoría](docs/seguridad_etapa10.md)
- [Carga de archivos y ETL](docs/cargas_archivos_etapa11.md)
- [Interfaz de usuario](docs/frontend_etapa12.md)
- [Arquitectura y organización técnica](docs/arquitectura.md)
- [Operación y respaldo](docs/operacion.md)

## Pruebas

Las dependencias de ejecución están en `backend/requirements.txt`; las herramientas de prueba están separadas en `requirements-dev.txt` y no se incluyen en la imagen de producción.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt

docker compose up -d db
set -a
. ./.env
set +a

cd backend
python -m pytest
```

La suite requiere una base separada llamada `<DB_NAME>_test`. Para una instalación desechable con los valores de ejemplo:

```sql
CREATE DATABASE entrecol_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON entrecol_test.* TO 'entrecol_user'@'%';
```

Las pruebas crean y eliminan las tablas de la base de pruebas. **No se deben ejecutar con credenciales de producción**.

## Operación básica

```sh
docker compose ps
docker compose logs -f api
docker compose logs -f db
docker compose restart api
docker compose down
```

`docker compose down` conserva el volumen de MariaDB. Para detener y eliminar solo los contenedores conservando los datos, usa este último comando sin `-v`.

## Solución de problemas

| Problema | Comprobación |
| --- | --- |
| La API no responde | `docker compose ps`, `docker compose logs api` y `docker compose restart api` |
| MariaDB no está lista | `docker compose logs db` y `docker compose ps db` |
| La interfaz usa código antiguo | Reconstruye con `docker compose up -d --build api` |
| La base no existe | Comprueba `<DB_NAME>_test` y los permisos para pruebas |
| La sesión TOTP falla | Confirma reloj del servidor, estado de la cuenta y vigencia de `TOTP_ENCRYPTION_KEY` |
| Hay cambios sin inicializar | En una base existente, aplica los scripts SQL indicados en las guías |
