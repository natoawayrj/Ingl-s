"""Cliente do LLM — qualquer endpoint OpenAI-compatible.

Por padrão aponta pro LM Studio local (sem chave). Pra usar uma API paga
(OpenAI, Groq, OpenRouter...), basta trocar LLM_URL/LLM_MODEL no .env e
preencher LLM_API_KEY — o header Authorization só vai quando a chave existe.

Usado para:
  1) gerar feedback de pronúncia (modo leitura guiada)
  2) gerar frases-alvo por nível (em lote)
  3) conversar (chat multi-turno)
"""
import json
import re

import httpx

from .. import config
from . import diff as diffsvc
from . import pronunciation as pron


async def _chat_messages(messages: list[dict], temperature: float | None = None,
                         max_tokens: int = 2500,
                         response_format: dict | None = None) -> str:
    """Chama o LLM local com uma lista de mensagens (suporta multi-turno)."""
    payload = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "temperature": config.LLM_TEMPERATURE if temperature is None else temperature,
        "max_tokens": max_tokens,
        "stream": False,
        # desliga o thinking do Qwen3.5 (LM Studio): sem isso ele gasta os tokens
        # raciocinando, fica ~9x mais lento e o texto do raciocínio vazava na resposta
        "reasoning_effort": "none",
    }
    if response_format:
        payload["response_format"] = response_format
    # Servidor local não pede chave; API paga pede. Só mando o header se houver.
    headers = {}
    if config.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(config.LLM_URL, json=payload, headers=headers)
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


# ---------- 1) feedback e explicação: entrada estruturada, saída validada ----------
# O LLM só comenta as palavras erradas que o Python lista, adaptando a dica
# (hint) que o Python já verificou pra aquela palavra. IPA, "Pratique" e
# fallback são montados/validados em Python.
_IPA_RE = re.compile(r"[ɐ-˿Ͱ-Ͽðæŋ]")
_QUOTED_RE = re.compile(r"""['"“‘]([A-Za-z][A-Za-z'-]*)['"”’]""")
_FEEDBACK_MAX_WORDS = 2      # feedback cabe em 4 linhas
_EXPLAIN_MAX_WORDS = 3
_GENERIC_TIP_EN = "Speak slowly, word by word, and compare the sound with a native speaker."
_GENERIC_TIP_PT = "Fale devagar, palavra por palavra, e compare o som com o de um falante nativo."

FEEDBACK_SYSTEM = """You are an English pronunciation coach for a Brazilian learner.
You receive a TARGET sentence, what the speech engine HEARD, and a short list of PROBLEM WORDS
(each with what was heard, its ARPAbet pronunciation when known, and a verified "hint" or null).
Answer ONLY with JSON: {"heard": str, "words": [{"word": str, "tip": str}], "encouragement": str}

Rules:
- Comment ONLY on the listed problem words, once each. Never add other words.
- NEVER write IPA or phonetic spelling or invented words. Plain English only.
- Base each tip on that word's "hint". Only mention sounds the word really contains
  (no TH tip for a word without "th", no -ed tip for a word that does not end in "ed").
- If the hint is null, give a short general tip about slow, clear pronunciation.
- "heard": one short line saying what came out differently. Max 4 lines of feedback in total.
- "encouragement": one short friendly sentence."""

EXPLAIN_SYSTEM = """Você é um professor de inglês paciente ensinando uma CRIANÇA brasileira.
Você recebe a frase-ALVO, o que o reconhecedor OUVIU e uma lista de PALAVRAS-PROBLEMA
(com o que foi ouvido, a pronúncia em ARPAbet quando conhecida e uma "hint" verificada ou null).
Responda SOMENTE com JSON: {"words": [{"word": str, "how": str}]}

Regras:
- Comente SÓ as palavras listadas, uma vez cada. Nunca invente palavras.
- É PROIBIDO escrever IPA ou grafia fonética. Português do Brasil simples.
- "how": 1 frase curta e concreta, baseada na "hint" da palavra. Só cite sons que a palavra
  realmente tem (nada de TH em palavra sem "th", nem -ed em palavra que não termina em "ed").
- Se a hint for null, dê uma dica geral de falar devagar e com clareza.
- Não escreva "Pratique" nem despedidas."""

_FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "heard": {"type": "string"},
        "words": {"type": "array", "items": {
            "type": "object",
            "properties": {"word": {"type": "string"}, "tip": {"type": "string"}},
            "required": ["word", "tip"]}},
        "encouragement": {"type": "string"},
    },
    "required": ["heard", "words", "encouragement"],
}
_EXPLAIN_SCHEMA = {
    "type": "object",
    "properties": {
        "words": {"type": "array", "items": {
            "type": "object",
            "properties": {"word": {"type": "string"}, "how": {"type": "string"}},
            "required": ["word", "how"]}},
    },
    "required": ["words"],
}

# few-shot: (entrada do usuário, JSON correto)
_FEEDBACK_SHOTS = [
    ('TARGET: "I think this is the right thing."\nHEARD: "I sink this is the right sing."\n'
     'PROBLEM WORDS: [{"word": "think", "heard": "sink", "arpabet": "TH IH NG K", '
     '"hint": "Tongue lightly between the teeth, air flowing out, no voice."}, '
     '{"word": "thing", "heard": "sing", "arpabet": "TH IH NG", '
     '"hint": "Tongue lightly between the teeth, air flowing out, no voice."}]',
     {"heard": "\"think\" and \"thing\" came out as \"sink\" and \"sing\".",
      "words": [{"word": "think", "tip": "Put your tongue lightly between your teeth and blow air, like a soft hiss."},
                {"word": "thing", "tip": "Same TH: tongue between the teeth, no voice, then finish with the nasal ending."}],
      "encouragement": "Great effort, try it once more!"}),
    ('TARGET: "The young boy sang a song."\nHEARD: "The young boys sang a song."\n'
     'PROBLEM WORDS: [{"word": "boy", "heard": "boys", "arpabet": "B OY", '
     '"hint": "Say \'boy\' without the /z/ sound at the end."}]',
     {"heard": "\"boy\" came out as \"boys\" - an extra sound at the end.",
      "words": [{"word": "boy", "tip": "Stop right after \"boy\"; do not add the /z/ sound at the end."}],
      "encouragement": "Almost there, say it once more!"}),
    ('TARGET: "She walked to the park."\nHEARD: "She walk to the park."\n'
     'PROBLEM WORDS: [{"word": "walked", "heard": "walk", "arpabet": null, '
     '"hint": "For -ed endings: /t/ after voiceless sounds, /d/ after voiced sounds."}]',
     {"heard": "\"walked\" came out as \"walk\" - the ending was missing.",
      "words": [{"word": "walked", "tip": "Add a quick final sound after the k, like a small t."}],
      "encouragement": "You are close, say it again!"}),
]
_EXPLAIN_SHOTS = [
    ('ALVO: "I think this is the right thing."\nOUVIDO: "I sink this is the right sing."\n'
     'PALAVRAS-PROBLEMA: [{"word": "think", "heard": "sink", "arpabet": "TH IH NG K", '
     '"hint": "Língua levemente entre os dentes, soltando o ar, sem vibrar a voz."}]',
     {"words": [{"word": "think",
                 "how": "Ponha a ponta da língua entre os dentes e sopre o ar devagar, sem usar a voz."}]}),
    ('ALVO: "The young boy sang a song."\nOUVIDO: "The young boys sang a song."\n'
     'PALAVRAS-PROBLEMA: [{"word": "boy", "heard": "boys", "arpabet": "B OY", '
     '"hint": "Diga \'boy\' sem o som /z/ no fim."}]',
     {"words": [{"word": "boy", "how": "Pare logo depois de \"boy\", sem soltar o som /z/ no final."}]}),
    ('ALVO: "She walked to the park."\nOUVIDO: "She walk to the park."\n'
     'PALAVRAS-PROBLEMA: [{"word": "walked", "heard": "walk", "arpabet": null, '
     '"hint": "No final -ed: soa /t/ depois de som sem voz, /d/ depois de som com voz."}]',
     {"words": [{"word": "walked",
                 "how": "Termine a palavra com um toque rápido da língua, sem deixar o final sumir."}]}),
]


