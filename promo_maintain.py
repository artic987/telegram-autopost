import asyncio
import json
import os
import random

from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient, errors, types
from telethon.sessions import StringSession

from promo_rules import (
    ADMIN_ONLY_PATTERNS,
    BLOCK_PATTERNS,
    direct_rules_blocked,
    explicit_direct_permission,
    fetch_rule_context,
    matches,
    medical_promo_blocked,
)


FILE = Path("promo_targets.json")

MAX_CHECKS = int(
    os.getenv(
        "PROMO_MAINTAIN_MAX_CHECKS",
        "80"
    )
)

PAUSE_MIN = float(
    os.getenv(
        "PROMO_MAINTAIN_PAUSE_MIN",
        "0.8"
    )
)

PAUSE_MAX = float(
    os.getenv(
        "PROMO_MAINTAIN_PAUSE_MAX",
        "1.6"
    )
)
def entity_of(item):
    if isinstance(item, str):
        return item.lower()

    if isinstance(item, dict):
        return str(
            item.get(
                "entity",
                item.get("target", "")
            )
        ).lower()

    return ""


def item_dict(item):
    if isinstance(item, dict):
        return dict(item)

    return {
        "entity": str(item),
        "title": "",
        "source": "maintenance",
    }


def append_unique(section, item):
    key = entity_of(item)

    if not key:
        return

    if any(
        entity_of(existing) == key
        for existing in section
    ):
        return

    section.append(item)


async def main():
    api_id = int(
        os.environ["TG_API_ID"]
    )
    api_hash = os.environ["TG_API_HASH"]
    session = os.environ["TG_STRING_SESSION"]

    data = json.loads(
        FILE.read_text(encoding="utf-8")
    )

    direct = data.setdefault("direct", [])
    auto = data.setdefault(
        "auto_discovered_direct",
        []
    )
    admin_only = data.setdefault(
        "admin_only",
        []
    )
    review = data.setdefault(
        "needs_review",
        []
    )
    disabled = data.setdefault(
        "disabled",
        []
    )

    moves = []
    checked = 0
    async with TelegramClient(
        StringSession(session),
        api_id,
        api_hash
    ) as client:
        for source_name, section in (
            ("direct", direct),
            ("auto_discovered_direct", auto),
        ):
            for raw in list(section):
                if checked >= MAX_CHECKS:
                    break

                handle = entity_of(raw)

                if not handle:
                    continue

                checked += 1
                print(
                    f"CHECK {checked}/{MAX_CHECKS}:",
                    handle
                )

                try:
                    entity = await client.get_entity(
                        handle
                    )
                except (
                    errors.ChannelPrivateError,
                    errors.UsernameNotOccupiedError,
                    ValueError,
                ) as exc:
                    moves.append(
                        (
                            source_name,
                            handle,
                            "disabled",
                            "unreachable/private: "
                            + type(exc).__name__,
                        )
                    )
                    continue
                except errors.FloodWaitError as exc:
                    print(
                        "FloodWait:",
                        exc.seconds
                    )
                    break
                except Exception as exc:
                    print(
                        "  transient resolve error:",
                        repr(exc)
                    )
                    continue

                if (
                    not isinstance(entity, types.Channel)
                    or not getattr(
                        entity,
                        "megagroup",
                        False
                    )
                ):
                    moves.append(
                        (
                            source_name,
                            handle,
                            "disabled",
                            "not an active megagroup",
                        )
                    )
                    continue
                try:
                    context = await fetch_rule_context(
                        client,
                        entity,
                        recent_limit=80,
                        max_admin_rules=12,
                    )
                except errors.FloodWaitError as exc:
                    print(
                        "FloodWait rules:",
                        exc.seconds
                    )
                    break
                except Exception as exc:
                    print(
                        "  transient rules error:",
                        repr(exc)
                    )
                    continue

                title = (
                    getattr(entity, "title", "")
                    or ""
                )
                rules_text = "\n\n".join(
                    x
                    for x in (
                        title,
                        context["combined"],
                    )
                    if x
                )

                if medical_promo_blocked(
                    rules_text
                ):
                    dest = "disabled"
                    reason = (
                        "rules prohibit medical/"
                        "pharma promotion"
                    )
                elif matches(
                    rules_text,
                    BLOCK_PATTERNS
                ):
                    dest = "disabled"
                    reason = (
                        "rules block direct "
                        "advertising/links"
                    )
                elif matches(
                    rules_text,
                    ADMIN_ONLY_PATTERNS
                ):
                    dest = "admin_only"
                    reason = (
                        "advertising now requires "
                        "administrator placement"
                    )
                elif not explicit_direct_permission(
                    rules_text
                ):
                    dest = "needs_review"
                    reason = (
                        "explicit direct-ad permission "
                        "no longer confirmed"
                    )
                else:
                    print(
                        "  ✓ still eligible"
                    )
                    await asyncio.sleep(
                        random.uniform(
                            PAUSE_MIN,
                            PAUSE_MAX
                        )
                    )
                    continue

                moves.append(
                    (
                        source_name,
                        handle,
                        dest,
                        reason,
                    )
                )
                await asyncio.sleep(
                    random.uniform(
                        PAUSE_MIN,
                        PAUSE_MAX
                    )
                )

            if checked >= MAX_CHECKS:
                break

    moved = 0

    for source_name, handle, dest, reason in moves:
        source = data[source_name]
        found = None

        for raw in list(source):
            if entity_of(raw) == handle:
                found = raw
                source.remove(raw)
                break

        if found is None:
            continue

        item = item_dict(found)
        item["maintenance_checked_at"] = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )
        item["reason"] = reason

        target_section = data[dest]
        append_unique(
            target_section,
            item
        )

        moved += 1
        print(
            "  → moved",
            handle,
            "to",
            dest,
            "|",
            reason,
        )

    FILE.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "Maintenance complete:",
        f"checked={checked}",
        f"moved={moved}",
    )


if __name__ == "__main__":
    asyncio.run(main())
