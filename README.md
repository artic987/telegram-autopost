# Telegram Autopost

Автопостинг из личного Telegram-аккаунта через Telethon и GitHub Actions.

## Расписание

Workflow запускается два раза в час:

- на 7-й минуте
- на 37-й минуте

Файл: `.github/workflows/autopost.yml`

## Что нужно добавить вручную

Открой:

`Settings → Secrets and variables → Actions`

Создай три Repository secrets:

- `TG_API_ID`
- `TG_API_HASH`
- `TG_STRING_SESSION`

## Как получить TG_STRING_SESSION

На компьютере, где уже есть `my_account.session`, создай рядом файл `export_session.py`:

```python
import os
from pathlib import Path
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

BASE_DIR = Path(__file__).resolve().parent
API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]

with TelegramClient(str(BASE_DIR / "my_account"), API_ID, API_HASH) as client:
    print(StringSession.save(client.session))
```

В PowerShell в этой папке:

```powershell
$env:TG_API_ID="ВАШ_API_ID"
$env:TG_API_HASH="ВАШ_API_HASH"
py export_session.py
```

Полученную длинную строку сохрани в Secret `TG_STRING_SESSION`.

## Ручной запуск

`Actions → Telegram Autopost → Run workflow`

## Группы

Редактируются в `groups.csv`.

`enabled=1` — публиковать.
`enabled=0` — пропускать.

## Текст объявления

Редактируется в `message.txt`.
