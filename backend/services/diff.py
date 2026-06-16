"""Compara frase-alvo com a transcrição do Whisper.

Esse é o coração da avaliação de pronúncia no modo leitura guiada:
a frase-alvo é o 'ground truth'. Se o Whisper ouviu algo diferente,
provavelmente houve erro de pronúncia (ou palavra omitida/trocada).
"""
import re
from difflib import SequenceMatcher


def _normalize(text: str) -> list[str]:
    """Minúsculas, sem pontuação -> lista de palavras."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9'\s]", " ", text)
    return [w for w in text.split() if w]


def compare(target: str, heard: str) -> dict:
    """Retorna diff palavra-a-palavra entre alvo e transcrição.

    Saída:
      {
        "words": [ {word, status}, ... ],   # status: ok|wrong|missing
        "extra": [palavras a mais que o Whisper ouviu],
        "accuracy": 0..1,                    # fração de palavras-alvo corretas
        "summary": "x de y palavras bateram"
      }
    """
    tgt = _normalize(target)
    hrd = _normalize(heard)

    sm = SequenceMatcher(a=tgt, b=hrd, autojunk=False)
    words = []
    extra = []
    ok = 0

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for w in tgt[i1:i2]:
                words.append({"word": w, "status": "ok"})
                ok += 1
        elif tag == "replace":
            for w in tgt[i1:i2]:
                words.append({"word": w, "status": "wrong"})
            extra.extend(hrd[j1:j2])
        elif tag == "delete":  # estava no alvo, sumiu na fala
            for w in tgt[i1:i2]:
                words.append({"word": w, "status": "missing"})
        elif tag == "insert":  # fala tinha palavra a mais
            extra.extend(hrd[j1:j2])

    total = len(tgt) or 1
    accuracy = ok / total
    return {
        "words": words,
        "extra": extra,
        "accuracy": round(accuracy, 3),
        "summary": f"{ok} de {total} palavras bateram com o alvo",
    }


def estimate_wpm(word_count: int, duration_sec: float) -> int | None:
    """Ritmo aproximado em palavras por minuto."""
    if not duration_sec or duration_sec <= 0:
        return None
    return round(word_count / (duration_sec / 60.0))
