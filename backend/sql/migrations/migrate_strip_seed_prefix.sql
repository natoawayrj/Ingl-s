-- Remove o prefixo 'seed: ' do campo focus (ex.: 'seed: TH + -worth' -> 'TH + -worth').
-- Rodar MANUALMENTE no Workbench. O código já normaliza o foco, então é opcional.
-- Já coberta por migrate_fix_focus_encoding.sql (que também corrige o encoding).
USE pronuncia;

UPDATE phrases
SET focus = TRIM(SUBSTRING(focus, 6))
WHERE focus LIKE 'seed:%';
