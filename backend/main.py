"""Pronuncia - backend FastAPI (tudo local).

Pipeline do modo leitura guiada:
  frente grava audio -> POST /api/practice
  -> Whisper local transcreve
  -> diff(alvo, transcricao)
  -> LLM local gera feedback de pronuncia
  -> descarta audio, salva texto/feedback no MySQL
  -> devolve resultado

Rode:  uvicorn main:app --reload --port 8000
"""
import json
import random

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
import db
import auth
from services import whisper_client, llm_client
from services import diff as diffsvc

app = FastAPI(title="Pronuncia")

# frente e back na mesma maquina; liberamos local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Health / status (pra voce saber se esta "no ar")
# ============================================================
@app.get("/api/health")
async def health():
    return {
        "db": db.ping(),
        "whisper_url": config.WHISPER_URL,
        "llm_url": config.LLM_URL,
        "llm_model": config.LLM_MODEL,
    }


# ============================================================
# Auth
# ============================================================
class LoginIn(BaseModel):
    email: str
    password: str


@app.post("/api/login")
async def login(body: LoginIn):
    user = db.query_one(
        "SELECT id, name, email, password_hash, role, level FROM users WHERE email=%s",
        (body.email.lower().strip(),),
    )
    if not user or not auth.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email ou senha inválidos")
    token = auth.create_token(user["id"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "role": user["role"],
            "level": user["level"],
        },
    }


@app.get("/api/me")
async def me(user: dict = Depends(auth.current_user)):
    return user


# ============================================================
# Frases-alvo
# ============================================================
# quantas frases recentes evitar repetir por usuario
RECENT_PHRASE_WINDOW = 10


@app.get("/api/phrase/next")
async def next_phrase(level: str | None = None, user: dict = Depends(auth.current_user)):
    """Sorteia uma frase do nivel do usuario, evitando as ultimas praticadas."""
    lvl = level or user["level"]
    rows = db.query_all(
        "SELECT id, text, level, focus FROM phrases WHERE level=%s AND active=1",
        (lvl,),
    )
    if not rows:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Sem frases para o nível {lvl}. Gere com POST /api/phrases/generate.",
        )

    # ids das ultimas frases que ESTE usuario praticou (anti-repeticao)
    recent = db.query_all(
        """SELECT phrase_id FROM attempts
           WHERE user_id=%s ORDER BY created_at DESC LIMIT %s""",
        (user["id"], RECENT_PHRASE_WINDOW),
    )
    recent_ids = {r["phrase_id"] for r in recent}

    # evita repetir; se sobrou pouca coisa (nivel pequeno), usa tudo
    fresh = [r for r in rows if r["id"] not in recent_ids]
    pool = fresh if len(fresh) >= 2 else rows
    return random.choice(pool)


VALID_LEVELS = {"A2", "B1", "B2", "C1"}


def _require_parent(user: dict):
    if user["role"] != "parent":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só o responsável pode fazer isso")


class GenIn(BaseModel):
    level: str = "B1"
    focus: str = "general clarity"
    count: int = 10


@app.post("/api/phrases/generate")
async def generate_phrases(body: GenIn, user: dict = Depends(auth.current_user)):
    """Gera frases em lote com o LLM local e salva no banco. Só 'parent'."""
    _require_parent(user)

    phrases = await llm_client.generate_phrases(body.level, body.focus, body.count)
    saved = 0
    for text in phrases:
        if not text or len(text) > 480:
            continue
        db.execute(
            "INSERT INTO phrases (text, level, focus) VALUES (%s, %s, %s)",
            (text, body.level, body.focus),
        )
        saved += 1
    return {"generated": len(phrases), "saved": saved, "level": body.level}


# ============================================================
# Admin de frases (CRUD) — só 'parent', sem precisar abrir o Workbench
# ============================================================
@app.get("/api/phrases")
async def list_phrases(
    level: str | None = None,
    active: int | None = None,
    user: dict = Depends(auth.current_user),
):
    """Lista frases para gerenciamento (parent). Filtra por nível e/ou ativo."""
    _require_parent(user)
    where, params = [], []
    if level:
        where.append("level=%s")
        params.append(level)
    if active is not None:
        where.append("active=%s")
        params.append(1 if active else 0)
    sql = "SELECT id, text, level, focus, active, created_at FROM phrases"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY level, id DESC"
    return db.query_all(sql, tuple(params))


