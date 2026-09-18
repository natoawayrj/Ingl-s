# Pronúncia — meu app de inglês (100% local)

Fiz este app pra eu e meus 2 filhos praticarmos inglês em casa, rodando tudo na
**minha máquina** (Ryzen 5600 / RX 6900 XT 16GB / 24GB RAM). São 3 usuários e dois modos:

**1) Leitura guiada** — o app mostra uma frase-alvo, eu leio em voz alta,
o **Whisper local** transcreve, comparo com o alvo e o **LLM local (LM Studio)** me dá
feedback de pronúncia. Quando a nota fica baixa, o LLM ainda gera uma
**explicação fonética detalhada em português** (onde pôr a língua/boca, par mínimo).

**2) Conversar** — uma caixa de diálogo (chatbot) pra conversa livre em inglês com o
mesmo LLM local. Escrevo **ou falo** (mic → Whisper vira mensagem); o bot responde no
meu nível CEFR e corrige de leve quando erro. A conversa é **efêmera** (só fica na
memória do navegador — não salvo nada no banco). A ideia foi da minha filha.

Áudio é **descartado** (nunca salvo) nos dois modos. Só o histórico de pronúncia vai pro MySQL.

```
Frontend (navegador)  ──>  Backend FastAPI  ──>  Whisper local (whisper.cpp)
   grava áudio              diff alvo/ouvido  ──>  LLM local (LM Studio / Qwen2.5 7B)
   conversa (chat)          chat multi-turno  ──>  MySQL (users / phrases / attempts)
```

Eu controlo ligar/desligar; o app mostra "no ar / offline" no topo.

`Python` · `FastAPI` · `MySQL` · `Docker Compose` · `whisper.cpp` · `LLM local (LM Studio)` · `JWT` · `PWA`

