-- ============================================================
-- Pronuncia - schema MySQL
-- Rode no MySQL Workbench (uma vez) para criar o banco.
-- ============================================================

CREATE DATABASE IF NOT EXISTS pronuncia
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE pronuncia;

-- ---------- usuarios (voce + 2 filhos) ----------
CREATE TABLE IF NOT EXISTS users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  name          VARCHAR(50)  NOT NULL,
  email         VARCHAR(120) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,          -- bcrypt, nunca senha pura
  role          ENUM('parent','child') NOT NULL DEFAULT 'child',
  level         ENUM('A2','B1','B2','C1') NOT NULL DEFAULT 'B1',
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------- banco de frases-alvo para ler ----------
CREATE TABLE IF NOT EXISTS phrases (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  text       VARCHAR(500) NOT NULL,
  level      ENUM('A2','B1','B2','C1') NOT NULL DEFAULT 'B1',
  focus      VARCHAR(80)  NULL,                 -- ex: "th sound", "vowel /ae/ vs /e/"
  active     TINYINT(1)   NOT NULL DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_level (level, active)
);

-- ---------- cada tentativa de pratica ----------
-- audio e descartado: guardamos so texto/feedback
CREATE TABLE IF NOT EXISTS attempts (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  user_id       INT NOT NULL,
  phrase_id     INT NOT NULL,
  target_text   VARCHAR(500) NOT NULL,          -- copia da frase no momento (historico estavel)
  transcription VARCHAR(500) NULL,              -- o que o Whisper ouviu
  diff_json     JSON NULL,                      -- palavras erradas / baixa confianca / pausas
  feedback      TEXT NULL,                      -- feedback curto do LLM local
  explanation   TEXT NULL,                      -- explicacao fonetica detalhada (so quando nota baixa)
  wpm           INT NULL,                       -- ritmo aproximado (palavras/min)
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id)   REFERENCES users(id)   ON DELETE CASCADE,
  FOREIGN KEY (phrase_id) REFERENCES phrases(id) ON DELETE CASCADE,
  INDEX idx_user_time (user_id, created_at)
);
