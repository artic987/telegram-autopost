"""Read participant IDs of one Telegram chat using already authorized GH Actions account."""
import asyncio
import csv
import json
import os
import re
from pathlib import Path
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon import errors
from telethon.tl.types import User

OUTPUT = Path("members_export")
OUTPUT.mkdir(exist_ok=True)
TARGET = "PROFARM - ЧАТ"

def normalized(s):
    return re.sub(r"[^a-zа-яё0-9]+", "", s.casefold())

async def main():
    client = TelegramClient(
        StringSession(os.environ["TG_STRING_SESSION"]),
        int(os.environ["TG_API_ID"]),
        os.environ["TG_API_HASH"],
    )
    async with client:
        matches = []
        async for dialog in client.iter_dialogs(limit=None):
            if "profarm" in normalized(dialog.name):
                matches.append(dialog)
        if not matches:
            raise RuntimeError("Группа PROFARM не найдена в диалогах Telegram-аккаунта")
        exact = [d for d in matches if normalized(d.name) == normalized(TARGET)]
        dialog = (exact or matches)[0]
        print("Выбрана группа:", repr(dialog.name), "ID:", dialog.id)
        seen = {}
        try:
            async for member in client.iter_participants(dialog.entity, aggressive=True):
                if not isinstance(member, User):
                    continue
                seen[member.id] = {
                    "telegram_id": str(member.id),
                    "username": member.username or "",
                    "first_name": member.first_name or "",
                    "last_name": member.last_name or "",
                    "is_bot": "да" if member.bot else "нет",
                    "source": "Участник (API)",
                }
                if len(seen) % 200 == 0:
                    print("Получено участников:", len(seen))
        except (errors.ChatAdminRequiredError, errors.ChannelPrivateError, errors.FloodWaitError) as err:
            print("Ограничение Telegram:", type(err).__name__, str(err)[:200])
        member_count = len(seen)
        scanned = 0
        print("Проверяю авторов последних 50000 сообщений…", flush=True)
        try:
            async for message in client.iter_messages(dialog.entity, limit=50000):
                scanned += 1
                sender_id = message.sender_id
                if sender_id is None or sender_id <= 0:
                    continue
                sender = message.sender
                if sender_id not in seen:
                    seen[sender_id] = {
                        "telegram_id": str(sender_id),
                        "username": (sender.username or "") if isinstance(sender, User) else "",
                        "first_name": (sender.first_name or "") if isinstance(sender, User) else "",
                        "last_name": (sender.last_name or "") if isinstance(sender, User) else "",
                        "is_bot": ("да" if sender.bot else "нет") if isinstance(sender, User) else "",
                        "source": "Автор сообщения (членство не проверено)",
                        "last_message_utc": "",
                    }
                record = seen[sender_id]
                if not record.get("last_message_utc") and message.date:
                    record["last_message_utc"] = message.date.isoformat()
                if scanned % 5000 == 0:
                    print("Прочитано сообщений:", scanned, "найдено уникальных ID:", len(seen), flush=True)
        except errors.FloodWaitError as err:
            print("Чтение истории остановлено лимитом Telegram:", err)
        for record in seen.values():
            record.setdefault("last_message_utc", "")
        with (OUTPUT / "participants.csv").open("w", newline="", encoding="utf-8-sig") as f:
            cols = ["telegram_id", "username", "first_name", "last_name", "is_bot", "source", "last_message_utc"]
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(seen.values())
        meta = {"chat_name": dialog.name, "chat_id": str(dialog.id), "api_members": member_count, "message_count_scanned": scanned, "unique_ids": len(seen), "visible_member_count": 2834, "note": "Авторы сообщений могут больше не состоять в группе; Telegram ограничивает список участников."}
        (OUTPUT / "summary.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print("ИТОГО:", json.dumps(meta, ensure_ascii=False))
if __name__ == "__main__":
    asyncio.run(main())
