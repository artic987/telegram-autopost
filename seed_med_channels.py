import asyncio
import json
import os
import random
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from telethon import TelegramClient, functions, types, errors
from telethon.sessions import StringSession


MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


CHANNELS = [
    {
        "title": "Атаракс",
        "subject": "Атаракс (гидроксизин)",
        "handles": [
            "atarax_info_ru",
            "atarax_ru_info",
            "atarax_channel_ru",
            "atarax_simple"
        ],
        "palette": ((183, 220, 245), (68, 132, 182)),
        "topics": [
            "Что такое Атаракс?",
            "Гидроксизин: как он действует?",
            "Почему Атаракс может вызывать сонливость?",
            "Атаракс и тревога: что важно понимать",
            "Антигистаминное действие гидроксизина",
            "Почему реакция на препарат у людей различается",
            "Атаракс и алкоголь: почему нужна осторожность",
            "Вождение и работа с техникой",
            "Лекарственные взаимодействия",
            "Когда побочные эффекты требуют обращения к врачу"
        ]
    },

    {
        "title": "Бронхолитин",
        "subject": "Бронхолитин и противокашлевые препараты",
        "handles": [
            "bronholitin_info",
            "bronholitin_ru",
            "bronholitin_channel",
            "bronholitin_simple"
        ],
        "palette": ((201, 232, 205), (63, 143, 105)),
        "topics": [
            "Что такое Бронхолитин?",
            "Почему кашель — это симптом, а не отдельный диагноз",
            "Как в целом работают противокашлевые средства",
            "Почему комбинированные препараты требуют осторожности",
            "Побочные эффекты: что важно знать",
            "Почему возраст и сопутствующие болезни имеют значение",
            "Лекарственные взаимодействия",
            "Почему нельзя применять лекарство не по инструкции",
            "Какие симптомы при кашле требуют обращения к врачу",
            "Мифы о противокашлевых препаратах"
        ]
    },

    {
        "title": "Прегабалин",
        "subject": "прегабалин",
        "handles": [
            "pregabalin_info_ru",
            "pregabalin_ru_info",
            "pregabalin_channel",
            "pregabalin_simple"
        ],
        "palette": ((217, 204, 242), (112, 82, 172)),
        "topics": [
            "Что такое прегабалин?",
            "Как прегабалин действует на нервную систему",
            "Что такое нейропатическая боль",
            "Прегабалин и тревожные расстройства",
            "Почему возможны сонливость и головокружение",
            "Риск зависимости и почему о нём важно знать",
            "Прегабалин и алкоголь: почему сочетание рискованно",
            "Вождение и концентрация внимания",
            "Почему резкая самостоятельная отмена нежелательна",
            "Почему чужой опыт нельзя переносить на себя"
        ]
    },

    {
        "title": "Золофт",
        "subject": "Золофт (сертралин)",
        "handles": [
            "zoloft_info_ru",
            "zoloft_ru_info",
            "zoloft_channel_ru",
            "zoloft_simple"
        ],
        "palette": ((205, 226, 248), (70, 113, 184)),
        "topics": [
            "Что такое Золофт?",
            "Сертралин и группа СИОЗС",
            "Как работает обратный захват серотонина",
            "Почему эффект антидепрессанта развивается постепенно",
            "Золофт и тревога",
            "Побочные эффекты СИОЗС",
            "Антидепрессанты и сон",
            "Сертралин и алкоголь",
            "Почему нельзя оценивать лечение по первым дням",
            "Мифы об антидепрессантах"
        ]
    },

    {
        "title": "Эсциталопрам",
        "subject": "эсциталопрам",
        "handles": [
            "escitalopram_info",
            "escitalopram_ru",
            "escitalopram_channel",
            "escitalopram_simple"
        ],
        "palette": ((225, 222, 247), (101, 112, 186)),
        "topics": [
            "Что такое эсциталопрам?",
            "Эсциталопрам и СИОЗС",
            "Серотонин: почему всё сложнее популярного объяснения",
            "Почему антидепрессанты не действуют мгновенно",
            "Эсциталопрам и тревога",
            "Изменения сна в начале терапии",
            "Побочные эффекты: что важно понимать",
            "Эсциталопрам и алкоголь",
            "Что такое серотониновый синдром",
            "Почему отзывы не заменяют медицинскую оценку"
        ]
    },

    {
        "title": "Триттико",
        "subject": "Триттико (тразодон)",
        "handles": [
            "trittico_info_ru",
            "trittico_ru",
            "trittico_channel",
            "trittico_simple"
        ],
        "palette": ((242, 213, 218), (166, 91, 115)),
        "topics": [
            "Что такое Триттико?",
            "Тразодон: особенности действия",
            "Почему тразодон может влиять на сон",
            "Антидепрессант и снотворное — почему это не одно и то же",
            "Триттико и дневная сонливость",
            "Головокружение и изменение давления",
            "Лекарственные взаимодействия",
            "Триттико и алкоголь",
            "Почему самолечение психотропными препаратами рискованно",
            "Какие необычные симптомы стоит обсудить с врачом"
        ]
    }
]


