import asyncio
import csv
import os
import random
from pathlib import Path

from telethon import TelegramClient, errors
from telethon.sessions import StringSession

BASE_DIR = Path(__file__).resolve().parent
GROUPS_CSV = BASE_DIR / "groups.csv"
MESSAGE_FILE = BASE_DIR / "message.txt"

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
STRING_SESSION = os.environ["TG_STRING_SESSION"]

DELAY_MIN = int(os.getenv("DELAY_MIN_SECONDS", "45"))
DELAY_MAX = int(os.getenv("DELAY_MAX_SECONDS", "75"))


def load_groups():
    groups = []
    with GROUPS_CSV.open("r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            enabled = (row.get("enabled") or "").strip().lower()
            if enabled not in {"1", "true", "yes", "да", "y"}:
                continue
            entity = (row.get("entity") or "").strip()
            title = (row.get("title") or "").strip()
            if entity:
                groups.append((entity, title))
    return groups


async def main():
    text = MESSAGE_FILE.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError("message.txt пустой")

    groups = load_groups()
    if not groups:
        raise RuntimeError("В groups.csv нет включённых групп")

    client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        raise RuntimeError("TG_STRING_SESSION не авторизована")

    me = await client.get_me()
    print(f"Аккаунт: @{me.username or me.id}")
    print(f"Групп в этом круге: {len(groups)}")

    sent = 0
    skipped = 0
    failed = 0

    try:
        for i, (target, title) in enumerate(groups, start=1):
            label = title or target

            try:
                await client.send_message(target, text)
                sent += 1
                print(f"[{i}/{len(groups)}] OK: {label}")

            except errors.SlowModeWaitError as e:
                skipped += 1
                print(f"[{i}/{len(groups)}] SLOW MODE: {label}; ждать ещё {e.seconds} сек. Пропускаю до следующего запуска.")

            except errors.FloodWaitError as e:
                print(f"[{i}/{len(groups)}] FLOOD WAIT: Telegram требует ждать {e.seconds} сек.")
                print("Останавливаю текущий круг.")
                break

            except (
                errors.ChatWriteForbiddenError,
                errors.UserBannedInChannelError,
                errors.ChannelPrivateError,
            ) as e:
                failed += 1
                print(f"[{i}/{len(groups)}] Нельзя писать: {label} ({type(e).__name__})")

            except Exception as e:
                failed += 1
                print(f"[{i}/{len(groups)}] Ошибка: {label}: {type(e).__name__}: {e}")

            if i < len(groups):
                delay = random.randint(DELAY_MIN, DELAY_MAX)
                print(f"Пауза {delay} сек.")
                await asyncio.sleep(delay)

    finally:
        await client.disconnect()

    print(f"Итог: успешно={sent}, пропущено={skipped}, ошибок={failed}")


if __name__ == "__main__":
    asyncio.run(main())
