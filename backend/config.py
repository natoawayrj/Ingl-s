"""Configuração central — lê variáveis do .env."""
import os
from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default)


# MySQL
DB_HOST = _get("DB_HOST", "127.0.0.1")
DB_PORT = int(_get("DB_PORT", "3306"))
DB_USER = _get("DB_USER", "root")
DB_PASSWORD = _get("DB_PASSWORD", "")
DB_NAME = _get("DB_NAME", "pronuncia")

# Auth
JWT_SECRET = _get("JWT_SECRET", "dev-insecure-change-me")
JWT_EXPIRE_HOURS = int(_get("JWT_EXPIRE_HOURS", "720"))
JWT_ALGO = "HS256"

# Whisper: provider "openai" (API paga) ou "whispercpp" (local)
WHISPER_PROVIDER = _get("WHISPER_PROVIDER", "whispercpp").lower()
# whispercpp local:
WHISPER_URL = _get("WHISPER_URL", "http://127.0.0.1:8080/inference")
# openai API:
OPENAI_API_KEY = _get("OPENAI_API_KEY", "")
OPENAI_WHISPER_URL = _get(
    "OPENAI_WHISPER_URL", "https://api.openai.com/v1/audio/transcriptions"
)
OPENAI_WHISPER_MODEL = _get("OPENAI_WHISPER_MODEL", "whisper-1")

# LLM local (LM Studio, OpenAI-compatible)
LLM_URL = _get("LLM_URL", "http://127.0.0.1:1234/v1/chat/completions")
LLM_MODEL = _get("LLM_MODEL", "gemma-4-12b-it")
LLM_TEMPERATURE = float(_get("LLM_TEMPERATURE", "0.3"))

# Pronúncia: abaixo deste accuracy (0..1), o LLM gera explicação fonética
# detalhada (posição de língua/boca). Acima, só o feedback curto basta.
EXPLAIN_ACCURACY_THRESHOLD = float(_get("EXPLAIN_ACCURACY_THRESHOLD", "0.8"))

# ffmpeg
FFMPEG_BIN = _get("FFMPEG_BIN", "ffmpeg")
