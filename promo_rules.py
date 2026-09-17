import re

from telethon import (
    functions,
    types,
    utils,
)


# ============================================================
# ПРИЗНАКИ ЯВНО РАЗРЕШЁННОЙ РЕКЛАМЫ
# ============================================================

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

    r"\bсамопиар\w*\s+разрешен\w*\b",

    r"\bможно\s+"
    r"(?:размещать|публиковать|присылать|отправлять)"
    r".{0,80}"
    r"(?:реклам\w*|объявлен\w*|ссылк\w*|канал\w*)",

    r"\bлюб\w*\s+(?:ваш\w*\s+)?реклам\w*"
    r".{0,60}\bбесплатн\w*\b",

    r"\bгрупп\w*\s+для\s+"
    r"(?:бесплатн\w*\s+)?"
    r"(?:реклам\w*|объявлен\w*|пиар\w*)\b",
]


# ============================================================
# ОБЩИЙ ЗАПРЕТ РЕКЛАМЫ / ССЫЛОК
# ============================================================

BLOCK_PATTERNS = [
    r"\bреклам\w*\s+запрещен\w*\b",
    r"\bзапрещен\w*\s+реклам\w*\b",

    r"\bсамопиар\w*\s+запрещен\w*\b",
    r"\bзапрещен\w*\s+самопиар\w*\b",

    r"\bнесогласованн\w*\s+"
    r"реклам\w*.{0,40}запрещен\w*\b",

    r"\bссылк\w*.{0,35}запрещен\w*\b",
    r"\bзапрещен\w*.{0,35}ссылк\w*\b",

    r"\bвнешн\w*\s+ссылк\w*.{0,35}"
    r"(?:запрещ|нельзя|удаля)\w*",

    r"\bавторассылк\w*\s+запрещен\w*\b",
    r"\bзапрещен\w*\s+авторассылк\w*\b",

    r"\bспам\w*.{0,20}запрещен\w*\b",
]


# ============================================================
# РЕКЛАМА ТОЛЬКО ЧЕРЕЗ АДМИНА / ПЛАТНО
# ============================================================

ADMIN_ONLY_PATTERNS = [
    r"\bпо\s+вопросам\s+реклам\w*\b",

    r"\bпо\s+реклам\w*\s+"
    r"(?:обращ|писат|пишите|сюда)",

    r"\bреклам\w*.{0,40}"
    r"(?:админ\w*|менеджер\w*|бот\w*)",

    r"\b(?:купить|заказать)\s+реклам\w*\b",

    r"\bплатн\w*\s+реклам\w*\b",

    r"\bплатн\w*\s+размещен\w*\b",

    r"\bреклам\w*\s+платн\w*\b",
]


# ============================================================
# СПЕЦИАЛЬНЫЙ ЗАПРЕТ ДЛЯ НАШЕЙ ТЕМАТИКИ
#
# Если площадка допускает обычную рекламу, но запрещает
# лекарства/фармацевтику/медицинские услуги, туда наши
# медицинские каналы автоматически не отправляем.
# ============================================================

MEDICAL_PROMO_BLOCK_PATTERNS = [
    r"(?:лекарств\w*|препарат\w*|фармац\w*|фармацевт\w*|"
    r"аптек\w*|медицин\w*|психотроп\w*|рецептур\w*|"
    r"бад\w*|наркот\w*)"
    r".{0,70}"
    r"(?:запрещ\w*|нельзя|не\s+размещ\w*|"
    r"не\s+публик\w*|не\s+реклам\w*)",

    r"(?:запрещ\w*|нельзя|не\s+размещ\w*|"
    r"не\s+публик\w*|не\s+реклам\w*)"
    r".{0,70}"
    r"(?:лекарств\w*|препарат\w*|фармац\w*|фармацевт\w*|"
    r"аптек\w*|медицин\w*|психотроп\w*|рецептур\w*|"
    r"бад\w*|наркот\w*)",

    r"\bникак\w*\s+"
    r"(?:лекарств\w*|медицин\w*|фармац\w*|аптек\w*)",

    r"\bмедицинск\w*\s+реклам\w*"
    r".{0,40}"
    r"(?:запрещ\w*|нельзя)",
]


# ============================================================
# КАТЕГОРИИ
# ============================================================

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


ESOTERIC_PATTERNS = [
    r"\bтаро\b",
    r"\bэзотер\w*",
    r"\bгороскоп\w*",
    r"\bастролог\w*",
    r"\bмагическ\w*",
    r"\bнумеролог\w*",
    r"\bгадани\w*",
    r"\bтаролог\w*",
]


# ============================================================
# КАКИЕ СООБЩЕНИЯ АДМИНОВ СЧИТАТЬ ПОХОЖИМИ НА ПРАВИЛА
# ============================================================

