import asyncio
import csv
import os
import random
from pathlib import Path

from telethon import TelegramClient, errors, functions
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
RUN_CADENCE = os.getenv("RUN_CADENCE", "daily").strip().lower()
RUN_MODE = os.getenv("RUN_MODE", "post").strip().lower()
RUN_ATTEMPT = int(os.getenv("GITHUB_RUN_ATTEMPT", "1"))
TARGET_ENTITIES = {
    item.strip().lower()
    for item in os.getenv("TARGET_ENTITIES", "").split(",")
    if item.strip()
}


def load_groups(cadence):
    groups = []
    with GROUPS_CSV.open("r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            enabled = (row.get("enabled") or "").strip().lower()
            if enabled not in {"1", "true", "yes", "да", "y"}:
                continue

            row_cadence = (row.get("cadence") or "daily").strip().lower()
            if row_cadence != cadence:
                continue

            entity = (row.get("entity") or "").strip()
            title = (row.get("title") or "").strip()
            if not entity:
                continue

            if TARGET_ENTITIES and entity.lower() not in TARGET_ENTITIES:
                continue

            groups.append((entity, title))
    return groups


async def join_channel(client, entity, label, prefix=""):
    try:
        await client(functions.channels.JoinChannelRequest(entity))
        print(f"{prefix}ВСТУПИЛ: {label}")
        return "joined"
    except errors.UserAlreadyParticipantError:
        print(f"{prefix}УЖЕ СОСТОИМ: {label}")
        return "already"
    except errors.InviteRequestSentError:
        print(f"{prefix}ЗАЯВКА НА ВСТУПЛЕНИЕ ОТПРАВЛЕНА: {label}; ждём одобрения администратора")
        return "requested"
    except errors.FloodWaitError:
        raise
    except Exception as e:
        print(f"{prefix}НЕ УДАЛОСЬ ВСТУПИТЬ: {label}: {type(e).__name__}: {e}")
        return "failed"


async def try_join_linked_discussion(client, entity, label, prefix=""):
    if not getattr(entity, "broadcast", False):
        return None

    try:
        full = await client(functions.channels.GetFullChannelRequest(entity))
        linked_id = getattr(full.full_chat, "linked_chat_id", None)
        if not linked_id:
            return None

        linked = next(
            (chat for chat in full.chats if getattr(chat, "id", None) == linked_id),
            None,
        )
        if linked is None:
            print(f"{prefix}Есть связанный чат id={linked_id}, но Telegram не вернул его объект")
            return None

        linked_title = getattr(linked, "title", None) or f"discussion {linked_id}"
        linked_username = getattr(linked, "username", None)
        print(
            f"{prefix}Связанный чат: {linked_title} | "
            f"@{linked_username if linked_username else '-'} | id={linked_id}"
        )
        await join_channel(client, linked, f"{label} → {linked_title}", prefix=prefix)
        return linked
    except errors.FloodWaitError:
        raise
    except Exception as e:
        print(f"{prefix}Не удалось проверить связанный чат: {label}: {type(e).__name__}: {e}")
        return None


async def main():
    if RUN_CADENCE not in {"frequent", "daily"}:
        raise RuntimeError(f"Неизвестный RUN_CADENCE: {RUN_CADENCE}")
    if RUN_MODE not in {"post", "join"}:
        raise RuntimeError(f"Неизвестный RUN_MODE: {RUN_MODE}")

    # Повторный rerun ежедневной публикации не должен дублировать посты.
    if RUN_MODE == "post" and RUN_CADENCE == "daily" and RUN_ATTEMPT > 1:
        print(f"Daily-запуск, attempt={RUN_ATTEMPT}: повторная отправка отключена.")
        return

    text = ""
    if RUN_MODE == "post":
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
    print(f"Режим: {RUN_MODE}; периодичность: {RUN_CADENCE}")
    if TARGET_ENTITIES:
        print(f"Точечный запуск: {len(TARGET_ENTITIES)} целей")
    print(f"Групп: {len(groups)}")

    sent = 0
    verified = 0
    deleted = 0
    skipped = 0
    failed = 0
    joined = 0
    requested = 0

    try:
        for i, (target, title) in enumerate(groups, start=1):
            label = title or target
            prefix = f"[{i}/{len(groups)}] "

            try:
                entity = await client.get_entity(target)
                real_title = getattr(entity, "title", None) or label
                real_username = getattr(entity, "username", None)
                real_id = getattr(entity, "id", None)
                print(
                    f"{prefix}Цель: {real_title} | "
                    f"@{real_username if real_username else '-'} | id={real_id}"
                )

                join_result = await join_channel(client, entity, label, prefix=prefix)
                if join_result == "joined":
                    joined += 1
                elif join_result == "requested":
                    requested += 1

                # Для каналов дополнительно вступаем в связанный discussion-чат, если он есть.
                await try_join_linked_discussion(client, entity, label, prefix=prefix)

                if RUN_MODE == "join":
                    await asyncio.sleep(3)
                    continue

                msg = await client.send_message(entity, text)
                sent += 1
                print(f"{prefix}Telegram принял сообщение: {label}; message_id={msg.id}")

                await asyncio.sleep(VERIFY_AFTER_SECONDS)
                check = await client.get_messages(entity, ids=msg.id)
                if check is None:
                    deleted += 1
                    print(
                        f"{prefix}УДАЛЕНО ПОСЛЕ ОТПРАВКИ: {label}; "
                        "вероятно, сообщение удалил бот/модерация группы"
                    )
                else:
                    verified += 1
                    link = None
                    if real_username:
                        link = f"https://t.me/{real_username}/{msg.id}"
                    print(
                        f"{prefix}ПОДТВЕРЖДЕНО: сообщение всё ещё существует"
                        + (f" | {link}" if link else "")
                    )

            except errors.SlowModeWaitError as e:
                skipped += 1
                print(
                    f"{prefix}SLOW MODE: {label}; ждать ещё {e.seconds} сек. "
                    "Пропускаю до следующего запуска."
                )

            except errors.FloodWaitError as e:
                print(f"{prefix}FLOOD WAIT: Telegram требует ждать {e.seconds} сек.")
                print("Останавливаю текущий круг.")
                break

            except (
                errors.ChatWriteForbiddenError,
                errors.UserBannedInChannelError,
                errors.ChannelPrivateError,
            ) as e:
                failed += 1
                print(f"{prefix}Нельзя писать: {label} ({type(e).__name__})")

            except Exception as e:
                failed += 1
                print(f"{prefix}Ошибка: {label}: {type(e).__name__}: {e}")

            if RUN_MODE == "post" and i < len(groups):
                delay = random.randint(DELAY_MIN, DELAY_MAX)
                print(f"Пауза {delay} сек.")
                await asyncio.sleep(delay)

    finally:
        await client.disconnect()

    if RUN_MODE == "join":
        print(f"Итог вступления: новых={joined}, заявок={requested}, ошибок={failed}")
    else:
        print(
            f"Итог: Telegram принял={sent}, подтверждено={verified}, "
            f"удалено после отправки={deleted}, пропущено={skipped}, ошибок={failed}"
        )


if __name__ == "__main__":
    asyncio.run(main())
