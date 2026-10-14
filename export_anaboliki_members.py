"""Export accessible members and distinct message authors from АНАБОЛИКИ.net «ЧАТ»."""
import asyncio
import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from telethon.tl.types import User

OUTPUT = Path("anaboliki_members_export")
OUTPUT.mkdir(exist_ok=True)
TARGET_NORM = "анаболикиnetчат"
MAX_MESSAGES = 75000

def normalize(value):
    return re.sub(r"[^a-zа-яё0-9]+", "", (value or "").casefold())

def record(user, source, last_message=""):
    return {
        "telegram_id": str(user.id),
        "username": user.username or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "is_bot": "да" if user.bot else "нет",
        "source": source,
        "last_message_utc": last_message,
    }

async def main():
    client = TelegramClient(
        StringSession(os.environ["TG_STRING_SESSION"]),
        int(os.environ["TG_API_ID"]),
        os.environ["TG_API_HASH"],
    )
    async with client:
        matches = []
        async for dialog in client.iter_dialogs(limit=None):
            norm = normalize(dialog.name)
            if "анаболики" in norm:
                matches.append(dialog)
        print("Найденные похожие чаты:", [(d.name, d.id) for d in matches], flush=True)
        exact = [d for d in matches if normalize(d.name) == TARGET_NORM]
        if not exact:
            raise RuntimeError("Группа АНАБОЛИКИ.net «ЧАТ» не найдена")
        if len(exact) > 1:
            from telethon.tl.functions.channels import GetFullChannelRequest
            counts = []
            for candidate in exact:
                try:
                    info = await client(GetFullChannelRequest(candidate.entity))
                    count = getattr(info.full_chat, "participants_count", 0) or 0
                except Exception as exc:
                    print("Ошибка определения количества:", candidate.id, repr(exc), flush=True)
                    count = 0
                counts.append((candidate, count))
                print("Одинаковое название:", candidate.name, "id:", candidate.id, "участников:", count, flush=True)
            closest = sorted(counts, key=lambda item: abs(item[1] - 2665))
            if len(closest) > 1 and (closest[0][1] <= 0 or abs(closest[0][1] - 2665) >= abs(closest[1][1] - 2665)):
                raise RuntimeError("Не удалось однозначно отличить одноимённые группы по численности")
            if abs(closest[0][1] - 2665) > 150:
                raise RuntimeError("Нет группы с числом участников, похожим на 2665")
            dialog = closest[0][0]
        else:
            dialog = exact[0]
        print("Выбран чат:", dialog.name, dialog.id, flush=True)
        members = {}
        member_error = ""
        try:
            async for member in client.iter_participants(dialog.entity, aggressive=True):
                if isinstance(member, User):
                    members[member.id] = record(member, "Участник (API)")
            print("Получено через API участников:", len(members), flush=True)
        except (errors.ChatAdminRequiredError, errors.ChannelPrivateError, errors.FloodWaitError) as exc:
            member_error = str(exc)
            print("Ограничение API участников:", member_error, flush=True)
        api_count = len(members)
        search_added = 0
        search_queries = ("а", "е", "и", "о", "н", "р", "т", "м", "s", "a", "i", "o", "e", "1", "0")
        for q in search_queries:
            try:
                added = 0
                async for member in client.iter_participants(dialog.entity, search=q):
                    if isinstance(member, User) and member.id not in members:
                        members[member.id] = record(member, "Поиск участников (API)")
                        added += 1
                search_added += added
                print("Поиск", repr(q), "добавлено:", added, "всего:", len(members), flush=True)
            except (errors.ChatAdminRequiredError, errors.ChannelPrivateError, errors.FloodWaitError) as exc:
                print("Поиск ограничен:", repr(exc), flush=True)
                break
        scanned = 0
        history_error = ""
        try:
            async for msg in client.iter_messages(dialog.entity, limit=MAX_MESSAGES):
                scanned += 1
                user = msg.sender
                if isinstance(user, User):
                    stamp = msg.date.isoformat() if msg.date else ""
                    if user.id not in members:
                        members[user.id] = record(user, "Автор сообщения (членство не проверено)", stamp)
                    elif not members[user.id]["last_message_utc"]:
                        members[user.id]["last_message_utc"] = stamp
                if scanned % 5000 == 0:
                    print("История:", scanned, "сообщений; уникальных аккаунтов:", len(members), flush=True)
        except errors.FloodWaitError as exc:
            history_error = str(exc)
            print("Ограничение Telegram истории:", history_error, flush=True)
        columns = ["telegram_id", "username", "first_name", "last_name", "is_bot", "source", "last_message_utc"]
        with (OUTPUT / "participants.csv").open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(sorted(members.values(), key=lambda r: (r["source"] != "Участник (API)", r["telegram_id"])))
        meta = {
            "chat_name": dialog.name,
            "chat_id": str(dialog.id),
            "visible_members_in_screenshot": 2665,
            "api_members": api_count,
            "messages_scanned": scanned,
            "unique_accounts": len(members),
            "export_time_utc": datetime.now(timezone.utc).isoformat(),
            "member_api_error": member_error,
            "history_error": history_error,
            "note": "Авторы истории не обязательно остаются участниками; Telegram может ограничивать просмотр участников.",
        }
        (OUTPUT / "summary.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print("ИТОГО:", json.dumps(meta, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    asyncio.run(main())
