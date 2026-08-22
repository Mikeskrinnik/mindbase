# Obsidian + iCloud: настройка Mindbase

Mindbase работает **поверх** ваших существующих инструментов:

- **Obsidian** — вы пишете заметки как обычно
- **iCloud Drive** — всё хранится в облаке Apple, синхронизируется на iPhone/iPad/Mac
- **Mindbase API** — индексирует, структурирует, отдаёт AI-моделям

```
Obsidian Vault ──→ Sync Agent ──→ Mindbase API ──→ Worker
                       │                              │
                       └──── iCloud Drive ←───────────┘
                             (entries/*.md)
```

## Шаг 1: iCloud-папка

На Mac:

```bash
pip install ./packages/sync-agent
mindbase-sync init
```

Создаётся папка:
```
~/Library/Mobile Documents/com~apple~CloudDocs/Mindbase/
├── entries/        ← структурированные записи (markdown)
├── inbox/          ← новые заметки
├── obsidian-sync/  ← состояние синхронизации
└── index.json      ← офлайн-индекс
```

Эта папка автоматически появится на iPhone/iPad через «Файлы».

## Шаг 2: Подключить Obsidian

### Вариант A — Sync Agent (рекомендуется, без плагина)

```bash
# В .env:
OBSIDIAN_VAULT_PATH=~/Documents/MyVault
MINDBASE_API_URL=http://localhost:8080
MINDBASE_API_KEY=your-secret

mindbase-sync watch
```

Агент следит за vault и при каждом изменении:
1. Отправляет заметку в Mindbase API
2. Зеркалирует обработанные записи в iCloud

### Вариант B — Obsidian Plugin

1. Скопируйте `integrations/obsidian-mindbase/` в `.obsidian/plugins/mindbase-sync/`
2. В Obsidian: Settings → Community plugins → Enable «Mindbase Sync»
3. Укажите API URL и API Key

Плагин пушит заметки при сохранении — iCloud-зеркало делает sync-agent (`mindbase-sync pull`).

## Шаг 3: Obsidian + iCloud вместе

**Рекомендуемая схема:**

| Папка | Назначение |
|-------|------------|
| Ваш основной vault | Ежедневные заметки, Zettelkasten |
| `Mindbase/inbox/` в iCloud | Быстрые мысли с iPhone |
| `Mindbase/entries/` | Авто-зеркало из Mindbase (read-only) |

В Obsidian можно открыть iCloud-папку как **второй vault**:
Settings → Manage vaults → Open folder as vault → выберите `Mindbase/entries`

## Шаг 4: Фоновый запуск на Mac (launchd)

```bash
cp config/com.mindbase.sync.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.mindbase.sync.plist
```

Агент стартует при входе в систему и работает незаметно.

## Что хранится где

| Данные | Где | Зачем |
|--------|-----|-------|
| Сырые заметки Obsidian | Ваш vault (локально / Obsidian Sync) | Ваш рабочий процесс |
| Структурированный контекст | iCloud `entries/` | Доступ с любого устройства |
| Индекс + embeddings | PostgreSQL (Docker / cloud) | Семантический поиск для AI |
| Состояние синхронизации | iCloud `obsidian-sync/` | Идемпотентность |

## iPhone / Shortcuts

Быстрая запись в iCloud inbox:

1. Shortcut «Быстрая заметка» → Save File → `Mindbase/inbox/`
2. Sync-agent подхватит при следующем `watch`

Или через webhook:
```
POST /v1/ingest
{"content": "мысль", "source": "webhook", "metadata": {"device": "iphone"}}
```

## Команды

```bash
mindbase-sync status          # проверить пути и API
mindbase-sync push            # Obsidian → API (разово)
mindbase-sync pull            # API → iCloud (разово)
mindbase-sync watch           # непрерывная синхронизация
```
