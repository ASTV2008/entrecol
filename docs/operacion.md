# Operación y respaldo

## Comandos diarios

```sh
docker compose ps
docker compose logs --tail=100 api
docker compose logs --tail=100 db
docker compose restart api
docker compose exec api python -m app.security.cli purge-audit --confirm
```

La interfaz puede verificarse en `http://127.0.0.1:8000`. La salud técnica puede comprobarse con:

```sh
curl -fsS http://127.0.0.1:8000/api/v1/health
```

El servicio `api` incluye un healthcheck automático. Un estado `degraded` significa que la API responde, pero MariaDB no pudo ejecutar la consulta de salud.

## Actualización de una instalación

1. Conserva una copia del archivo `.env` y realiza el respaldo.
2. Obtén el código actualizado.
3. Revisa si los scripts SQL incluyen cambios respecto a la base existente.
4. Construye e inicia:

   ```sh
   docker compose up -d --build
   ```

5. Comprueba contenedores y salud:

   ```sh
   docker compose ps
   curl -fsS http://127.0.0.1:8000/api/v1/health
   ```

Los scripts `database/init/*.sql` no deben ejecutarse automáticamente sobre un volumen existente. En ese caso, aplica solo los scripts documentados como aditivos.

## Respaldo de MariaDB

Ejemplo de respaldo lógico desde el contenedor:

```sh
docker compose exec -T db sh -c \
  'mariadb-dump --protocol=socket -uroot -p"$MARIADB_ROOT_PASSWORD" "$MARIADB_DATABASE"' \
  > respaldo-entrecol.sql
```

El archivo contiene información sensible y debe cifrarse o almacenarse con permisos restringidos.

Para restaurar en una base creada y vacía:

```sh
docker compose exec -T db sh -c \
  'mariadb --protocol=socket -uroot -p"$MARIADB_ROOT_PASSWORD" "$MARIADB_DATABASE"' \
  < respaldo-entrecol.sql
```

Detener tráfico de escritura antes de restaurar es una práctica obligatoria. Prueba periódicamente la restauración en una base desechable.

## Respaldo de claves

Respalda de forma segura y separada:

- `SECRET_KEY`.
- `TOTP_ENCRYPTION_KEY`.
- Contraseñas de la base de datos de `.env`.

No cambies `TOTP_ENCRYPTION_KEY` sin un procedimiento explícito de re-cifrado o restablecimiento de MFA. Cambiar `SECRET_KEY` puede invalidar la firma usada por las sesiones o las protecciones derivadas.

## Retención y auditoría

La retención predeterminada es de 365 días y se puede configurar entre 30 y 3650 días. La eliminación real exige:

```sh
docker compose exec api python -m app.security.cli purge-audit --confirm
```

Conservar o archivar auditoría fuera de la aplicación debe incluir una política de acceso, integridad y protección de datos personales.

## Administración de cuentas

Crear el primer administrador:

```sh
docker compose exec api python -m app.security.cli create-admin
```

Restablecer una contraseña:

```sh
docker compose exec api python -m app.security.cli reset-password --email correo --confirm
```

Restablecer MFA:

```sh
docker compose exec api python -m app.security.cli reset-totp --email correo --confirm
```

Estos comandos generan o revocan credenciales sensibles y solo deben ejecutarse desde un host autorizado.

## Despliegue

La configuración incluida está diseñada para localhost. Para producción:

- Termina HTTPS en un proxy reverso o balanceador confiable.
- Conserva `COOKIE_SECURE=true` y el atributo `Secure` de la cookie.
- Usa secretos únicos, aleatorios y administrados fuera del repositorio.
- No publiques el puerto de MariaDB.
- Limita el acceso administrativo y de operación.
- Configura respaldos, renovación de certificados y supervisión.
- Conserva registros y métricas sin escribir contraseñas o semillas TOTP.
