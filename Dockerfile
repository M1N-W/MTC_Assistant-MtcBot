FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PORT=5000

WORKDIR /app

RUN groupadd --system appuser \
    && useradd --system --gid appuser --create-home --home-dir /home/appuser appuser

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/healthz', timeout=3).read()" || exit 1

CMD ["sh", "-c", "gunicorn --worker-class gthread --threads ${GUNICORN_THREADS:-4} --workers 1 --timeout ${GUNICORN_TIMEOUT:-120} --keep-alive ${GUNICORN_KEEP_ALIVE:-5} --bind 0.0.0.0:${PORT:-5000} mtc_assistant.main:app"]