def _words_of(text: str) -> list[str]:
    return re.findall(r"[a-z']+", (text or "").lower())


def _word_tip(word: str, heard: str | None, focus: str | None, lang: str) -> str | None:
    """Dica verificada pra ESTA palavra: diferença de final calculada em Python,
    ou a dica do foco só se ela fala de sons que a palavra realmente tem."""
    fix = pron.ending_fix(word, heard, lang)
    if fix:
        return fix
    tip = pron.focus_tip(focus, lang)
    return tip if tip and pron.tip_applies(tip, word) else None


def _problem_words(target: str, transcription: str, diff: dict, max_n: int,
                   focus: str | None = None, exclude: set[str] = frozenset()) -> list[dict]:
    """Palavras wrong/missing sem repetição, com o que foi ouvido, a pronúncia e a dica."""
    heard_for: dict[str, str] = {}
    for tw, hw, _ in diffsvc.aligned_pairs(target, transcription):
        heard_for.setdefault(tw, hw)
    out, seen = [], set()
    for w in diff.get("words", []):
        if w.get("status") not in ("wrong", "missing"):
            continue
        word = w["word"].lower()
        if word in seen or word in exclude:
            continue
        seen.add(word)
        arpa = pron.get_pronunciation(word)
        heard = heard_for.get(word) if w["status"] == "wrong" else None
        out.append({
            "word": word,
            "heard": heard,
            "arpabet": arpa,
            "ipa": pron.to_ipa(arpa) if arpa else None,
            "tip_en": _word_tip(word, heard, focus, "en"),
            "tip_pt": _word_tip(word, heard, focus, "pt"),
        })
        if len(out) >= max_n:
            break
    return out


def _llm_view(problems: list[dict], lang: str) -> str:
    """Só o que o LLM precisa ver (sem o IPA, que é montado em Python)."""
    return json.dumps(
        [{"word": p["word"], "heard": p["heard"], "arpabet": p["arpabet"],
          "hint": p[f"tip_{lang}"]} for p in problems],
        ensure_ascii=False)


def _check_text(text, allowed: set[str], max_len: int, issues: list, flags: dict):
    if not isinstance(text, str) or not text.strip():
        issues.append("campo de texto vazio")
        return
    if len(text) > max_len:
        issues.append("texto longo demais")
    if _IPA_RE.search(text):
        flags["ipa"] = True
        issues.append("IPA no texto")
    for q in _QUOTED_RE.findall(text):
        if len(q) > 1 and q.lower() not in allowed:   # letras soltas ('t', 'd') = sons, não palavras
            flags["outside"].append(q.lower())
            issues.append(f"palavra fora da frase: {q}")


def _validate(data, kind: str, problems: list[dict], allowed: set[str]) -> dict:
    """Confere a saída do LLM. Retorna {issues, ipa, outside, wrong_sound}; issues vazio = ok."""
    issues: list[str] = []
    flags = {"ipa": False, "outside": [], "wrong_sound": []}
    listed = {p["word"] for p in problems}
    field = "tip" if kind == "feedback" else "how"
    limit = 180 if kind == "feedback" else 260
    cap = _FEEDBACK_MAX_WORDS if kind == "feedback" else _EXPLAIN_MAX_WORDS
    if not isinstance(data, dict) or not isinstance(data.get("words"), list):
        return {"issues": ["JSON fora do formato"], **flags}
    if kind == "feedback":
        _check_text(data.get("heard"), allowed, 200, issues, flags)
        _check_text(data.get("encouragement"), allowed, 120, issues, flags)
    items = data["words"]
    if not items or len(items) > cap:
        issues.append("quantidade de palavras inválida")
    seen = set()
    for it in items:
        if not isinstance(it, dict) or not isinstance(it.get("word"), str):
            issues.append("item inválido")
            continue
        w = it["word"].strip().lower()
        if w not in listed:
            flags["outside"].append(w)
            issues.append(f"palavra não listada: {w}")
        if w in seen:
            issues.append(f"palavra repetida: {w}")
        seen.add(w)
        _check_text(it.get(field), allowed, limit, issues, flags)
        if isinstance(it.get(field), str) and not pron.tip_applies(it[field], w):
            flags["wrong_sound"].append(w)
            issues.append(f"dica cita som que '{w}' não tem")
    return {"issues": issues, **flags}


