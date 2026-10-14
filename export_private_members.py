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
        with (OUTPUT / "participants.csv").open("w", newline="", encoding="utf-8-sig") as f:
            cols = ["telegram_id", "username", "first_name", "last_name", "is_bot", "source"]
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(seen.values())
        meta = {"chat_name": dialog.name, "chat_id": str(dialog.id), "api_members": len(seen), "visible_member_count": 2834, "note": "Telegram may limit how many members are visible to nonadmins"}
        (OUTPUT / "summary.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print("ИТОГО:", json.dumps(meta, ensure_ascii=False))
if __name__ == "__main__":
    asyncio.run(main())
