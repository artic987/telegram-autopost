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


FILE = Path(
    "promo_targets.json"
)


SEARCHES = [
    (
        "медицина реклама",
        "medical"
    ),
    (
        "фармацевт чат",
        "medical"
    ),
    (
        "фармацевтика реклама",
        "medical"
    ),
    (
        "психология реклама",
        "medical"
    ),
    (
        "здоровье реклама",
        "medical"
    ),
    (
        "бесплатная реклама",
        "general"
    ),
    (
        "пиар каналов",
        "general"
    ),
    (
        "доска объявлений",
        "general"
    ),
]


POSITIVE = (
    "реклама разрешена",
    "разрешена реклама",
    "бесплатная реклама",
    "реклама бесплатно",
    "можно размещать рекламу",
    "можно размещать объявления",
    "объявления разрешены",
    "разрешены объявления",
    "пиар разрешен",
    "пиар разрешён",
    "самопиар разрешен",
    "самопиар разрешён",
)


NEGATIVE = (
    "реклама запрещена",
    "запрещена реклама",
    "без рекламы",
    "авторассылка запрещена",
    "запрещена авторассылка",
)


ADMIN_ONLY = (
    "по рекламе",
    "по вопросам рекламы",
    "купить рекламу",
    "покупка рекламы",
    "платная реклама",
    "реклама платная",
)


def entity_of(
    item
):
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


def matched(
    text,
    phrases
):
    low = (
        text
        or ""
    ).lower()

    return [
        phrase
        for phrase in phrases
        if phrase in low
    ]


async def about_for(
    client,
    entity
):
    try:
        full = await client(
            functions.channels.GetFullChannelRequest(
                channel=entity
            )
        )

        return (
            full.full_chat.about
            or ""
        )

    except Exception:
        return ""


async def main():
    api_id = int(
        os.environ[
            "TG_API_ID"
        ]
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
            entity = entity_of(
                item
            )

            if entity:
                known.add(
                    entity
                )


    added_direct = 0
    added_admin = 0
    added_review = 0


    async with TelegramClient(
        StringSession(
            session
        ),
        api_id,
        api_hash
    ) as client:

        # Не даём Telethon самому долго спать.
        client.flood_sleep_threshold = 30


        for query, category in SEARCHES:
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

                # Не обходим лимит.
                break

            except Exception as exc:
                print(
                    "Search error:",
                    repr(exc)
                )

                continue


            for entity in result.chats:
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
                    # В обычный broadcast-канал
                    # пользователь сам писать не может.
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


                about = await about_for(
                    client,
                    entity
                )


                pos = matched(
                    about,
                    POSITIVE
                )

                neg = matched(
                    about,
                    NEGATIVE
                )

                admin = matched(
                    about,
                    ADMIN_ONLY
                )


                item = {
                    "entity": handle,
                    "title": (
                        getattr(
                            entity,
                            "title",
                            ""
                        )
                        or ""
                    ),
                    "category": category,
                    "source": "auto_discovery",
                    "discovered_at":
                        datetime.now(
                            timezone.utc
                        ).isoformat(),
                    "search_query": query,
                    "about_excerpt":
                        about[:500],
                }


                if (
                    pos
                    and not neg
                    and not admin
                ):
                    item[
                        "permission_evidence"
                    ] = pos[0]

                    auto_direct.append(
                        item
                    )

                    known.add(
                        key
                    )

                    added_direct += 1

                    print(
                        "  ✓ AUTO DIRECT:",
                        handle,
                        "|",
                        pos[0]
                    )


                elif admin:
                    item[
                        "permission_evidence"
                    ] = admin[0]

                    admin_only.append(
                        item
                    )

                    known.add(
                        key
                    )

                    added_admin += 1

                    print(
                        "  ADMIN ONLY:",
                        handle
                    )


                elif not neg:
                    review.append(
                        item
                    )

                    known.add(
                        key
                    )

                    added_review += 1

                    print(
                        "  REVIEW:",
                        handle
                    )


                await asyncio.sleep(
                    random.uniform(
                        0.8,
                        1.7
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
        "=============================="
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
        "Всего auto direct:",
        len(auto_direct)
    )

    print(
        "=============================="
    )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
