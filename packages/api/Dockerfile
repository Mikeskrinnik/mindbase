FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY packages/shared /app/packages/shared
COPY packages/api /app/packages/api

RUN pip install --no-cache-dir /app/packages/shared /app/packages/api

EXPOSE 8080
CMD ["uvicorn", "mindbase_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