ABOUT_TEMPLATE = (
    "Информационный канал о {subject}. "
    "Фармакология и психическое здоровье простым языком. "
    "Публикации не заменяют консультацию врача."
)


def get_font(size, bold=False):
    candidates = [
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold else
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
        (
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
            if bold else
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
        )
    ]

    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


def fit_font(draw, text, max_width, start_size=92):
    size = start_size

    while size >= 34:
        f = get_font(size, True)
        box = draw.textbbox((0, 0), text, font=f)

        if box[2] - box[0] <= max_width:
            return f

        size -= 3

    return get_font(34, True)


def make_avatar(title, palette):
    path = f"avatar_{title}.jpg"

    size = 800
    top, bottom = palette

    img = Image.new(
        "RGB",
        (size, size),
        top
    )

    px = img.load()

    for y in range(size):
        t = y / (size - 1)

        c = tuple(
            int(top[i] * (1 - t) + bottom[i] * t)
            for i in range(3)
        )

        for x in range(size):
            px[x, y] = c

    d = ImageDraw.Draw(img)

    # мягкий центральный круг
    d.ellipse(
        (105, 80, 695, 670),
        fill=(244, 248, 252),
        outline=(255, 255, 255),
        width=6
    )

    # абстрактная нейросеть
    nodes = [
        (260, 260),
        (350, 205),
        (455, 230),
        (535, 315),
        (465, 395),
        (345, 420),
        (265, 350),
    ]

    links = [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 4),
        (4, 5),
        (5, 6),
        (6, 0),
        (1, 5),
        (2, 4),
        (0, 4)
    ]

    for a, b in links:
        d.line(
            (
                nodes[a][0],
                nodes[a][1],
                nodes[b][0],
                nodes[b][1]
            ),
            fill=(125, 155, 185),
            width=7
        )

    for x, y in nodes:
        d.ellipse(
            (x - 15, y - 15, x + 15, y + 15),
            fill=bottom
        )

    title_upper = title.upper()

    title_font = fit_font(
        d,
        title_upper,
        690,
        82
    )

    bbox = d.textbbox(
        (0, 0),
        title_upper,
        font=title_font
    )

    tw = bbox[2] - bbox[0]

    d.rounded_rectangle(
        (45, 515, 755, 715),
        radius=35,
        fill=(247, 249, 252)
    )

    d.text(
        ((size - tw) / 2, 545),
        title_upper,
        font=title_font,
        fill=(31, 65, 100)
    )

    subtitle = "ПРОСТО О СЛОЖНОМ"

    sf = get_font(
        28,
        False
    )

    bbox = d.textbbox(
        (0, 0),
        subtitle,
        font=sf
    )

    sw = bbox[2] - bbox[0]

    d.text(
        ((size - sw) / 2, 655),
        subtitle,
        font=sf,
        fill=(80, 100, 120)
    )

    img.save(
        path,
        quality=94,
        subsampling=0
    )

    return path


def groq_request(prompt):
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
                        "Ты редактор русскоязычного "
                        "образовательного канала о лекарствах "
                        "и фармакологии."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.72,
            "max_completion_tokens": 5000
        },
        ensure_ascii=False
    ).encode("utf-8")

    for attempt in range(1, 4):
        req = urllib.request.Request(
            GROQ_URL,
            data=payload,
            method="POST",
            headers={
                "Authorization":
                    f"Bearer {key}",
                "Content-Type":
                    "application/json",
                "User-Agent":
                    "telegram-autopost/1.0"
            }
        )

        try:
            with urllib.request.urlopen(
                req,
                timeout=180
            ) as response:
                data = json.loads(
                    response.read().decode(
                        "utf-8"
                    )
                )

            text = (
                data["choices"][0]
                ["message"]["content"]
                .strip()
            )

            return text

        except urllib.error.HTTPError as exc:
            body = exc.read().decode(
                "utf-8",
                errors="replace"
            )

            if (
                exc.code == 429
                or exc.code >= 500
            ) and attempt < 3:

                wait = 15 * attempt

                print(
                    f"Groq HTTP {exc.code}; "
                    f"жду {wait} секунд"
                )

                time.sleep(wait)
                continue

            raise RuntimeError(
                f"Groq HTTP {exc.code}: {body}"
            ) from exc

    raise RuntimeError(
        "Groq не ответил"
    )


