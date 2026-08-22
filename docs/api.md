# Mindbase API Reference

Base URL: `http://localhost:8080` (local) or your cloud deployment.

Authentication: header `X-API-Key: <your-key>`

## Endpoints

### `GET /health`
No auth. Returns service health.

### `POST /v1/ingest`
Accept raw context fragment.

```json
{
  "content": "Завтра созвон с командой в 15:00 #работа",
  "source": "cli",
  "external_id": "optional-idempotency-key",
  "metadata": {"app": "telegram"},
  "captured_at": "2026-08-22T12:00:00Z"
}
```

Response:
```json
{
  "fragment_id": "uuid",
  "status": "queued",
  "message": "Fragment accepted for processing"
}
```

### `GET /v1/fragments/{id}`
Get fragment processing status and raw content.

### `POST /v1/search`
Search structured entries.

```json
{
  "query": "созвон команда",
  "limit": 10,
  "min_importance": 0.3,
  "tags": ["работа"],
  "since": "2026-08-01T00:00:00Z"
}
```

### `GET /v1/context/recent?limit=20`
Most recent entries.

### `GET /v1/context/summary`
Markdown bundle of last 30 entries — designed for AI system prompts.

## Webhook integration example (n8n / Shortcuts)

```
POST https://your-mindbase.example.com/v1/ingest
Headers: X-API-Key: secret
Body: {"content": "{{note}}", "source": "webhook", "metadata": {"device": "iphone"}}
```
