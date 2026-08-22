FROM python:3.12-slim

WORKDIR /app

COPY packages/shared /app/packages/shared
COPY packages/worker /app/packages/worker

RUN pip install --no-cache-dir /app/packages/shared /app/packages/worker

CMD ["python", "-m", "mindbase_worker.main"]
