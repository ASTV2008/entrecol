-- =============================================================================
-- 02_entretenimiento.sql  ·  Módulo ENTRETENIMIENTO (películas y libros)
-- Proyecto Entrecol · Motor: MariaDB (InnoDB, utf8mb4)
--
-- Películas y libros son dos subdominios independientes: no se relacionan.
-- Las relaciones N:M (película-género, libro-autor) se resuelven con tablas
-- intermedias cuya llave primaria es compuesta por las dos llaves foráneas.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- PELÍCULAS
-- ---------------------------------------------------------------------------

-- El año viaja dentro del título en el archivo origen ("Toy Story (1995)").
-- El ETL lo separa en anio_estreno para poder consultar por rango de años.
CREATE TABLE pelicula (
    id_pelicula   INT UNSIGNED      NOT NULL COMMENT 'ID entregado en movies.dat (con huecos)',
    titulo        VARCHAR(200)      NOT NULL COMMENT 'Título sin el año',
    anio_estreno  SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (id_pelicula),
    KEY ix_pelicula_anio (anio_estreno),
    CONSTRAINT ck_pelicula_anio CHECK (anio_estreno BETWEEN 1800 AND 2100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Catálogo de películas';

CREATE TABLE genero (
    id_genero  TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    nombre     VARCHAR(30)      NOT NULL,
    PRIMARY KEY (id_genero),
    UNIQUE KEY uk_genero_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Géneros cinematográficos';

-- Una película puede tener 0 géneros: la etiqueta "(no genres listed)" del
-- archivo no es un género y el ETL no genera filas para ella.
CREATE TABLE pelicula_genero (
    id_pelicula  INT UNSIGNED     NOT NULL,
    id_genero    TINYINT UNSIGNED NOT NULL,
    PRIMARY KEY (id_pelicula, id_genero),
    CONSTRAINT fk_pelicula_genero_pelicula
        FOREIGN KEY (id_pelicula) REFERENCES pelicula (id_pelicula)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_pelicula_genero_genero
        FOREIGN KEY (id_genero)   REFERENCES genero (id_genero)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Relación N:M entre película y género';

-- ---------------------------------------------------------------------------
-- LIBROS
-- ---------------------------------------------------------------------------

CREATE TABLE editorial (
    id_editorial  INT UNSIGNED NOT NULL AUTO_INCREMENT,
    nombre        VARCHAR(120) NOT NULL,
    PRIMARY KEY (id_editorial),
    UNIQUE KEY uk_editorial_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Editoriales';

-- El código se conserva tal como viene (eng, en-US, en-GB, spa...): unificarlos
-- sería inventar información que el archivo origen no contiene.
CREATE TABLE idioma (
    id_idioma  TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    codigo     VARCHAR(15)      NOT NULL,
    PRIMARY KEY (id_idioma),
    UNIQUE KEY uk_idioma_codigo (codigo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Códigos de idioma de los libros';

-- El archivo no trae identificador de autor: se asume que el nombre identifica
-- al autor (limitación: dos homónimos se tratarían como una sola persona).
CREATE TABLE autor (
    id_autor  INT UNSIGNED NOT NULL AUTO_INCREMENT,
    nombre    VARCHAR(120) NOT NULL,
    PRIMARY KEY (id_autor),
    UNIQUE KEY uk_autor_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Autores';

-- isbn e isbn13 son texto (hay ISBN con letras) y NO son únicos: el archivo
-- origen trae un ISBN duplicado, por eso la llave es id_libro.
-- fecha_publicacion admite NULL: llega como texto M/D/AAAA y puede no ser una
-- fecha de calendario válida; en ese caso el ETL lo registra como rechazo.
CREATE TABLE libro (
    id_libro               INT UNSIGNED      NOT NULL COMMENT 'bookID entregado en Books.json',
    titulo                 VARCHAR(300)      NOT NULL,
    isbn                   VARCHAR(13)       NOT NULL,
    isbn13                 VARCHAR(13)       NOT NULL,
    num_paginas            SMALLINT UNSIGNED NOT NULL,
    fecha_publicacion      DATE              NULL,
    calificacion_promedio  DECIMAL(3,2)      NOT NULL,
    num_calificaciones     INT UNSIGNED      NOT NULL,
    num_resenas            INT UNSIGNED      NOT NULL,
    id_editorial           INT UNSIGNED      NOT NULL,
    id_idioma              TINYINT UNSIGNED  NOT NULL,
    PRIMARY KEY (id_libro),
    KEY ix_libro_calificacion (calificacion_promedio),
    KEY ix_libro_fecha_publicacion (fecha_publicacion),
    CONSTRAINT ck_libro_calificacion CHECK (calificacion_promedio BETWEEN 0 AND 5),
    CONSTRAINT fk_libro_editorial
        FOREIGN KEY (id_editorial) REFERENCES editorial (id_editorial)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_libro_idioma
        FOREIGN KEY (id_idioma)    REFERENCES idioma (id_idioma)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Catálogo de libros';

-- orden_autoria: posición del autor en el campo "authors" del origen
-- (1 = autor principal), porque el orden es información de la relación.
CREATE TABLE libro_autor (
    id_libro       INT UNSIGNED     NOT NULL,
    id_autor       INT UNSIGNED     NOT NULL,
    orden_autoria  TINYINT UNSIGNED NOT NULL,
    PRIMARY KEY (id_libro, id_autor),
    CONSTRAINT ck_libro_autor_orden CHECK (orden_autoria >= 1),
    CONSTRAINT fk_libro_autor_libro
        FOREIGN KEY (id_libro) REFERENCES libro (id_libro)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_libro_autor_autor
        FOREIGN KEY (id_autor) REFERENCES autor (id_autor)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Relación N:M entre libro y autor';
