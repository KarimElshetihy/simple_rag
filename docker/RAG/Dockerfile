FROM ghcr.io/astral-sh/uv:0.6.14-python3.12-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libavif-dev \
    libffi-dev \
    libjpeg-dev \
    libxml2-dev \
    libxslt1-dev \
    pkg-config \
    tesseract-ocr \
    tesseract-ocr-ara \
    tesseract-ocr-eng \
    unzip \
    zip \
    && rm -rf /var/lib/apt/lists/*

COPY src/requirements.txt /app/requirements.txt
RUN uv pip install --system -r /app/requirements.txt

COPY src/ /app/src/
COPY alembic/ /app/alembic/
COPY docker/RAG/alembic.ini /app/docker/RAG/alembic.ini
COPY docker/RAG/entrypoint.sh /entrypoint.sh

ENV DATA_DIR=/app/data \
    TESSERACT_CMD=/usr/bin/tesseract \
    TESSDATA_DIR=/usr/share/tesseract-ocr/5/tessdata

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app \
        --no-create-home --shell /usr/sbin/nologin app \
    && chmod +x /entrypoint.sh \
    && mkdir -p /app/data \
    && chown app:app /app/data

USER app:app

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]