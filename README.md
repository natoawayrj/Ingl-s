# Pronúncia — Leitura Guiada (100% local)

App de prática de inglês para 3 usuários (você + 2 filhos). Dois modos:

**1) Leitura guiada** — o app mostra uma frase-alvo, você lê em voz alta,
o **Whisper local** transcreve, comparamos com o alvo e o **LLM local (LM Studio)**
dá feedback de pronúncia. Quando a nota fica baixa, o LLM também gera uma
**explicação fonética detalhada em português** (onde pôr a língua/boca, par mínimo).

**2) Conversar** — caixa de diálogo (chatbot) para conversa livre em inglês com o
mesmo LLM local. Você escreve **ou fala** (mic → Whisper vira mensagem); o bot
responde no seu nível CEFR, com correção gentil quando há erro claro. A conversa é
**efêmera** (só na memória do navegador — nada é salvo no banco).

Áudio é **descartado** (nunca salvo) nos dois modos. Histórico de pronúncia fica no MySQL.

```
Frontend (navegador)  ──>  Backend FastAPI  ──>  Whisper local (whisper.cpp)
   grava áudio              diff alvo/ouvido  ──>  LLM local (LM Studio / Qwen2.5 7B)
   conversa (chat)          chat multi-turno  ──>  MySQL (users / phrases / attempts)
```

Tudo roda na **sua máquina** (Ryzen 5600 / RX 6900 XT 16GB / 24GB). Você controla
ligar/desligar; o app mostra "no ar / offline" no topo.

---

## Pré-requisitos

1. **Python 3.11+**
2. **MySQL** (Workbench) rodando local
3. **ffmpeg** no PATH — converte o áudio do navegador p/ wav 16k
   (`winget install Gyan.FFmpeg` ou baixe e adicione ao PATH)
4. **LM Studio** com um modelo **não-thinking** carregado e o **Server ligado** (porta 1234)
   - Recomendado: **Qwen2.5 7B Instruct** (`qwen2.5-7b-instruct`). Baixe com:
     `lms get https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF -y`
   - **Não use modelos thinking** (ex.: gemma-4): eles "raciocinam" antes de
     responder → ~8x mais lento (explicação 59s vs 7,5s) e gastam o orçamento de
     tokens pensando, às vezes voltando vazio. O `.env` já aponta p/ o qwen.
   - Em Developer / Local Server: Start.
5. **whisper.cpp server** (STT). Build com Vulkan p/ usar a GPU AMD:
   ```
   # no repo do whisper.cpp
   cmake -B build -DGGML_VULKAN=1
   cmake --build build -j --config Release
   # baixe um modelo, ex: ggml-medium.en.bin, e suba o server:
   ./build/bin/whisper-server -m models/ggml-medium.en.bin --host 127.0.0.1 --port 8080
   ```
   (Sem GPU/Vulkan funciona em CPU, só mais lento. Frase curta = ok.)

---

## Setup (uma vez)

### 1. Banco
Abra o **Workbench** e rode `backend/schema.sql` (cria o database `pronuncia` e as tabelas).

> **Já tem o banco de antes?** Rode também `backend/migrate_add_explanation.sql`
> (adiciona a coluna `explanation` em `attempts`, usada pela explicação fonética).

### 2. Backend
```bash
cd pronuncia/backend
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt

copy .env.example .env            # edite .env: senha do MySQL + JWT_SECRET
python -c "import secrets; print(secrets.token_hex(32))"   # cole no JWT_SECRET
```

### 3. Criar os 3 usuários
Edite nomes/emails/senhas em `seed_users.py`, depois:
```bash
python seed_users.py
```

### 4. Subir o backend
```bash
uvicorn main:app --reload --port 8000
```
Abra **http://127.0.0.1:8000** → tela de login.

### 5. Frases para ler
**Caminho fácil (recomendado p/ começar):** rode `backend/seed_phrases.sql` no Workbench.
Já vem ~80 frases prontas (A2/B1/B2/C1) focadas nos sons que brasileiro erra
(TH, ship/sheep, consoante final, clusters, -ed, R/H, W/V). Testa o pipeline na hora,
sem depender do LLM.

**Caminho gerar com IA (opcional, depois):** logado como responsável, via Swagger em
**http://127.0.0.1:8000/docs** → `POST /api/phrases/generate`
(ex.: level=B1, focus="th sound", count=10). Repita por nível/foco.

**Editor pela interface (responsável):** logado como `parent`, aparece o link
**"frases (admin)"** no app. Dá pra adicionar, editar, filtrar por nível e
ativar/desativar frases sem abrir o Workbench. Desativar é o jeito seguro de
"remover": some das práticas mas preserva o histórico das tentativas.

---

## Uso diário
1. Ligue: MySQL, LM Studio (server), whisper.cpp server, depois `uvicorn`.
2. Cada um abre o site, faz login, escolhe nível, lê a frase, grava, recebe feedback.
3. Ou clica em **💬 conversar** para bater papo em inglês (escreve ou fala 🎤).
4. O topo mostra se está "no ar".

## Painel do responsável (role=parent)
Logado como `parent`, aparecem 2 links no app:
- **frases (admin)** — adiciona/edita/ativa/desativa frases por nível, sem Workbench.
- **relatório** — por filho, mostra a dificuldade por som (`focus` da frase): accuracy
  média com barra colorida (vermelho <60% < amarelo <80% < verde) e as palavras
  mais erradas. Ordena do som mais difícil pro mais fácil — você vê na hora onde
  direcionar o estudo de cada um.

## Acesso dos filhos de fora de casa (depois)
- **Cloudflare Tunnel** (grátis) ou **Tailscale** apontando p/ a porta 8000.
- Enquanto isso: funciona na rede local (eles acessam `http://SEU-IP:8000`).

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
- [ ] Túnel p/ acesso externo (Cloudflare/Tailscale)
- [ ] Ajuste fino dos prompts depois de testar com voz real

## Notas técnicas
- **faster-whisper não acelera na sua GPU AMD** (é CUDA). Por isso whisper.cpp + Vulkan.
- **Modelo thinking vs não-thinking**: modelos "reasoning" (gemma-4) gastam tokens
  pensando em `reasoning_content` e às vezes devolvem `content` vazio se o teto de
  tokens for baixo. O backend tem fallback (usa o raciocínio se o conteúdo vier
  vazio) e teto folgado, mas o certo é usar modelo não-thinking (qwen2.5-7b) — mais
  rápido e direto. Troca de modelo é só mudar `LLM_MODEL` no `.env`.
- **Conversar (chat)**: `POST /api/chat` recebe o histórico do cliente (lista de
  mensagens) e devolve a resposta do bot — multi-turno, sem estado no servidor. O
  histórico é cortado nos últimos 20 turnos p/ manter o prompt enxuto. `POST
  /api/transcribe` faz só áudio→texto (sem diff/feedback), usado pela voz no chat.
  Nada da conversa é salvo no banco (efêmero). Prompt do bot em `CHAT_SYSTEM`
  (`services/llm_client.py`) — ajuste lá o tom/correção.
- LM Studio expõe API OpenAI-compatible; o backend só aponta a URL — sem chave paga.
- Microfone exige contexto seguro: `localhost` funciona; IP externo precisa de HTTPS (o túnel resolve).
