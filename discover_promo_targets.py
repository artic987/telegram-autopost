import asyncio
import json
import os
import random

from datetime import (
    datetime,
    timezone,
)

from pathlib import Path

from telethon import (
    TelegramClient,
    functions,
    types,
    errors,
)

from telethon.sessions import StringSession

from promo_rules import (
    ADMIN_ONLY_PATTERNS,
    BLOCK_PATTERNS,
    DIRECT_PATTERNS,
    category_for,
    direct_rules_blocked,
    fetch_rule_context,
    matches,
    medical_promo_blocked,
)


FILE = Path(
    "promo_targets.json"
)


SEARCHES = [
    # Медицина / фарма
    "медицина реклама",
    "медицинский чат реклама",
    "медицина пиар",
    "фармацевт чат",
    "фармацевтика реклама",
    "фармацевтический чат",
    "лекарства чат",
    "аптека чат",
    "психология реклама",
    "психотерапия чат",

    # Таро / эзотерика — ТЕПЕРЬ ПОДХОДИТ
    "таро реклама",
    "таро пиар",
    "таро чат реклама",
    "тарологи реклама",
    "эзотерика реклама",
    "эзотерика пиар",
    "гадание реклама",
    "гадания чат",

    # Общие доски
    "бесплатная реклама",
    "бесплатные объявления",
    "пиар каналов",
    "реклама телеграм каналов",
    "доска объявлений",
]


MAX_INSPECTED_PER_RUN = 70
MAX_NEW_PER_QUERY = 12


def entity_of(item):
    if isinstance(
        item,
        str
    ):
        return item.lower()

    if isinstance(
        item,
        dict
    ):
        return str(
            item.get(
                "entity",
                item.get(
                    "target",
                    ""
                )
            )
        ).lower()

    return ""