class PhraseIn(BaseModel):
    text: str
    level: str = "B1"
    focus: str | None = None


def _clean_phrase_fields(text: str, level: str):
    text = (text or "").strip()
    if not text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Texto da frase vazio")
    if len(text) > 480:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Frase longa demais (máx 480)")
    if level not in VALID_LEVELS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Nível inválido: {level}")
    return text


@app.post("/api/phrases", status_code=status.HTTP_201_CREATED)
async def create_phrase(body: PhraseIn, user: dict = Depends(auth.current_user)):
    """Cria uma frase manualmente pela interface (parent)."""
    _require_parent(user)
    text = _clean_phrase_fields(body.text, body.level)
    focus = (body.focus or "").strip() or None
    new_id = db.execute(
        "INSERT INTO phrases (text, level, focus) VALUES (%s, %s, %s)",
        (text, body.level, focus),
    )
    return db.query_one(
        "SELECT id, text, level, focus, active, created_at FROM phrases WHERE id=%s",
        (new_id,),
    )


class PhrasePatch(BaseModel):
    text: str | None = None
    level: str | None = None
    focus: str | None = None
    active: bool | None = None


@app.patch("/api/phrases/{phrase_id}")
async def update_phrase(
    phrase_id: int, body: PhrasePatch, user: dict = Depends(auth.current_user)
):
    """Edita texto/nível/foco ou ativa/desativa uma frase (parent).

    Desativar (active=false) é o jeito seguro de 'remover': some das práticas
    mas preserva o histórico das tentativas (FK ON DELETE CASCADE não dispara).
    """
    _require_parent(user)
    current = db.query_one(
        "SELECT text, level FROM phrases WHERE id=%s", (phrase_id,)
    )
    if not current:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Frase não existe")

    sets, params = [], []
    if body.text is not None or body.level is not None:
        # se mexeu em texto ou nível, valida o par resultante
        new_text = body.text if body.text is not None else current["text"]
        new_level = body.level if body.level is not None else current["level"]
        new_text = _clean_phrase_fields(new_text, new_level)
        if body.text is not None:
            sets.append("text=%s"); params.append(new_text)
        if body.level is not None:
            sets.append("level=%s"); params.append(new_level)
    if body.focus is not None:
        sets.append("focus=%s"); params.append(body.focus.strip() or None)
    if body.active is not None:
        sets.append("active=%s"); params.append(1 if body.active else 0)

    if not sets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nada para atualizar")

    params.append(phrase_id)
    db.execute(f"UPDATE phrases SET {', '.join(sets)} WHERE id=%s", tuple(params))
    return db.query_one(
        "SELECT id, text, level, focus, active, created_at FROM phrases WHERE id=%s",
        (phrase_id,),
    )


