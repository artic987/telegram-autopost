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


MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)

GROQ_URL = (
    "https://api.groq.com/openai/v1/chat/completions"
)

DRY_RUN = (
    os.getenv("DRY_RUN", "false")
    .lower()
    in ("1", "true", "yes", "on")
)

MOSCOW = timezone(
    timedelta(hours=3)
)

# Первый реальный автоматический запуск:
# 18.09.2026 -> Атаракс
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
            "как препарат действует простыми словами",
            "история появления препарата",
            "к какому фармакологическому классу относится препарат",
            "почему действие лекарства нельзя объяснить одной фразой",
            "почему люди могут по-разному реагировать на один препарат",
            "что такое период полувыведения и почему он важен",
            "что такое активный метаболит",
            "почему побочные эффекты у разных людей отличаются",
            "распространённый миф о препарате",
            "почему чужой отзыв не предсказывает индивидуальный результат",
            "зачем врачу знать о других принимаемых лекарствах",
            "что такое лекарственное взаимодействие",
        ],
    },

    {
        "name": "психическое здоровье",

        "ideas": [
            "как тревога может проявляться физически",
            "почему хронический стресс влияет на самочувствие",
            "сон и психическое здоровье",
            "почему тревожность и усталость иногда усиливают друг друга",
            "как психотерапия и фармакотерапия могут дополнять друг друга",
            "почему стигма мешает людям обращаться за помощью",
            "что такое навязчивые мысли простыми словами",
            "чем плохой день отличается от устойчивого ухудшения состояния",
            "почему психические симптомы нельзя свести к силе воли",
            "как режим сна связан с эмоциональным состоянием",
            "почему диагноз важнее советов из интернета",
            "что означает доказательный подход к психическому здоровью",
        ],
    },

    {
        "name": "фармакология",

        "ideas": [
            "что такое рецептор простыми словами",
            "что такое нейромедиатор",
            "как лекарство попадает в кровь",
            "как печень участвует в переработке лекарств",
            "как организм выводит лекарства",
            "что означает биодоступность",
            "что такое фармакокинетика",
            "что такое фармакодинамика",
            "побочный эффект и аллергия — почему это не одно и то же",
            "почему взаимодействуют разные лекарства",
            "что такое терапевтический эффект",
            "зачем нужны клинические исследования",
            "как исследователи сравнивают пользу и риск препарата",
            "почему отдельный отзыв не является доказательством",
        ],
    },

    {
        "name": "аптеки и фармацевтика",

        "ideas": [
            "чем занимается фармацевт в аптеке",
            "как лекарства хранят в аптеке",
            "почему температура хранения имеет значение",
            "зачем лекарству срок годности",
            "что происходит с просроченными лекарствами",
            "что такое дженерик",
            "чем торговое название отличается от действующего вещества",
            "зачем читать инструкцию к препарату",
            "как устроена упаковка лекарства",
            "почему таблетки одного вещества могут выглядеть по-разному",
            "как работают серии и партии лекарств",
            "что такое фармаконадзор",
            "зачем сообщают о нежелательных реакциях",
            "почему фармацевту важно знать о других лекарствах пациента",
        ],
    },
]


def words(text):
    return set(
        re.findall(
            r"[а-яёa-z0-9]{5,}",
            text.lower()
        )
    )


def select_day():
    today = datetime.now(
        MOSCOW
    ).date()

    delta = (
        today - BASE_DATE
    ).days

    # Для ручного теста до первого дня
    # показываем первый канал.
    if delta < 0:
        delta = 0

    channel_index = (
        delta
        % len(CHANNELS)
    )

    cycle_number = (
        delta
        // len(CHANNELS)
    )

    # Благодаря + channel_index каналы
    # внутри одного 8-дневного круга получают
    # разные рубрики.
    #
    # Благодаря + cycle_number рубрика
    # конкретного канала меняется каждый раз,
    # когда очередь возвращается к нему.
    category_index = (
        channel_index
        + cycle_number
    ) % len(CATEGORIES)

    return (
        today,
        delta,
        channel_index,
        category_index,
        CHANNELS[channel_index],
        CATEGORIES[category_index],
    )