async def _structured(system: str, shots: list, user: str, schema_name: str,
                      schema: dict, kind: str, problems: list[dict],
                      allowed: set[str]) -> tuple[dict | None, list[dict]]:
    """Pede JSON ao LLM e valida; 1 nova tentativa se falhar. (dados|None, tentativas)"""
    messages = [{"role": "system", "content": system}]
    for u, a in shots:
        messages.append({"role": "user", "content": u})
        messages.append({"role": "assistant", "content": json.dumps(a, ensure_ascii=False)})
    messages.append({"role": "user", "content": user})
    rf = {"type": "json_schema",
          "json_schema": {"name": schema_name, "strict": True, "schema": schema}}
    attempts = []
    for _ in range(2):
        raw = await _chat_messages(messages, temperature=0.2, max_tokens=600,
                                   response_format=rf)
        try:
            start, end = raw.find("{"), raw.rfind("}")
            data = json.loads(raw[start:end + 1])
        except ValueError:
            data = None
        res = _validate(data, kind, problems, allowed)
        attempts.append({"raw": raw, **res})
        if not res["issues"]:
            return data, attempts
    return None, attempts


def _unsure_note(uncertain) -> str:
    return (f"⚠️ Not sure I heard {', '.join(uncertain)} clearly - "
            "that may be the microphone, not you. Try again a bit slower.")


def _feedback_template(transcription: str, problems: list[dict]) -> str:
    if not problems:
        return ("🔎 What I heard: it matched the target very well.\n"
                "🗣️ Sounds to fix: nothing important - nice job!\n"
                "✅ Try again: read it once more with a natural rhythm.")
    bullets = [f"• {p['word']} - {p['tip_en'] or _GENERIC_TIP_EN}" for p in problems]
    lines = [f"🔎 What I heard: \"{transcription}\"",
             f"🗣️ Sounds to fix: {bullets[0]}"]
    lines += [f"   {b}" for b in bullets[1:]]
    lines.append("✅ Try again: good effort, read it once more, slowly!")
    return "\n".join(lines)


def _feedback_text(data: dict) -> str:
    bullets = [f"• {w['word']} - {w['tip'].strip()}" for w in data["words"]]
    lines = [f"🔎 What I heard: {data['heard'].strip()}",
             f"🗣️ Sounds to fix: {bullets[0]}"]
    lines += [f"   {b}" for b in bullets[1:]]
    lines.append(f"✅ Try again: {data['encouragement'].strip()}")
    return "\n".join(lines)


def _explain_block(p: dict, how: str) -> str:
    """Bloco da explicação; IPA e 'Pratique' vêm do Python, nunca do LLM."""
    head = f"👅 {p['word']}" + (f" — som /{p['ipa']}/" if p["ipa"] else "")
    note = pron.suffix_note(p["word"])
    how = f"{how.strip()} {note}" if note else how.strip()
    return f"{head}\n   Como fazer: {how}\n   Pratique: {p['word']}, {p['word']}"


async def build_feedback(target: str, transcription: str, diff: dict,
                         focus: str | None = None, uncertain: list[str] | None = None) -> dict:
    """{'text', 'fallback', 'attempts'} — nunca devolve texto não validado.

    'uncertain': palavras em que o Whisper tinha pouca confiança. Não entram como
    erro de pronúncia; viram só um aviso no fim.
    """
    unc = [w.lower() for w in uncertain or []]
    res = await _build_feedback(target, transcription, diff, focus, set(unc))
    if unc:
        # só sobrou erro incerto: nada a comentar além do aviso
        note = _unsure_note(unc)
        res["text"] = note if _no_errors(diff, unc) else res["text"] + "\n" + note
    return res


