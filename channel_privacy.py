import asyncio
import os

from telethon import TelegramClient, functions, errors
from telethon.sessions import StringSession


CONTACT = "@addvk39"

CHANNELS = [
    "@atarax_info_ru",
    "@bronholitin_info",
    "@pregabalin_info_ru",
    "@zoloft_info_ru",
    "@escitalopram_info",
    "@trittico_info_ru",
    "@fenibut_buy",
    "@fluoxeti",
]


PIN_TEXT = """📌 Связь с администрацией

По вопросам сотрудничества, предложений,
замечаний и обратной связи:

👉 @addvk39

Это официальный контакт администрации канала.
"""


REAL_NAME_MARKERS = [
    "кравцов артур",
    "артур кравцов",
]


async def configure_channel(client, username):
    print()
    print("=" * 60)
    print(username)
    print("=" * 60)

    channel = await client.get_entity(username)

    # --------------------------------------------------------
    # Отключаем подписи администраторов
    # и ссылки на их личные профили.
    # --------------------------------------------------------

    try:
        await client(
            functions.channels.ToggleSignaturesRequest(
                channel=channel,
                signatures_enabled=False,
                profiles_enabled=False,
            )
        )

        print("✓ Подписи администраторов отключены")
        print("✓ Профили администраторов отключены")

    except errors.ChatNotModifiedError:
        print("✓ Подписи/профили уже отключены")

    except Exception as exc:
        print(
            "⚠ Не удалось изменить signatures:",
            repr(exc)
        )


    # --------------------------------------------------------
    # Описание канала
    # --------------------------------------------------------

    try:
        full = await client(
            functions.channels.GetFullChannelRequest(
                channel=channel
            )
        )

        old_about = (
            full.full_chat.about
            or ""
        ).strip()

        clean_lines = []

        for line in old_about.splitlines():
            low = line.lower()

            if CONTACT.lower() in low:
                continue

            if "связь с администрацией" in low:
                continue

            if any(
                marker in low
                for marker in REAL_NAME_MARKERS
            ):
                continue

            clean_lines.append(line)

        old_about = "\n".join(
            clean_lines
        ).strip()

        suffix = (
            f"Связь с администрацией: "
            f"{CONTACT}"
        )

        # Telegram ограничивает длину about.
        max_len = 250
        available = (
            max_len
            - len(suffix)
            - 2
        )

        if len(old_about) > available:
            old_about = (
                old_about[:available]
                .rstrip()
            )

        if old_about:
            new_about = (
                old_about
                + "\n\n"
                + suffix
            )
        else:
            new_about = suffix

        try:
            await client(
                functions.channels.EditAboutRequest(
                    channel=channel,
                    about=new_about
                )
            )

            print(
                "✓ @addvk39 добавлен "
                "в описание"
            )

        except errors.ChatNotModifiedError:
            print(
                "✓ Описание уже актуально"
            )

    except Exception as exc:
        print(
            "⚠ Ошибка описания:",
            repr(exc)
        )


    # --------------------------------------------------------
    # Находим существующий пост контактов
    # --------------------------------------------------------

    contact_message = None

    async for msg in client.iter_messages(
        channel,
        limit=150
    ):
        text = (
            msg.raw_text
            or ""
        )

        if (
            CONTACT.lower()
            in text.lower()
            and
            "связь с администрацией"
            in text.lower()
        ):
            contact_message = msg
            break


    # --------------------------------------------------------
    # Если нет — создаём
    # --------------------------------------------------------

    if contact_message is None:
        contact_message = await client.send_message(
            channel,
            PIN_TEXT,
            link_preview=False
        )

        print(
            "✓ Создан пост контактов"
        )

    else:
        # Приводим старый пост к единому виду.
        if contact_message.raw_text.strip() != PIN_TEXT.strip():
            try:
                await client.edit_message(
                    channel,
                    contact_message,
                    PIN_TEXT,
                    link_preview=False
                )

                print(
                    "✓ Старый пост контактов обновлён"
                )

            except Exception as exc:
                print(
                    "⚠ Не удалось обновить пост:",
                    repr(exc)
                )

        else:
            print(
                "✓ Пост контактов уже существует"
            )


    # --------------------------------------------------------
    # Закрепляем
    # --------------------------------------------------------

    try:
        await client.pin_message(
            channel,
            contact_message,
            notify=False
        )

        print(
            "✓ Пост @addvk39 закреплён"
        )

    except Exception as exc:
        print(
            "⚠ Не удалось закрепить:",
            repr(exc)
        )


    # --------------------------------------------------------
    # Проверяем последние 200 публикаций:
    # нет ли публичного имени в тексте/подписи.
    # Ничего автоматически не удаляем.
    # --------------------------------------------------------

    suspicious = []

    async for msg in client.iter_messages(
        channel,
        limit=200
    ):
        text = (
            msg.raw_text
            or ""
        ).lower()

        post_author = str(
            getattr(
                msg,
                "post_author",
                ""
            )
            or ""
        ).lower()

        found = False

        for marker in REAL_NAME_MARKERS:
            if (
                marker in text
                or marker in post_author
            ):
                found = True
                break

        if found:
            suspicious.append(
                (
                    msg.id,
                    getattr(
                        msg,
                        "post_author",
                        None
                    )
                )
            )

    if suspicious:
        print(
            "⚠ Найдены старые публикации, "
            "где может светиться имя:"
        )

        for msg_id, author in suspicious:
            print(
                f"  message_id={msg_id} "
                f"author={author!r}"
            )

    else:
        print(
            "✓ В последних 200 постах "
            "«Кравцов Артур» не найден"
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

        # Намеренно не печатаем имя/фамилию
        # аккаунта даже в GitHub Actions.
        print(
            "Telegram session:",
            me.id
        )

        for username in CHANNELS:
            try:
                await configure_channel(
                    client,
                    username
                )

            except Exception as exc:
                print(
                    f"✗ {username}:",
                    repr(exc)
                )

            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
