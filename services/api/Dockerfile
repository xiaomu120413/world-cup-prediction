FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
COPY data ./data
COPY db ./db
COPY scripts ./scripts

EXPOSE 8001

COPY docker-entrypoint.sh /usr/local/bin/worldcup-api-entrypoint
RUN chmod +x /usr/local/bin/worldcup-api-entrypoint

ENTRYPOINT ["worldcup-api-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