def _no_errors(diff: dict, unc: list[str]) -> bool:
    """True se todo erro do diff é uma palavra incerta (não sobra nada pra comentar)."""
    return all(w["word"].lower() in unc for w in diff.get("words", [])
               if w.get("status") in ("wrong", "missing"))


async def _build_feedback(target: str, transcription: str, diff: dict,
                          focus: str | None, exclude: set[str]) -> dict:
    problems = _problem_words(target, transcription, diff, _FEEDBACK_MAX_WORDS, focus, exclude)
    if not problems:
        return {"text": _feedback_template(transcription, []),
                "fallback": False, "attempts": []}
    allowed = set(_words_of(target)) | set(_words_of(transcription))
    user = (f'TARGET: "{target}"\nHEARD: "{transcription}"\n'
            f"PROBLEM WORDS: {_llm_view(problems, 'en')}")
    data, attempts = await _structured(FEEDBACK_SYSTEM, _FEEDBACK_SHOTS, user,
                                       "feedback", _FEEDBACK_SCHEMA, "feedback",
                                       problems, allowed)
    if data is None:
        return {"text": _feedback_template(transcription, problems),
                "fallback": True, "attempts": attempts}
    return {"text": _feedback_text(data), "fallback": False, "attempts": attempts}


async def build_explanation(target: str, transcription: str, diff: dict,
                            focus: str | None = None, uncertain: list[str] | None = None) -> dict:
    exclude = {w.lower() for w in uncertain or []}
    problems = _problem_words(target, transcription, diff, _EXPLAIN_MAX_WORDS, focus, exclude)
    if not problems:
        return {"text": "", "fallback": False, "attempts": []}
    allowed = set(_words_of(target)) | set(_words_of(transcription))
    user = (f'ALVO: "{target}"\nOUVIDO: "{transcription}"\n'
            f"PALAVRAS-PROBLEMA: {_llm_view(problems, 'pt')}")
    data, attempts = await _structured(EXPLAIN_SYSTEM, _EXPLAIN_SHOTS, user,
                                       "explanation", _EXPLAIN_SCHEMA, "explanation",
                                       problems, allowed)
    if data is None:
        blocks = [_explain_block(p, p["tip_pt"] or _GENERIC_TIP_PT) for p in problems]
        return {"text": "\n\n".join(blocks), "fallback": True, "attempts": attempts}
    by_word = {p["word"]: p for p in problems}
    blocks = [_explain_block(by_word[w["word"].strip().lower()], w["how"])
              for w in data["words"]]
    return {"text": "\n\n".join(blocks), "fallback": False, "attempts": attempts}


async def pronunciation_feedback(target: str, transcription: str, diff: dict,
                                 wpm: int | None, focus: str | None = None,
                                 uncertain: list[str] | None = None) -> str:
    return (await build_feedback(target, transcription, diff, focus, uncertain))["text"]


# ---------- 1b) explicação fonética detalhada (só quando nota baixa) ----------
async def phonetic_explanation(target: str, transcription: str, diff: dict,
                               focus: str | None, uncertain: list[str] | None = None) -> str:
    return (await build_explanation(target, transcription, diff, focus, uncertain))["text"]


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

    # o template do Qwen3.5 (LM Studio) dá 400 "No user query found" se uma
    # mensagem do assistente (o cumprimento inicial do front) vier antes da 1ª do usuário
    while clean and clean[0]["role"] == "assistant":
        clean.pop(0)

    messages = [{"role": "system", "content": CHAT_SYSTEM.format(level=level)}]
    messages.extend(clean)
    # temperatura mais alta = conversa mais viva; teto baixo = resposta curta
    return await _chat_messages(messages, temperature=0.7, max_tokens=400)
