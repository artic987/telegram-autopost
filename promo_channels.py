import asyncio
import json
import os
import random
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

from telethon import TelegramClient, errors, functions, types
from telethon.sessions import StringSession


MOSCOW = timezone(
    timedelta(hours=3)
)

DRY_RUN = (
    os.getenv("DRY_RUN", "false")
    .lower()
    in ("1", "true", "yes", "on")
)

EVENT_NAME = os.getenv(
    "EVENT_NAME",
    "manual"
)

# Расписание начинаем с 18.09.
SCHEDULE_START = date(
    2026,
    9,
    18
)


CHANNELS = [
    {
        "title": "Атаракс",
        "username": "atarax_info_ru",
        "subject": (
            "гидроксизине, тревоге, сне, "
            "фармакологии и безопасности лекарств"
        )
    },

    {
        "title": "Бронхолитин",
        "username": "bronholitin_info",
        "subject": (
            "Бронхолитине, кашле, "
            "фармакологии и безопасном применении лекарств"
        )
    },

    {
        "title": "Прегабалин",
        "username": "pregabalin_info_ru",
        "subject": (
            "прегабалине, нервной системе, "
            "нейропатической боли, фармакологии и рисках"
        )
    },

    {
        "title": "Золофт",
        "username": "zoloft_info_ru",
        "subject": (
            "сертралине, СИОЗС, "
            "психическом здоровье и фармакологии"
        )
    },

    {
        "title": "Эсциталопрам",
        "username": "escitalopram_info",
        "subject": (
            "эсциталопраме, СИОЗС, "
            "психическом здоровье и фармакологии"
        )
    },

    {
        "title": "Триттико",
        "username": "trittico_info_ru",
        "subject": (
            "тразодоне, сне, "
            "психическом здоровье и фармакологии"
        )
    },

    {
        "title": "Фенибут",
        "username": "fenibut_buy",
        "subject": (
            "фенибуте, нервной системе, "
            "фармакологии и рисках применения"
        )
    },

    {
        "title": "Флуоксетин",
        "username": "fluoxeti",
        "subject": (
            "флуоксетине, СИОЗС, "
            "психическом здоровье и фармакологии"
        )
    },
]


TEMPLATES = [
    (
        "📚 {title} — информационный канал о {subject}.\n\n"
        "Разбираем механизм действия препаратов, "
        "побочные эффекты, психологическое здоровье "
        "и работу лекарств простым языком.\n\n"
        "Без схем самолечения и рекламы препаратов.\n"
        "👉 https://t.me/{username}"
    ),

    (
        "💊 Интересует фармакология без сложного медицинского языка?\n\n"
        "В канале «{title}» публикуем материалы о {subject}: "
        "как работают лекарства, почему возникают побочные эффекты "
        "и что известно о психическом здоровье.\n\n"
        "👉 https://t.me/{username}"
    ),

    (
        "🧠 Канал «{title}» — понятные материалы о {subject}.\n\n"
        "Фармакология, психическое здоровье, "
        "работа аптек и разбор распространённых мифов "
        "о лекарствах.\n\n"
        "👉 https://t.me/{username}"
    ),

    (
        "🔬 {title}\n\n"
        "Образовательный Telegram-канал о {subject}. "
        "Короткие разборы лекарств, фармакологии, "
        "побочных эффектов и современных представлений "
        "о психическом здоровье.\n\n"
        "https://t.me/{username}"
    ),

    (
        "📖 Если хочется лучше понимать лекарства, "
        "а не ориентироваться только на отзывы в интернете:\n\n"
        "«{title}» — канал о {subject}. "
        "Объясняем сложные темы простыми словами.\n\n"
        "👉 https://t.me/{username}"
    ),

    (
        "⚕️ «{title}» — информационный проект о {subject}.\n\n"
        "Что происходит с лекарством в организме, "
        "как работают рецепторы, почему реакции людей отличаются "
        "и как устроена современная фармакология.\n\n"
        "👉 https://t.me/{username}"
    ),
]


def load_targets():
    data = json.loads(
        Path("promo_targets.json")
        .read_text(
            encoding="utf-8"
        )
    )

    targets = data["direct"]

    if len(targets) < 8:
        raise RuntimeError(
            "Нужно минимум 8 рекламных площадок"
        )

    return targets


def build_text(
    cfg,
    day_index
):
    template = TEMPLATES[
        (
            day_index
            + CHANNELS.index(cfg)
        )
        % len(TEMPLATES)
    ]

    text = template.format(
        **cfg
    )

    return (
        text
        + "\n\n"
        + "Связь с администрацией: @addvk39"
    )


