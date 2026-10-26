-- ============================================================
-- Pacote inicial de frases-alvo (leitura guiada)
-- Foco nos sons que falante de PORTUGUES-BR mais erra.
-- Rode DEPOIS do schema.sql:  no Workbench, abra e execute.
-- Idempotente: só insere frases cujo texto ainda não existe em phrases.
-- Nunca apaga nada (DELETE levaria junto as tentativas, pela FK ON DELETE CASCADE).
-- ============================================================
-- Sem isso, o docker-entrypoint lê este arquivo como latin1 e grava θ/ð/ɪ/æ/ː quebrados.
SET NAMES utf8mb4;
USE pronuncia;

-- as frases entram numa tabela temporária e só passam pra phrases se forem novas
CREATE TEMPORARY TABLE seed_tmp (
  text  VARCHAR(500) NOT NULL,
  level ENUM('A2','B1','B2','C1') NOT NULL,
  focus VARCHAR(80)  NULL
) DEFAULT CHARSET=utf8mb4;

-- ---------- A2 ----------
INSERT INTO seed_tmp (text, level, focus) VALUES
('I think this is the right thing to do.',            'A2', 'TH /θ/ /ð/'),
('The three brothers are at home today.',             'A2', 'TH /θ/ /ð/'),
('My ship is bigger than that little sheep.',         'A2', '/ɪ/ vs /iː/'),
('Please sit down and eat your big meal.',            'A2', '/ɪ/ vs /iː/'),
('The dog and the cat live in a small house.',        'A2', 'consoante final'),
('I like to read a good book at night.',              'A2', 'consoante final'),
('She walked to school and played all day.',          'A2', '-ed endings'),
('We wanted to help, so we cleaned the room.',        'A2', '-ed endings'),
('He has a happy heart and a kind hand.',             'A2', 'H sound'),
('Where is the white car with the small wheel?',      'A2', 'W vs V'),
('My red rabbit runs around the green grass.',        'A2', 'R sound'),
('The bad man had a black hat and a bag.',            'A2', 'vowel /æ/'),
('I work hard every week at my new job.',             'A2', 'consoante final'),
('Can you give me a cup of cold water?',              'A2', 'consoante final'),
('The young boy sang a long song at school.',         'A2', '-ng nasal'),
('Thank you for the things you bought me.',           'A2', 'TH /θ/'),
('This watch is very thin and very thick.',           'A2', 'TH + /ɪ/'),
('We live near the sea and we leave at six.',         'A2', 'live/leave'),
('Please speak slowly and stop at the street.',       'A2', 'cluster sp/st'),
('The blue bird flew over the bright sky.',           'A2', 'cluster bl/br');

-- ---------- B1 ----------
INSERT INTO seed_tmp (text, level, focus) VALUES
('I would rather think things through before deciding.',     'B1', 'TH /θ/ /ð/'),
('The athletes breathed deeply throughout the marathon.',    'B1', 'TH /θ/ /ð/'),
('She lives a peaceful life and leaves work at three.',      'B1', '/ɪ/ vs /iː/'),
('His ship reached the beach just before the storm hit.',    'B1', '/ɪ/ vs /iː/'),
('They developed the product and launched it last month.',   'B1', '-ed endings'),
('I appreciated how he explained the difficult problem.',    'B1', '-ed endings'),
('The whole household helped to host the holiday dinner.',   'B1', 'H sound'),
('We watched a vivid movie about a brave young woman.',      'B1', 'W vs V'),
('The strong wind spread the bright spring flowers around.', 'B1', 'cluster str/spr'),
('Could you describe the strange structure on the street?',  'B1', 'cluster str'),
('That advanced class attracts talented and ambitious adults.','B1', 'vowel /æ/'),
('He carefully recorded the results and shared the report.', 'B1', 'consoante final'),
('My brother prefers a warmer climate near the river.',      'B1', 'R sound'),
('The clever children answered the questions quickly.',      'B1', 'consonant clusters'),
('It is worth thinking about both sides of the truth.',      'B1', 'TH /θ/ /ð/'),
('She bought twelve fresh fish at the busy market.',         'B1', '/ɪ/ + final'),
('We arranged the schedule and managed the whole team.',     'B1', '-ed + g sound'),
('The famous singer thrilled the thousands in the crowd.',   'B1', 'TH + cluster'),
('Please pronounce these three words very precisely.',       'B1', 'TH + /iː/'),
('The weather was rough, yet the workers finished early.',   'B1', 'GH /f/ + R');

