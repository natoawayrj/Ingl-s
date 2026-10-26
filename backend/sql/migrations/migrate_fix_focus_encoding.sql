-- Corrige phrases.focus com encoding duplo ("TH /Î¸/ /Ã°/" -> "TH /θ/ /ð/")
-- e remove o prefixo 'seed: '. Rodar MANUALMENTE no Workbench (conexão utf8mb4).
--
-- Causa: o docker-entrypoint do MySQL lê os .sql de initdb com o cliente em latin1.
-- Os bytes UTF-8 de θ/ð/ɪ/æ/ː foram tratados como latin1 e gravados de novo em
-- utf8mb4. Colunas, tabelas e a conexão do backend (db.py) já estão em utf8mb4.
--
-- Idempotente: a guarda "focus = CONVERT(focus USING latin1)" só vale pra texto
-- que cabe em latin1 (o mojibake). Texto já correto (com θ, ð...) é pulado.
-- Faça backup antes:  mysqldump pronuncia phrases > phrases_backup.sql
USE pronuncia;
SET NAMES utf8mb4;

-- 1) desfaz o encoding duplo
UPDATE phrases
SET focus = CONVERT(CAST(CONVERT(focus USING latin1) AS BINARY) USING utf8mb4)
WHERE focus REGEXP '[^ -~]'
  AND focus COLLATE utf8mb4_bin = CONVERT(focus USING latin1);

-- 2) tira o prefixo 'seed: '
UPDATE phrases
SET focus = TRIM(SUBSTRING(focus, 6))
WHERE focus LIKE 'seed:%';

-- conferência: não deve sobrar 'Ã', 'Î', 'Ë', 'É' nem 'seed:'
SELECT DISTINCT focus FROM phrases ORDER BY focus;
