"""Cliente do LLM local (LM Studio, API OpenAI-compatible).

Usado para:
  1) gerar feedback de pronúncia (modo leitura guiada)
  2) gerar frases-alvo por nível (em lote)
"""
import json

import httpx

from .. import config


async def _chat_messages(messages: list[dict], temperature: float | None = None,
                         max_tokens: int = 2500) -> str:
    """Chama o LLM local com uma lista de mensagens (suporta multi-turno)."""
    payload = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "temperature": config.LLM_TEMPERATURE if temperature is None else temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(config.LLM_URL, json=payload)
        resp.raise_for_status()
        body = resp.json()

    msg = body["choices"][0]["message"]
    content = (msg.get("content") or "").strip()
    # Modelos reasoning (ex.: Gemma 4) gastam o orçamento de tokens pensando em
    # 'reasoning_content'. Se o conteúdo final vier vazio, usamos o raciocínio
    # como último recurso (melhor que devolver string vazia).
    if not content:
        content = (msg.get("reasoning_content") or "").strip()
    return content


async def _chat(system: str, user: str, temperature: float | None = None,
                max_tokens: int = 2500) -> str:
    return await _chat_messages(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )


# ---------- 1) feedback de pronúncia ----------
FEEDBACK_SYSTEM = """You are a precise English pronunciation coach for a Brazilian learner.
You are given a TARGET sentence the learner was asked to read aloud, and the TRANSCRIPTION
produced by a speech-to-text engine from their actual audio.

Important reasoning:
- The transcription reflects what the engine *heard*. Where it differs from the target,
  the learner most likely mispronounced that word (or a nearby sound).
- Words marked "wrong" or "missing" in the diff are your main clues.
- Focus on SOUNDS, not grammar. The target grammar is already correct.

Give SHORT, encouraging, specific feedback. Do NOT give a score or number.
Format exactly:

🔎 What I heard: <one line — note the words that came out differently, or say it matched well>
🗣️ Sounds to fix: <1-3 bullet points, each: the word + the specific sound/IPA + a tiny tip>
✅ Try again: <one short motivating line>

Keep it under 90 words. If everything matched, celebrate briefly and suggest reading with
more natural rhythm."""


async def pronunciation_feedback(target: str, transcription: str, diff: dict,
                                 wpm: int | None) -> str:
    wrong = [w["word"] for w in diff.get("words", []) if w["status"] == "wrong"]
    missing = [w["word"] for w in diff.get("words", []) if w["status"] == "missing"]
    extra = diff.get("extra", [])

    user = f"""TARGET: "{target}"
TRANSCRIPTION: "{transcription}"

Diff analysis:
- words heard wrong (likely mispronounced): {wrong or "none"}
- words missing (not detected): {missing or "none"}
- extra words heard: {extra or "none"}
- match: {diff.get('summary')}
- speaking pace: {str(wpm) + ' wpm' if wpm else 'unknown'}

Write the feedback now."""
    return await _chat(FEEDBACK_SYSTEM, user, temperature=0.3, max_tokens=2500)


# ---------- 1b) explicação fonética detalhada (só quando nota baixa) ----------
EXPLAIN_SYSTEM = """Você é um professor nativo de inglês, paciente e encorajador,
ensinando uma CRIANÇA brasileira a pronunciar melhor.

Você recebe a frase-ALVO que ela tentou ler e a TRANSCRIÇÃO do que o reconhecedor
de fala realmente ouviu. Onde diferem, provavelmente houve erro de pronúncia.

Sua tarefa: explicar, EM PORTUGUÊS simples, como corrigir os sons errados.
Para CADA palavra problemática (no máximo 3, as mais importantes), escreva um bloco:

👅 <palavra> — som /IPA/
   Como fazer: <onde por a língua/lábios/dentes, em 1 frase clara e concreta>
   Pratique: <um par mínimo ou exemplo curto, ex.: "think (não 'tink'), three">

Regras:
- Português do Brasil, tom carinhoso e simples (criança lê isso).
- Foque em SONS, nunca gramática.
- Seja concreto na mecânica da boca (ex.: "ponha a ponta da língua entre os dentes").
- Máximo ~140 palavras no total. Sem introdução nem despedida — vá direto aos blocos."""


