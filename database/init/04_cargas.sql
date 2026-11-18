-- Etapa 11: historial de cargas de archivos. Es idempotente para bases existentes.

CREATE TABLE IF NOT EXISTS carga_archivo (
    id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    usuario_id       INT UNSIGNED NULL,
    usuario_email    VARCHAR(254) NOT NULL,
    nombre_archivo   VARCHAR(255) NOT NULL,
    tipo             VARCHAR(16) NOT NULL,
    periodo          CHAR(7) NULL,
    tamano_bytes     BIGINT UNSIGNED NOT NULL,
    sha256           CHAR(64) NOT NULL,
    estado           VARCHAR(16) NOT NULL,
    filas_leidas     INT UNSIGNED NOT NULL DEFAULT 0,
    filas_aceptadas  INT UNSIGNED NOT NULL DEFAULT 0,
    filas_rechazadas INT UNSIGNED NOT NULL DEFAULT 0,
    mensaje          VARCHAR(512) NULL,
    fecha_carga      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    KEY ix_carga_archivo_fecha (fecha_carga),
    KEY ix_carga_archivo_usuario_fecha (usuario_id, fecha_carga),
    CONSTRAINT ck_carga_archivo_tipo
        CHECK (tipo IN ('nomina', 'peliculas', 'libros')),
    CONSTRAINT ck_carga_archivo_estado
        CHECK (estado IN ('succeeded', 'failed')),
    CONSTRAINT fk_carga_archivo_usuario
        FOREIGN KEY (usuario_id) REFERENCES app_user (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
