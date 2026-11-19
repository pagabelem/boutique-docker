
# STAGE 1 : BUILDER
FROM python:3.12-slim AS builder

WORKDIR /install

COPY requirements.txt .

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# STAGE 2 : IMAGE FINALE
FROM python:3.12-slim

WORKDIR /app

# Copier les dependances
COPY --from=builder /install /usr/local

# Copier le code
COPY app/ ./app/

# Creer un utilisateur non-root
RUN useradd --create-home appuser \
    && chown -R appuser:appuser /app

USER appuser

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health')"

EXPOSE 5000

CMD ["python", "app/app.py"]
