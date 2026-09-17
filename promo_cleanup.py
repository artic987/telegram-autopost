import asyncio
import os

from telethon import (
    TelegramClient,
    functions,
    errors,
)

from telethon.sessions import StringSession


# Только группы, в которые старая версия
# точно/почти точно успела вступить до FloodWait.
TARGETS = [
    "@reklama_chatr",
    "@rektgkp",
    "@free_piarr",
    "@PR_FREEEE",
    "@P1Rchatik",
    "@reklamy_chat",
    "@telegabirza",
    "@business_club_portal",
    "@club_guarantor",
    "@club_reformer",
]


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

        left = 0
        skipped = 0


        for username in TARGETS:
            print()
            print(
                "Проверяем:",
                username
            )

            try:
                entity = await client.get_entity(
                    username
                )

            except Exception as exc:
                print(
                    "  ⚠ не удалось открыть:",
                    repr(exc)
                )

                skipped += 1
                continue


            try:
                await client(
                    functions.channels.LeaveChannelRequest(
                        channel=entity
                    )
                )

                print(
                    "  ✓ вышли из группы"
                )

                left += 1

            except errors.UserNotParticipantError:
                print(
                    "  ✓ аккаунт и так "
                    "не состоит в группе"
                )

            except errors.FloodWaitError as exc:
                seconds = int(
                    exc.seconds
                )

                print(
                    f"  ⚠ FloodWait: "
                    f"{seconds} сек."
                )

                if seconds <= 120:
                    await asyncio.sleep(
                        seconds + 2
                    )

                    try:
                        await client(
                            functions.channels.LeaveChannelRequest(
                                channel=entity
                            )
                        )

                        print(
                            "  ✓ вышли после ожидания"
                        )

                        left += 1

                    except Exception as retry_exc:
                        print(
                            "  ⚠ повтор:",
                            repr(retry_exc)
                        )

                        skipped += 1

                else:
                    print(
                        "  ⏳ слишком большой FloodWait, "
                        "не обходим ограничение"
                    )

                    skipped += 1

            except Exception as exc:
                # LeaveChannelRequest иногда может вернуть
                # ошибку, если уже не участник.
                text = repr(exc)

                if (
                    "USER_NOT_PARTICIPANT"
                    in text.upper()
                ):
                    print(
                        "  ✓ уже не участник"
                    )

                else:
                    print(
                        "  ⚠ ошибка выхода:",
                        text
                    )

                    skipped += 1


            await asyncio.sleep(3)


        print()
        print(
            "====================================="
        )

        print(
            "Вышли:",
            left
        )

        print(
            "Пропущено/не требовалось:",
            skipped
        )

        print(
            "====================================="
        )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
