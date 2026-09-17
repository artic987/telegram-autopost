import asyncio
import hashlib
import json
import os
import random
import re
import time

from datetime import (
    datetime,
    date,
    timedelta,
    timezone,
)

from pathlib import Path

from telethon import (
    TelegramClient,
    errors,
    functions,
    types,
)

from telethon.sessions import StringSession

from promo_rules import (
    direct_rules_blocked,
    explicit_direct_permission,
    fetch_rule_context,
    medical_promo_blocked,
)


MOSCOW = timezone(
    timedelta(hours=3)
)

DRY_RUN = (
    os.getenv(
        "DRY_RUN",
        "false"
    ).lower()
    in (
        "1",
        "true",
        "yes",
        "on",
    )
)

EVENT_NAME = os.getenv(
    "EVENT_NAME",
    "manual"
)

PAUSE_MIN = float(
    os.getenv(
        "PROMO_PAUSE_MIN",
        "55"
    )
)

PAUSE_MAX = float(
    os.getenv(
        "PROMO_PAUSE_MAX",
        "85"
    )
)

SCHEDULE_START = date(
    2026,
    9,
    18
)

ADMIN_CONTACT = "@addvk39"


CHANNELS = [
    {
        "title": "Атаракс",
        "username": "atarax_info_ru",
        "subject": (
            "гидроксизине, тревоге, сне, "
            "фармакологии и безопасности лекарств"
        ),
    },
    {
        "title": "Бронхолитин",
        "username": "bronholitin_info",
        "subject": (
            "Бронхолитине, кашле, "
            "фармакологии и безопасности лекарств"
        ),
    },
    {
        "title": "Прегабалин",
        "username": "pregabalin_info_ru",
        "subject": (
            "прегабалине, нервной системе, "
            "фармакологии и рисках"
        ),
    },
    {
        "title": "Золофт",
        "username": "zoloft_info_ru",
        "subject": (
            "сертралине, СИОЗС, "
            "психическом здоровье и фармакологии"
        ),
    },
    {
        "title": "Эсциталопрам",
        "username": "escitalopram_info",
        "subject": (
            "эсциталопраме, СИОЗС, "
            "психическом здоровье и фармакологии"
        ),
    },
    {
        "title": "Триттико",
        "username": "trittico_info_ru",
        "subject": (
            "тразодоне, сне, "
            "психическом здоровье и фармакологии"
        ),
    },
    {
        "title": "Фенибут",
        "username": "fenibut_buy",
        "subject": (
            "фенибуте, нервной системе, "
            "фармакологии и рисках применения"
        ),
    },
    {
        "title": "Флуоксетин",
        "username": "fluoxeti",
        "subject": (
            "флуоксетине, СИОЗС, "
            "психическом здоровье и фармакологии"
        ),
    },
]


TEMPLATES = [
    (
        "📚 {title} — информационный канал о {subject}.\n\n"
        "Разбираем механизм действия препаратов, "
        "побочные эффекты и фармакологию простым языком.\n\n"
        "Без схем самолечения и рекламы препаратов.\n"
        "👉 https://t.me/{username}"
    ),

    (
        "💊 Интересует фармакология без сложного "
        "медицинского языка?\n\n"
        "В канале «{title}» публикуем материалы о {subject}: "
        "как работают лекарства и почему возникают "
        "побочные эффекты.\n\n"
        "👉 https://t.me/{username}"
    ),

    (
        "🧠 Канал «{title}» — понятные материалы о {subject}.\n\n"
        "Фармакология, здоровье и разбор распространённых "
        "мифов о лекарствах.\n\n"
        "👉 https://t.me/{username}"
    ),

    (
        "🔬 {title}\n\n"
        "Образовательный Telegram-канал о {subject}. "
        "Короткие разборы лекарств, фармакологии "
        "и побочных эффектов.\n\n"
        "👉 https://t.me/{username}"
    ),

    (
        "📖 Если хочется лучше понимать лекарства, "
        "а не ориентироваться только на отзывы:\n\n"
        "«{title}» — информационный канал о {subject}. "
        "Объясняем сложное простыми словами.\n\n"
        "👉 https://t.me/{username}"
    ),

    (
        "⚕️ «{title}» — информационный проект о {subject}.\n\n"
        "Как лекарства действуют в организме, "
        "почему реакции людей отличаются и как устроена "
        "современная фармакология.\n\n"
        "👉 https://t.me/{username}"
    ),
]


