# Etapa 11: carga de archivos

## Alcance

Los administradores pueden cargar archivos nuevos desde **Carga de archivos** o mediante la API. Se reutilizan los servicios ETL actuales; el archivo se procesa durante la solicitud y no se conserva en el servidor.

| Tipo | Archivo esperado | Período |
| --- | --- | --- |
| Películas | `movies.dat` (`.dat`) | No aplica |
| Libros | `Books.json` (`.json`) | No aplica |
| Nómina | `Nomina.xlsx` (`.xlsx`) | Obligatorio, `AAAA-MM` |

El límite de tamaño es 20 MiB. El nombre/extensión no sustituye la validación del contenido: cada ETL verifica la estructura del archivo. Si el procesamiento falla, se revierte la carga de datos y se conserva el intento fallido en el historial.

## API

- `POST /api/v1/cargas`: recibe `multipart/form-data` con `tipo`, `archivo` y, para nómina, `periodo`. Requiere una sesión MFA activa de administrador y el encabezado CSRF `X-CSRF-Token`.
- `GET /api/v1/cargas?limit=50`: consulta el historial reciente. Requiere sesión MFA activa de administrador; el límite permitido es de 1 a 100 registros.

`carga_archivo` guarda el usuario (también una copia del correo), nombre original saneado, tipo, período, tamaño, SHA-256, resultado, conteos del ETL y fecha. No conserva el contenido del archivo. Los eventos de auditoría registran cargas exitosas y fallidas.

## Base de datos

En una base nueva, `database/init/04_cargas.sql` se ejecuta después de los scripts anteriores.

En una base existente, aplica una vez el script aditivo e idempotente:

```sh
docker compose exec -T db sh -c \
  'mariadb --protocol=socket -uroot -p"$MARIADB_ROOT_PASSWORD" "$MARIADB_DATABASE"' \
  < database/init/04_cargas.sql
```

Después de actualizar dependencias/código, reconstruye la API:

```sh
docker compose up -d --build api
```
