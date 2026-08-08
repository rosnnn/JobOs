FROM python:3.11-slim

WORKDIR /app

ARG INSTALL_PLAYWRIGHT=false

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts
COPY data/application_defaults.json ./data/application_defaults.json

RUN pip install --no-cache-dir -e .

RUN if [ "$INSTALL_PLAYWRIGHT" = "true" ]; then \
            playwright install-deps chromium && playwright install chromium; \
        fi

RUN mkdir -p /app/data/artifacts /app/data/resumes /app/data/cover_letters

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "job_os.main:app", "--host", "0.0.0.0", "--port", "8000"]
