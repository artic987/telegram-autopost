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

    return template.format(
        **cfg
    )


async def join_target(
    client,
    entity
):
    try:
        await client(
            functions.channels.JoinChannelRequest(
                entity
            )
        )

        await asyncio.sleep(
            2
        )

    except errors.UserAlreadyParticipantError:
        pass

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

        else:
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
        f"\n{cfg['title']} "
        f"→ {target_name}"
    )

    target = await resolve_target(
        client,
        target_name
    )

    if DRY_RUN:
        print(
            "  ✓ цель найдена"
        )

        print(
            "  PREVIEW:",
            text.replace(
                "\n",
                " "
            )[:180]
        )

        return True

    await join_target(
        client,
        target
    )

    allowed = await can_send_as(
        client,
        target,
        source
    )

    if not allowed:
        print(
            "  ✗ этот канал нельзя использовать "
            "как Send As здесь"
        )

        return False

    try:
        msg = await client.send_message(
            target,
            text,
            link_preview=False,
            send_as=source
        )

        print(
            f"  ✓ опубликовано "
            f"message_id={msg.id}"
        )

        return True

    except errors.FloodWaitError as exc:
        if exc.seconds <= 180:
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

            print(
                f"  ✓ опубликовано после ожидания "
                f"message_id={msg.id}"
            )

            return True

        raise

    except Exception as exc:
        print(
            "  ✗ ошибка отправки:",
            repr(exc)
        )

        return False


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
            "Telegram account:",
            me.id,
            "Premium:",
            getattr(
                me,
                "premium",
                False
            )
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
