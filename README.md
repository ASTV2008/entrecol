# Entrecol

Aplicación web para administrar y consultar información de nómina y entretenimiento. Incluye ETL para películas, libros y nómina; reportes JSON y PDF; autenticación con MFA, roles y auditoría; y carga administrativa de archivos.

## Requisitos

- Docker Engine con Docker Compose v2.
- Python 3.12 para ejecutar las pruebas desde un entorno virtual.
- `curl` para comprobar el estado de la API.

## Configuración y arranque

1. Crea `.env` desde la plantilla, sin sobrescribir una configuración existente:

   ```sh
   if [ ! -f .env ]; then cp .env.example .env; fi
   ```

2. Edita `.env`: define contraseñas propias para MariaDB y genera claves nuevas para la aplicación:

   ```sh
   python3 -c 'import secrets; print(secrets.token_hex(32))'
   python3 -c 'import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())'
   ```

   Usa la primera salida como `SECRET_KEY` y la segunda como `TOTP_ENCRYPTION_KEY`. Conserva copias privadas y respaldadas de ambas. No compartas ni subas `.env` al repositorio.

3. Inicia los servicios:

   ```sh
   docker compose up -d --build
   docker compose ps
   curl -fsS http://127.0.0.1:8000/api/v1/health
   ```

   La API y MariaDB solo se publican en `127.0.0.1`. La imagen de ejecución contiene el frontend y ejecuta la API como el usuario sin privilegios `entrecol` (UID 10001). Al modificar código o recursos de interfaz, vuelve a construir la API con `docker compose up -d --build api`.

4. En una instalación nueva, MariaDB ejecuta los scripts `database/init/*.sql` al crear el volumen. Si la base ya existía, esos scripts no se ejecutan de nuevo: conserva el volumen y consulta las instrucciones de actualización de [seguridad](docs/seguridad_etapa10.md) y [cargas](docs/cargas_archivos_etapa11.md).

5. Crea el primer administrador una sola vez:

   ```sh
   docker compose exec api python -m app.security.cli create-admin
   ```

   El comando pide el correo y la contraseña de forma interactiva. En el primer inicio de sesión se configura TOTP. No hay credenciales iniciales ni auto-registro.

Abre `http://127.0.0.1:8000`. Los administradores pueden crear cuentas, consultar la auditoría y cargar películas (`.dat`), libros (`.json`) o nómina (`.xlsx`, indicando período `AAAA-MM`). Los lectores pueden consultar y exportar reportes, pero no administrar cuentas ni cargar archivos.

## Pruebas

Las dependencias de ejecución están en `backend/requirements.txt`. Las herramientas de pruebas se mantienen aparte en `requirements-dev.txt` y no se instalan en la imagen de la API.

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

La suite requiere una base de pruebas llamada `<DB_NAME>_test` y permisos para crear, eliminar y consultar sus tablas. En un entorno local desechable, créala y otorga permisos al usuario de desarrollo; por ejemplo, con los valores de la plantilla:

```sql
CREATE DATABASE entrecol_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON entrecol_test.* TO 'entrecol_user'@'%';
```

La suite crea y elimina tablas en esa base de pruebas. **No la ejecutes con credenciales o una base de producción**. La prueba de sincronización ORM consulta la base configurada en `DB_NAME` en modo de solo lectura.

## Operación

```sh
docker compose logs -f api
docker compose logs -f db
docker compose down
```

`docker compose down` conserva el volumen de MariaDB. Evita `docker compose down -v` salvo que quieras eliminar deliberadamente la base de datos. Respalda el volumen de MariaDB y las claves de `.env`.

Para desplegar fuera de localhost, configura TLS delante de la API y conserva las cookies seguras. No publiques MariaDB ni la API en interfaces públicas sin una revisión de infraestructura.

## Documentación

- [Seguridad y auditoría — etapa 10](docs/seguridad_etapa10.md)
- [Carga de archivos — etapa 11](docs/cargas_archivos_etapa11.md)
- [Frontend — etapa 12](docs/frontend_etapa12.md)
