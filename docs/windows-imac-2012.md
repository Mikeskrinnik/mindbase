# iMac 2012 + Windows 10: домашний сервер Mindbase

У вас **не macOS**, а Windows 10 — это меняет пути и способ автозапуска, но **iCloud всё равно работает** через приложение [iCloud for Windows](https://apps.microsoft.com/detail/9PKTQ5699M62).

## Честная оценка железа

iMac 2012 на Windows 10 — это примерно:
- 4–8 GB RAM (редко 16)
- HDD или старый SSD
- Docker Desktop + WSL2 **может не потянуть** или будет тормозить

Поэтому три режима — от лёгкого к полному:

| Режим | Что на iMac | RAM | Когда |
|-------|-------------|-----|-------|
| **A — Hub** ⭐ | Только sync-agent + iCloud | ~200 MB | Рекомендуем для 2012 |
| **B — Light API** | sync-agent + Docker light | ~1.5 GB | Если RAM ≥ 8 GB |
| **C — Full** | Полный docker compose | ~3 GB+ | Только с апгрейдом RAM/SSD |

---

## Режим A (рекомендуем): iMac = sync-хаб

iMac **не** крутит тяжёлый API. Он только:
1. Следит за папкой iCloud (Obsidian vault / inbox)
2. Отправляет изменения на API

API живёт **на MacBook** (когда работаете) или на **дешёвом VPS** ($4–5/мес).

```
iPhone ──→ iCloud ──→ iMac Win10 (sync-agent) ──→ API (MacBook или VPS)
                ↑                                        │
                └──────── Mindbase/entries/ ←────────────┘
                     (markdown в iCloud)
```

### Шаг 1: iCloud for Windows

1. Microsoft Store → **iCloud**
2. Войти в Apple ID
3. Включить **iCloud Drive**

Папка появится (одна из):
```
C:\Users\ВАШ_ЛОГИН\iCloudDrive\
C:\Users\ВАШ_ЛОГИН\Apple iCloud\iCloudDrive\
```

Проверка в PowerShell:
```powershell
Get-ChildItem "$env:USERPROFILE\iCloudDrive" -ErrorAction SilentlyContinue
Get-ChildItem "$env:USERPROFILE\Apple iCloud\iCloudDrive" -ErrorAction SilentlyContinue
```

### Шаг 2: Python + sync-agent

```powershell
# Установить Python 3.11+ с python.org (галочка "Add to PATH")
cd $HOME\mindbase
python -m pip install .\packages\shared .\packages\sync-agent

# Создать папку Mindbase в iCloud
python -m mindbase_sync.cli init --icloud "$env:USERPROFILE\iCloudDrive\Mindbase"
```

### Шаг 3: .env на iMac

Создайте `C:\Users\ВАШ_ЛОГИН\mindbase\.env`:

```env
# Куда слать заметки — API на MacBook или VPS
MINDBASE_API_URL=http://100.x.x.x:8080
MINDBASE_API_KEY=ваш-длинный-секрет

# Путь к Obsidian vault в iCloud (после синка)
OBSIDIAN_VAULT_PATH=C:\Users\ВАШ_ЛОГИН\iCloudDrive\Obsidian\MyVault

# Явный путь к Mindbase в iCloud
ICLOUD_MINDBASE_PATH=C:\Users\ВАШ_ЛОГИН\iCloudDrive\Mindbase

SYNC_POLL_INTERVAL_SEC=60
```

`100.x.x.x` — Tailscale IP машины, где крутится API (MacBook или VPS).

### Шаг 4: Автозапуск (Task Scheduler)

```powershell
cd $HOME\mindbase
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install-sync-task.ps1
```

Или вручную: Task Scheduler → Create Task → At log on → `mindbase-sync watch`.

### Шаг 5: iMac не засыпает

Settings → System → Power & sleep:
- Screen: можно выключать через 10 мин
- Sleep: **Never** (when plugged in)

---

## Режим B: API прямо на iMac (если RAM ≥ 8 GB)

### Docker Desktop на Windows 10

1. [Docker Desktop](https://www.docker.com/products/docker-desktop/) — включить WSL2 backend
2. Если WSL2 не ставится (старый CPU/BIOS) — **не используйте Docker**, берите Режим A

```powershell
cd $HOME\mindbase
copy .env.example .env
# Отредактируйте .env

docker compose -f docker-compose.light.yml up -d
```

Light-стек: только Postgres + Redis + API + Worker (~1.2 GB RAM, без MinIO).

Проверка:
```powershell
curl http://localhost:8080/health
```

### Sync-agent на тот же iMac

```powershell
python -m pip install .\packages\shared .\packages\sync-agent
python -m mindbase_sync.cli watch
```

API URL в `.env`: `http://localhost:8080`

---

## iCloud + Obsidian на Windows

### Где держать vault

**Лучший вариант:** vault в iCloud Drive — тогда iPhone/MacBook/iMac видят одно и то же.

```
C:\Users\you\iCloudDrive\Obsidian\MyVault\
```

На MacBook (если есть): тот же vault через
```
~/Library/Mobile Documents/com~apple~CloudDocs/Obsidian/MyVault/
```

Obsidian на Windows: Open folder → `iCloudDrive\Obsidian\MyVault`

### Важно про iCloud for Windows

- Синк **не мгновенный** — задержка 30 сек – несколько минут
- `sync-agent` с `SYNC_POLL_INTERVAL_SEC=60` это учитывает
- Не кладите vault на сетевой диск — только локальная iCloud-папка

---

## Доступ Edit/Cursor с MacBook к API на iMac

### Tailscale (рекомендуем)

На **обоих** устройствах:
1. https://tailscale.com/download/windows
2. `tailscale up` / войти в аккаунт
3. На MacBook в MCP:

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

`100.x.x.x` = Tailscale IP iMac (команда `tailscale ip` на Windows).

### Без Tailscale

- Проброс порта 8080 на роутере (небезопасно без HTTPS)
- Или API только когда MacBook в той же Wi‑Fi сети: `http://192.168.1.x:8080`

---

## Сбор контекста без налога (ваша схема)

| Что вы делаете | Как попадает в базу |
|----------------|---------------------|
| Пишете в Obsidian (любое устройство) | iCloud синкает → iMac sync-agent → API |
| Общаетесь с Edit | MCP `mindbase_remember` / `mindbase_summary` |
| Мысль с iPhone | Shortcut → `iCloudDrive/Mindbase/inbox/` → sync-agent |

**iMac 2012 в фоне** только перекладывает файлы iCloud → API. Вы ничего не запускаете руками.

---

## Чеклист для вашего iMac

- [ ] iCloud for Windows установлен, Drive включён
- [ ] Python 3.11+ установлен
- [ ] `mindbase-sync init` создал `iCloudDrive\Mindbase\`
- [ ] Task Scheduler запускает `watch` при входе
- [ ] Sleep отключён при питании
- [ ] Tailscale установлен, MacBook видит iMac по `100.x.x.x`
- [ ] Тест: создать `.md` в vault → через 1–2 мин запись в API

---

## Если iMac совсем не тянет

Минимальный рабочий вариант:
1. **API** — Oracle Cloud free tier / Hetzner CX11 / MacBook когда включён
2. **iMac** — только sync-agent + iCloud (200 MB RAM)
3. **Хранение markdown** — iCloud (бесплатно, уже есть)

Это всё равно даёт target state: Edit спрашиваете → он читает ту же базу.

---

## Скрипты

- `scripts/windows/install-sync-task.ps1` — автозапуск sync-agent
- `scripts/windows/setup.ps1` — первичная установка
- `docker-compose.light.yml` — облегчённый API-стек