JOIN_COOLDOWN_UNTIL = 0.0


class JoinCooldown(Exception):
    def __init__(
        self,
        seconds
    ):
        self.seconds = max(
            1,
            int(seconds)
        )

        super().__init__(
            f"Join cooldown "
            f"{self.seconds} sec"
        )


class SendCooldown(Exception):
    def __init__(
        self,
        seconds
    ):
        self.seconds = max(
            1,
            int(seconds)
        )

        super().__init__(
            f"Send cooldown "
            f"{self.seconds} sec"
        )


def set_join_cooldown(
    seconds
):
    global JOIN_COOLDOWN_UNTIL

    JOIN_COOLDOWN_UNTIL = max(
        JOIN_COOLDOWN_UNTIL,
        time.monotonic()
        + seconds
    )


def join_cooldown_remaining():
    return max(
        0,
        int(
            JOIN_COOLDOWN_UNTIL
            - time.monotonic()
        )
    )


def clear_join_cooldown():
    global JOIN_COOLDOWN_UNTIL

    JOIN_COOLDOWN_UNTIL = 0.0



def stable_cooldown_days(
    entity
):
    """
    Каждая площадка получает постоянный
    cooldown от 7 до 14 суток.
    """

    digest = hashlib.sha256(
        entity.lower().encode(
            "utf-8"
        )
    ).digest()

    return (
        7
        + digest[0] % 8
    )


def normalize_target(
    item,
    *,
    source="manual"
):
    if isinstance(
        item,
        str
    ):
        entity = item

        return {
            "entity": entity,
            "category": "general",
            "source": source,
            "cooldown_days":
                stable_cooldown_days(
                    entity
                ),
        }


    entity = (
        item.get("entity")
        or item.get("target")
    )

    if not entity:
        return None


    return {
        **item,
        "entity": entity,
        "category": item.get(
            "category",
            "general"
        ),
        "source": item.get(
            "source",
            source
        ),
        "cooldown_days": int(
            item.get(
                "cooldown_days",
                stable_cooldown_days(
                    entity
                )
            )
        ),
    }


