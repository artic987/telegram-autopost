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

# Приоритет тем форума для объявления о пассажирских перевозках.
TOPIC_KEYWORDS = (
    ("объяв", 100),
    ("такси", 95),
    ("межгород", 95),
    ("попут", 90),
    ("пассаж", 85),
    ("поезд", 80),
    ("водител", 75),
    ("трансфер", 70),
    ("заказ", 65),
    ("услуг", 60),
    ("общ", 10),
)


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
        print(f"{prefix}ВСТУПИЛ/УЖЕ СОСТОИМ: {label}")
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


async def get_linked_discussion(client, entity, label, prefix="", join=True):
    """Вернуть связанный discussion-чат для broadcast-канала, если он есть."""
    if not getattr(entity, "broadcast", False):
        return None

    try:
        full = await client(functions.channels.GetFullChannelRequest(entity))
        linked_id = getattr(full.full_chat, "linked_chat_id", None)
        if not linked_id:
            print(f"{prefix}У канала нет связанного discussion-чата: {label}")
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

        if join:
            await join_channel(client, linked, f"{label} → {linked_title}", prefix=prefix)
        return linked
    except errors.FloodWaitError:
        raise
    except Exception as e:
        print(f"{prefix}Не удалось получить связанный чат: {label}: {type(e).__name__}: {e}")
        return None


def topic_score(topic):
    title = (getattr(topic, "title", None) or "").lower()
    score = 0
    for needle, weight in TOPIC_KEYWORDS:
        if needle in title:
            score = max(score, weight)
    # При равном смысловом приоритете предпочитаем более раннюю тему.
    return score


async def choose_open_forum_topic(client, entity, prefix="", verbose=True):
    """Выбрать открытую и тематически подходящую тему форума.

    Возвращает (topic_id, title) или (None, None). Для General id=1; в этом
    случае send_message без reply_to и так попадёт в General.
    """
    if not getattr(entity, "forum", False):
        return None, None

    try:
        result = await client(
            functions.channels.GetForumTopicsRequest(
                channel=entity,
                offset_date=None,
                offset_id=0,
                offset_topic=0,
                limit=100,
            )
        )
    except Exception as e:
        print(f"{prefix}Не удалось получить темы форума: {type(e).__name__}: {e}")
        return None, None

    open_topics = []
    if verbose:
        print(f"{prefix}Форум: найдено тем={len(getattr(result, 'topics', []) or [])}")

    for topic in getattr(result, "topics", []) or []:
        topic_id = getattr(topic, "id", None)
        title = getattr(topic, "title", None) or f"topic {topic_id}"
        closed = bool(getattr(topic, "closed", False))
        hidden = bool(getattr(topic, "hidden", False))
        if verbose:
            print(
                f"{prefix}Тема id={topic_id}: {title}; "
                f"closed={closed}; hidden={hidden}"
            )
        if topic_id is not None and not closed and not hidden:
            open_topics.append(topic)

    if not open_topics:
        print(f"{prefix}Нет открытых тем форума для публикации")
        return None, None

    ranked = sorted(
        open_topics,
        key=lambda t: (topic_score(t), -int(getattr(t, "id", 0) or 0)),
        reverse=True,
    )
    chosen = ranked[0]
    chosen_id = getattr(chosen, "id", None)
    chosen_title = getattr(chosen, "title", None) or f"topic {chosen_id}"
    print(
        f"{prefix}Выбрана открытая тема: {chosen_title} | id={chosen_id} | "
        f"score={topic_score(chosen)}"
    )
    return chosen_id, chosen_title


def message_link(entity, message_id):
    username = getattr(entity, "username", None)
    if username:
        return f"https://t.me/{username}/{message_id}"

    entity_id = getattr(entity, "id", None)
    if entity_id:
        # Для приватных supergroup/discussion Telegram использует /c/<id>/<message>.
        return f"https://t.me/c/{entity_id}/{message_id}"
    return None


