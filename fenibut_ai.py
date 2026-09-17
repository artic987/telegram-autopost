import asyncio
import json
import os
import random
import urllib.error
import urllib.request

from telethon import TelegramClient
from telethon.sessions import StringSession


CHANNEL = os.getenv("TG_CHANNEL", "@fenibut_buy")
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")


TOPICS = [
    "что такое фенибут и почему вокруг него столько споров",
    "ГАМК и GABA-B: простое объяснение механизма действия",
    "толерантность и почему эффект при регулярном употреблении может меняться",
    "зависимость и синдром отмены: какие риски важно знать",
    "фенибут и сон: почему улучшение сна не всегда решает причину бессонницы",
    "фенибут и алкоголь: почему сочетание может быть непредсказуемым",
    "побочные эффекты и когда человеку стоит обратиться за медицинской помощью",
    "почему чужой опыт применения нельзя автоматически переносить на себя",
    "фенибут как анксиолитик и ноотроп: что означают эти понятия",
    "история появления фенибута",
    "распространённые мифы о фенибуте",
    "почему самолечение тревожности может мешать обнаружить её причину",
    "фенибут и концентрация: почему субъективные ощущения у людей отличаются",
    "почему при регулярном использовании может формироваться толерантность",
    "что такое ГАМК простыми словами и какое отношение она имеет к фенибуту",
]


def make_prompt(topic, recent_posts):
    history = "\n\n---\n\n".join(recent_posts[:12])

    return f"""
Ты редактор русского информационного Telegram-канала о фенибуте.

Напиши ОДИН новый Telegram-пост.

ТЕМА:
{topic}

Требования:

700–1200 знаков.

Красивый короткий заголовок.

После заголовка 3–6 небольших абзацев, удобно читаемых с телефона.

Слово «фенибут» должно естественно появиться в заголовке
или в первых двух абзацах.

Можно использовать несколько уместных эмодзи.

В конце добавь 2–4 релевантных хэштега, например:
#фенибут #фармакология #здоровье

Стиль спокойный, понятный и интересный.

Это исключительно образовательный канал.

ЗАПРЕЩЕНО:
— рекламировать продажу;
— писать цены;
— писать про наличие;
— предлагать заказать или купить;
— рекламировать доставку;
— давать схемы приёма;
— назначать дозировки;
— советовать повышать дозу;
— давать персональные медицинские назначения;
— выдумывать исследования и статистику;
— выдумывать юридический статус препарата.

Если медицинский факт неоднозначен, формулируй осторожно.

При обсуждении зависимости или синдрома отмены напомни,
что при выраженных симптомах либо регулярном употреблении
разумно обратиться к врачу.

Не повторяй темы, заголовки и основные формулировки
недавних сообщений канала.

Недавние сообщения:

{history if history else "(канал пока практически пуст)"}

Верни ТОЛЬКО текст готового Telegram-поста.
Не добавляй пояснений от себя.
""".strip()


def generate_post(prompt):
    api_key = os.environ["GROQ_API_KEY"]

    payload = json.dumps(
        {
            "model": MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты редактор русскоязычного информационного "
                        "Telegram-канала. Пиши ясно, естественно и кратко."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": 0.8,
            "max_completion_tokens": 900,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Groq API HTTP {exc.code}: {body}"
        ) from exc

    try:
        post = data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        raise RuntimeError(
            "Groq не вернул текст: "
            + json.dumps(data, ensure_ascii=False)[:1200]
        ) from exc

    if not post:
        raise RuntimeError("Groq вернул пустой текст")

    return post

async def main():
    api_id = int(os.environ["TG_API_ID"])
    api_hash = os.environ["TG_API_HASH"]
    string_session = os.environ["TG_STRING_SESSION"]

    async with TelegramClient(
        StringSession(string_session),
        api_id,
        api_hash
    ) as telegram:

        print(f"Читаю последние публикации {CHANNEL}...")

        recent_posts = []

        async for message in telegram.iter_messages(
            CHANNEL,
            limit=20
        ):
            text = (message.message or "").strip()

            if text:
                recent_posts.append(text[:1200])

        topic = random.choice(TOPICS)

        print("Выбрана тема:", topic)

        prompt = make_prompt(topic, recent_posts)

        print("Генерирую публикацию...")

        post = generate_post(prompt)

        if len(post) > 3900:
            post = post[:3890].rsplit("\n", 1)[0].rstrip() + "…"

        print()
        print("===== ГОТОВЫЙ ПОСТ =====")
        print(post)
        print("=========================")
        print()

        await telegram.send_message(
            CHANNEL,
            post,
            link_preview=False
        )

        print(
            f"ГОТОВО: опубликовано в {CHANNEL}, "
            f"{len(post)} символов."
        )


if __name__ == "__main__":
    asyncio.run(main())