RULE_HINT_PATTERNS = [
    r"\bправил\w*",
    r"\bреклам\w*",
    r"\bпиар\w*",
    r"\bсамопиар\w*",
    r"\bобъявлен\w*",
    r"\bссылк\w*",
    r"\bзапрещ\w*",
    r"\bнельзя\b",
    r"\bможно\b",
    r"\bспам\w*",
    r"\bадмин\w*",
    r"\bмодератор\w*",
    r"\bлекарств\w*",
    r"\bпрепарат\w*",
    r"\bфармац\w*",
    r"\bаптек\w*",
    r"\bмедицин\w*",
    r"\bпсихотроп\w*",
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

    result = []

    for pattern in patterns:
        if re.search(
            pattern,
            text,
            flags=re.I | re.S
        ):
            result.append(
                pattern
            )

    return result


def has_match(
    text,
    patterns
):
    return bool(
        matches(
            text,
            patterns
        )
    )


def explicit_direct_permission(
    text
):
    return (
        has_match(
            text,
            DIRECT_PATTERNS
        )
        and not direct_rules_blocked(
            text
        )
        and not medical_promo_blocked(
            text
        )
    )


def direct_rules_blocked(
    text
):
    return (
        has_match(
            text,
            BLOCK_PATTERNS
        )
        or has_match(
            text,
            ADMIN_ONLY_PATTERNS
        )
    )


def medical_promo_blocked(
    text
):
    return has_match(
        text,
        MEDICAL_PROMO_BLOCK_PATTERNS
    )


def category_for(
    title,
    about="",
    pinned="",
    admin_rules=None
):
    admin_rules = (
        admin_rules
        or []
    )

    combined = "\n".join(
        [
            title or "",
            about or "",
            pinned or "",
            *admin_rules,
        ]
    )


    # Таро/эзотерика теперь ПОДХОДИТ.
    # Просто выделяем её в отдельную категорию.
    if has_match(
        combined,
        ESOTERIC_PATTERNS
    ):
        return "esoteric"


    if has_match(
        combined,
        MEDICAL_PATTERNS
    ):
        return "medical"


    return "general"


async def fetch_rule_context(
    client,
    entity,
    recent_limit=80,
    max_admin_rules=12
):
    """
    Собирает:
      • about;
      • закреп;
      • последние сообщения администраторов,
        похожие на правила.

    Обычные сообщения участников не используются
    для определения правил.
    """

    about = ""
    pinned = ""
    admin_rules = []

    full = None


    # --------------------------------------------------------
    # ABOUT + PINNED ID
    # --------------------------------------------------------

    try:
        full = await client(
            functions.channels.GetFullChannelRequest(
                channel=entity
            )
        )

        about = (
            full.full_chat.about
            or ""
        )

    except Exception as exc:
        print(
            "    ⚠ full channel:",
            type(exc).__name__
        )


    pinned_id = None

    if full is not None:
        pinned_id = getattr(
            full.full_chat,
            "pinned_msg_id",
            None
        )


    # --------------------------------------------------------
    # ЗАКРЕП
    # --------------------------------------------------------

    if pinned_id:
        try:
            msg = await client.get_messages(
                entity,
                ids=pinned_id
            )

            if msg:
                pinned = (
                    msg.raw_text
                    or ""
                ).strip()

        except Exception as exc:
            print(
                "    ⚠ pinned:",
                type(exc).__name__
            )


    # --------------------------------------------------------
    # ID АДМИНИСТРАТОРОВ
    # --------------------------------------------------------

    admin_ids = set()

    try:
        admin_ids.add(
            utils.get_peer_id(
                entity
            )
        )
    except Exception:
        pass

    try:
        admin_ids.add(
            entity.id
        )
    except Exception:
        pass


    try:
        result = await client(
            functions.channels.GetParticipantsRequest(
                channel=entity,
                filter=types.ChannelParticipantsAdmins(),
                offset=0,
                limit=100,
                hash=0
            )
        )

        for participant in (
            result.participants
            or []
        ):
            user_id = getattr(
                participant,
                "user_id",
                None
            )

            if user_id:
                admin_ids.add(
                    user_id
                )

        for user in (
            result.users
            or []
        ):
            user_id = getattr(
                user,
                "id",
                None
            )

            if user_id:
                admin_ids.add(
                    user_id
                )

    except Exception as exc:
        # Для некоторых публичных групп список
        # админов получить нельзя. Закреп всё равно
        # остаётся доступным.
        print(
            "    ⚠ admin list:",
            type(exc).__name__
        )


    # --------------------------------------------------------
    # ПОСЛЕДНИЕ СООБЩЕНИЯ АДМИНОВ
    # --------------------------------------------------------

    seen = set()

    try:
        async for msg in client.iter_messages(
            entity,
            limit=recent_limit
        ):
            text = (
                msg.raw_text
                or ""
            ).strip()

            if not text:
                continue


            sender_id = getattr(
                msg,
                "sender_id",
                None
            )

            post_author = getattr(
                msg,
                "post_author",
                None
            )


            admin_like = (
                sender_id in admin_ids
                or bool(post_author)
            )


            if not admin_like:
                continue


            if not has_match(
                text,
                RULE_HINT_PATTERNS
            ):
                continue


            key = normal(text)

            if key in seen:
                continue

            seen.add(
                key
            )

            admin_rules.append(
                text
            )


            if (
                len(admin_rules)
                >= max_admin_rules
            ):
                break

    except Exception as exc:
        print(
            "    ⚠ admin messages:",
            type(exc).__name__
        )


    combined_parts = [
        about.strip(),
        pinned.strip(),
        *[
            x.strip()
            for x in admin_rules
            if x.strip()
        ],
    ]


    combined = "\n\n".join(
        x
        for x in combined_parts
        if x
    )


    return {
        "about": about,
        "pinned": pinned,
        "admin_rules": admin_rules,
        "combined": combined,
        "pinned_id": pinned_id,
    }
