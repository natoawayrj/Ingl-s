"""Avalia feedback/explicação contra o LLM configurado (sem banco nem Whisper).

Uso (de dentro de backend/):
    python -m tests.run_eval                      # usa LLM_MODEL do ambiente
    python -m tests.run_eval qwen2.5-7b-instruct  # compara outro modelo
Lê LLM_URL / LLM_API_KEY do ambiente (ou do env/.env).
"""
import asyncio
import json
import sys
import time
from pathlib import Path

from app import config
from app.services import llm_client

CASES = Path(__file__).resolve().parent / "eval_cases.json"


def _row(case_id: str, kind: str, secs: float, res: dict) -> str:
    atts = res["attempts"]
    ipa = any(a["ipa"] for a in atts)
    outside = sorted({w for a in atts for w in a["outside"]})
    wrong_sound = sorted({w for a in atts for w in a["wrong_sound"]})
    first_ok = bool(atts) and not atts[0]["issues"]
    valid = first_ok or not atts          # sem LLM (nada a validar) conta como ok
    return (f"| {case_id} | {kind} | {secs:.1f}s | {'sim' if ipa else 'não'} | "
            f"{', '.join(outside) or '-'} | {', '.join(wrong_sound) or '-'} | {'sim' if res['fallback'] else 'não'} | "
            f"{'sim' if valid else 'não'} |")


async def main(model: str | None) -> None:
    if model:
        config.LLM_MODEL = model
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    print(f"Modelo: `{config.LLM_MODEL}`  ·  {config.LLM_URL}\n")
    print("| caso | tipo | tempo | IPA | palavras fora do alvo | dica com som ausente | fallback | validou (1ª tentativa) |")
    print("|---|---|---|---|---|---|---|---|")
    texts = []
    for c in cases:
        for kind, fn in (("feedback", llm_client.build_feedback),
                         ("explicação", llm_client.build_explanation)):
            t0 = time.perf_counter()
            try:
                res = await fn(c["target"], c["transcription"], c["diff_json"], c["focus"])
            except Exception as e:  # LLM fora do ar etc.
                print(f"| {c['id']} | {kind} | - | - | - | - | - | erro: {type(e).__name__} |")
                continue
            print(_row(c["id"], kind, time.perf_counter() - t0, res))
            texts.append(f"### {c['id']} · {kind}\n```\n{res['text']}\n```")
    if "--texts" in sys.argv:
        print("\n" + "\n".join(texts))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    asyncio.run(main(args[0] if args else None))
