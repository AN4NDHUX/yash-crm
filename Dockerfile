FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --disable-pip-version-check -r requirements.txt \
    && useradd --create-home --uid 10001 app
COPY --chown=app:app . .
RUN chmod 0755 /app/cloud-entrypoint.sh
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import os, urllib.request; host=os.getenv('RENDER_EXTERNAL_HOSTNAME') or os.getenv('ALLOWED_HOSTS','localhost').split(',')[0].strip(); req=urllib.request.Request('http://127.0.0.1:' + os.getenv('PORT','8000') + '/health', headers={'Host':host}); urllib.request.urlopen(req, timeout=3)"
CMD ["./cloud-entrypoint.sh"]
