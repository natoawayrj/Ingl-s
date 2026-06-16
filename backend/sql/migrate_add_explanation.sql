-- ============================================================
-- Migração: adiciona coluna 'explanation' em attempts.
-- Rode UMA vez no Workbench se o banco 'pronuncia' já existe
-- (bancos novos via schema.sql já têm a coluna).
-- ============================================================
USE pronuncia;

ALTER TABLE attempts
  ADD COLUMN explanation TEXT NULL AFTER feedback;
