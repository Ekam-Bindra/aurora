# AURORA API image. Build context is the repo root.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install the package (deps + source). Copy metadata first for better layer caching.
COPY apps/api/pyproject.toml apps/api/README.md ./
COPY apps/api/aurora ./aurora
RUN pip install --upgrade pip && pip install .

EXPOSE 8000

CMD ["uvicorn", "aurora.main:app", "--host", "0.0.0.0", "--port", "8000"]
