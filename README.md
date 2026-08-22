# Mindbase

**Единая облачная память контекста** — система автоматического, незаметного сбора и структурирования вашего контекста (мысли, заметки, окружение, активность) в единую базу, доступную всем вашим AI-моделям.

## Что это

Mindbase собирает «сырой» контекст из разных источников, нормализует его, извлекает сущности, строит семантические embeddings и отдаёт структурированные данные через REST API и MCP-протокол.

```
[Источники] → [Collector] → [API Gateway] → [Queue] → [Worker] → [PostgreSQL + pgvector]
                                                                    ↘ [MinIO/S3]
                                              [MCP Server] ←──────────┘
                                              [REST API]
```

## Источники контекста (roadmap)

| Источник | Статус | Описание |
|----------|--------|----------|
| CLI / stdin | ✅ v0 | Текст, файлы, clipboard |
| REST webhook | ✅ v0 | Интеграции (Shortcuts, Zapier, n8n) |
| MCP push | ✅ v0 | Прямая запись из Cursor/Claude |
| Browser extension | 🔜 v1 | Страницы, выделения |
| macOS/iOS agent | 🔜 v1 | Фоновый сбор без участия |
| Voice | 🔜 v2 | Whisper-транскрипция |

## Быстрый старт

```bash
cp .env.example .env
docker compose up -d
# API: http://localhost:8080/docs
# MCP: http://localhost:8090
```

Локальная разработка без Docker:

```bash
cd packages/api && pip install -e ".[dev]" && uvicorn mindbase_api.main:app --reload
```

## Архитектура

- **PostgreSQL + pgvector** — структурированное хранение + семантический поиск
- **Redis Streams** — очередь событий с at-least-once delivery
- **MinIO / S3** — бинарные вложения (аудио, скриншоты)
- **Worker** — embeddings, извлечение сущностей, дедупликация
- **MCP Server** — нативный доступ для Cursor, Claude Desktop и других MCP-клиентов

Подробнее: [docs/architecture.md](docs/architecture.md)

## Облако и отказоустойчивость

- Health checks + auto-restart (Docker/K8s)
- Идемпотентная запись по `source_id + external_id`
- Retry с exponential backoff в worker
- PostgreSQL streaming replication (Terraform)
- S3 cross-region replication для вложений

Deploy: [infra/terraform/README.md](infra/terraform/README.md)

## Лицензия

MIT