# ============================================================
# Pratica (core)
# ============================================================
@app.post("/api/practice")
async def practice(
    phrase_id: int = Form(...),
    audio: UploadFile = File(...),
    user: dict = Depends(auth.current_user),
):
    phrase = db.query_one("SELECT id, text, focus FROM phrases WHERE id=%s", (phrase_id,))
    if not phrase:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Frase não existe")

    raw = await audio.read()
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Áudio vazio")

    # 1) transcreve (Whisper local)
    try:
        stt = await whisper_client.transcribe(raw)
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Whisper indisponível: {e}")

    transcription = stt["text"]
    target = phrase["text"]

    # 2) compara alvo x ouvido
    diff = diffsvc.compare(target, transcription)
    word_count = len(diff["words"])
    wpm = diffsvc.estimate_wpm(word_count, stt.get("duration") or 0)

    # 3) feedback (LLM local)
    try:
        feedback = await llm_client.pronunciation_feedback(
            target, transcription, diff, wpm
        )
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"LLM indisponível: {e}")

    # 3b) explicação fonética detalhada — só quando a nota ficou baixa e houve
    # palavra errada/sumida. É um EXTRA: se o LLM falhar aqui, não quebra a prática.
    explanation = None
    has_errors = any(w["status"] in ("wrong", "missing") for w in diff["words"])
    if has_errors and diff["accuracy"] < config.EXPLAIN_ACCURACY_THRESHOLD:
        try:
            explanation = await llm_client.phonetic_explanation(
                target, transcription, diff, phrase.get("focus")
            )
        except Exception:
            explanation = None  # bonus opcional; ignora falha

    # 4) salva (audio ja foi descartado — nunca persistido)
    db.execute(
        """INSERT INTO attempts
           (user_id, phrase_id, target_text, transcription, diff_json,
            feedback, explanation, wpm)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            user["id"], phrase_id, target, transcription,
            json.dumps(diff, ensure_ascii=False), feedback, explanation, wpm,
        ),
    )

    return {
        "target": target,
        "transcription": transcription,
        "diff": diff,
        "wpm": wpm,
        "feedback": feedback,
        "explanation": explanation,
    }


# ============================================================
# Conversa livre (chatbot em inglês) — efêmero, nada salvo no banco
# ============================================================
class ChatMsg(BaseModel):
    role: str          # "user" ou "assistant"
    content: str


class ChatIn(BaseModel):
    messages: list[ChatMsg]


@app.post("/api/chat")
async def chat(body: ChatIn, user: dict = Depends(auth.current_user)):
    """Conversa em inglês com o LLM local, no nível CEFR do usuário.

    O histórico vem do cliente (efêmero — nada é salvo). Última mensagem deve
    ser do aprendiz ('user').
    """
    history = [{"role": m.role, "content": m.content} for m in body.messages]
    if not history or history[-1]["role"] != "user":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Última mensagem deve ser do usuário")
    try:
        reply = await llm_client.chat_reply(history, user["level"])
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"LLM indisponível: {e}")
    return {"reply": reply}


@app.post("/api/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    user: dict = Depends(auth.current_user),
):
    """Transcreve áudio em texto (sem diff/feedback). Usado pela voz no chat.

    Áudio é descartado após transcrever — nunca persistido.
    """
    raw = await audio.read()
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Áudio vazio")
    try:
        stt = await whisper_client.transcribe(raw)
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Whisper indisponível: {e}")
    return {"text": stt["text"]}


# ============================================================
# Historico por usuario
# ============================================================
@app.get("/api/history")
async def history(limit: int = 30, user: dict = Depends(auth.current_user)):
    rows = db.query_all(
        """SELECT id, target_text, transcription, diff_json, feedback, explanation,
                  wpm, created_at
           FROM attempts WHERE user_id=%s ORDER BY created_at DESC LIMIT %s""",
        (user["id"], min(limit, 200)),
    )
    for r in rows:
        if isinstance(r.get("diff_json"), str):
            try:
                r["diff_json"] = json.loads(r["diff_json"])
            except Exception:
                pass
    return rows


# ============================================================
# Estatisticas / progresso (gamificacao) — usa diff_json ja salvo
# ============================================================
def _calc_streak(dates: list) -> int:
    """Dias seguidos praticando, contando a partir do dia mais recente.

    'dates' = lista de date (uma por tentativa, pode repetir). Aceita streak
    se a ultima pratica foi hoje OU ontem (nao quebra por ainda nao ter
    praticado hoje).
    """
    from datetime import date, timedelta

    days = sorted({d for d in dates if d}, reverse=True)
    if not days:
        return 0
    today = date.today()
    if (today - days[0]).days > 1:   # parou ha mais de 1 dia: streak zerado
        return 0
    streak = 1
    for prev, cur in zip(days, days[1:]):
        if (prev - cur).days == 1:
            streak += 1
        else:
            break
    return streak


@app.get("/api/stats")
async def stats(user: dict = Depends(auth.current_user)):
    """Resumo de progresso do usuario para o dashboard."""
    rows = db.query_all(
        """SELECT diff_json, wpm, created_at FROM attempts
           WHERE user_id=%s ORDER BY created_at DESC""",
        (user["id"],),
    )

    total = len(rows)
    acc_sum = 0.0
    acc_n = 0
    wpm_sum = 0
    wpm_n = 0
    weak = {}          # palavra -> quantas vezes errada/sumida
    dates = []

    for r in rows:
        if r.get("created_at"):
            dates.append(r["created_at"].date())
        if r.get("wpm"):
            wpm_sum += r["wpm"]
            wpm_n += 1

        diff = r.get("diff_json")
        if isinstance(diff, str):
            try:
                diff = json.loads(diff)
            except Exception:
                diff = None
        if not isinstance(diff, dict):
            continue

        if isinstance(diff.get("accuracy"), (int, float)):
            acc_sum += diff["accuracy"]
            acc_n += 1
        for w in diff.get("words", []):
            if w.get("status") in ("wrong", "missing"):
                word = w.get("word", "")
                if word:
                    weak[word] = weak.get(word, 0) + 1

    top_weak = sorted(weak.items(), key=lambda kv: kv[1], reverse=True)[:6]
    return {
        "total": total,
        "streak": _calc_streak(dates),
        "avg_accuracy": round(acc_sum / acc_n, 3) if acc_n else None,
        "avg_wpm": round(wpm_sum / wpm_n) if wpm_n else None,
        "weak_words": [{"word": w, "count": c} for w, c in top_weak],
    }


# ============================================================
# Relatorio de fonema (parent) — onde cada filho erra mais, por 'focus'
# ============================================================
def _parse_diff(raw) -> dict | None:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return None
    return raw if isinstance(raw, dict) else None


def _child_phoneme_report(user_id: int) -> list[dict]:
    """Agrega as tentativas de um filho por 'focus' da frase (o som-alvo).

    Pra cada foco: nº de tentativas, accuracy média (pior = mais difícil) e as
    palavras mais erradas. Ordena do mais difícil (menor accuracy) pro mais fácil.
    """
    rows = db.query_all(
        """SELECT a.diff_json, p.focus
           FROM attempts a JOIN phrases p ON p.id = a.phrase_id
           WHERE a.user_id=%s""",
        (user_id,),
    )

    buckets: dict[str, dict] = {}
    for r in rows:
        diff = _parse_diff(r.get("diff_json"))
        if not diff:
            continue
        focus = (r.get("focus") or "geral").strip() or "geral"
        b = buckets.setdefault(focus, {"acc_sum": 0.0, "acc_n": 0, "weak": {}})
        if isinstance(diff.get("accuracy"), (int, float)):
            b["acc_sum"] += diff["accuracy"]
            b["acc_n"] += 1
        for w in diff.get("words", []):
            if w.get("status") in ("wrong", "missing"):
                word = w.get("word", "")
                if word:
                    b["weak"][word] = b["weak"].get(word, 0) + 1

    report = []
    for focus, b in buckets.items():
        if not b["acc_n"]:
            continue
        top_weak = sorted(b["weak"].items(), key=lambda kv: kv[1], reverse=True)[:5]
        report.append({
            "focus": focus,
            "attempts": b["acc_n"],
            "avg_accuracy": round(b["acc_sum"] / b["acc_n"], 3),
            "weak_words": [{"word": w, "count": c} for w, c in top_weak],
        })
    # pior accuracy primeiro = onde o filho mais precisa de ajuda
    report.sort(key=lambda x: x["avg_accuracy"])
    return report


@app.get("/api/report/phonemes")
async def phoneme_report(
    user_id: int | None = None, user: dict = Depends(auth.current_user)
):
    """Relatório de dificuldade por som (focus), por filho. Só 'parent'."""
    _require_parent(user)
    if user_id is not None:
        kids = db.query_all(
            "SELECT id, name FROM users WHERE id=%s AND role='child'", (user_id,)
        )
    else:
        kids = db.query_all(
            "SELECT id, name FROM users WHERE role='child' ORDER BY name"
        )
    return {
        "children": [
            {
                "user_id": k["id"],
                "name": k["name"],
                "by_focus": _child_phoneme_report(k["id"]),
            }
            for k in kids
        ]
    }


# ============================================================
# Frontend estático (serve a SPA)
# ============================================================
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
