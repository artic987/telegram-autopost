import asyncio
import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

from telethon import TelegramClient, types
from telethon.sessions import StringSession


MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

DRY_RUN = (
    os.getenv("DRY_RUN", "false").lower()
    in ("1", "true", "yes", "on")
)

EVENT_NAME = os.getenv(
    "EVENT_NAME",
    "manual"
)

MOSCOW = timezone(
    timedelta(hours=3)
)

# Первый настоящий день публикаций.
BASE_DATE = date(
    2026,
    9,
    18
)


CHANNELS = [
    {
        "title": "Атаракс",
        "drug": "Атаракс (гидроксизин)",
        "usernames": [
            "atarax_info_ru",
            "atarax_ru_info",
            "atarax_channel_ru",
            "atarax_simple",
        ],
    },

    {
        "title": "Бронхолитин",
        "drug": "Бронхолитин",
        "usernames": [
            "bronholitin_info",
            "bronholitin_ru",
            "bronholitin_channel",
            "bronholitin_simple",
        ],
    },

    {
        "title": "Прегабалин",
        "drug": "прегабалин",
        "usernames": [
            "pregabalin_info_ru",
            "pregabalin_ru_info",
            "pregabalin_channel",
            "pregabalin_simple",
        ],
    },

    {
        "title": "Золофт",
        "drug": "Золофт (сертралин)",
        "usernames": [
            "zoloft_info_ru",
            "zoloft_ru_info",
            "zoloft_channel_ru",
            "zoloft_simple",
        ],
    },

    {
        "title": "Эсциталопрам",
        "drug": "эсциталопрам",
        "usernames": [
            "escitalopram_info",
            "escitalopram_ru",
            "escitalopram_channel",
            "escitalopram_simple",
        ],
    },

    {
        "title": "Триттико",
        "drug": "Триттико (тразодон)",
        "usernames": [
            "trittico_info_ru",
            "trittico_ru",
            "trittico_channel",
            "trittico_simple",
        ],
    },

    {
        "title": "Фенибут",
        "drug": "фенибут",
        "usernames": [
            "fenibut_buy",
        ],
    },

    {
        "title": "Флуоксетин",
        "drug": "флуоксетин",
        "usernames": [
            "fluoxeti",
        ],
    },
]


CATEGORIES = [
    {
        "name": "сам препарат",
        "ideas": [
            "как работает препарат простыми словами",
            "история появления препарата",
            "к какому фармакологическому классу он относится",
            "почему люди по-разному реагируют на один препарат",
            "что такое период полувыведения",
            "почему возникают побочные эффекты",
            "что такое лекарственное взаимодействие",
            "миф о препарате и разбор этого мифа",
            "почему отзывы других людей нельзя переносить на себя",
            "почему важен индивидуальный подбор лечения",
        ],
    },

    {
        "name": "психическое здоровье",
        "ideas": [
            "как тревога проявляется физически",
            "почему хронический стресс влияет на организм",
            "сон и психическое здоровье",
            "тревога и усталость",
            "психотерапия и фармакотерапия",
            "почему психические симптомы не сводятся к силе воли",
            "почему люди откладывают обращение за помощью",
            "что такое навязчивые мысли",
            "как режим влияет на эмоциональное состояние",
            "почему самодиагностика бывает ошибочной",
        ],
    },

    {
        "name": "фармакология",
        "ideas": [
            "что такое рецептор",
            "что такое нейромедиатор",
            "как лекарство всасывается",
            "как печень перерабатывает лекарства",
            "как организм выводит препараты",
            "что такое биодоступность",
            "что такое фармакокинетика",
            "что такое фармакодинамика",
            "чем побочный эффект отличается от аллергии",
            "что такое активный метаболит",
            "зачем нужны клинические исследования",
            "как оценивают пользу и риск лекарства",
        ],
    },

    {
        "name": "аптеки и фармацевтика",
        "ideas": [
            "чем занимается фармацевт",
            "как лекарства хранят в аптеке",
            "почему важна температура хранения",
            "зачем лекарствам срок годности",
            "что происходит с просроченными лекарствами",
            "что такое дженерик",
            "бренд и действующее вещество",
            "как читать инструкцию к лекарству",
            "как устроена упаковка лекарства",
            "почему одинаковые лекарства выглядят по-разному",
            "что такое серия лекарственного препарата",
            "что такое фармаконадзор",
        ],
    },
]


def normalized_words(text):
    return set(
        re.findall(
            r"[а-яёa-z0-9]{5,}",
            text.lower()
        )
    )


def current_cycle():
    today = datetime.now(
        MOSCOW
    ).date()

    delta = (
        today - BASE_DATE
    ).days

    return today, delta


def should_publish_today():
    today, delta = current_cycle()

    # Ручной запуск разрешаем всегда.
    if EVENT_NAME == "workflow_dispatch":
        return True

    if delta < 0:
        return False

    return delta % 2 == 0


