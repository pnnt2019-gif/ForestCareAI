CREATE DATABASE IF NOT EXISTS forestcare_db
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE forestcare_db;

DROP TABLE IF EXISTS diagnosis_history;
DROP TABLE IF EXISTS activation_codes;
DROP TABLE IF EXISTS subscriptions;
DROP TABLE IF EXISTS users;

-- =====================================================
-- 1. USERS
-- =====================================================
CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    avatar_url VARCHAR(500) NULL,
    plan VARCHAR(50) NOT NULL DEFAULT 'free',
    premium TINYINT(1) NOT NULL DEFAULT 0,
    plan_expires_at TIMESTAMP NULL,
    status ENUM('active', 'disabled', 'banned') NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_users_email (email),
    INDEX idx_users_plan (plan),
    INDEX idx_users_status (status)
);

-- =====================================================
-- 2. SUBSCRIPTIONS
-- =====================================================
CREATE TABLE subscriptions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    plan_name ENUM('free', 'premium', 'business', 'enterprise') NOT NULL DEFAULT 'free',
    status ENUM('active', 'expired', 'cancelled') NOT NULL DEFAULT 'active',
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL,
    activated_by_code VARCHAR(100) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_subscriptions_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE,
    INDEX idx_subscriptions_user_id (user_id),
    INDEX idx_subscriptions_plan (plan_name),
    INDEX idx_subscriptions_status (status),
    INDEX idx_subscriptions_expires_at (expires_at),
    INDEX idx_subscriptions_user_active (user_id, status, expires_at)
);

-- =====================================================
-- 3. ACTIVATION CODES
-- =====================================================
CREATE TABLE activation_codes (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(100) NOT NULL UNIQUE,
    plan_name ENUM('premium', 'business') NOT NULL,
    valid_for_days INT NOT NULL DEFAULT 30,
    is_used TINYINT(1) NOT NULL DEFAULT 0,
    used_by_user_id BIGINT NULL,
    used_at TIMESTAMP NULL,
    created_by VARCHAR(100) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL,
    status ENUM('active', 'used', 'expired', 'revoked') NOT NULL DEFAULT 'active',
    CONSTRAINT fk_activation_codes_user
        FOREIGN KEY (used_by_user_id) REFERENCES users(id)
        ON DELETE SET NULL,
    INDEX idx_activation_code_status (code, status),
    INDEX idx_activation_code_plan (plan_name, status),
    INDEX idx_activation_codes_used_by_user (used_by_user_id)
);

-- =====================================================
-- 4. DIAGNOSIS HISTORY
-- =====================================================
CREATE TABLE diagnosis_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    image_name VARCHAR(255) NULL,
    image_path VARCHAR(500) NULL,
    tree_name VARCHAR(255) NULL,
    disease_name VARCHAR(255) NULL,
    symptoms TEXT NULL,
    severity_level VARCHAR(100) NULL,
    diagnosis_status VARCHAR(100) NULL,
    result_json JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_diagnosis_history_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE,
    INDEX idx_diagnosis_user_time (user_id, created_at DESC),
    INDEX idx_diagnosis_tree (tree_name),
    INDEX idx_diagnosis_status (diagnosis_status)
);

-- =====================================================
-- 5. SAMPLE DATA (OPTIONAL)
-- =====================================================
INSERT INTO users (name, email, password_hash, plan, premium, plan_expires_at)
VALUES
('ForestCare Admin', 'admin@forestcare.ai', '$2b$12$examplehash', 'free', 0, NULL);

INSERT INTO subscriptions (user_id, plan_name, status, started_at, expires_at)
VALUES
(1, 'free', 'active', NOW(), NULL);

INSERT INTO activation_codes (code, plan_name, valid_for_days, is_used, created_by, expires_at, status)
VALUES
('FORESTCARE-PREMIUM-2026', 'premium', 30, 0, 'system', DATE_ADD(NOW(), INTERVAL 365 DAY), 'active');

SELECT 'ForestCare AI MySQL normalized schema ready.' AS status;