async def join_target(
    client,
    entity
):
    """
    Возвращает True, если аккаунт
    вступил в группу именно сейчас.
    """

    try:
        await client(
            functions.channels.JoinChannelRequest(
                entity
            )
        )

        print(
            "  ↪ временно вступили "
            "для проверки Send As"
        )

        await asyncio.sleep(2)

        return True

    except errors.UserAlreadyParticipantError:
        return False

    except errors.FloodWaitError as exc:
        if exc.seconds <= 180:
            print(
                f"  FloodWait join: "
                f"{exc.seconds} сек."
            )

            await asyncio.sleep(
                exc.seconds + 2
            )

            await client(
                functions.channels.JoinChannelRequest(
                    entity
                )
            )

            return True

        raise


async def can_send_as(
    client,
    target,
    source
):
    try:
        result = await client(
            functions.channels.GetSendAsRequest(
                peer=target
            )
        )

    except Exception as exc:
        print(
            "  Не удалось получить send_as:",
            repr(exc)
        )

        return False

    for item in result.peers:
        peer = item.peer

        if (
            isinstance(
                peer,
                types.PeerChannel
            )
            and peer.channel_id == source.id
        ):
            if getattr(
                item,
                "premium_required",
                False
            ):
                me = await client.get_me()

                if not getattr(
                    me,
                    "premium",
                    False
                ):
                    print(
                        "  Для Send As требуется Premium"
                    )

                    return False

            return True

    return False


async def resolve_source(
    client,
    cfg
):
    return await client.get_entity(
        "@" + cfg["username"]
    )


async def resolve_target(
    client,
    username
):
    entity = await client.get_entity(
        username
    )

    if not isinstance(
        entity,
        types.Channel
    ):
        raise RuntimeError(
            "Цель не является каналом/супергруппой"
        )

    if not getattr(
        entity,
        "megagroup",
        False
    ):
        raise RuntimeError(
            "Цель не является группой для сообщений"
        )

    return entity


async def publish_one(
    client,
    cfg,
    source,
    target_name,
    text
):
    print(
        f"\\n{cfg['title']} "
        f"→ {target_name}"
    )

    target = await resolve_target(
        client,
        target_name
    )

    if DRY_RUN:
        print(
            "  ✓ цель существует"
        )

        print(
            "  PREVIEW:",
            text.replace(
                "\\n",
                " "
            )[:220]
        )

        return True


    joined_now = False

    try:
        # ----------------------------------------------------
        # Сначала пробуем Send As БЕЗ нового вступления.
        # Это лучший вариант для приватности.
        # ----------------------------------------------------

        allowed = await can_send_as(
            client,
            target,
            source
        )

        # ----------------------------------------------------
        # Если Telegram не позволяет Send As без членства,
        # временно вступаем и проверяем ещё раз.
        # ----------------------------------------------------

        if not allowed:
            joined_now = await join_target(
                client,
                target
            )

            allowed = await can_send_as(
                client,
                target,
                source
            )

        # ----------------------------------------------------
        # НИКАКОГО FALLBACK НА ЛИЧНЫЙ АККАУНТ.
        # Если каналом писать нельзя — пропускаем площадку.
        # ----------------------------------------------------

        if not allowed:
            print(
                "  ✗ Send As этого канала "
                "недоступен"
            )

            return False


        # ----------------------------------------------------
        # Публикация ТОЛЬКО от имени канала.
        # ----------------------------------------------------

        try:
            msg = await client.send_message(
                target,
                text,
                link_preview=False,
                send_as=source
            )

        except errors.FloodWaitError as exc:
            if exc.seconds > 180:
                raise

            print(
                f"  FloodWait send: "
                f"{exc.seconds} сек."
            )

            await asyncio.sleep(
                exc.seconds + 2
            )

            msg = await client.send_message(
                target,
                text,
                link_preview=False,
                send_as=source
            )


        # ----------------------------------------------------
        # Дополнительная проверка:
        # Telegram должен считать отправителем именно канал.
        # ----------------------------------------------------

        sender_id = getattr(
            msg,
            "sender_id",
            None
        )

        if (
            sender_id is not None
            and sender_id != source.id
        ):
            print(
                "  ⚠ ВНИМАНИЕ: sender_id "
                "не совпал с ID канала"
            )

            try:
                await client.delete_messages(
                    target,
                    [msg.id]
                )

                print(
                    "  ✓ подозрительное сообщение удалено"
                )

            except Exception:
                pass

            return False


        print(
            f"  ✓ опубликовано ОТ ИМЕНИ КАНАЛА "
            f"message_id={msg.id}"
        )

        return True


    except Exception as exc:
        print(
            "  ✗ ошибка:",
            repr(exc)
        )

        return False


    finally:
        # ----------------------------------------------------
        # Если личный аккаунт вступил только ради этой
        # публикации — после неё пытаемся уйти.
        #
        # Это уменьшает публичное присутствие аккаунта,
        # но не гарантирует сокрытие от администраторов.
        # ----------------------------------------------------

        if joined_now:
            try:
                await asyncio.sleep(3)

                await client(
                    functions.channels.LeaveChannelRequest(
                        channel=target
                    )
                )

                print(
                    "  ↩ личный аккаунт "
                    "вышел из группы"
                )

            except Exception as exc:
                print(
                    "  ⚠ выйти из группы "
                    "не удалось:",
                    repr(exc)
                )


