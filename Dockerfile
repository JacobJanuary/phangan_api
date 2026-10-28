FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl libgl1 libglib2.0-0 libgomp1 libsm6 libxext6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app app

USER app
EXPOSE 62537

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:62537/health', timeout=3).read()"

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "62537", "--workers", "4"]
