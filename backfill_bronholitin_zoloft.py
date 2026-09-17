import asyncio
import json
import os
import random
import time
import urllib.error
import urllib.request

from telethon import TelegramClient
from telethon.sessions import StringSession


MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)

GROQ_URL = (
    "https://api.groq.com/openai/v1/chat/completions"
)

TARGET_COUNT = 10


CHANNELS = [
    {
        "title": "Бронхолитин",
        "username": "bronholitin_info",
        "drug": "Бронхолитин",
        "themes": [
            "что такое противокашлевые препараты",
            "как устроен кашлевой рефлекс",
            "сухой и продуктивный кашель — в чём разница",
            "почему не каждый кашель нужно подавлять",
            "как действуют лекарства на дыхательные пути",
            "что такое бронходилатация простыми словами",
            "зачем учитывать другие принимаемые лекарства",
            "побочный эффект и аллергия — не одно и то же",
            "почему самолечение кашля иногда опасно",
            "как фармацевты хранят жидкие лекарственные формы",
            "что такое действующее и вспомогательное вещество",
            "почему инструкции к препаратам важны",
            "как организм перерабатывает лекарства",
            "что означает период полувыведения",
            "почему один препарат действует на людей по-разному",
        ],
        "special": """
Не описывай способы рекреационного использования,
получения эйфории, усиления действия, опасные сочетания,
извлечение компонентов или обход ограничений.
"""
    },

    {
        "title": "Золофт",
        "username": "zoloft_info_ru",
        "drug": "Золофт (сертралин)",
        "themes": [
            "что такое СИОЗС простыми словами",
            "как работает обратный захват серотонина",
            "почему эффект антидепрессантов развивается не мгновенно",
            "тревога и физические симптомы",
            "сон и психическое здоровье",
            "психотерапия и фармакотерапия",
            "что такое побочный эффект",
            "почему чужой опыт лечения нельзя переносить на себя",
            "почему резкие изменения терапии обсуждают с врачом",
            "что такое фармакокинетика",
            "что такое фармакодинамика",
            "как лекарства проходят клинические исследования",
            "что такое дженерик",
            "действующее вещество и торговое название",
            "зачем существует фармаконадзор",
            "почему психические симптомы не сводятся к силе воли",
        ],
        "special": ""
    },
]


def clean(text):
    text = text.strip()

    for marker in (
        "```markdown",
        "```text",
        "```"
    ):
        text = text.replace(
            marker,
            ""
        )

    return text.strip()


def generate(prompt):
    key = os.environ["GROQ_API_KEY"]

    payload = json.dumps(
        {
            "model": MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты редактор образовательного "
                        "Telegram-канала о фармакологии "
                        "и психическом здоровье. "
                        "Пиши фактически осторожно, "
                        "не выдумывай исследования, даты "
                        "или медицинские утверждения."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.72,
            "max_completion_tokens": 900
        },
        ensure_ascii=False
    ).encode("utf-8")

    for attempt in range(1, 7):
        req = urllib.request.Request(
            GROQ_URL,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "User-Agent": "telegram-autopost/1.0",
            },
        )

        try:
            with urllib.request.urlopen(
                req,
                timeout=150
            ) as response:
                data = json.loads(
                    response.read().decode("utf-8")
                )

            text = (
                data
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )

            if text:
                return clean(text)

            if attempt < 6:
                wait = attempt * 20

                print(
                    f"Groq пустой ответ. "
                    f"Жду {wait} сек."
                )

                time.sleep(wait)
                continue

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
            ) and attempt < 6:
                wait = attempt * 25

                print(
                    f"Groq HTTP {exc.code}. "
                    f"Жду {wait} сек."
                )

                time.sleep(wait)
                continue

            raise RuntimeError(
                f"Groq HTTP {exc.code}: {body}"
            )

        except Exception as exc:
            if attempt < 6:
                wait = attempt * 15

                print(
                    f"Groq error {repr(exc)}. "
                    f"Жду {wait} сек."
                )

                time.sleep(wait)
                continue

            raise

    raise RuntimeError(
        "Не удалось получить пост после 6 попыток"
    )