async def main():
    today = datetime.now(
        MOSCOW
    ).date()

    if (
        EVENT_NAME == "schedule"
        and today < SCHEDULE_START
    ):
        print(
            "Плановый запуск ещё не начался."
        )

        return

    targets = load_targets()

    day_index = (
        today
        - date(
            2026,
            9,
            17
        )
    ).days

    if day_index < 0:
        day_index = 0

    # Каждый день смещаемся сразу на 8 площадок.
    # При 36 целях одна площадка повторяется
    # примерно раз в 4–5 дней.
    start = (
        day_index * len(CHANNELS)
    ) % len(targets)

    ordered_targets = (
        targets[start:]
        + targets[:start]
    )

    api_id = int(
        os.environ["TG_API_ID"]
    )

    api_hash = os.environ[
        "TG_API_HASH"
    ]

    session = os.environ[
        "TG_STRING_SESSION"
    ]

    print(
        "====================================="
    )

    print(
        "PROMO DATE:",
        today
    )

    print(
        "DRY_RUN:",
        DRY_RUN
    )

    print(
        "Площадок в базе:",
        len(targets)
    )

    print(
        "Нужно публикаций:",
        len(CHANNELS)
    )

    print(
        "====================================="
    )

    successes = []
    failures = []
    used_targets = set()
    cursor = 0

    async with TelegramClient(
        StringSession(
            session
        ),
        api_id,
        api_hash
    ) as client:

        me = await client.get_me()

        print(
            "Telegram session:",
            me.id
        )

        sources = {}

        for cfg in CHANNELS:
            sources[
                cfg["username"]
            ] = await resolve_source(
                client,
                cfg
            )

        for cfg in CHANNELS:
            source = sources[
                cfg["username"]
            ]

            text = build_text(
                cfg,
                day_index
            )

            posted = False
            attempts = 0

            while (
                cursor < len(
                    ordered_targets
                )
                and attempts < 12
            ):
                target_name = (
                    ordered_targets[
                        cursor
                    ]
                )

                cursor += 1

                if target_name in used_targets:
                    continue

                attempts += 1

                try:
                    ok = await publish_one(
                        client,
                        cfg,
                        source,
                        target_name,
                        text
                    )

                except Exception as exc:
                    print(
                        "  ✗ target failed:",
                        repr(exc)
                    )

                    ok = False

                if ok:
                    used_targets.add(
                        target_name
                    )

                    successes.append(
                        (
                            cfg["title"],
                            target_name
                        )
                    )

                    posted = True
                    break

                await asyncio.sleep(
                    4
                )

            if not posted:
                failures.append(
                    cfg["title"]
                )

            # Не строчим мгновенной очередью.
            await asyncio.sleep(
                random.uniform(
                    8,
                    14
                )
            )

    print()
    print(
        "=============== ИТОГ ==============="
    )

    for title, target in successes:
        print(
            f"✓ {title:14} -> {target}"
        )

    for title in failures:
        print(
            f"✗ {title:14} -> не найден "
            f"доступный target"
        )

    print(
        "====================================="
    )

    print(
        "Успешно:",
        len(successes),
        "/",
        len(CHANNELS)
    )

    if DRY_RUN:
        print(
            "DRY RUN: сообщений не отправляли."
        )

    # Частичный успех не валит ежедневный cron.
    # Полный провал считаем ошибкой.
    if not DRY_RUN and not successes:
        raise RuntimeError(
            "Не удалось опубликовать ни одного промо-поста"
        )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
