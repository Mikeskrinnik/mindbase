# Домашний сервер на iMac + iCloud + оркестратор

Целевое состояние: вы спрашиваете агента-оркестратора (Edit / Cursor) о чём угодно — и он знает то же, что и вы, потому что читает одну базу. Информация попадает туда **сама**, пока вы живёте обычной жизнью.

## Главное заблуждение про iCloud

**Отдельно «подключать iMac к iCloud» не нужно.** Если вы вошли в Apple ID на Mac — iCloud Drive уже работает.

Mindbase просто пишет файлы сюда:

```
~/Library/Mobile Documents/com~apple~CloudDocs/Mindbase/
```

macOS сам синхронизирует эту папку на iPhone, iPad и другие Mac. Никакого API Apple, ключей и туннелей для iCloud не требуется — это обычные файлы в специальной папке.

```
┌─────────────────────────────────────────────────────────────┐
│  iMac (дома, включён 24/7)                                  │
│                                                             │
│  Obsidian vault ──→ sync-agent ──→ Mindbase API (Docker)   │
│       │                    │              │                 │
│       │                    └──────────────┘                 │
│       │                           │                         │
│       ▼                           ▼                         │
│  iCloud Drive/Mindbase/     PostgreSQL + embeddings          │
│  (macOS sync)                     │                         │
└───────────────────────────────────┼─────────────────────────┘
                                    │ Apple iCloud
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
                 iPhone           iPad         MacBook
              (Файлы/inbox)   (Obsidian)    (Cursor + Edit)
```

## Роли устройств

| Устройство | Роль |
|------------|------|
| **Старый iMac** | Сервер: Docker (API + worker + DB), sync-agent, всегда включён |
| **MacBook / основной Mac** | Работа: Cursor, Edit, Obsidian |
| **iPhone** | Быстрый inbox через «Файлы» или Shortcut |
| **iCloud** | Транспорт и бэкап markdown-файлов (не сервер логики) |

iMac **не хранит** iCloud вместо API — он **зеркалирует** туда markdown для доступа с телефона. Поиск и embeddings живут в PostgreSQL на iMac.

## Настройка iMac (один раз, ~30 мин)

### 1. Не давать iMac засыпать

System Settings → Energy → «Prevent automatic sleeping when the display is off» (на питании).

Или в терминале:
```bash
sudo pmset -c sleep 0 disksleep 0
```

### 2. Docker + Mindbase

```bash
git clone https://github.com/Mikeskrinnik/mindbase.git ~/mindbase
cd ~/mindbase
cp .env.example .env
# Отредактируйте MINDBASE_API_KEY и OBSIDIAN_VAULT_PATH

docker compose up -d
```

Проверка: `curl http://localhost:8080/health`

### 3. Sync-agent (фоновый сбор из Obsidian)

```bash
pip install ~/mindbase/packages/sync-agent

# Укажите путь к vault в .env:
# OBSIDIAN_VAULT_PATH=/Users/you/Library/Mobile Documents/com~apple~CloudDocs/Obsidian/MyVault

mindbase-sync init
mindbase-sync watch
```

Автозапуск при входе:
```bash
# Отредактируйте пути в config/com.mindbase.sync.plist
cp config/com.mindbase.sync.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.mindbase.sync.plist
```

### 4. Доступ с MacBook (Tailscale)

Чтобы Edit на ноутбуке видел API на iMac:

```bash
# На обоих Mac:
brew install tailscale
sudo tailscale up
```

В Cursor MCP config на MacBook:
```json
{
  "mcpServers": {
    "mindbase": {
      "command": "python3",
      "args": ["-m", "mindbase_mcp.server"],
      "env": {
        "MINDBASE_API_URL": "http://100.x.x.x:8080",
        "MINDBASE_API_KEY": "ваш-ключ"
      }
    }
  }
}
```

`100.x.x.x` — Tailscale IP вашего iMac (видно в `tailscale status`).

Tailscale бесплатен для личного use, не требует проброса портов и белого IP.

## Где держать Obsidian vault

