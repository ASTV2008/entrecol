-- =============================================================================
-- 01_nomina.sql  ·  Módulo NÓMINA
-- Proyecto Entrecol · Motor: MariaDB (InnoDB, utf8mb4)
--
-- Orden de creación: de las tablas "padre" (catálogos) a las "hijas",
-- para que cada llave foránea apunte a una tabla que ya existe.
--
-- Política de llaves foráneas:
--   ON UPDATE CASCADE  -> si cambia una llave del padre, se propaga a los hijos.
--   ON DELETE RESTRICT -> no se puede borrar un padre con hijos (protege el
--                         histórico de nómina; el borrado debe ser consciente).
-- =============================================================================

-- ---------------------------------------------------------------------------
-- CATÁLOGOS
-- ---------------------------------------------------------------------------

CREATE TABLE dependencia (
    id_dependencia  SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    nombre          VARCHAR(60)       NOT NULL,
    PRIMARY KEY (id_dependencia),
    UNIQUE KEY uk_dependencia_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Áreas de la empresa (Comercial, Tecnología, ...)';

-- CARGO es entidad débil en el MER: su nombre solo es único DENTRO de una
-- dependencia. Por eso la unicidad es compuesta (id_dependencia, nombre).
CREATE TABLE cargo (
    id_cargo        SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_dependencia  SMALLINT UNSIGNED NOT NULL,
    nombre          VARCHAR(80)       NOT NULL,
    PRIMARY KEY (id_cargo),
    UNIQUE KEY uk_cargo_dependencia_nombre (id_dependencia, nombre),
    CONSTRAINT fk_cargo_dependencia
        FOREIGN KEY (id_dependencia) REFERENCES dependencia (id_dependencia)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Cargos; cada uno pertenece a una única dependencia';

CREATE TABLE eps (
    id_eps  SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    nombre  VARCHAR(60)       NOT NULL,
    PRIMARY KEY (id_eps),
    UNIQUE KEY uk_eps_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Entidades Promotoras de Salud';

CREATE TABLE arl (
    id_arl  SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    nombre  VARCHAR(60)       NOT NULL,
    PRIMARY KEY (id_arl),
    UNIQUE KEY uk_arl_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Administradoras de Riesgos Laborales';

CREATE TABLE fondo_pension (
    id_fondo_pension  SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    nombre            VARCHAR(60)       NOT NULL,
    PRIMARY KEY (id_fondo_pension),
    UNIQUE KEY uk_fondo_pension_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Fondos de pensión';

-- ---------------------------------------------------------------------------
-- EMPLEADO
-- La llave primaria es el código que entrega el cliente (llave natural estable).
-- La dependencia NO se guarda aquí: se obtiene vía cargo (3FN).
-- ---------------------------------------------------------------------------

CREATE TABLE empleado (
    codigo            INT UNSIGNED      NOT NULL COMMENT 'Código del empleado entregado por el cliente',
    nombre_empleado   VARCHAR(100)      NOT NULL COMMENT 'Apellidos y nombres, como los entrega el cliente',
    fecha_ingreso     DATE              NOT NULL,
    sueldo            DECIMAL(14,2)     NOT NULL,
    id_cargo          SMALLINT UNSIGNED NOT NULL,
    id_eps            SMALLINT UNSIGNED NOT NULL,
    id_arl            SMALLINT UNSIGNED NOT NULL,
    id_fondo_pension  SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (codigo),
    CONSTRAINT ck_empleado_sueldo CHECK (sueldo > 0),
    CONSTRAINT fk_empleado_cargo
        FOREIGN KEY (id_cargo)         REFERENCES cargo (id_cargo)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_empleado_eps
        FOREIGN KEY (id_eps)           REFERENCES eps (id_eps)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_empleado_arl
        FOREIGN KEY (id_arl)           REFERENCES arl (id_arl)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_empleado_fondo_pension
        FOREIGN KEY (id_fondo_pension) REFERENCES fondo_pension (id_fondo_pension)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Empleados de la empresa';

-- ---------------------------------------------------------------------------
-- PERIODOS Y NOVEDADES
-- ---------------------------------------------------------------------------

CREATE TABLE periodo (
    id_periodo  SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    anio        SMALLINT UNSIGNED NOT NULL,
    mes         TINYINT UNSIGNED  NOT NULL,
    PRIMARY KEY (id_periodo),
    UNIQUE KEY uk_periodo_anio_mes (anio, mes),
    CONSTRAINT ck_periodo_mes  CHECK (mes BETWEEN 1 AND 12),
    CONSTRAINT ck_periodo_anio CHECK (anio BETWEEN 1990 AND 2100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Meses de nómina (MM/AAAA)';

-- Una fila por empleado y mes. Los días trabajados NO se guardan: son un valor
-- derivado (30 - días de incapacidad - días de vacaciones) y se calculan al
-- consultar, para evitar inconsistencias.
CREATE TABLE novedad_mensual (
    id_novedad    INT UNSIGNED      NOT NULL AUTO_INCREMENT,
    codigo        INT UNSIGNED      NOT NULL,
    id_periodo    SMALLINT UNSIGNED NOT NULL,
    bonificacion  DECIMAL(14,2)     NOT NULL DEFAULT 0,
    transporte    DECIMAL(14,2)     NOT NULL DEFAULT 0,
    PRIMARY KEY (id_novedad),
    UNIQUE KEY uk_novedad_empleado_periodo (codigo, id_periodo),
    CONSTRAINT ck_novedad_bonificacion CHECK (bonificacion >= 0),
    CONSTRAINT ck_novedad_transporte   CHECK (transporte >= 0),
    CONSTRAINT fk_novedad_empleado
        FOREIGN KEY (codigo)     REFERENCES empleado (codigo)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_novedad_periodo
        FOREIGN KEY (id_periodo) REFERENCES periodo (id_periodo)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Novedades de un empleado en un periodo';

-- dias_reportados se guarda tal como lo entrega el cliente: en los datos de
-- muestra NO coincide siempre con la diferencia entre fechas, por lo que no es
-- derivable. Si un evento cruza de mes, hay una fila por cada mes afectado.
CREATE TABLE incapacidad (
    id_incapacidad   INT UNSIGNED     NOT NULL AUTO_INCREMENT,
    id_novedad       INT UNSIGNED     NOT NULL,
    fecha_inicio     DATE             NOT NULL,
    fecha_fin        DATE             NOT NULL,
    dias_reportados  TINYINT UNSIGNED NOT NULL,
    PRIMARY KEY (id_incapacidad),
    UNIQUE KEY uk_incapacidad_novedad_inicio (id_novedad, fecha_inicio),
    CONSTRAINT ck_incapacidad_fechas CHECK (fecha_fin >= fecha_inicio),
    CONSTRAINT ck_incapacidad_dias   CHECK (dias_reportados BETWEEN 1 AND 31),
    CONSTRAINT fk_incapacidad_novedad
        FOREIGN KEY (id_novedad) REFERENCES novedad_mensual (id_novedad)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Incapacidades registradas en una novedad mensual';

CREATE TABLE vacacion (
    id_vacacion      INT UNSIGNED     NOT NULL AUTO_INCREMENT,
    id_novedad       INT UNSIGNED     NOT NULL,
    fecha_inicio     DATE             NOT NULL,
    fecha_fin        DATE             NOT NULL,
    dias_reportados  TINYINT UNSIGNED NOT NULL,
    PRIMARY KEY (id_vacacion),
    UNIQUE KEY uk_vacacion_novedad_inicio (id_novedad, fecha_inicio),
    CONSTRAINT ck_vacacion_fechas CHECK (fecha_fin >= fecha_inicio),
    CONSTRAINT ck_vacacion_dias   CHECK (dias_reportados BETWEEN 1 AND 31),
    CONSTRAINT fk_vacacion_novedad
        FOREIGN KEY (id_novedad) REFERENCES novedad_mensual (id_novedad)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Vacaciones registradas en una novedad mensual';