def choose_category(
    channel_index
):
    today, delta = current_cycle()

    if delta < 0:
        cycle = 0
    else:
        cycle = (
            delta // 2
        )

    return CATEGORIES[
        (
            cycle
            + channel_index
        )
        % len(CATEGORIES)
    ]


async def find_channel(
    client,
    cfg
):
    for username in cfg["usernames"]:
        try:
            entity = await client.get_entity(
                "@" + username
            )

            if isinstance(
                entity,
                types.Channel
            ):
                print(
                    f"✓ {cfg['title']}: "
                    f"@{username}"
                )

                return entity

        except Exception:
            pass

    async for dialog in client.iter_dialogs():
        entity = dialog.entity

        if (
            dialog.name == cfg["title"]
            and isinstance(
                entity,
                types.Channel
            )
            and getattr(
                entity,
                "broadcast",
                False
            )
        ):
            print(
                f"✓ {cfg['title']}: "
                "найден по названию"
            )

            return entity

    raise RuntimeError(
        f"Канал {cfg['title']} "
        "не найден"
    )


async def recent_posts(
    client,
    channel
):
    result = []

    async for msg in client.iter_messages(
        channel,
        limit=30
    ):
        text = (
            msg.message
            or ""
        ).strip()

        if text:
            result.append(
                text[:1800]
            )

    return result


def choose_idea(
    category,
    recent
):
    used = normalized_words(
        "\n".join(recent)
    )

    scored = []

    for idea in category["ideas"]:
        idea_words = normalized_words(
            idea
        )

        score = len(
            idea_words & used
        )

        scored.append(
            (
                score,
                random.random(),
                idea
            )
        )

    scored.sort()

    best = scored[0][0]

    candidates = [
        item[2]
        for item in scored
        if item[0] == best
    ]

    return random.choice(
        candidates
    )


def prompt_for(
    cfg,
    category,
    idea,
    recent
):
    history = "\n\n---\n\n".join(
        recent[:15]
    )

    special = ""

    if cfg["title"] in (
        "Прегабалин",
        "Бронхолитин",
        "Фенибут",
    ):
        special = """
Не описывай рекреационное употребление,
способы получения эйфории, усиления действия,
опасные комбинации ради эффекта,
обход ограничений или получение препарата
в обход законных правил.
"""

    return f"""
Ты редактор русскоязычного образовательного
Telegram-канала.

Канал:
{cfg["title"]}

Основная тема:
{cfg["drug"]}

Сегодняшняя рубрика:
{category["name"]}

Конкретная тема:
{idea}

Создай ОДИН новый Telegram-пост.

Формат:

— 700–1200 знаков;
— короткий интересный заголовок;
— 3–6 небольших абзацев;
— простой современный русский язык;
— полезный информационный материал;
— несколько уместных эмодзи допустимы;
— 2–4 хэштега в конце;
— не повторяй последние публикации.

Тематика канала может включать:

— сам препарат;
— фармакологию;
— психическое здоровье;
— устройство аптек;
— профессию фармацевта;
— лекарственные исследования;
— безопасность лекарств.

Если пост не непосредственно про препарат,
не нужно искусственно вставлять его название
в каждый абзац.

Нельзя:

— рекламировать продажу;
— писать цены;
— сообщать наличие;
— предлагать купить;
— рекламировать доставку;
— назначать лечение;
— давать персональные рекомендации;
— давать дозировки;
— составлять схемы приёма;
— объяснять повышение доз;
— описывать опасные сочетания как инструкцию;
— придумывать исследования или статистику;
— придумывать юридический статус препарата.

Если речь идёт о тяжёлой побочной реакции,
зависимости, выраженной отмене,
суицидальных мыслях или другом опасном состоянии,
укажи на необходимость медицинской помощи.

{special}

Последние публикации канала:

{history if history else "(публикаций мало)"}

Верни только готовый текст поста.
""".strip()


def clean(text):
    text = text.strip()

    for marker in (
        "```markdown",
        "```text",
        "```",
    ):
        text = text.replace(
            marker,
            ""
        )

    text = text.strip()

    if len(text) > 3900:
        text = (
            text[:3890]
            .rsplit(
                "\n",
                1
            )[0]
            .rstrip()
            + "…"
        )

    return text