def generate_posts(cfg):
    subject = cfg["subject"]
    topics = cfg["topics"]

    topic_block = "\n".join(
        f"{i + 1}. {topic}"
        for i, topic in enumerate(topics)
    )

    extra = ""

    if cfg["title"] in (
        "Прегабалин",
        "Бронхолитин"
    ):
        extra = """
Особенно важно:
не описывай рекреационное употребление,
эйфорические эффекты, способы усиления действия,
опасные сочетания ради эффекта, способы обхода контроля
или способы получения препарата.
"""

    prompt = f"""
Подготовь содержимое ДЕСЯТИ стартовых постов
для информационного Telegram-канала.

Препарат/тема:
{subject}

Темы, строго в этом порядке:

{topic_block}

Верни ТОЛЬКО JSON-массив из ровно 10 строк.

Каждая строка — тело одного поста БЕЗ заголовка.
Заголовок будет добавлен программой отдельно.

Для каждого текста:

— примерно 450–850 знаков;
— 2–5 коротких абзацев;
— понятный естественный русский язык;
— спокойно и без запугивания;
— информация образовательного характера;
— можно добавить 1–3 подходящих эмодзи;
— в конце 2–4 релевантных хэштега.

Нельзя:

— рекламировать препарат;
— сообщать цены и наличие;
— предлагать купить или заказать;
— обсуждать доставку;
— давать дозировки;
— составлять схемы приёма;
— объяснять, как самостоятельно увеличивать дозу;
— давать персональные медицинские назначения;
— подсказывать способы немедицинского употребления;
— выдумывать исследования или статистику;
— выдумывать противопоказания;
— выдавать личные отзывы за доказательство.

Не утверждай, что препарат подходит конкретному человеку.

Если речь о зависимости, отмене, серьёзной реакции,
суицидальных мыслях, выраженном ухудшении состояния
или другом потенциально опасном симптоме,
коротко укажи на необходимость обращения за
медицинской помощью.

{extra}

JSON должен быть валидным.
Никаких ``` и никакого текста до или после массива.
""".strip()

    for attempt in range(3):
        raw = groq_request(
            prompt
        ).strip()

        if raw.startswith("```"):
            raw = raw.replace(
                "```json",
                ""
            ).replace(
                "```",
                ""
            ).strip()

        try:
            posts = json.loads(
                raw
            )
        except Exception:
            posts = None

        if (
            isinstance(posts, list)
            and len(posts) == 10
            and all(
                isinstance(x, str)
                and len(x.strip()) >= 200
                for x in posts
            )
        ):
            return [
                x.strip()
                for x in posts
            ]

        print(
            "Groq вернул неправильный формат, "
            "повтор..."
        )

    raise RuntimeError(
        f"Не удалось получить 10 корректных постов "
        f"для {cfg['title']}"
    )