async def resolve_post_destination(client, entity, label, prefix=""):
    """Определить реальное место публикации.

    Broadcast-канал сам по себе писать не даст обычному участнику, поэтому
    публикуем в его связанном discussion-чате. Для forum-группы выбираем
    открытую тематическую тему вместо закрытого General.
    """
    post_entity = entity

    if getattr(entity, "broadcast", False):
        linked = await get_linked_discussion(client, entity, label, prefix=prefix, join=True)
        if linked is None:
            print(f"{prefix}ПРОПУСК: broadcast-канал без доступного discussion-чата")
            return None, None, None
        post_entity = linked
        linked_title = getattr(linked, "title", None) or label
        print(f"{prefix}Публикация будет в связанном чате: {linked_title}")

    topic_id, topic_title = await choose_open_forum_topic(client, post_entity, prefix=prefix)
    return post_entity, topic_id, topic_title


async def send_with_topic_fallback(client, post_entity, text, topic_id, prefix=""):
    """Отправить сообщение, а при TOPIC_CLOSED ещё раз выбрать открытую тему."""
    kwargs = {}
    if topic_id and topic_id != 1:
        kwargs["reply_to"] = topic_id

    try:
        return await client.send_message(post_entity, text, **kwargs)
    except errors.BadRequestError as e:
        if "TOPIC_CLOSED" not in str(e).upper():
            raise

        print(f"{prefix}General/выбранная тема закрыта. Ищу другую открытую тему...")
        retry_topic_id, retry_title = await choose_open_forum_topic(
            client, post_entity, prefix=prefix, verbose=True
        )
        if not retry_topic_id:
            raise

        retry_kwargs = {}
        if retry_topic_id != 1:
            retry_kwargs["reply_to"] = retry_topic_id
        print(f"{prefix}Повторная отправка в тему: {retry_title} | id={retry_topic_id}")
        return await client.send_message(post_entity, text, **retry_kwargs)


async def main():
    if RUN_CADENCE not in {"frequent", "daily"}:
        raise RuntimeError(f"Неизвестный RUN_CADENCE: {RUN_CADENCE}")
    if RUN_MODE not in {"post", "join", "inspect"}:
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
                    f"@{real_username if real_username else '-'} | id={real_id} | "
                    f"broadcast={bool(getattr(entity, 'broadcast', False))} | "
                    f"forum={bool(getattr(entity, 'forum', False))}"
                )

                join_result = await join_channel(client, entity, label, prefix=prefix)
                if join_result == "joined":
                    joined += 1
                elif join_result == "requested":
                    requested += 1

                if RUN_MODE == "join":
                    await get_linked_discussion(client, entity, label, prefix=prefix, join=True)
                    await asyncio.sleep(3)
                    continue

                if RUN_MODE == "inspect":
                    inspect_entity = entity
                    if getattr(entity, "broadcast", False):
                        linked = await get_linked_discussion(
                            client, entity, label, prefix=prefix, join=True
                        )
                        if linked is not None:
                            inspect_entity = linked
                    await choose_open_forum_topic(client, inspect_entity, prefix=prefix, verbose=True)
                    continue

                post_entity, topic_id, topic_title = await resolve_post_destination(
                    client, entity, label, prefix=prefix
                )
                if post_entity is None:
                    failed += 1
                    continue

                post_title = getattr(post_entity, "title", None) or label
                if topic_title:
                    print(f"{prefix}Куда пишем: {post_title} → {topic_title}")
                else:
                    print(f"{prefix}Куда пишем: {post_title}")

                msg = await send_with_topic_fallback(
                    client, post_entity, text, topic_id, prefix=prefix
                )
                sent += 1
                print(f"{prefix}Telegram принял сообщение: {label}; message_id={msg.id}")

                await asyncio.sleep(VERIFY_AFTER_SECONDS)
                check = await client.get_messages(post_entity, ids=msg.id)
                if check is None:
                    deleted += 1
                    print(
                        f"{prefix}УДАЛЕНО ПОСЛЕ ОТПРАВКИ: {label}; "
                        "вероятно, сообщение удалил бот/модерация группы"
                    )
                else:
                    verified += 1
                    link = message_link(post_entity, msg.id)
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
    elif RUN_MODE == "inspect":
        print("Диагностика завершена")
    else:
        print(
            f"Итог: Telegram принял={sent}, подтверждено={verified}, "
            f"удалено после отправки={deleted}, пропущено={skipped}, ошибок={failed}"
        )


if __name__ == "__main__":
    asyncio.run(main())
