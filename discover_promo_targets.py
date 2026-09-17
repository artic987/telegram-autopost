import asyncio
import json
import os
import random
import re

from datetime import datetime, timezone
from pathlib import Path

from telethon import (
    TelegramClient,
    functions,
    types,
    errors,
)

from telethon.sessions import StringSession


FILE = Path("promo_targets.json")


SEARCHES = [
    "медицина реклама",
    "медицинский чат реклама",
    "фармацевт чат",
    "фармацевтика реклама",
    "фармацевтический чат",
    "лекарства чат",
    "аптека чат",
    "психология реклама",
    "психотерапия чат",
    "бесплатная реклама",
    "бесплатные объявления",
    "пиар каналов",
    "реклама телеграм каналов",
    "доска объявлений",
]


# ------------------------------------------------------------
# ЯВНО РАЗРЕШЁННАЯ ПРЯМАЯ РЕКЛАМА
# ------------------------------------------------------------

DIRECT_PATTERNS = [
    r"\bбесплатн\w*\s+"
    r"(?:реклам\w*|пиар\w*|объявлен\w*)\b",

    r"\b(?:реклам\w*|пиар\w*|объявлен\w*)"
    r"\s+(?:совершенно\s+|полностью\s+)?"
    r"бесплатн\w*\b",

    r"\b(?:реклам\w*|объявлен\w*)"
    r"\s+разрешен\w*\b",

    r"\bразрешен\w*\s+"
    r"(?:реклам\w*|объявлен\w*|самопиар\w*)\b",

    r"\bможно\s+"
    r"(?:размещать|публиковать|присылать|отправлять)"
    r".{0,60}"
    r"(?:реклам\w*|объявлен\w*|ссылк\w*)",

    r"\bлюб\w*\s+(?:ваш\w*\s+)?реклам\w*"
    r".{0,50}\bбесплатн\w*\b",

    r"\bгрупп\w*\s+для\s+"
    r"(?:бесплатн\w*\s+)?"
    r"(?:реклам\w*|объявлен\w*)\b",
]


# ------------------------------------------------------------
# ЯВНЫЙ ЗАПРЕТ
# ------------------------------------------------------------

BLOCK_PATTERNS = [
    r"\bреклам\w*\s+запрещен\w*\b",
    r"\bзапрещен\w*\s+реклам\w*\b",

    r"\bсамопиар\w*\s+запрещен\w*\b",

    r"\bнесогласованн\w*\s+"
    r"реклам\w*.{0,30}запрещен\w*\b",

    r"\bссылк\w*.{0,20}запрещен\w*\b",

    r"\bавторассылк\w*\s+запрещен\w*\b",
    r"\bзапрещен\w*\s+авторассылк\w*\b",
]


# ------------------------------------------------------------
# ТОЛЬКО ЧЕРЕЗ АДМИНА / ПЛАТНО
#
# \b перед "платн" принципиален:
# "бесплатная" больше не совпадёт с "платная".
# ------------------------------------------------------------

ADMIN_PATTERNS = [
    r"\bпо\s+вопросам\s+реклам\w*\b",

    r"\bпо\s+реклам\w*\s+"
    r"(?:обращ|писат|пишите|сюда)",

    r"\bреклам\w*.{0,35}"
    r"(?:админ\w*|менеджер\w*|бот\w*)",

    r"\b(?:купить|заказать)\s+реклам\w*\b",

    r"\bплатн\w*\s+реклам\w*\b",

    r"\bплатн\w*\s+размещен\w*\b",

    r"\bреклам\w*\s+платн\w*\b",
]


# ------------------------------------------------------------
# МЕДИЦИНСКАЯ ТЕМАТИКА
# "здоровье" само по себе недостаточно.
# ------------------------------------------------------------

MEDICAL_PATTERNS = [
    r"\bмедицин\w*",
    r"\bмедик\w*",
    r"\bврач\w*",
    r"\bдоктор\w*",
    r"\bфармац\w*",
    r"\bфармацевт\w*",
    r"\bпровизор\w*",
    r"\bлекарств\w*",
    r"\bпрепарат\w*",
    r"\bаптек\w*",
    r"\bпсихиатр\w*",
    r"\bпсихотерап\w*",
    r"\bпсихолог\w*",
]


NOT_MEDICAL_PATTERNS = [
    r"\bтаро\b",
    r"\bэзотер\w*",
    r"\bгороскоп\w*",
    r"\bастролог\w*",
    r"\bмагическ\w*",
    r"\bнумеролог\w*",
    r"\bгадани\w*",
]


def normal(text):
    return (
        text
        or ""
    ).lower().replace(
        "ё",
        "е"
    )


def matches(
    text,
    patterns
):
    text = normal(text)

    found = []

    for pattern in patterns:
        if re.search(
            pattern,
            text,
            flags=re.I | re.S
        ):
            found.append(
                pattern
            )

    return found


def is_medical(
    title,
    about
):
    combined = (
        normal(title)
        + "\n"
        + normal(about)
    )

    if matches(
        combined,
        NOT_MEDICAL_PATTERNS
    ):
        return False

    return bool(
        matches(
            combined,
            MEDICAL_PATTERNS
        )
    )


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
    blocked = 0


    async with TelegramClient(
        StringSession(session),
        api_id,
        api_hash
    ) as client:

        client.flood_sleep_threshold = 30


        for query in SEARCHES:
            print()
            print(
                "SEARCH:",
                query
            )

            try:
                result = await client(
                    functions.contacts.SearchRequest(
                        q=query,
                        limit=50
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

                about = await about_for(
                    client,
                    entity
                )


                combined = (
                    title
                    + "\n"
                    + about
                )


                direct_match = matches(
                    combined,
                    DIRECT_PATTERNS
                )

                blocked_match = matches(
                    combined,
                    BLOCK_PATTERNS
                )

                admin_match = matches(
                    combined,
                    ADMIN_PATTERNS
                )


                category = (
                    "medical"
                    if is_medical(
                        title,
                        about
                    )
                    else "general"
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
                }


                # --------------------------------------------
                # ЯВНЫЙ ЗАПРЕТ:
                # вообще не сохраняем как рекламную цель.
                # --------------------------------------------

                if blocked_match:
                    blocked += 1

                    print(
                        "  BLOCKED:",
                        handle
                    )

                    continue


                # --------------------------------------------
                # РЕКЛАМА ЧЕРЕЗ АДМИНА
                # --------------------------------------------

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
                        "  ADMIN ONLY:",
                        handle,
                        "|",
                        category
                    )

                    continue


                # --------------------------------------------
                # ЯВНО РАЗРЕШЕНА ПРЯМАЯ РЕКЛАМА
                # --------------------------------------------

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
                        "  ✓ AUTO DIRECT:",
                        handle,
                        "|",
                        category
                    )

                    continue


                # --------------------------------------------
                # ВСЁ ОСТАЛЬНОЕ НЕ АВТОПУБЛИКУЕМ.
                # --------------------------------------------

                review.append(
                    item
                )

                known.add(
                    key
                )

                added_review += 1

                print(
                    "  REVIEW:",
                    handle,
                    "|",
                    category
                )


                await asyncio.sleep(
                    random.uniform(
                        0.7,
                        1.5
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
        "===================================="
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
        "BLOCKED:",
        blocked
    )

    print(
        "Всего AUTO DIRECT:",
        len(auto_direct)
    )

    print(
        "===================================="
    )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