def generate(
    prompt
):
    key = os.environ[
        "GROQ_API_KEY"
    ]

    payload = json.dumps(
        {
            "model": MODEL,

            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты редактор образовательных "
                        "Telegram-каналов о фармакологии, "
                        "психическом здоровье и аптеках."
                    ),
                },

                {
                    "role": "user",
                    "content": prompt,
                },
            ],

            "temperature": 0.82,

            "max_completion_tokens": 1000,
        },
        ensure_ascii=False,
    ).encode(
        "utf-8"
    )

    for attempt in range(
        1,
        6
    ):
        request = urllib.request.Request(
            GROQ_URL,

            data=payload,

            method="POST",

            headers={
                "Authorization":
                    f"Bearer {key}",

                "Content-Type":
                    "application/json",

                "User-Agent":
                    "telegram-autopost/1.0",
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=150
            ) as response:

                result = json.loads(
                    response
                    .read()
                    .decode(
                        "utf-8"
                    )
                )

            text = (
                result["choices"][0]
                ["message"]["content"]
                .strip()
            )

            if not text:
                if attempt < 5:
                    wait = attempt * 15

                    print(
                        f"Groq вернул пустой ответ, "
                        f"повтор через {wait} сек."
                    )

                    time.sleep(wait)
                    continue

                raise RuntimeError(
                    "Groq 5 раз вернул пустой ответ"
                )

            return clean(
                text
            )

        except urllib.error.HTTPError as exc:
            body = (
                exc.read()
                .decode(
                    "utf-8",
                    errors="replace"
                )
            )

            if (
                exc.code == 429
                or exc.code >= 500
            ) and attempt < 5:

                wait = (
                    attempt * 20
                )

                print(
                    f"Groq HTTP "
                    f"{exc.code}, "
                    f"повтор через "
                    f"{wait} сек."
                )

                time.sleep(
                    wait
                )

                continue

            raise RuntimeError(
                f"Groq HTTP "
                f"{exc.code}: "
                f"{body}"
            ) from exc

    raise RuntimeError(
        "Groq не ответил"
    )


async def posted_today(
    client,
    channel,
    today
):
    async for msg in client.iter_messages(
        channel,
        limit=20
    ):
        if not msg.date:
            continue

        local_date = (
            msg.date
            .astimezone(
                MOSCOW
            )
            .date()
        )

        if local_date == today:
            return True

        if local_date < today:
            return False

    return False


async def process_channel(
    client,
    cfg,
    index,
    today
):
    print()
    print(
        "=" * 60
    )

    print(
        f"{index + 1}/"
        f"{len(CHANNELS)} "
        f"{cfg['title']}"
    )

    print(
        "=" * 60
    )

    channel = await find_channel(
        client,
        cfg
    )

    # При реальной публикации не создаём
    # второй пост в этом канале в тот же день.
    if not DRY_RUN:
        if await posted_today(
            client,
            channel,
            today
        ):
            print(
                "↷ Сегодня уже есть публикация. "
                "Пропускаю."
            )

            return "skip"

    recent = await recent_posts(
        client,
        channel
    )

    category = choose_category(
        index
    )

    idea = choose_idea(
        category,
        recent
    )

    print(
        "Рубрика:",
        category["name"]
    )

    print(
        "Тема:",
        idea
    )

    post = await asyncio.to_thread(
        generate,
        prompt_for(
            cfg,
            category,
            idea,
            recent
        )
    )

    print()
    print(
        "----- PREVIEW -----"
    )

    print(
        post
    )

    print(
        "-------------------"
    )

    if DRY_RUN:
        print(
            "✓ DRY RUN — "
            "не опубликовано"
        )

        return "preview"

    msg = await client.send_message(
        channel,
        post,
        link_preview=False
    )

    print(
        f"✓ ОПУБЛИКОВАНО "
        f"message_id={msg.id}"
    )

    return "published"


async def main():
    today, delta = current_cycle()

    print(
        "========================================"
    )

    print(
        "Дата МСК:",
        today
    )

    print(
        "Дней от старта:",
        delta
    )

    print(
        "EVENT:",
        EVENT_NAME
    )

    print(
        "DRY_RUN:",
        DRY_RUN
    )

    print(
        "========================================"
    )

    if not should_publish_today():
        print(
            "Сегодня день без публикаций."
        )

        print(
            "Следующий цикл — завтра."
        )

        return

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

    results = []
    failures = []

    async with TelegramClient(
        StringSession(
            session
        ),
        api_id,
        api_hash
    ) as client:

        me = await client.get_me()

        print(
            "Telegram:",
            me.id
        )

        for index, cfg in enumerate(
            CHANNELS
        ):
            try:
                result = await process_channel(
                    client,
                    cfg,
                    index,
                    today
                )

                results.append(
                    (
                        cfg["title"],
                        result
                    )
                )

            except Exception as exc:
                failures.append(
                    (
                        cfg["title"],
                        repr(exc)
                    )
                )

                print(
                    f"✗ Ошибка "
                    f"{cfg['title']}: "
                    f"{repr(exc)}"
                )

            await asyncio.sleep(
                10
            )

    print()
    print(
        "============== ИТОГ =============="
    )

    for title, status in results:
        print(
            f"{title:16} "
            f"{status}"
        )

    for title, error in failures:
        print(
            f"{title:16} "
            f"ERROR {error}"
        )

    print(
        "==================================="
    )

    if failures:
        raise RuntimeError(
            f"Ошибок каналов: "
            f"{len(failures)}"
        )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