**Рекомендация:** vault прямо в iCloud Drive:

```
~/Library/Mobile Documents/com~apple~CloudDocs/Obsidian/MyVault/
```

Плюсы:
- Obsidian на iPhone/iPad из коробки
- sync-agent на iMac видит те же файлы
- Apple делает бэкап и sync

В Obsidian: Open folder as vault → выбрать эту папку.

## Как информация попадает без «налога»

Принцип: **собирать как побочный продукт того, что вы уже делаете**, а не отдельным действием «записать в базу».

### Уровень 0 — нулевой налог (уже делаете)

| Источник | Как попадает | Ваши действия |
|----------|--------------|---------------|
| Заметки в Obsidian | sync-agent следит за vault | Пишете как обычно |
| Диалоги с Edit/Cursor | MCP `mindbase_remember` | Ничего — агент сам сохраняет важное |
| Решения в чате | Правило в system prompt агента | Ничего |

### Уровень 1 — почти нулевой

| Источник | Как | Налог |
|----------|-----|-------|
| iPhone: мысль на ходу | Shortcut → файл в `Mindbase/inbox/` | 1 тап или Siri |
| Выделение на странице | Browser extension (roadmap) | 1 клик |
| Голосовая заметка | Voice memo → Whisper (roadmap) | Записал как обычно |

### Уровень 2 — избегать в daily use

| Источник | Налог |
|----------|-------|
| `mindbase note "..."` в терминале | Высокий — отдельное действие |
| Ручной copy-paste в базу | Высокий |
| Заполнение форм/тегов | Высокий |

**Правило:** 80% контекста должно приходить с уровня 0.

## Оркестратор Edit: как «знать то же, что и вы»

### При старте сессии

Агент автоматически загружает контекст:

```
1. mindbase_summary     → последние 30 записей (markdown)
2. mindbase_search(query) → по теме текущего разговора
3. mindbase_recent      → что было недавно
```

Добавьте в правила Edit / `.cursor/rules`:

```markdown
## Mindbase (память)

В начале каждой сессии вызови mindbase_summary.
При ответах на личные/проектные вопросы — mindbase_search.
В конце значимых решений — mindbase_remember с кратким summary.
Не спрашивай разрешения на remember — сохраняй факты молча.
```

### Во время работы

```
Вы: "Когда у меня созвон с командой?"
Edit: mindbase_search("созвон команда") → находит заметку из Obsidian
Edit: "В субботу в 15:00, ты писал в заметке meeting-notes"
```

### После работы (автосохранение)

Агент сам вызывает:
```
mindbase_remember({
  content: "Решили использовать Tailscale для доступа к iMac. API на порту 8080.",
  tags: ["infra", "mindbase"]
})
```

Вы ничего не делаете — агент фиксирует итоги сессии.

## Минимальный стек для старого iMac

Если iMac слабый, урежьте ресурсы:

```yaml
# docker-compose.override.yml на iMac
services:
  postgres:
    deploy:
      resources:
        limits:
          memory: 512M
  api:
    deploy:
      resources:
        limits:
          memory: 256M
  worker:
    deploy:
      resources:
        limits:
          memory: 256M
```

Без `EMBEDDING_API_KEY` система работает на keyword search — для старта достаточно.

## Чеклист «всё работает»

- [ ] `curl http://localhost:8080/health` → healthy
- [ ] Написал заметку в Obsidian → через 30 сек появилась в API (`mindbase search`)
- [ ] `Mindbase/entries/` в iCloud пополняется markdown-файлами
- [ ] С MacBook через Tailscale: MCP `mindbase_summary` отвечает
- [ ] Edit в начале сессии видит ваш контекст

## Что строим дальше (для нулевого налога)

| Фича | Эффект |
|------|--------|
| Auto-remember в MCP | Агент сохраняет без явного tool call |
| iOS Shortcut «Запомни» | Голос → inbox → sync |
| Clipboard watcher (opt-in) | Копируете текст → автозахват |
| Temporal facts | «Раньше работал в X» vs «сейчас в Y» |
