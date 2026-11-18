-- Etapa 10: usuarios, sesiones revocables, códigos de recuperación y auditoría.
-- Es idempotente para poder aplicarlo tanto en una base nueva como en una existente.

CREATE TABLE IF NOT EXISTS app_user (
    id                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
    email                 VARCHAR(254) NOT NULL,
    password_hash         VARCHAR(255) NOT NULL,
    role                  VARCHAR(32) NOT NULL DEFAULT 'report_reader',
    is_active             TINYINT(1) NOT NULL DEFAULT 1,
    must_change_password  TINYINT(1) NOT NULL DEFAULT 0,
    totp_secret_encrypted VARCHAR(512) NULL,
    totp_enabled          TINYINT(1) NOT NULL DEFAULT 0,
    last_totp_step        BIGINT UNSIGNED NULL,
    failed_login_attempts INT NOT NULL DEFAULT 0,
    locked_until          DATETIME(6) NULL,
    created_at            DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at            DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    last_login_at         DATETIME(6) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_app_user_email (email),
    CONSTRAINT ck_app_user_role CHECK (role IN ('admin', 'report_reader'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS auth_session (
    token_hash          CHAR(64) NOT NULL,
    user_id             INT UNSIGNED NOT NULL,
    state               VARCHAR(24) NOT NULL,
    created_at          DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    last_seen_at        DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    expires_at          DATETIME(6) NOT NULL,
    absolute_expires_at DATETIME(6) NOT NULL,
    PRIMARY KEY (token_hash),
    KEY ix_auth_session_user_expires (user_id, expires_at),
    CONSTRAINT ck_auth_session_state
        CHECK (state IN ('password_change', 'totp_setup', 'totp_required', 'active')),
    CONSTRAINT fk_auth_session_user
        FOREIGN KEY (user_id) REFERENCES app_user (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_recovery_code (
    id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id    INT UNSIGNED NOT NULL,
    code_hash  CHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    used_at    DATETIME(6) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_user_recovery_code_hash (code_hash),
    CONSTRAINT fk_recovery_code_user
        FOREIGN KEY (user_id) REFERENCES app_user (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audit_event (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    actor_user_id INT UNSIGNED NULL,
    target_user_id INT UNSIGNED NULL,
    event_type    VARCHAR(64) NOT NULL,
    resource      VARCHAR(128) NULL,
    success       TINYINT(1) NOT NULL,
    ip_address    VARCHAR(45) NULL,
    user_agent    VARCHAR(255) NULL,
    created_at    DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    KEY ix_audit_event_created (created_at),
    KEY ix_audit_event_actor_created (actor_user_id, created_at),
    CONSTRAINT fk_audit_actor
        FOREIGN KEY (actor_user_id) REFERENCES app_user (id) ON DELETE SET NULL,
    CONSTRAINT fk_audit_target
        FOREIGN KEY (target_user_id) REFERENCES app_user (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
