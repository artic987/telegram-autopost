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
VERIFY_AFTER_SECONDS = int(os.getenv("VERIFY_AFTER_SECONDS", "5"))
RUN_CADENCE = os.getenv("RUN_CADENCE", "frequent").strip().lower()
RUN_ATTEMPT = int(os.getenv("GITHUB_RUN_ATTEMPT", "1"))


def load_groups(cadence):
    groups = []
    with GROUPS_CSV.open("r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            enabled = (row.get("enabled") or "").strip().lower()
            if enabled not in {"1", "true", "yes", "да", "y"}:
                continue

            row_cadence = (row.get("cadence") or "frequent").strip().lower()
            if row_cadence != cadence:
                continue

            entity = (row.get("entity") or "").strip()
            title = (row.get("title") or "").strip()
            if entity:
                groups.append((entity, title))
    return groups


async def main():
    if RUN_CADENCE not in {"frequent", "daily"}:
        raise RuntimeError(f"Неизвестный RUN_CADENCE: {RUN_CADENCE}")

    # Защита от повторной отправки daily-групп при ручном rerun того же GitHub Actions run.
    if RUN_CADENCE == "daily" and RUN_ATTEMPT > 1:
        print(f"Daily-запуск, attempt={RUN_ATTEMPT}: повторная отправка отключена.")
        return

    text = MESSAGE_FILE.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError("message.txt пустой")

    groups = load_groups(RUN_CADENCE)
    if not groups:
        print(f"Для режима {RUN_CADENCE} включённых групп нет.")
        return

    client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        raise RuntimeError("TG_STRING_SESSION не авторизована")

    me = await client.get_me()
    print(f"Аккаунт: @{me.username or me.id}")
    print(f"Режим: {RUN_CADENCE}")
    print(f"Групп в этом круге: {len(groups)}")

    sent = 0
    verified = 0
    deleted = 0
    skipped = 0
    failed = 0

    try:
        for i, (target, title) in enumerate(groups, start=1):
            label = title or target

            try:
                entity = await client.get_entity(target)
                real_title = getattr(entity, "title", None) or label
                real_username = getattr(entity, "username", None)
                real_id = getattr(entity, "id", None)
                print(
                    f"[{i}/{len(groups)}] Цель: {real_title} | "
                    f"@{real_username if real_username else '-'} | id={real_id}"
                )

                msg = await client.send_message(entity, text)
                sent += 1
                print(f"[{i}/{len(groups)}] Telegram принял сообщение: {label}; message_id={msg.id}")

                await asyncio.sleep(VERIFY_AFTER_SECONDS)
                check = await client.get_messages(entity, ids=msg.id)
                if check is None:
                    deleted += 1
                    print(
                        f"[{i}/{len(groups)}] УДАЛЕНО ПОСЛЕ ОТПРАВКИ: {label}; "
                        "вероятно, сообщение удалил бот/модерация группы"
                    )
                else:
                    verified += 1
                    link = None
                    if real_username:
                        link = f"https://t.me/{real_username}/{msg.id}"
                    print(
                        f"[{i}/{len(groups)}] ПОДТВЕРЖДЕНО: сообщение всё ещё существует"
                        + (f" | {link}" if link else "")
                    )

            except errors.SlowModeWaitError as e:
                skipped += 1
                print(
                    f"[{i}/{len(groups)}] SLOW MODE: {label}; ждать ещё {e.seconds} сек. "
                    "Пропускаю до следующего запуска."
                )

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

    print(
        f"Итог: Telegram принял={sent}, подтверждено={verified}, "
        f"удалено после отправки={deleted}, пропущено={skipped}, ошибок={failed}"
    )


if __name__ == "__main__":
    asyncio.run(main())
