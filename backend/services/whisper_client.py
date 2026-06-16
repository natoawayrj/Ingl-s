"""Cliente do Whisper local (whisper.cpp server).

Fluxo:
  audio do navegador (webm/ogg) -> ffmpeg -> wav 16k mono -> whisper.cpp /inference
  -> texto + (se disponivel) segmentos com tempo.

whisper.cpp server: build com -DGGML_VULKAN=1 (acelera na RX 6900 XT) e rode:
  whisper-server -m models/ggml-medium.en.bin --host 127.0.0.1 --port 8080
"""
import subprocess
import tempfile
import os

import httpx

import config


def _to_wav16k(raw: bytes) -> bytes:
    """Converte qualquer audio recebido para wav 16k mono via ffmpeg."""
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "in")
        dst = os.path.join(d, "out.wav")
        with open(src, "wb") as f:
            f.write(raw)
        cmd = [
            config.FFMPEG_BIN, "-y", "-i", src,
            "-ar", "16000", "-ac", "1", "-f", "wav", dst,
        ]
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError(
                "ffmpeg falhou (instale ffmpeg e ponha no PATH): "
                + proc.stderr.decode(errors="ignore")[-300:]
            )
        with open(dst, "rb") as f:
            return f.read()


async def transcribe(raw_audio: bytes) -> dict:
    """Transcreve audio. Retorna {text, duration}.

    Provider definido no .env (WHISPER_PROVIDER):
      - "openai"     -> Whisper API (paga, audio sai da maquina)
      - "whispercpp" -> whisper.cpp server local (100% local)
    """
    wav = _to_wav16k(raw_audio)
    if config.WHISPER_PROVIDER == "openai":
        return await _transcribe_openai(wav)
    return await _transcribe_whispercpp(wav)


async def _transcribe_openai(wav: bytes) -> dict:
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY vazio no .env")
    files = {"file": ("audio.wav", wav, "audio/wav")}
    # verbose_json devolve duracao + segmentos (ritmo/pausas)
    data = {
        "model": config.OPENAI_WHISPER_MODEL,
        "language": "en",
        "temperature": "0",
        "response_format": "verbose_json",
    }
    headers = {"Authorization": f"Bearer {config.OPENAI_API_KEY}"}
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            config.OPENAI_WHISPER_URL, files=files, data=data, headers=headers
        )
        resp.raise_for_status()
        body = resp.json()
    return {
        "text": (body.get("text") or "").strip(),
        "duration": body.get("duration"),
    }


async def _transcribe_whispercpp(wav: bytes) -> dict:
    files = {"file": ("audio.wav", wav, "audio/wav")}
    data = {"response_format": "json", "language": "en", "temperature": "0"}
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(config.WHISPER_URL, files=files, data=data)
        resp.raise_for_status()
        body = resp.json()

    text = (body.get("text") or "").strip()
    duration = None
    segments = body.get("segments")
    if isinstance(segments, list) and segments:
        last = segments[-1]
        duration = last.get("end") or last.get("t1")
        if isinstance(duration, (int, float)) and duration > 1000:
            duration = duration / 100.0  # alguns builds usam centissegundos
    return {"text": text, "duration": duration}
