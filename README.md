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

---

## Estrutura

```
pronuncia/
  frontend/
    index.html              # SPA inteira (HTML/CSS/JS, sem build)
  backend/
    app/                    # código Python (pacote)
      main.py               # rotas FastAPI
      config.py             # lê o .env
      db.py                 # MySQL (PyMySQL)
      auth.py               # JWT + hash de senha
      seed_users.py         # cria os 3 usuários
      services/             # whisper_client, llm_client, diff
    sql/                    # schema.sql, seed_phrases.sql, migrate_*.sql
    env/                    # .env (real, fora do git) e .env.example
    requirements.txt
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

## Setup (uma vez)

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
o domínio fixo grátis da conta, então a URL **não muda**:

**https://oversold-starboard-elastic.ngrok-free.dev**

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

# 2) túnel ngrok (URL fixa)
ngrok http --url=https://oversold-starboard-elastic.ngrok-free.dev 8000
```
O authtoken do ngrok já está salvo na máquina (`ngrok config add-authtoken …` só uma vez).

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
- [x] Túnel p/ acesso externo (ngrok com domínio fixo)
- [ ] Ajuste fino dos prompts depois de testar com voz real

## 🚧 EM ANDAMENTO: migração p/ Docker (backend + MySQL em container)

> **Onde paramos (2026-06-17):** Docker Desktop instalado, vou reiniciar o PC.
> Próximo passo ao voltar: criar os arquivos abaixo e subir `docker compose up`.

**Decisão de arquitetura:**
- **Vão pro container:** backend FastAPI + MySQL.
- **Ficam no host (nativos):** whisper.cpp (GPU AMD/Vulkan — passthrough no Windows não vale) e LM Studio (app desktop). Continuam nas portas 8080 e 1234.
- Backend no container fala com esses 2 serviços do host via `host.docker.internal`.

**Detalhes técnicos já mapeados:**
1. `config.py` usa `load_dotenv(override=False)` → **env do compose ganha sobre o `.env`**. Sobrescrevo só `DB_HOST`/`WHISPER_URL`/`LLM_URL` no compose; resto vem do `.env`. **Sem mudar código Python.**
2. **ffmpeg** entra no Dockerfile (`apt install ffmpeg`) — some a dependência de PATH do host.
3. Backend acha MySQL pelo nome do serviço compose (`db`), não `127.0.0.1`.
4. Frontend é servido pelo backend (`app/main.py:567` monta `../../frontend`). Então **build context = raiz `pronuncia/`** (não só `backend/`), pra copiar `frontend/` junto. OU monto `frontend/` como volume.
5. SQL auto-seed: montar `backend/sql/` em `/docker-entrypoint-initdb.d` roda `schema.sql` + `seed_phrases.sql` na 1ª subida (ordem alfabética — conferir nomes).
6. `seed_users.py` roda à parte depois: `docker compose exec backend python -m app.seed_users`.

**Arquivos a criar (ao voltar do reboot):**
```
pronuncia/
  docker-compose.yml          # services: db (mysql:8) + backend
  backend/
    Dockerfile                # python:3.11-slim + ffmpeg + requirements + uvicorn
    .dockerignore             # exclui .venv, env/.env, __pycache__
```

**Esboço do compose:**
```yaml
services:
  db:
    image: mysql:8
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_PASSWORD}
      MYSQL_DATABASE: pronuncia
    volumes:
      - dbdata:/var/lib/mysql
      - ./backend/sql:/docker-entrypoint-initdb.d:ro
    ports: ["3306:3306"]
  backend:
    build:
      context: .                 # raiz pronuncia/ (precisa do frontend/)
      dockerfile: backend/Dockerfile
    environment:
      DB_HOST: db
      WHISPER_URL: http://host.docker.internal:8080/inference
      LLM_URL: http://host.docker.internal:1234/v1/chat/completions
    env_file: ./backend/env/.env
    extra_hosts: ["host.docker.internal:host-gateway"]
    ports: ["8000:8000"]
    depends_on: [db]
volumes:
  dbdata: {}
```

**Pendências/cuidados:**
- [ ] Criar Dockerfile, docker-compose.yml, .dockerignore
- [ ] Migrar dados do MySQL atual (Workbench) → volume novo (mysqldump → restore), se quiser manter histórico
- [ ] Conferir ordem de execução dos `.sql` no initdb (schema antes do seed)
- [ ] `seed_users.py` via `docker compose exec` após 1ª subida
- [ ] Whisper + LM Studio: lembrar de ligar no host antes do `compose up`

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