-- ---------- B2 ----------
INSERT INTO seed_tmp (text, level, focus) VALUES
('The thorough analysis revealed a thoughtful underlying theme.', 'B2', 'TH /θ/ /ð/'),
('Although the theory seems sound, the evidence is thin.',        'B2', 'TH /θ/ /ð/'),
('A brief glimpse of the bleak scene left a vivid impression.',   'B2', '/ɪ/ vs /iː/'),
('The committee unanimously approved the proposed amendment.',    'B2', '-ed endings'),
('Researchers questioned whether the hypothesis was justified.',  'B2', '-ed + H'),
('His sophisticated vocabulary impressed the whole department.',  'B2', 'consonant clusters'),
('We acknowledged the strengths and weaknesses of the strategy.', 'B2', 'cluster str + -ths'),
('The ambitious entrepreneur established a thriving enterprise.', 'B2', 'vowel /æ/ + TH'),
('Several volunteers vividly described the overwhelming event.',  'B2', 'W vs V'),
('The architect scrutinised every structural detail precisely.',  'B2', 'cluster str/scr'),
('Their interpretation differed throughout the lengthy debate.',  'B2', 'TH /ð/ + R'),
('The fragile ecosystem gradually recovered after the drought.',  'B2', '-ed + GH'),
('She emphasised the crucial difference between the theories.',   'B2', 'TH /θ/ /ð/'),
('A reliable witness recalled the rapid sequence of events.',     'B2', 'R + W'),
('The breakthrough threatened to reshape the entire industry.',   'B2', 'TH + cluster'),
('Authorities thoroughly examined the worthwhile proposal.',      'B2', 'TH + -worth'),
('The peaceful negotiations yielded a feasible agreement.',       'B2', '/iː/ + -ed'),
('His persuasive arguments influenced the sceptical audience.',   'B2', '-ed + consonant'),
('The intricate mechanism functioned smoothly despite the strain.','B2', 'cluster + smooth TH'),
('Both researchers withheld their conflicting conclusions.',      'B2', 'TH /ð/ + cluster');

-- ---------- C1 ----------
INSERT INTO seed_tmp (text, level, focus) VALUES
('The phenomenon, though counterintuitive, withstands rigorous scrutiny.', 'C1', 'TH /θ/ /ð/'),
('A nuanced synthesis of these threads underpins the thesis.',            'C1', 'TH + cluster'),
('Their unwavering commitment thwarted the looming catastrophe.',         'C1', 'TH /θ/ + W'),
('The unprecedented breakthrough precipitated widespread upheaval.',      'C1', 'cluster + -ed'),
('She articulated her grievances with remarkable thoughtfulness.',        'C1', '-ed + TH'),
('The labyrinthine bureaucracy thwarted every well-intentioned reform.',  'C1', 'cluster + TH'),
('His clandestine manoeuvres jeopardised the fragile alliance.',          'C1', '-ed + R'),
('The juxtaposition of wealth and squalor was strikingly vivid.',         'C1', 'cluster + W/V'),
('A thorough reassessment rendered the prevailing assumptions obsolete.', 'C1', 'TH + -ed'),
('The eloquent rhetoric belied an underlying ruthlessness.',              'C1', 'R + TH'),
('Sceptics scrutinised the seemingly seamless theoretical framework.',    'C1', 'cluster scr/str'),
('The conscientious physician thoroughly weighed the therapeutic risks.', 'C1', 'TH + W'),
('Their unyielding perseverance ultimately yielded tangible rewards.',    'C1', '-ed + R'),
('The intricate choreography demanded breathtaking precision.',           'C1', 'TH + cluster'),
('An authoritative voice acknowledged the inherent contradictions.',      'C1', 'TH /ð/ + -ed'),
('The ephemeral euphoria swiftly gave way to sober reflection.',          'C1', 'vowel + W/V'),
('He methodically dismantled the prevailing orthodoxy with wit.',         'C1', '-ed + TH'),
('The threshold between rigour and rigidity is often blurred.',           'C1', 'TH + R cluster'),
('Their wholehearted endorsement reverberated throughout the institution.','C1', 'TH + R'),
('A formidable array of variables thwarted any straightforward solution.', 'C1', 'V + TH + str');

INSERT INTO phrases (text, level, focus)
SELECT t.text, t.level, t.focus FROM seed_tmp t
WHERE NOT EXISTS (SELECT 1 FROM phrases p WHERE p.text = t.text);

DROP TEMPORARY TABLE seed_tmp;

SELECT level, COUNT(*) AS frases FROM phrases GROUP BY level;
