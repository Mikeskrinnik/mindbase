FROM python:3.12-slim

WORKDIR /app

COPY packages/shared /app/packages/shared
COPY packages/mcp-server /app/packages/mcp-server

RUN pip install --no-cache-dir /app/packages/shared /app/packages/mcp-server

EXPOSE 8090
CMD ["python", "-m", "mindbase_mcp.server"]