def build_prompt(cfg, theme, previous):
    history = "\n\n---\n\n".join(
        previous[-10:]
    )

    return f"""
Ты пишешь информационный пост для Telegram-канала.

Канал:
{cfg["title"]}

Основная тема:
{cfg["drug"]}

Тема текущего поста:
{theme}

Напиши один самостоятельный образовательный пост.

Требования:

— 650–1100 знаков;
— короткий заголовок;
— 3–5 небольших абзацев;
— простой современный русский язык;
— допускаются 1–3 уместных эмодзи;
— в конце 2–4 хэштега;
— не повторяй предыдущие публикации;
— избегай категоричных медицинских утверждений;
— не придумывай исследования, цифры и исторические даты;
— не рекламируй покупку лекарства;
— не пиши цены, наличие и доставку;
— не назначай лечение;
— не давай персональные медицинские рекомендации;
— не давай дозировки и схемы приёма;
— не объясняй самостоятельное повышение дозировки;
— если тема требует индивидуального решения,
  укажи, что оно обсуждается с врачом.

{cfg["special"]}

Предыдущие посты:

{history if history else "(пока нет)"}

Верни только готовый текст публикации.
""".strip()


async def educational_posts(client, channel):
    posts = []

    async for msg in client.iter_messages(
        channel,
        limit=100
    ):
        text = (
            msg.raw_text
            or ""
        ).strip()

        if not text:
            continue

        low = text.lower()

        # Закреп с администрацией в счёт
        # образовательных публикаций не идёт.
        if (
            "@addvk39" in low
            and
            "связь с администрацией" in low
        ):
            continue

        posts.append(text)

    posts.reverse()

    return posts


async def process(client, cfg):
    print()
    print("=" * 60)
    print(cfg["title"])
    print("=" * 60)

    channel = await client.get_entity(
        "@" + cfg["username"]
    )

    existing = await educational_posts(
        client,
        channel
    )

    print(
        "Образовательных постов сейчас:",
        len(existing)
    )

    missing = max(
        0,
        TARGET_COUNT - len(existing)
    )

    if missing == 0:
        print(
            "✓ Уже есть минимум 10 постов"
        )

        return

    print(
        "Нужно добавить:",
        missing
    )

    themes = cfg["themes"][:]

    random.shuffle(themes)

    used = set()

    for number in range(missing):
        available = [
            theme
            for theme in themes
            if theme not in used
        ]

        if not available:
            used.clear()
            available = themes[:]

        theme = random.choice(
            available
        )

        used.add(theme)

        print()
        print(
            f"Пост {number + 1}/{missing}"
        )

        print(
            "Тема:",
            theme
        )

        prompt = build_prompt(
            cfg,
            theme,
            existing
        )

        post = await asyncio.to_thread(
            generate,
            prompt
        )

        if len(post) < 250:
            raise RuntimeError(
                "Groq вернул слишком короткий пост"
            )

        msg = await client.send_message(
            channel,
            post,
            link_preview=False
        )

        existing.append(post)

        print(
            f"✓ опубликовано "
            f"message_id={msg.id}"
        )

        # Не долбим Groq и Telegram подряд.
        await asyncio.sleep(
            random.uniform(
                15,
                22
            )
        )

    final = await educational_posts(
        client,
        channel
    )

    print()
    print(
        f"✓ Теперь постов: "
        f"{len(final)}"
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

    async with TelegramClient(
        StringSession(session),
        api_id,
        api_hash
    ) as client:

        me = await client.get_me()

        print(
            "Telegram session:",
            me.id
        )

        for cfg in CHANNELS:
            try:
                await process(
                    client,
                    cfg
                )

            except Exception as exc:
                print(
                    f"✗ {cfg['title']}: "
                    f"{repr(exc)}"
                )

            await asyncio.sleep(20)


if __name__ == "__main__":
    asyncio.run(main())