async def phonetic_explanation(target: str, transcription: str, diff: dict,
                               focus: str | None) -> str:
    wrong = [w["word"] for w in diff.get("words", []) if w["status"] == "wrong"]
    missing = [w["word"] for w in diff.get("words", []) if w["status"] == "missing"]
    extra = diff.get("extra", [])

    user = f"""ALVO: "{target}"
TRANSCRIÇÃO (o que foi ouvido): "{transcription}"

Pistas do diff:
- prováveis erros de pronúncia: {wrong or "nenhum"}
- palavras não detectadas: {missing or "nenhuma"}
- sons extras ouvidos: {extra or "nenhum"}
- foco desta frase: {focus or "clareza geral"}

Escreva a explicação agora."""
    return await _chat(EXPLAIN_SYSTEM, user, temperature=0.3, max_tokens=3000)


# ---------- 2) geração de frases em lote ----------
PHRASE_SYSTEM = """You generate short English sentences for READING-ALOUD pronunciation practice.
Rules:
- Each sentence: 6 to 14 words, natural, self-contained, no quotes, no numbering.
- Match the requested CEFR level.
- Each sentence should stress the requested pronunciation focus when possible.
- Return ONLY a JSON array of strings. No prose, no markdown."""


async def generate_phrases(level: str, focus: str, count: int = 10) -> list[str]:
    user = (
        f"Level: {level}\nPronunciation focus: {focus}\n"
        f"Generate {count} sentences. Return a JSON array of strings only."
    )
    raw = await _chat(PHRASE_SYSTEM, user, temperature=0.8, max_tokens=2500)

    # tenta extrair o array JSON mesmo se o modelo enrolar com markdown
    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end != -1:
        raw = raw[start : end + 1]
    try:
        arr = json.loads(raw)
        return [str(s).strip() for s in arr if str(s).strip()]
    except Exception:
        # fallback: uma frase por linha
        return [ln.strip("-• ").strip() for ln in raw.splitlines() if ln.strip()]


# ---------- 3) conversa livre (chatbot em inglês) ----------
CHAT_SYSTEM = """You are a friendly English conversation partner for a Brazilian {level}-level learner (often a child).
Have a natural, fun, back-and-forth conversation in ENGLISH.

Rules:
- Speak ENGLISH only. Match {level} level: simple words and short sentences for low levels.
- Keep YOUR replies short (1-3 sentences) and always end with a question to keep the chat going.
- Be warm, patient and encouraging. Pick topics a kid enjoys (games, animals, school, food, hobbies).
- GENTLE correction: if the learner makes a clear grammar/vocabulary mistake, briefly fix it in a
  kind way BEFORE continuing, like: "(small tip: we say 'I went', not 'I goed') ". One tip max per reply.
  If there is no real mistake, do not invent one.
- Never switch to Portuguese. Never lecture. No long explanations."""


# o histórico que o front envia não passa de N turnos (mantém o prompt enxuto)
CHAT_MAX_TURNS = 20


async def chat_reply(history: list[dict], level: str) -> str:
    """Responde uma mensagem de conversa, dado o histórico [{role, content}].

    'role' é "user" (o aprendiz) ou "assistant" (o bot). 'level' é o CEFR do
    usuário, usado para calibrar a dificuldade do inglês.
    """
    clean = []
    for m in history[-CHAT_MAX_TURNS:]:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            clean.append({"role": role, "content": content[:2000]})

    messages = [{"role": "system", "content": CHAT_SYSTEM.format(level=level)}]
    messages.extend(clean)
    # temperatura mais alta = conversa mais viva; teto baixo = resposta curta
    return await _chat_messages(messages, temperature=0.7, max_tokens=400)