> **Clonou o repo?** Ele vem apontado pros motores de IA que rodam **na minha máquina**
> (Whisper e LLM locais), que não existem na sua. Antes de subir, edite o `.env` seguindo
> [Trocar os motores de IA](#trocar-os-motores-de-ia-leia-antes-de-clonar) — dá pra rodar
> tudo local de graça ou apontar pra uma API paga, sem tocar em código.

> Se você veio ver a parte de dados: [modelagem e decisões de dados](#modelagem-e-decisões-de-dados)
> (pipeline de ingestão, por que o histórico é imutável, índices, retenção e o que eu faria
> diferente em escala).

---

## Estrutura

```
pronuncia/
  frontend/
    index.html              # SPA inteira (HTML/CSS/JS, sem build)
    manifest.json           # PWA: dá pra instalar no celular
    sw.js                   # service worker
    icon.svg
  backend/
    app/                    # código Python (pacote)
      main.py               # rotas FastAPI
      config.py             # lê o .env
      db.py                 # MySQL (PyMySQL)
      auth.py               # JWT + hash de senha
      seed_users.py         # cria os 3 usuários
      services/             # whisper_client, llm_client, diff
    sql/                    # schema.sql, seed_phrases.sql, migrations/
    env/                    # .env (real, fora do git) e .env.example
    Dockerfile              # python:3.11-slim + ffmpeg
    requirements.txt
  docker-compose.yml        # db (mysql:8) + backend
  start-ngrok.ps1           # sobe o túnel no logon do Windows
```

> Organizei em `app/` (código), `sql/` (dados) e `env/` (configuração) pra não ficar
> tudo solto na raiz do backend.

---

## Pré-requisitos

1. **Python 3.11+**
2. **MySQL** (Workbench) rodando local
3. **ffmpeg** no PATH — converte o áudio do navegador p/ wav 16k
   (`winget install Gyan.FFmpeg` ou baixo e adiciono ao PATH)
4. **LM Studio** com um modelo **não-thinking** carregado e o **Server ligado** (porta 1234)
   - Uso o **Qwen2.5 7B Instruct** (`qwen2.5-7b-instruct`). Baixo com:
     `lms get https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF -y`
   - **Não uso modelos thinking** (ex.: gemma-4): eles "raciocinam" antes de responder
     → ~8x mais lento (explicação 59s vs 7,5s) e gastam o orçamento de tokens pensando,
     às vezes voltando vazio. O `.env` já aponta pro qwen.
   - Em Developer / Local Server: Start.
5. **whisper.cpp server** (STT). Buildo com Vulkan p/ usar a GPU AMD:
   ```
   # no repo do whisper.cpp
   cmake -B build -DGGML_VULKAN=1
   cmake --build build -j --config Release
   # baixo um modelo, ex: ggml-medium.en.bin, e subo o server:
   ./build/bin/whisper-server -m models/ggml-medium.en.bin --host 127.0.0.1 --port 8080
   ```
   (Sem GPU/Vulkan roda em CPU, só mais lento. Frase curta = ok.)

---

## Trocar os motores de IA (leia antes de clonar)

O app depende de **dois motores de IA**, e o repositório vem configurado pros que rodam
na minha máquina. Se você clonou, esses endereços não existem aí — **é aqui que você
precisa mexer**. Os dois são trocáveis **só pelo `.env`, sem tocar em código**.

| Motor | Pra que serve | Variáveis |
|---|---|---|
| **STT** (fala → texto) | transcrever o áudio lido e a voz no chat | `WHISPER_PROVIDER`, `WHISPER_URL` **ou** `OPENAI_API_KEY` |
| **LLM** (texto → texto) | feedback, explicação fonética, chat, gerar frases | `LLM_URL`, `LLM_MODEL`, `LLM_API_KEY` |

### Opção A — tudo local, de graça (é como eu uso)

Nada sai da sua máquina, custo zero, mas você precisa subir os dois servidores
(ver [Pré-requisitos](#pré-requisitos)) e ter GPU ou paciência.

```ini
WHISPER_PROVIDER=whispercpp
WHISPER_URL=http://127.0.0.1:8080/inference

LLM_URL=http://127.0.0.1:1234/v1/chat/completions   # LM Studio
LLM_MODEL=qwen2.5-7b-instruct
LLM_API_KEY=                                        # vazio: local não pede chave
```

Serve qualquer servidor **OpenAI-compatible**, não só o LM Studio. Com Ollama, por
exemplo, muda só a URL e o nome do modelo:

```ini
LLM_URL=http://127.0.0.1:11434/v1/chat/completions
LLM_MODEL=qwen2.5:7b-instruct
```

### Opção B — API paga (sem servidor local, mas custa e o dado sai)

Se você não quer subir nada, aponte pros endpoints de um provedor e preencha as chaves.
O `LLM_API_KEY` vai como `Authorization: Bearer` — se estiver vazio, nenhum header é
enviado, que é o que faz o modo local funcionar.

```ini
# STT pela OpenAI (o áudio SAI da sua máquina)
WHISPER_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_WHISPER_MODEL=whisper-1

# LLM por qualquer provedor OpenAI-compatible
LLM_URL=https://api.openai.com/v1/chat/completions
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-...
```

Groq e OpenRouter funcionam igual, trocando só a `LLM_URL`:

```ini
LLM_URL=https://api.groq.com/openai/v1/chat/completions
LLM_URL=https://openrouter.ai/api/v1/chat/completions
```

Dá pra misturar: **STT local + LLM na nuvem** (ou o contrário). São independentes.

> ⚠️ **Se você usa Docker e API paga, o `.env` não basta.** O `docker-compose.yml` força
> `WHISPER_URL` e `LLM_URL` pra `host.docker.internal` (é como o container acha os
> servidores locais), e `environment:` ganha do `env_file:`. Então comente essas duas
> linhas no compose, senão sua URL da OpenAI é ignorada em silêncio e você leva
> `Connection refused` sem entender por quê.

### Dois avisos

- **Não é qualquer API, é qualquer API OpenAI-compatible.** Provedores com formato
  próprio de requisição precisariam de um adaptador em
  `backend/app/services/llm_client.py` — hoje o cliente fala só esse dialeto.
- **Prefira modelo não-thinking.** Modelo "reasoning" gasta o orçamento de tokens
  pensando antes de responder: ~8x mais lento aqui (59s contra 7,5s numa explicação) e
  às vezes devolve conteúdo vazio. O cliente tem fallback, mas o certo é não usar.

### Se algo não subir

O topo do app mostra **"no ar / offline"**, e aí o problema é quase sempre um destes:
`Connection refused` na porta 8080 (whisper.cpp desligado), na 1234 (LM Studio sem o
Server ligado), ou **`401`** (apontou pra API paga e esqueceu a chave).

---

## Setup (uma vez)

> Este é o caminho **nativo** (venv + MySQL do Workbench), que foi como comecei.
> Hoje eu subo por Docker — ver [Rodar com Docker](#rodar-com-docker-backend--mysql-em-container).
> De qualquer jeito, whisper.cpp e LM Studio continuam ligados no host nos dois caminhos.

### 1. Banco
Abro o **Workbench** e rodo `backend/sql/schema.sql` (cria o database `pronuncia` e as tabelas).

> **Já tinha o banco de antes?** Rodo também `backend/sql/migrations/migrate_add_explanation.sql`
> (adiciona a coluna `explanation` em `attempts`, usada pela explicação fonética).

### 2. Backend
```bash
cd pronuncia/backend
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt

copy env\.env.example env\.env    # edito o .env: senha do MySQL + JWT_SECRET
python -c "import secrets; print(secrets.token_hex(32))"   # colo no JWT_SECRET
```

### 3. Criar os 3 usuários
Edito nomes/emails/senhas em `app/seed_users.py`, depois (de dentro de `backend/`):
```bash
python -m app.seed_users
```

### 4. Subir o backend
De dentro de `backend/`:
```bash
uvicorn app.main:app --reload --port 8000
```
Abro **http://127.0.0.1:8000** → tela de login.

### 5. Frases para ler
**Caminho fácil (uso pra começar):** rodo `backend/sql/seed_phrases.sql` no Workbench.
Já vêm ~80 frases prontas (A2/B1/B2/C1) focadas nos sons que brasileiro erra
(TH, ship/sheep, consoante final, clusters, -ed, R/H, W/V). Testa o pipeline na hora,
sem depender do LLM.

**Caminho gerar com IA (opcional, depois):** logado como responsável, via Swagger em
**http://127.0.0.1:8000/docs** → `POST /api/phrases/generate`
(ex.: level=B1, focus="th sound", count=10). Repito por nível/foco.

**Editor pela interface (responsável):** logado como `parent`, aparece o link
**"frases (admin)"** no app. Dá pra adicionar, editar, filtrar por nível e
ativar/desativar frases sem abrir o Workbench. Desativar é o jeito seguro de
"remover": some das práticas mas preserva o histórico das tentativas.

---

## Uso diário
1. Ligo: MySQL, LM Studio (server), whisper.cpp server, depois `uvicorn app.main:app`.
2. Cada um abre o site, faz login, escolhe nível, lê a frase, grava, recebe feedback.
3. Ou clica em **💬 conversar** pra bater papo em inglês (escreve ou fala 🎤).
4. O topo mostra se está "no ar".

## Painel do responsável (role=parent)
Logado como `parent`, aparecem 2 links no app:
- **frases (admin)** — adiciono/edito/ativo/desativo frases por nível, sem Workbench.
- **relatório** — por filho, mostra a dificuldade por som (`focus` da frase): accuracy
  média com barra colorida (vermelho <60% < amarelo <80% < verde) e as palavras
  mais erradas. Ordena do som mais difícil pro mais fácil — vejo na hora onde
  direcionar o estudo de cada um.

## Acesso dos filhos de fora de casa
Exponho a porta 8000 com **ngrok** (o backend e a IA continuam na minha máquina). Usei
o domínio fixo grátis da conta, então a URL **não muda** (a minha eu não publico aqui —
fica em variável de ambiente, ver abaixo).

- O frontend manda o header `ngrok-skip-browser-warning` em todas as chamadas pra não
  cair na tela de aviso do ngrok free (senão a API devolve HTML e o login quebra).
- Na 1ª visita o navegador mostra a tela "Visit Site" do ngrok — clico uma vez e entra.
- Alternativas que considerei: **Cloudflare Tunnel** (URL aleatória no plano grátis) ou
  **Tailscale** (privado, cada aparelho instala o app).
- Na rede local sempre dá: eles acessam `http://MEU-IP:8000`.
- Microfone exige contexto seguro: `localhost` e HTTPS (o túnel) funcionam; IP puro não.

### Reerguer tudo (ex.: depois de reiniciar o PC)
Ligo MySQL, LM Studio (server, porta 1234) e whisper.cpp (porta 8080). Depois, em dois
terminais:
```bash
# 1) backend — de pronuncia/backend
.venv\Scripts\activate
uvicorn app.main:app --port 8000

# 2) túnel ngrok (URL fixa — vem da variável de ambiente)
ngrok http --url=$env:PRONUNCIA_NGROK_URL 8000
```
O authtoken do ngrok já está salvo na máquina (`ngrok config add-authtoken …` só uma vez).

> **ngrok agora sobe sozinho no logon.** Uma tarefa de Inicialização do Windows
> (`Startup\PronunciaNgrok.vbs` → `start-ngrok.ps1`) abre o túnel escondido ~30s após
> o login, sem duplicar se já houver um. Não preciso mais rodar o passo 2 à mão — só
> garanto Docker/whisper/LM Studio ligados. Pra desativar: apago o `.vbs` da pasta
> Inicializar (`shell:startup`). O erro `ERR_NGROK_3200` ("endpoint offline") quer dizer
> só que o túnel não está no ar — o ngrok é um 4º processo, separado do backend/IA.

> **Configuração do script (uma vez).** O `start-ngrok.ps1` não tem a URL nem o caminho
> do ngrok escritos no código — lê das variáveis de ambiente do usuário, pra o domínio
> não ir parar no repositório:
> ```powershell
> [Environment]::SetEnvironmentVariable("PRONUNCIA_NGROK_URL", "https://SEU-DOMINIO.ngrok-free.dev", "User")
> [Environment]::SetEnvironmentVariable("PRONUNCIA_NGROK_BIN", "C:\caminho\para\ngrok.exe", "User")
> ```
> Se o `ngrok` já estiver no PATH, a segunda não é necessária.

---

## Status do projeto
- [x] Schema MySQL
- [x] Backend FastAPI: login JWT, frases, prática (Whisper→diff→LLM), histórico
- [x] Explicação fonética detalhada (pt-BR) quando a nota fica baixa (< 0.8)
- [x] Geração de frases por nível com LLM local
- [x] Conversar (chatbot em inglês): chat multi-turno no nível CEFR, correção gentil,
      entrada por texto ou voz (mic→Whisper), efêmero (nada salvo)
- [x] Editor de frases na interface (parent): add/editar/ativar/desativar, sem Workbench
- [x] Relatório de fonema (parent): por filho, dificuldade por som (focus), pior primeiro
- [x] Pacote inicial de ~80 frases prontas (seed_phrases.sql)
- [x] Frontend: login, leitura guiada, gravação, diff colorido, feedback, histórico
- [x] Áudio descartado (nunca persistido)
- [x] Backend organizado em app/ + sql/ + env/
- [x] Túnel p/ acesso externo (ngrok com domínio fixo, sobe sozinho no logon)
- [x] Docker: backend + MySQL em container (`docker compose up`)
- [x] PWA instalável (manifest + service worker) — dá pra "instalar" no celular
- [x] Praticar sons fracos: sorteia frases do som que a pessoa mais erra
- [ ] Ajuste fino dos prompts depois de testar com voz real

## Rodar com Docker (backend + MySQL em container)

Hoje subo tudo com um comando só. **Vai pro container:** backend FastAPI + MySQL.
**Fica nativo no host:** whisper.cpp (GPU AMD via Vulkan — passthrough no Windows não
vale a pena) e LM Studio (app desktop). O backend do container fala com esses dois pelo
`host.docker.internal`.

```bash
# de dentro de pronuncia/ (com Docker Desktop, whisper e LM Studio ligados)
docker compose up -d

# só na 1ª subida: cria os 3 usuários
docker compose exec backend python -m app.seed_users
```
Abro **http://127.0.0.1:8000**.

Detalhes que valem lembrar:
- `config.py` usa `load_dotenv(override=False)`, então o env do compose **ganha** sobre o
  `.env`. Sobrescrevo só `DB_HOST` / `WHISPER_URL` / `LLM_URL` — o resto vem do `.env`.
  Não precisei mexer em nada do Python.
- **ffmpeg** está no Dockerfile, então sumiu a dependência de PATH do host.
- O MySQL do container expõe a **porta 3307** no host (3306 continua com o MySQL nativo do
  Workbench, sem conflito).
- `backend/sql/` é montado em `/docker-entrypoint-initdb.d`, então `schema.sql` e
  `seed_phrases.sql` rodam sozinhos na 1ª subida (ordem alfabética).
- Build context é a raiz `pronuncia/` (não só `backend/`), porque o backend serve o
  `frontend/`. Além disso `frontend/` entra como volume read-only: edito o `index.html` e
  basta dar refresh, sem rebuild.

Pendente: migrar o histórico do MySQL antigo (Workbench) pro volume novo via
`mysqldump` → restore, se eu quiser manter as tentativas de antes.

---

## Modelagem e decisões de dados

Essa parte foi o que mais me deu trabalho de pensar, então deixo registrado o porquê
de cada escolha — não só o que ficou.

### O pipeline de uma tentativa

```
áudio (webm, navegador)
   → ffmpeg            converte p/ wav 16kHz mono
   → whisper.cpp       transcreve (STT) — o que foi REALMENTE falado
   → diff.py           alinha alvo × transcrição (SequenceMatcher)
   → LLM local         feedback curto; se accuracy < 0.8, 2ª chamada p/ explicação fonética
   → MySQL             persiste texto + diff + métricas. Áudio é descartado aqui.
```

A frase-alvo funciona como **ground truth**: se o Whisper ouviu outra coisa, ou houve erro
de pronúncia ou a palavra sumiu. O `diff.py` classifica cada palavra do alvo em
`ok` / `wrong` / `missing` (e lista as `extra` que o Whisper ouviu a mais), e a
`accuracy` é a fração de palavras-alvo corretas. Esse dicionário inteiro vai pro
`attempts.diff_json`.

### As três tabelas

| Tabela | Papel | Cresce? |
|---|---|---|
| `users` | quem pratica (3 pessoas, `parent` / `child`) | não |
| `phrases` | catálogo de frases-alvo, com `level` e `focus` (o som treinado) | devagar |
| `attempts` | uma linha por tentativa: transcrição, diff, feedback, wpm | sempre |

Na prática `users` e `phrases` são dimensões e `attempts` é o fato — só não usei esses
nomes no schema porque o app é pequeno.

### Decisões que tomei de propósito

**Guardo o texto da frase dentro da tentativa.** `attempts.target_text` é uma cópia do
`phrases.text` no momento em que a pessoa praticou. É redundante de propósito: se eu
editar a frase depois pelo painel admin, o histórico antigo continua contando a verdade
do que foi lido naquele dia. Sem isso, editar uma frase reescreveria o passado.

**Não existe DELETE de frase, só `active = 0`.** A FK `attempts → phrases` é
`ON DELETE CASCADE`, então apagar uma frase levaria junto todas as tentativas dela.
Desativar tira a frase do sorteio e preserva a linhagem. O botão do admin faz isso.

**`diff_json` é JSON dentro do MySQL.** O resultado do diff tem formato variável (lista de
palavras com status, palavras extras, accuracy). Normalizar isso em `attempt_words` daria
uma tabela enorme pra um app de 3 pessoas. Guardo semi-estruturado e agrego na leitura.

**Áudio nunca é persistido, em nenhum dos modos.** O arquivo vive em temporário durante a
requisição e morre. Voz de criança é dado biométrico; não quis ter isso em disco. A
conversa do chat também é efêmera — vive só na memória do navegador, nada vai pro banco.
Por isso a tabela `attempts` guarda **texto**, nunca mídia.

**Índices pensados pelas duas leituras que existem.** `idx_user_time (user_id, created_at)`
serve o histórico e as estatísticas de uma pessoa; `idx_level (level, active)` serve o
sorteio da próxima frase, que sempre filtra por nível e ativo.

### O que me dá a leitura analítica

Duas agregações em cima de `attempts`:

- **`/api/stats`** (cada um vê o seu) — total de tentativas, accuracy média, wpm médio,
  streak de dias seguidos e as palavras mais erradas.
- **`/api/report/phonemes`** (só `parent`) — junta `attempts` com `phrases` e agrupa pelo
  `focus` da frase, ou seja, **pelo som treinado**. Pra cada som: quantas tentativas,
  accuracy média e as palavras que mais falham. Ordeno da pior accuracy pra melhor, então
  a primeira linha do relatório é literalmente o que o filho precisa treinar hoje. Isso
  realimenta o app: o modo **praticar sons fracos** sorteia frases desse `focus`.

### Limitações que eu conheço

Prefiro deixar explícito a fingir que não existem:

- **As duas agregações rodam em Python, não em SQL.** Puxo as linhas do usuário e somo em
  dicionário, porque a accuracy mora dentro do `diff_json` e eu queria o cálculo legível.
  Com 3 usuários isso é instantâneo. Crescendo, o certo seria `GROUP BY` com
  `JSON_EXTRACT` (ou uma coluna `accuracy` materializada na escrita) e janela de tempo —
  hoje a query não tem `LIMIT`.
- **Sem camada analítica separada.** Não há view nem tabela agregada; as métricas são
  calculadas a cada request. Num volume maior, valeria materializar por dia.
- **Migrations são manuais.** `sql/migrations/` tem arquivos avulsos que eu rodo à mão,
  sem versionamento nem rollback. Com mais gente mexendo, entraria Alembic.
- **`diff_json` não tem contrato validado** no banco — quem garante o formato é o
  `diff.py`, do lado da aplicação.

---

## Notas técnicas
- **faster-whisper não acelera na minha GPU AMD** (é CUDA). Por isso whisper.cpp + Vulkan.
- **Modelo thinking vs não-thinking**: modelos "reasoning" (gemma-4) gastam tokens
  pensando em `reasoning_content` e às vezes devolvem `content` vazio se o teto de
  tokens for baixo. O backend tem fallback (usa o raciocínio se o conteúdo vier vazio)
  e teto folgado, mas o certo é usar modelo não-thinking (qwen2.5-7b) — mais rápido e
  direto. Troca de modelo é só mudar `LLM_MODEL` no `.env`.
- **Conversar (chat)**: `POST /api/chat` recebe o histórico do cliente (lista de
  mensagens) e devolve a resposta do bot — multi-turno, sem estado no servidor. Corto
  o histórico nos últimos 20 turnos pra manter o prompt enxuto. `POST /api/transcribe`
  faz só áudio→texto (sem diff/feedback), usado pela voz no chat. Nada da conversa é
  salvo no banco (efêmero). O prompt do bot fica em `CHAT_SYSTEM`
  (`app/services/llm_client.py`) — ajusto lá o tom/correção.
- LM Studio expõe API OpenAI-compatible; o backend só aponta a URL — sem chave paga.
- O `.env` real (senha do MySQL, JWT) fica em `backend/env/.env` e **não vai pro git**
  (`.gitignore`). No repo só sobe o `env/.env.example` como modelo.
