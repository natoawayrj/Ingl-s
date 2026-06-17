FROM python:3.11-slim

# ffmpeg: converte áudio do navegador -> wav 16k (some a dependência de PATH do host)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

# deps primeiro (cache de camada)
COPY backend/requirements.txt /code/backend/requirements.txt
RUN pip install --no-cache-dir -r /code/backend/requirements.txt

# código + frontend (build context = raiz pronuncia/, pra ter o frontend/ ao lado)
COPY backend/ /code/backend/
COPY frontend/ /code/frontend/

# main.py sobe 3 níveis (app -> backend -> /code) e acha /code/frontend
WORKDIR /code/backend

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