async def find_channel(
    client,
    cfg
):
    # Сначала пробуем публичные username.
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
                    f"✓ Найден по username: "
                    f"@{username}"
                )

                return entity

        except Exception:
            pass

    # Если public username не назначился,
    # ищем среди собственных диалогов по названию.
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
                f"✓ Найден по названию: "
                f"{cfg['title']}"
            )

            return entity

    raise RuntimeError(
        "Не найден Telegram-канал: "
        + cfg["title"]
    )


async def read_recent(
    client,
    channel
):
    posts = []

    async for message in client.iter_messages(
        channel,
        limit=30
    ):
        text = (
            message.message
            or ""
        ).strip()

        if text:
            posts.append(
                text[:1800]
            )

    return posts


def choose_idea(
    category,
    recent
):
    recent_words = words(
        "\n".join(
            recent
        )
    )

    scored = []

    for idea in category["ideas"]:
        idea_words = words(
            idea
        )

        overlap = len(
            idea_words
            & recent_words
        )

        scored.append(
            (
                overlap,
                random.random(),
                idea
            )
        )

    scored.sort(
        key=lambda x: (
            x[0],
            x[1]
        )
    )

    best = scored[0][0]

    candidates = [
        idea
        for score, _, idea
        in scored
        if score == best
    ]

    return random.choice(
        candidates
    )


def make_prompt(
    cfg,
    category,
    idea,
    recent
):
    history = (
        "\n\n---\n\n"
        .join(
            recent[:15]
        )
    )

    special = ""

    if cfg["title"] in (
        "Прегабалин",
        "Фенибут",
        "Бронхолитин",
    ):
        special = """
Для этого канала особенно важно:
не объясняй способы рекреационного или немедицинского
употребления, способы усиления эффекта, опасные комбинации
ради эффекта, получение препарата в обход правил
или способы скрыть употребление.
"""

    return f"""
Ты редактор русскоязычного образовательного Telegram-канала.

Название канала:
{cfg["title"]}

Основная лекарственная тема:
{cfg["drug"]}

Сегодняшняя рубрика:
{category["name"]}

Фокус сегодняшнего материала:
{idea}

Напиши ОДИН новый Telegram-пост.

ТРЕБОВАНИЯ:

— примерно 700–1200 знаков;
— короткий интересный заголовок;
— 3–6 небольших абзацев;
— естественный современный русский язык;
— пост должен быть понятен обычному читателю;
— допускаются несколько подходящих эмодзи;
— в конце добавь 2–4 подходящих хэштега;
— избегай канцелярита и SEO-спама;
— не повторяй последние публикации канала.

Если сегодняшняя тема общая —
психология, аптеки или фармакология —
не нужно искусственно вставлять название лекарства
в каждый абзац. Достаточно естественной связи
с тематикой канала.

ЭТО ИНФОРМАЦИОННЫЙ КАНАЛ.

НЕЛЬЗЯ:

— рекламировать продажу лекарства;
— писать цены или наличие;
— предлагать купить или заказать;
— рекламировать доставку;
— составлять индивидуальные схемы лечения;
— назначать человеку препарат;
— давать дозировки;
— объяснять самостоятельное увеличение дозы;
— давать инструкции по опасным сочетаниям;
— выдумывать исследования или статистику;
— выдумывать юридический или рецептурный статус;
— представлять личные отзывы как научный факт.

Если правовой или рецептурный статус зависит
от страны, не делай конкретных утверждений без источника.

Если речь идёт о зависимости, выраженной отмене,
суицидальных мыслях, мании, тяжёлой аллергической
или другой потенциально опасной реакции,
кратко укажи на необходимость обращения
за медицинской помощью.

{special}

Последние публикации этого канала:

{history if history else "(данных пока мало)"}

Верни ТОЛЬКО готовый текст поста.
Без пояснений до или после него.
""".strip()