async def find_channel(
    client,
    title
):
    async for dialog in client.iter_dialogs():
        entity = dialog.entity

        if (
            dialog.name == title
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
            return entity

    return None


async def create_channel(
    client,
    cfg
):
    existing = await find_channel(
        client,
        cfg["title"]
    )

    if existing:
        print(
            f"✓ Канал {cfg['title']} "
            f"уже существует"
        )
        return existing

    about = ABOUT_TEMPLATE.format(
        subject=cfg["subject"]
    )

    for attempt in range(2):
        try:
            result = await client(
                functions.channels.CreateChannelRequest(
                    title=cfg["title"],
                    about=about,
                    broadcast=True,
                    megagroup=False
                )
            )

            channel = result.chats[0]

            print(
                f"✓ Создан канал: "
                f"{cfg['title']}"
            )

            return channel

        except errors.FloodWaitError as exc:
            print(
                f"Telegram FloodWait "
                f"{exc.seconds} сек."
            )

            await asyncio.sleep(
                exc.seconds + 3
            )

    raise RuntimeError(
        f"Не удалось создать "
        f"{cfg['title']}"
    )


async def assign_username(
    client,
    channel,
    cfg
):
    current = getattr(
        channel,
        "username",
        None
    )

    if current:
        return "@" + current

    for username in cfg["handles"]:
        try:
            await client(
                functions.channels.UpdateUsernameRequest(
                    channel=channel,
                    username=username
                )
            )

            print(
                f"✓ Username: @{username}"
            )

            return "@" + username

        except (
            errors.UsernameOccupiedError,
            errors.UsernameInvalidError
        ):
            print(
                f"  @{username} занят"
            )

        except errors.FloodWaitError as exc:
            print(
                f"FloodWait {exc.seconds} сек."
            )

            await asyncio.sleep(
                exc.seconds + 3
            )

        except Exception as exc:
            print(
                "⚠ Не удалось назначить "
                f"@{username}: {exc}"
            )
            break

    return "(без публичного username)"


async def set_avatar(
    client,
    channel,
    cfg
):
    path = make_avatar(
        cfg["title"],
        cfg["palette"]
    )

    uploaded = await client.upload_file(
        path
    )

    await client(
        functions.channels.EditPhotoRequest(
            channel=channel,
            photo=types.InputChatUploadedPhoto(
                file=uploaded
            )
        )
    )

    print(
        "✓ Аватар установлен"
    )


async def get_existing_texts(
    client,
    channel
):
    result = []

    async for message in client.iter_messages(
        channel,
        limit=150
    ):
        text = (
            message.message
            or ""
        ).strip()

        if text:
            result.append(text)

    return result


async def send_post(
    client,
    channel,
    text
):
    while True:
        try:
            return await client.send_message(
                channel,
                text,
                link_preview=False,
                parse_mode=None
            )

        except errors.FloodWaitError as exc:
            print(
                f"Telegram FloodWait: "
                f"{exc.seconds} сек."
            )

            await asyncio.sleep(
                exc.seconds + 3
            )


async def fill_channel(
    client,
    channel,
    cfg
):
    existing = await get_existing_texts(
        client,
        channel
    )

    missing_indexes = []

    for i, topic in enumerate(
        cfg["topics"]
    ):
        if not any(
            topic.lower()
            in old.lower()
            for old in existing
        ):
            missing_indexes.append(i)

    if not missing_indexes:
        print(
            "✓ Все 10 стартовых тем "
            "уже опубликованы"
        )
        return

    print(
        f"Генерирую 10 материалов "
        f"для {cfg['title']}..."
    )

    bodies = await asyncio.to_thread(
        generate_posts,
        cfg
    )

    published = 0

    for i in missing_indexes:
        topic = cfg["topics"][i]
        body = bodies[i]

        post = (
            f"📘 {topic}\n\n"
            f"{body}"
        )

        msg = await send_post(
            client,
            channel,
            post
        )

        published += 1

        print(
            f"✓ Пост {i + 1}/10 "
            f"message_id={msg.id}"
        )

        await asyncio.sleep(
            random.uniform(
                1.5,
                3.0
            )
        )

    print(
        f"✓ Добавлено публикаций: "
        f"{published}"
    )


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

    print(
        "Модель Groq:",
        MODEL
    )

    async with TelegramClient(
        StringSession(session),
        api_id,
        api_hash
    ) as client:

        me = await client.get_me()

        print(
            "Telegram подключён:",
            me.id
        )

        summary = []

        for num, cfg in enumerate(
            CHANNELS,
            start=1
        ):
            print()
            print(
                "=" * 60
            )
            print(
                f"{num}/6 — "
                f"{cfg['title']}"
            )
            print(
                "=" * 60
            )

            try:
                channel = await create_channel(
                    client,
                    cfg
                )

                username = await assign_username(
                    client,
                    channel,
                    cfg
                )

                try:
                    await set_avatar(
                        client,
                        channel,
                        cfg
                    )

                except Exception as exc:
                    print(
                        "⚠ Ошибка аватара:",
                        repr(exc)
                    )

                await fill_channel(
                    client,
                    channel,
                    cfg
                )

                summary.append(
                    (
                        cfg["title"],
                        username,
                        "OK"
                    )
                )

            except Exception as exc:
                print(
                    f"✗ ОШИБКА "
                    f"{cfg['title']}: "
                    f"{repr(exc)}"
                )

                summary.append(
                    (
                        cfg["title"],
                        "-",
                        f"ERROR: {exc}"
                    )
                )

            if num < len(CHANNELS):
                print(
                    "Пауза перед следующим "
                    "каналом..."
                )

                await asyncio.sleep(7)

        print()
        print(
            "=" * 60
        )
        print(
            "ИТОГ"
        )
        print(
            "=" * 60
        )

        for title, username, status in summary:
            print(
                f"{title:15} "
                f"{username:28} "
                f"{status}"
            )


if __name__ == "__main__":
    asyncio.run(main())
