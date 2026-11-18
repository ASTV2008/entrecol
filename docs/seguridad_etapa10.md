# Etapa 10: autenticación y auditoría

## Alcance implementado

- Cuentas sin auto-registro, con roles `admin` y `report_reader`.
- Contraseñas con Argon2id y cambio obligatorio para cuentas nuevas y contraseñas restablecidas.
- TOTP obligatorio para todas las cuentas; las semillas se cifran con Fernet.
- Códigos de recuperación aleatorios de un solo uso, almacenados como hashes.
- Renovación de códigos con una verificación TOTP; restablecimiento de TOTP de terceros por un administrador y recuperación local del administrador mediante CLI.
- Sesiones opacas en base de datos, revocables, con cookie `HttpOnly`, `Secure`, `SameSite=Strict`, protección CSRF, 30 minutos de inactividad y un máximo de 8 horas.
- Bloqueo de autenticación después de cinco intentos fallidos durante 15 minutos.
- Protección de todos los reportes JSON y PDF para administradores y lectores autenticados.
- Auditoría de autenticación, MFA, cierre de sesión, administración de cuentas y accesos a reportes. Los filtros y datos de los reportes no se escriben en la auditoría.
- Retención configurada en 365 días. La purga es manual y requiere confirmación explícita.

## Instalación o actualización de la base de datos

En una base nueva, `database/init/03_seguridad.sql` se ejecuta automáticamente al crear el volumen de MariaDB.

En una base que ya existe, aplicar el script idempotente una vez:

```sh
docker compose exec -T db sh -c \
  'mariadb --protocol=socket -uroot -p"$MARIADB_ROOT_PASSWORD" "$MARIADB_DATABASE"' \
  < database/init/03_seguridad.sql
```

La operación crea únicamente las tablas de seguridad; no borra ni transforma las tablas de reportes.

## Claves y primer administrador

1. Configura `SECRET_KEY` con al menos 32 bytes aleatorios:

   ```sh
   python3 -c 'import secrets; print(secrets.token_hex(32))'
   ```
2. Genera `TOTP_ENCRYPTION_KEY` y guárdala en `.env`:

   ```sh
   python3 -c 'import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())'
   ```

3. Conserva una copia privada y respaldada de ambas claves. Perder o cambiar `TOTP_ENCRYPTION_KEY` sin volver a cifrar las semillas deja las cuentas sin acceso al TOTP existente.
4. Recrea la API para inyectar las variables nuevas:

   ```sh
   docker compose up -d --build api
   ```

5. Crea el primer administrador de forma interactiva; la contraseña se solicita sin mostrarla ni pasarla como argumento:

   ```sh
   docker compose exec api python -m app.security.cli create-admin
   ```

El primer acceso de cada persona presenta un QR local para configurar una aplicación TOTP. Los códigos de recuperación solo se muestran una vez. Los administradores pueden crear cuentas, asignar roles, desactivarlas y restablecer contraseñas temporales desde la interfaz.

Una cuenta puede renovar sus códigos de recuperación con un TOTP actual. Si alguien pierde tanto su autenticador como sus códigos, otro administrador puede restablecerle MFA desde la administración. Para recuperar el único administrador, ejecutar `docker compose exec api python -m app.security.cli reset-totp --email correo --confirm` desde el host autorizado; la cuenta deberá registrar TOTP de nuevo.

## Auditoría y operación

Los eventos se consultan desde la sección de administración. Para eliminar manualmente eventos anteriores al período de retención:

```sh
docker compose exec api python -m app.security.cli purge-audit --confirm
```

La aplicación nunca registra contraseñas, semillas TOTP ni códigos de recuperación. Para despliegues fuera del entorno local, termina TLS en un proxy confiable y conserva `COOKIE_SECURE=true`; no publiques la API ni MariaDB en interfaces de red públicas sin una configuración de infraestructura revisada.
