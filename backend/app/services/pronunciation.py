"""Pronúncia calculada (CMUdict) e dicas por foco — nada disso passa pelo LLM.

- get_pronunciation: ARPAbet de uma palavra, ou None se não estiver no CMUdict.
- to_ipa: converte esse ARPAbet pra IPA (tabela fixa) pra exibir no front.
- suffix_note: regra fixa de -ed / -s aplicada sobre a pronúncia da raiz.
- focus_tip: dica curta por foco, lida de data/focus_tips.json (rascunho).
"""
import json
import re
from functools import lru_cache
from pathlib import Path

import pronouncing

_TIPS_PATH = Path(__file__).resolve().parent.parent / "data" / "focus_tips.json"

_ARPA_TO_IPA = {
    "AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "aʊ", "AY": "aɪ",
    "B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "EH": "ɛ", "ER": "ɝ",
    "EY": "eɪ", "F": "f", "G": "ɡ", "HH": "h", "IH": "ɪ", "IY": "iː",
    "JH": "dʒ", "K": "k", "L": "l", "M": "m", "N": "n", "NG": "ŋ",
    "OW": "oʊ", "OY": "ɔɪ", "P": "p", "R": "r", "S": "s", "SH": "ʃ",
    "T": "t", "TH": "θ", "UH": "ʊ", "UW": "uː", "V": "v", "W": "w",
    "Y": "j", "Z": "z", "ZH": "ʒ",
}
_VOICELESS = {"P", "K", "F", "S", "SH", "CH", "TH", "HH"}
_SIBILANT = {"S", "Z", "SH", "ZH", "CH", "JH"}


@lru_cache(maxsize=2048)
def get_pronunciation(word: str) -> str | None:
    """ARPAbet sem marcas de acento (ex.: 'IH M P R EH S T'), ou None."""
    w = (word or "").lower().strip()
    if not w:
        return None
    phones = pronouncing.phones_for_word(w)
    if not phones:
        return None
    return re.sub(r"\d", "", phones[0])


def to_ipa(arpa: str) -> str:
    """Tabela fixa ARPAbet -> IPA. O LLM nunca participa disso."""
    return "".join(_ARPA_TO_IPA.get(p, "") for p in arpa.split())


def suffix_note(word: str) -> str | None:
    """Regra do -ed / -s (em pt-BR) calculada sobre a pronúncia da raiz."""
    w = (word or "").lower()
    if len(w) < 5:
        return None
    if w.endswith("ed"):
        bases, kind = (w[:-1], w[:-2]), "ed"
    elif w.endswith("s") and not w.endswith(("ss", "us", "is")):
        bases, kind = (w[:-1], w[:-2] if w.endswith("es") else w[:-1]), "s"
    else:
        return None
    for base in bases:
        arpa = get_pronunciation(base)
        if not arpa:
            continue
        last = arpa.split()[-1]
        if kind == "ed":
            if last in ("T", "D"):
                snd = "um 'id' extra (sílaba a mais)"
            elif last in _VOICELESS:
                snd = "/t/"
            else:
                snd = "/d/"
            return f"O final -ed de '{w}' soa como {snd}."
        if last in _SIBILANT:
            snd = "um 'iz' extra (sílaba a mais)"
        elif last in _VOICELESS:
            snd = "/s/"
        else:
            snd = "/z/"
        return f"O final -s de '{w}' soa como {snd}."
    return None


def normalize_focus(focus: str | None) -> str:
    """Tira o prefixo 'seed:' e espaços extras (o banco não é alterado)."""
    f = re.sub(r"^\s*seed\s*:\s*", "", focus or "", flags=re.I)
    return re.sub(r"\s+", " ", f).strip()


@lru_cache(maxsize=1)
def _tips() -> dict:
    try:
        return json.loads(_TIPS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def focus_tip(focus: str | None, lang: str = "pt") -> str:
    """Dica do foco no idioma pedido ('pt' ou 'en'); genérica se não houver."""
    tips = _tips()
    entry = tips.get(normalize_focus(focus))
    if not isinstance(entry, dict):
        entry = tips.get("_default", {})
    return entry.get(lang) or entry.get("pt", "")


# ---------- a dica só pode falar de sons que a palavra tem ----------
_SOUND_RULES = [
    (re.compile(r"\bth\b", re.I), lambda w: "th" in w),
    (re.compile(r"-ed\b", re.I), lambda w: w.endswith("ed")),
    (re.compile(r"-ng\b|\bnasal\b", re.I), lambda w: "ng" in w),
    (re.compile(r"\bgh\b", re.I), lambda w: "gh" in w),
]


def tip_applies(tip: str, word: str) -> bool:
    """False se a dica cita um som (TH, -ed, -ng, GH) que a palavra não tem."""
    w = (word or "").lower()
    return all(has(w) for pat, has in _SOUND_RULES if pat.search(tip or ""))


def _s_sound(word: str) -> str:
    arpa = get_pronunciation(word)
    last = arpa.split()[-1] if arpa else ""
    if last in _SIBILANT:
        return "iz"
    return "/s/" if last in _VOICELESS else "/z/"


def ending_fix(word: str, heard: str | None, lang: str = "pt") -> str | None:
    """Dica calculada quando o ouvido difere só pelo final (ex.: boy -> boys)."""
    w, h = (word or "").lower(), (heard or "").lower()
    if not h or h == w:
        return None
    if h.startswith(w):
        end, extra = h[len(w):], True
    elif w.startswith(h):
        end, extra = w[len(h):], False
    else:
        return None
    if end in ("s", "es"):
        snd = _s_sound(w if extra else w[:len(h)])
        if lang == "pt":
            return (f"Diga '{w}' sem o som {snd} no fim." if extra
                    else f"Termine '{w}' com o som {snd} no fim.")
        return (f"Say '{w}' without the {snd} sound at the end." if extra
                else f"Finish '{w}' with the {snd} sound at the end.")
    if lang == "pt":
        return (f"Pare em '{w}', sem acrescentar '{end}' no fim." if extra
                else f"Não deixe o final '{end}' sumir: termine '{w}' com ele.")
    return (f"Stop at '{w}', without adding '{end}' at the end." if extra
            else f"Do not drop the ending '{end}': finish '{w}' with it.")