def load_targets():
    data = json.loads(
        Path(
            "promo_targets.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    targets = []


    for item in data.get(
        "direct",
        []
    ):
        normalized = normalize_target(
            item,
            source="manual"
        )

        if normalized:
            targets.append(
                normalized
            )


    for item in data.get(
        "auto_discovered_direct",
        []
    ):
        normalized = normalize_target(
            item,
            source="auto_discovery"
        )

        if normalized:
            targets.append(
                normalized
            )


    # Dedupe.
    unique = {}

    for item in targets:
        unique[
            item["entity"].lower()
        ] = item


    targets = list(
        unique.values()
    )


    if not targets:
        raise RuntimeError(
            "Нет direct-площадок"
        )


    # Медицинские approved direct
    # используем первыми.
    targets.sort(
        key=lambda x: (
            0
            if x.get("category")
            == "medical"
            else 1,

            x["entity"].lower()
        )
    )


    return targets


async def rules_still_allow(
    client,
    target_cfg,
    entity
):
    """
    Перед каждой публикацией заново проверяем:
      • описание;
      • закреп;
      • последние сообщения администраторов.

    Для auto-discovery обязательно сохраняется
    явное разрешение прямой рекламы.
    """

    try:
        context = await fetch_rule_context(
            client,
            entity,
            recent_limit=80,
            max_admin_rules=12
        )

    except errors.FloodWaitError:
        raise

    except Exception as exc:
        print(
            "  ✗ не удалось проверить правила:",
            repr(exc)
        )

        # Auto-target без проверки не используем.
        if (
            target_cfg.get(
                "source"
            )
            == "auto_discovery"
        ):
            return False

        return True


    title = (
        getattr(
            entity,
            "title",
            ""
        )
        or ""
    )


    rules_text = "\n\n".join(
        x
        for x in [
            title,
            context["combined"],
        ]
        if x
    )


    print(
        "  rules:",
        "pin="
        + str(
            bool(
                context["pinned"]
            )
        ),
        "admin_rules="
        + str(
            len(
                context["admin_rules"]
            )
        )
    )


    if medical_promo_blocked(
        rules_text
    ):
        print(
            "  ✗ правила запрещают "
            "медицинскую/фармацевтическую тематику"
        )

        return False


    if direct_rules_blocked(
        rules_text
    ):
        print(
            "  ✗ правила запрещают direct-рекламу "
            "или требуют обращения к администратору"
        )

        return False


    if (
        target_cfg.get(
            "source"
        )
        == "auto_discovery"
    ):
        if not explicit_direct_permission(
            rules_text
        ):
            print(
                "  ✗ auto-target больше "
                "не подтверждает разрешение "
                "самостоятельной рекламы"
            )

            return False


    return True


async def last_our_promo_date(
    client,
    entity,
    source_ids
):
    """
    Ищем последние сообщения с нашим
    административным контактом.

    Затем убеждаемся, что отправителем
    был один из наших восьми каналов.
    """

    try:
        async for msg in client.iter_messages(
            entity,
            search=ADMIN_CONTACT,
            limit=50
        ):
            sender_id = getattr(
                msg,
                "sender_id",
                None
            )

            if (
                sender_id
                in source_ids
            ):
                return msg.date

    except Exception as exc:
        print(
            "  ⚠ не удалось проверить "
            "историю:",
            repr(exc)
        )


    return None


async def target_is_due(
    client,
    target_cfg,
    entity,
    source_ids
):
    cooldown = int(
        target_cfg[
            "cooldown_days"
        ]
    )

    last_date = await last_our_promo_date(
        client,
        entity,
        source_ids
    )


    if not last_date:
        print(
            f"  ✓ площадка новая, "
            f"cooldown={cooldown} дней"
        )

        return True


    now = datetime.now(
        timezone.utc
    )

    if (
        last_date.tzinfo
        is None
    ):
        last_date = last_date.replace(
            tzinfo=timezone.utc
        )


    age = now - last_date

    age_days = (
        age.total_seconds()
        / 86400
    )


    if age_days < cooldown:
        left = (
            cooldown
            - age_days
        )

        print(
            f"  ⏳ последний наш пост "
            f"{age_days:.1f} дн. назад; "
            f"cooldown={cooldown}; "
            f"ещё {left:.1f} дн."
        )

        return False


    print(
        f"  ✓ cooldown прошёл: "
        f"{age_days:.1f}/{cooldown} дней"
    )

    return True


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
        + "Связь с администрацией: "
        + ADMIN_CONTACT
    )


async def resolve_source(
    client,
    cfg
):
    return await client.get_entity(
        "@"
        + cfg["username"]
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
            "Цель не является "
            "каналом/супергруппой"
        )

    if not getattr(
        entity,
        "megagroup",
        False
    ):
        raise RuntimeError(
            "Цель не является "
            "супергруппой"
        )

    return entity


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
            "  Send As check:",
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
            and peer.channel_id
            == source.id
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
                    return False

            return True

    return False


async def join_target(
    client,
    entity
):
    """
    True  = вступили именно сейчас.
    False = уже были участником.

    При большом FloodWait дальнейшие
    JoinChannelRequest в этом run блокируются.
    """

    remaining = (
        join_cooldown_remaining()
    )

    if remaining > 0:
        raise JoinCooldown(
            remaining
        )

    for attempt in range(2):
        try:
            await client(
                functions.channels.JoinChannelRequest(
                    entity
                )
            )

            print(
                "  ↪ временно вступили"
            )

            await asyncio.sleep(2)

            return True

        except errors.UserAlreadyParticipantError:
            return False

        except errors.FloodWaitError as exc:
            seconds = int(
                exc.seconds
            )

            set_join_cooldown(
                seconds + 5
            )

            print(
                f"  ⚠ FloodWait на вступление: "
                f"{seconds} сек."
            )

            # Один разумный FloodWait
            # можно спокойно переждать.
            if (
                seconds <= 180
                and attempt == 0
            ):
                print(
                    "  Ждём один раз, "
                    "новые запросы не отправляем..."
                )

                await asyncio.sleep(
                    seconds + 3
                )

                clear_join_cooldown()

                continue

            # Большой FloodWait:
            # никаких следующих JoinChannelRequest.
            raise JoinCooldown(
                seconds
            )

    raise JoinCooldown(
        180
    )


async def leave_if_joined_now(
    client,
    target
):
    try:
        await client(
            functions.channels.LeaveChannelRequest(
                channel=target
            )
        )

        print(
            "  ↩ личный аккаунт "
            "вышел из группы"
        )

    except errors.FloodWaitError as exc:
        seconds = int(
            exc.seconds
        )

        print(
            f"  ⚠ FloodWait при выходе: "
            f"{seconds} сек."
        )

        if seconds <= 120:
            await asyncio.sleep(
                seconds + 2
            )

            try:
                await client(
                    functions.channels.LeaveChannelRequest(
                        channel=target
                    )
                )

                print(
                    "  ↩ вышли после ожидания"
                )

            except Exception as retry_exc:
                print(
                    "  ⚠ повторный выход:",
                    repr(retry_exc)
                )

    except Exception as exc:
        print(
            "  ⚠ выйти из группы "
            "не удалось:",
            repr(exc)
        )


async def publish_one(
    client,
    cfg,
    source,
    target_name,
    text
):
    print()
    print(
        f"{cfg['title']} "
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
                "\n",
                " "
            )[:220]
        )

        return True


    joined_now = False

    try:
        # Сначала без вступления.
        allowed = await can_send_as(
            client,
            target,
            source
        )

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

        # Никакой отправки от личного профиля.
        if not allowed:
            print(
                "  ✗ Send As этого "
                "канала недоступен"
            )

            return False

        try:
            msg = await client.send_message(
                target,
                text,
                link_preview=False,
                send_as=source
            )

        except errors.FloodWaitError as exc:
            seconds = int(
                exc.seconds
            )

            print(
                f"  ⚠ FloodWait send: "
                f"{seconds} сек."
            )

            if seconds > 180:
                raise SendCooldown(
                    seconds
                )

            await asyncio.sleep(
                seconds + 3
            )

            msg = await client.send_message(
                target,
                text,
                link_preview=False,
                send_as=source
            )


        sender_id = getattr(
            msg,
            "sender_id",
            None
        )

        # Дополнительный контроль приватности.
        if (
            sender_id is not None
            and sender_id
            != source.id
        ):
            print(
                "  ⚠ sender_id не совпал "
                "с ID канала"
            )

            try:
                await client.delete_messages(
                    target,
                    [msg.id]
                )

                print(
                    "  ✓ сообщение удалено"
                )

            except Exception:
                pass

            return False


        print(
            f"  ✓ опубликовано "
            f"ОТ ИМЕНИ КАНАЛА "
            f"message_id={msg.id}"
        )

        return True


    except (
        JoinCooldown,
        SendCooldown,
    ):
        raise

    except Exception as exc:
        print(
            "  ✗ ошибка:",
            repr(exc)
        )

        return False

    finally:
        if joined_now:
            await asyncio.sleep(3)

            await leave_if_joined_now(
                client,
                target
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
            "Плановый запуск ещё "
            "не начался."
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


    medical_targets = [
        x
        for x in targets
        if x.get("category")
        == "medical"
    ]

    general_targets = [
        x
        for x in targets
        if x.get("category")
        != "medical"
    ]


    rng = random.Random(
        today.toordinal()
    )

    rng.shuffle(
        medical_targets
    )

    rng.shuffle(
        general_targets
    )


    ordered_targets = (
        medical_targets
        + general_targets
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
        "Площадок:",
        len(targets)
    )

    print(
        "Каналов:",
        len(CHANNELS)
    )

    print(
        "Пауза:",
        f"{PAUSE_MIN:.0f}–"
        f"{PAUSE_MAX:.0f} сек."
    )

    print(
        "====================================="
    )


    successes = []
    failures = []
    deferred = []

    used_targets = set()
    cursor = 0

    stop_due_limit = False


    async with TelegramClient(
        StringSession(
            session
        ),
        api_id,
        api_hash
    ) as client:

        me = await client.get_me()

        # Не печатаем имя аккаунта.
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


        source_ids = {
            entity.id
            for entity in sources.values()
        }


        for channel_index, cfg in enumerate(
            CHANNELS
        ):
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
                cursor
                < len(ordered_targets)
                and attempts < 60
            ):
                target_cfg = (
                    ordered_targets[
                        cursor
                    ]
                )

                cursor += 1

                target_name = (
                    target_cfg[
                        "entity"
                    ]
                )

                if (
                    target_name
                    in used_targets
                ):
                    continue

                attempts += 1


                try:
                    target_entity = (
                        await resolve_target(
                            client,
                            target_name
                        )
                    )


                    if not await rules_still_allow(
                        client,
                        target_cfg,
                        target_entity
                    ):
                        ok = False

                    elif not await target_is_due(
                        client,
                        target_cfg,
                        target_entity,
                        source_ids
                    ):
                        ok = False

                    else:
                        ok = await publish_one(
                            client,
                            cfg,
                            source,
                            target_name,
                            text
                        )

                except JoinCooldown as exc:
                    print()
                    print(
                        "⚠ Telegram ограничил "
                        "новые вступления."
                    )

                    print(
                        f"Осталось примерно "
                        f"{exc.seconds} сек."
                    )

                    print(
                        "Новые JoinChannelRequest "
                        "в этом запуске прекращаем."
                    )

                    deferred.append(
                        cfg["title"]
                    )

                    for rest in CHANNELS[
                        channel_index + 1:
                    ]:
                        deferred.append(
                            rest["title"]
                        )

                    stop_due_limit = True
                    break

                except SendCooldown as exc:
                    print()
                    print(
                        "⚠ Telegram ограничил "
                        "отправку сообщений."
                    )

                    print(
                        f"Осталось примерно "
                        f"{exc.seconds} сек."
                    )

                    deferred.append(
                        cfg["title"]
                    )

                    for rest in CHANNELS[
                        channel_index + 1:
                    ]:
                        deferred.append(
                            rest["title"]
                        )

                    stop_due_limit = True
                    break

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
                            target_name,
                        )
                    )

                    posted = True
                    break


                await asyncio.sleep(5)


            if stop_due_limit:
                break


            if not posted:
                failures.append(
                    cfg["title"]
                )


            # При dry-run длинная пауза не нужна.
            if not DRY_RUN:
                wait = random.uniform(
                    PAUSE_MIN,
                    PAUSE_MAX
                )

                print(
                    f"Пауза перед следующим "
                    f"каналом: {wait:.0f} сек."
                )

                await asyncio.sleep(
                    wait
                )

            else:
                await asyncio.sleep(1)


    print()
    print(
        "=============== ИТОГ ==============="
    )

    for title, target in successes:
        print(
            f"✓ {title:14} "
            f"-> {target}"
        )

    for title in failures:
        print(
            f"✗ {title:14} "
            f"-> не опубликован"
        )

    for title in deferred:
        print(
            f"⏳ {title:14} "
            f"-> отложен из-за FloodWait"
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
            "DRY RUN: сообщений "
            "не отправляли."
        )

    if stop_due_limit:
        print(
            "Запуск завершён корректно: "
            "ограничение Telegram не обходили."
        )

    # Ошибкой считаем только полный
    # провал без FloodWait.
    if (
        not DRY_RUN
        and not successes
        and not stop_due_limit
    ):
        raise RuntimeError(
            "Не удалось опубликовать "
            "ни одного промо-поста"
        )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