def clean(
    text
):
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
        text = text[:3890]

        if "\n" in text:
            text = text.rsplit(
                "\n",
                1
            )[0]

        text = (
            text.rstrip()
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
                        "Пиши качественные "
                        "образовательные Telegram-посты "
                        "о фармакологии, психическом здоровье "
                        "и устройстве аптек."
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
        4
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

                # Нужен, иначе Cloudflare Groq
                # может дать error 1010.
                "User-Agent":
                    "telegram-autopost/1.0",
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=150
            ) as response:

                data = json.loads(
                    response
                    .read()
                    .decode(
                        "utf-8"
                    )
                )

            text = (
                data
                .get(
                    "choices",
                    [{}]
                )[0]
                .get(
                    "message",
                    {}
                )
                .get(
                    "content",
                    ""
                )
                .strip()
            )

            if not text:
                raise RuntimeError(
                    "Groq вернул пустой текст"
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
            ) and attempt < 3:

                wait = (
                    attempt
                    * 15
                )

                print(
                    f"Groq HTTP "
                    f"{exc.code}. "
                    f"Повтор через "
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


async def already_posted_today(
    client,
    channel,
    today
):
    async for message in client.iter_messages(
        channel,
        limit=30
    ):
        if not message.date:
            continue

        local_date = (
            message.date
            .astimezone(
                MOSCOW
            )
            .date()
        )

        if local_date == today:
            return True

        if local_date < today:
            break

    return False


async def main():
    (
        today,
        delta,
        channel_index,
        category_index,
        cfg,
        category,
    ) = select_day()

    print(
        "========================================"
    )

    print(
        "Дата МСК:",
        today.isoformat()
    )

    print(
        "День цикла:",
        (
            channel_index
            + 1
        ),
        "/ 8"
    )

    print(
        "Сегодняшний канал:",
        cfg["title"]
    )

    print(
        "Препарат:",
        cfg["drug"]
    )

    print(
        "Рубрика:",
        category["name"]
    )

    print(
        "Модель:",
        MODEL
    )

    print(
        "DRY_RUN:",
        DRY_RUN
    )

    print(
        "========================================"
    )

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

    async with TelegramClient(
        StringSession(
            session
        ),
        api_id,
        api_hash
    ) as client:

        me = await client.get_me()

        print(
            "Telegram подключён:",
            me.id
        )

        channel = await find_channel(
            client,
            cfg
        )

        # При настоящем расписании:
        # если в сегодняшнем канале уже что-то
        # опубликовано сегодня, второй автоматический
        # пост не отправляем.
        #
        # DRY RUN это ограничение игнорирует,
        # чтобы тест всё равно сгенерировал текст.
        if not DRY_RUN:
            if await already_posted_today(
                client,
                channel,
                today
            ):
                print(
                    "Сегодня в этом канале "
                    "уже есть публикация."
                )

                print(
                    "Автопост пропущен, "
                    "чтобы не было дубля."
                )

                return

        recent = await read_recent(
            client,
            channel
        )

        print(
            "Прочитано последних постов:",
            len(recent)
        )

        idea = choose_idea(
            category,
            recent
        )

        print(
            "Фокус:",
            idea
        )

        prompt = make_prompt(
            cfg,
            category,
            idea,
            recent
        )

        print(
            "Генерирую пост..."
        )

        post = await asyncio.to_thread(
            generate,
            prompt
        )

        if len(post) < 300:
            raise RuntimeError(
                "Получился слишком "
                "короткий текст: "
                f"{len(post)} символов"
            )

        print()
        print(
            "=========== ПОСТ ==========="
        )

        print(
            post
        )

        print(
            "============================"
        )

        print(
            "Длина:",
            len(post)
        )

        if DRY_RUN:
            print()
            print(
                "✓ DRY RUN: "
                "публикация НЕ отправлена"
            )

            return

        message = await client.send_message(
            channel,
            post,
            link_preview=False
        )

        print()
        print(
            "✓ ОПУБЛИКОВАНО"
        )

        print(
            "Канал:",
            cfg["title"]
        )

        print(
            "message_id:",
            message.id
        )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