async def main():
    api_id = int(
        os.environ["TG_API_ID"]
    )

    api_hash = os.environ[
        "TG_API_HASH"
    ]

    session = os.environ[
        "TG_STRING_SESSION"
    ]


    data = json.loads(
        FILE.read_text(
            encoding="utf-8"
        )
    )


    direct = data.setdefault(
        "direct",
        []
    )

    auto_direct = data.setdefault(
        "auto_discovered_direct",
        []
    )

    admin_only = data.setdefault(
        "admin_only",
        []
    )

    review = data.setdefault(
        "needs_review",
        []
    )

    disabled = data.setdefault(
        "disabled",
        []
    )


    known = set()

    for section in (
        direct,
        auto_direct,
        admin_only,
        review,
        disabled,
    ):
        for item in section:
            key = entity_of(
                item
            )

            if key:
                known.add(
                    key
                )


    added_direct = 0
    added_admin = 0
    added_review = 0
    added_disabled = 0

    category_stats = {
        "medical": 0,
        "esoteric": 0,
        "general": 0,
    }

    inspected = 0
    stop_search = False


    async with TelegramClient(
        StringSession(session),
        api_id,
        api_hash
    ) as client:

        client.flood_sleep_threshold = 30


        for query in SEARCHES:
            if stop_search:
                break

            print()
            print(
                "SEARCH:",
                query
            )


            try:
                result = await client(
                    functions.contacts.SearchRequest(
                        q=query,
                        limit=40
                    )
                )

            except errors.FloodWaitError as exc:
                print(
                    "FloodWait discovery:",
                    exc.seconds
                )

                break

            except Exception as exc:
                print(
                    "Search error:",
                    repr(exc)
                )

                continue


            per_query = 0


            for entity in result.chats:

                if (
                    inspected
                    >= MAX_INSPECTED_PER_RUN
                ):
                    print(
                        "Достигнут дневной лимит "
                        "анализа площадок:",
                        MAX_INSPECTED_PER_RUN
                    )

                    stop_search = True
                    break


                if (
                    per_query
                    >= MAX_NEW_PER_QUERY
                ):
                    break


                if not isinstance(
                    entity,
                    types.Channel
                ):
                    continue


                if not getattr(
                    entity,
                    "megagroup",
                    False
                ):
                    continue


                username = getattr(
                    entity,
                    "username",
                    None
                )

                if not username:
                    continue


                handle = (
                    "@"
                    + username
                )

                key = handle.lower()


                if key in known:
                    continue


                title = (
                    getattr(
                        entity,
                        "title",
                        ""
                    )
                    or ""
                )


                print(
                    "  INSPECT:",
                    handle
                )


                try:
                    context = await fetch_rule_context(
                        client,
                        entity,
                        recent_limit=80,
                        max_admin_rules=12
                    )

                except errors.FloodWaitError as exc:
                    print(
                        "FloodWait rules:",
                        exc.seconds
                    )

                    stop_search = True
                    break

                except Exception as exc:
                    print(
                        "    rules error:",
                        repr(exc)
                    )

                    continue


                inspected += 1
                per_query += 1


                about = context[
                    "about"
                ]

                pinned = context[
                    "pinned"
                ]

                admin_rules = context[
                    "admin_rules"
                ]


                # Название тоже учитываем:
                # некоторые группы прямо называются
                # "Бесплатная реклама".
                rules_text = "\n\n".join(
                    x
                    for x in [
                        title,
                        context["combined"],
                    ]
                    if x
                )


                category = category_for(
                    title,
                    about,
                    pinned,
                    admin_rules
                )


                category_stats[
                    category
                ] = (
                    category_stats.get(
                        category,
                        0
                    )
                    + 1
                )


                direct_match = matches(
                    rules_text,
                    DIRECT_PATTERNS
                )

                block_match = matches(
                    rules_text,
                    BLOCK_PATTERNS
                )

                admin_match = matches(
                    rules_text,
                    ADMIN_ONLY_PATTERNS
                )


                item = {
                    "entity": handle,
                    "title": title,
                    "category": category,
                    "source": "auto_discovery",
                    "discovered_at":
                        datetime.now(
                            timezone.utc
                        ).isoformat(),
                    "search_query": query,

                    "about_excerpt":
                        about[:700],

                    "pinned_excerpt":
                        pinned[:900],

                    "admin_rules_excerpt":
                        [
                            text[:500]
                            for text
                            in admin_rules[:6]
                        ],

                    "rules_checked": True,
                }


                # =================================================
                # СПЕЦИФИЧЕСКИ ЗАПРЕЩЕНА НАША ТЕМАТИКА
                # =================================================

                if medical_promo_blocked(
                    rules_text
                ):
                    item[
                        "reason"
                    ] = (
                        "rules prohibit medical/"
                        "pharma promotion"
                    )

                    disabled.append(
                        item
                    )

                    known.add(
                        key
                    )

                    added_disabled += 1

                    print(
                        "    ✗ MEDICAL BLOCK:",
                        handle
                    )

                    continue


                # =================================================
                # ОБЩИЙ ЗАПРЕТ
                # =================================================

                if block_match:
                    item[
                        "reason"
                    ] = (
                        "advertising/link rules "
                        "block direct promotion"
                    )

                    disabled.append(
                        item
                    )

                    known.add(
                        key
                    )

                    added_disabled += 1

                    print(
                        "    ✗ BLOCKED:",
                        handle
                    )

                    continue


                # =================================================
                # ПРОТИВОРЕЧИЕ:
                # "бесплатно", но также "по рекламе к админу".
                # Самостоятельно не решаем.
                # =================================================

                if (
                    direct_match
                    and admin_match
                ):
                    item[
                        "reason"
                    ] = (
                        "conflicting direct/admin rules"
                    )

                    review.append(
                        item
                    )

                    known.add(
                        key
                    )

                    added_review += 1

                    print(
                        "    ? REVIEW CONFLICT:",
                        handle,
                        "|",
                        category
                    )

                    continue


                # =================================================
                # ТОЛЬКО ЧЕРЕЗ АДМИНА
                # =================================================

                if admin_match:
                    item[
                        "permission_type"
                    ] = "admin_only"

                    admin_only.append(
                        item
                    )

                    known.add(
                        key
                    )

                    added_admin += 1

                    print(
                        "    ADMIN ONLY:",
                        handle,
                        "|",
                        category
                    )

                    continue


                # =================================================
                # ЯВНОЕ РАЗРЕШЕНИЕ DIRECT
                # =================================================

                if direct_match:
                    item[
                        "permission_type"
                    ] = "direct"

                    item[
                        "permission_evidence"
                    ] = direct_match[0]

                    auto_direct.append(
                        item
                    )

                    known.add(
                        key
                    )

                    added_direct += 1

                    print(
                        "    ✓ AUTO DIRECT:",
                        handle,
                        "|",
                        category,
                        "| pin=",
                        bool(pinned),
                        "| admin_rules=",
                        len(admin_rules)
                    )

                    continue


                # =================================================
                # НЕТ ДОСТАТОЧНО ЯВНЫХ ПРАВИЛ
                # =================================================

                item[
                    "reason"
                ] = (
                    "no explicit direct advertising permission"
                )

                review.append(
                    item
                )

                known.add(
                    key
                )

                added_review += 1

                print(
                    "    REVIEW:",
                    handle,
                    "|",
                    category
                )


                await asyncio.sleep(
                    random.uniform(
                        0.8,
                        1.6
                    )
                )


            await asyncio.sleep(
                random.uniform(
                    3,
                    6
                )
            )


    FILE.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        )
        + "\n",
        encoding="utf-8"
    )


    print()
    print(
        "========================================"
    )

    print(
        "Проверено новых площадок:",
        inspected
    )

    print(
        "Новых AUTO DIRECT:",
        added_direct
    )

    print(
        "Новых ADMIN ONLY:",
        added_admin
    )

    print(
        "Новых REVIEW:",
        added_review
    )

    print(
        "Новых DISABLED:",
        added_disabled
    )

    print(
        "Категории проверенных:",
        category_stats
    )

    print(
        "Всего AUTO DIRECT:",
        len(auto_direct)
    )

    print(
        "========================================"
    )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
