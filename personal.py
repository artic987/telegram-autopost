"""Finite hourly Telegram helper. Private state lives in Saved Messages."""
import asyncio
import io
import json
import os
import time
from datetime import datetime, timedelta, timezone

MARKER = '#arthur_personal_helper_state_v1'
REPLY_USERNAME = 'addvk39'
MSK = timezone(timedelta(hours=3))
AWAY = ('Автоответ Артура: сейчас я не могу регулярно заходить в Telegram. '
        'Пиши сюда, прочитаю, когда появится возможность.')
GREETING = ('{name}, с днём рождения! Желаю здоровья, спокойствия, хороших людей '
            'рядом и радостных событий. Обнимаю! Артур. '
            'Это поздравление я подготовил заранее.')
HELP = ('Помощник подключён. Команды отправляйте отдельными сообщениями в Избранное:\n'
        '/helper on — автоответ только @addvk39\n'
        '/helper off — выключить автоответ\n'
        '/away ваш текст — изменить автоответ\n'
        '/birthday @username ДД.ММ Имя — добавить день рождения\n'
        '/forget @username — удалить дату\n'
        '/greeting текст с {name} — шаблон поздравления\n'
        '/helper status — настройки\n'
        'Проверка раз в час с возможными задержками GitHub. '
        'Автоответ не чаще раза в сутки; поздравления с 10:00 МСК. '
        'Автоответ включён только для @addvk39. Файл состояния ниже не удаляйте.')


def initial_state(now):
    return dict(version=1, enabled=True, since=now, command_id=0,
                away=AWAY, greeting=GREETING, friends={}, sent={}, pause=0)


def date_matches(date, now):
    return datetime.strptime(date+'.2000', '%d.%m.%Y').strftime('%d.%m') == now.strftime('%d.%m')


def reply_due(message, since, last, now):
    return (message is not None and not message.out
            and message.date.timestamp() >= max(since, now-86400)
            and now-last >= 86400)


class Store:
    def __init__(self, client):
        self.client, self.message, self.state = client, None, None

    async def load(self):
        async for msg in self.client.iter_messages('me', search=MARKER, limit=20):
            if msg.out and msg.raw_text == MARKER and msg.document:
                raw = await self.client.download_media(msg, file=bytes)
                self.state = json.loads(raw)
                if self.state.get('version') != 1:
                    raise ValueError('Unknown state version')
                self.message = msg
                return False
        self.state = initial_state(time.time())
        await self.save()
        return True

    async def save(self):
        data = io.BytesIO(json.dumps(self.state, ensure_ascii=False).encode())
        data.name = 'personal-helper-state.json'
        if self.message:
            self.message = await self.client.edit_message('me', self.message.id,
                text=MARKER, file=data, parse_mode=None)
        else:
            self.message = await self.client.send_file('me', data, caption=MARKER, parse_mode=None)


async def run():
    from telethon import TelegramClient, errors, types
    from telethon.sessions import StringSession
    client = TelegramClient(StringSession(os.environ['TG_STRING_SESSION']),
        int(os.environ['TG_API_ID']), os.environ['TG_API_HASH'],
        flood_sleep_threshold=0, request_retries=0)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError('Telegram session is not authorized')
        me = await client.get_me()
        store = Store(client)
        fresh = await store.load()
        s = store.state
        if fresh:
            await client.send_message('me', HELP, parse_mode=None)
        if s['pause'] > time.time():
            print('Telegram cooldown still active; skipping.')
            return
        # Saved Messages is the only command source. No commands from other users.
        pending = []
        async for msg in client.iter_messages('me', min_id=s['command_id'], limit=1000, reverse=True):
            if msg.out and (msg.raw_text or '').startswith(('/helper ', '/away ', '/birthday ', '/forget ', '/greeting ')):
                pending.append(msg)
        # Fail instead of silently skipping a backlog beyond the limit.
        if len(pending) >= 1000:
            raise RuntimeError('Too many pending commands')
        for msg in pending:
            text = msg.raw_text.strip()
            result = 'Команда не распознана. Используйте /helper status.'
            try:
                if text == '/helper on':
                    if not s['enabled']: s['since'] = time.time()
                    s['enabled'] = True
                    result = 'Автоответ включён только для новых личных сообщений от @addvk39.'
                elif text == '/helper off':
                    s['enabled'] = False
                    result = 'Автоответ выключен. Поздравления остаются включены для добавленных дат.'
                elif text == '/helper status':
                    result = ('Автоответ: '+('включён' if s['enabled'] else 'выключен')
                        +'\nТекст: '+s['away']+'\nДни рождения:\n'
                        +'\n'.join(f"{f['target']} {f['date']} {f['name']}" for f in s['friends'].values()))
                elif text.startswith(('/away ', '/greeting ')):
                    field = 'away' if text.startswith('/away ') else 'greeting'
                    value = text.split(' ', 1)[1].strip()
                    if not 1 <= len(value) <= 1500: raise ValueError('Текст: от 1 до 1500 символов.')
                    s[field] = value
                    result = 'Текст сохранён.'
                elif text.startswith('/birthday '):
                    parts = text.split(maxsplit=3)
                    if len(parts) < 3: raise ValueError('Формат: /birthday @username ДД.ММ Имя')
                    target, date = parts[1:3]
                    datetime.strptime(date+'.2000', '%d.%m.%Y')
                    entity = await client.get_entity(int(target) if target.isdigit() else target)
                    if not isinstance(entity, types.User) or entity.bot or entity.id == me.id:
                        raise ValueError('Нужен личный аккаунт друга.')
                    name = parts[3] if len(parts) > 3 else entity.first_name or 'Друг'
                    if len(name) > 100: raise ValueError('Имя слишком длинное.')
                    if len(s['friends']) >= 100 and str(entity.id) not in s['friends']:
                        raise ValueError('Лимит: 100 друзей.')
                    s['friends'][str(entity.id)] = dict(target=target, date=date, name=name,
                        id=entity.id, access_hash=entity.access_hash)
                    result = f'Добавлено: {name}, {date}.'
                elif text.startswith('/forget '):
                    target = text.split(maxsplit=1)[1].lower()
                    keys = [k for k,v in s['friends'].items() if v['target'].lower()==target or k==target]
                    for k in keys: del s['friends'][k]
                    result = f'Удалено дат: {len(keys)}.'
            except (ValueError, errors.UsernameNotOccupiedError, errors.UsernameInvalidError):
                result = 'Не удалось выполнить команду. Проверьте username, дату ДД.ММ и формат в инструкции.'
            s['command_id'] = msg.id
            await store.save()
            await client.send_message('me', result[:4000], parse_mode=None)
        count = 0
        async def send(key, peer, text, interval):
            nonlocal count
            now = time.time()
            if count >= 30 or now - s['sent'].get(key, 0) < interval: return
            # Reserve BEFORE sending. Ambiguous failures are not retried this period.
            # This trades occasional missed messages for protection from duplicate sends.
            s['sent'][key] = now
            await store.save()
            await client.send_message(peer, text, parse_mode=None, link_preview=False)
            count += 1
            await asyncio.sleep(3)
        now = datetime.now(MSK)
        for friend in s['friends'].values():
            if now.hour >= 10 and date_matches(friend['date'], now):
                peer = types.InputPeerUser(friend['id'], friend['access_hash'])
                try:
                    await send(f"birthday:{friend['id']}:{now.year}", peer,
                        s['greeting'].replace('{name}', friend['name']), 370*86400)
                except (errors.UserIsBlockedError, errors.YouBlockedUserError, errors.UserPrivacyRestrictedError):
                    print('Birthday recipient unavailable; skipped.')
        if s['enabled']:
            # Resolve the exact username once, then pin the numeric user ID.
            # Refuse a future username reassignment instead of contacting a different user.
            entity = await client.get_entity(REPLY_USERNAME)
            if not isinstance(entity, types.User) or entity.bot or entity.id == me.id:
                raise RuntimeError('Auto-reply target must be a different human account')
            if s.get('reply_id') and s['reply_id'] != entity.id:
                raise RuntimeError('Auto-reply username now belongs to another account')
            s['reply_id'] = entity.id
            await store.save()
            messages = await client.get_messages(entity, limit=1)
            latest = messages[0] if messages else None
            key = f'away:{entity.id}'
            if reply_due(latest, s['since'], s['sent'].get(key, 0), time.time()):
                try:
                    await send(key, entity, s['away'], 86400)
                except (errors.UserIsBlockedError, errors.YouBlockedUserError, errors.UserPrivacyRestrictedError):
                    print('Reply recipient unavailable; skipped.')
        s['sent'] = {k:v for k,v in s['sent'].items() if time.time()-v < (370*86400 if k.startswith('birthday:') else 2*86400)}
        await store.save()
        print(f'Personal helper completed. Sent: {count}.')
    except errors.PeerFloodError:
        if 'store' in locals() and store.state:
            store.state['pause'] = time.time()+86400
            try: await store.save()
            except errors.RPCError: pass
        raise RuntimeError('Telegram restricted sending; paused for 24 hours') from None
    except errors.FloodWaitError as exc:
        # State save may itself be rate-limited. Workflow is finite, never sleeps past its budget.
        if 'store' in locals() and store.state:
            store.state['pause'] = time.time()+exc.seconds+60
            try: await store.save()
            except errors.RPCError: pass
        print(f'Telegram FloodWait: {exc.seconds}s. Run stopped.')
        raise RuntimeError('Telegram rate limit; wait before retrying') from None
    finally:
        await client.disconnect()


if __name__ == '__main__':
    try:
        asyncio.run(run())
    except Exception as exc:
        # Public Actions logs must not contain private message text, credentials or state.
        print('Personal helper stopped:', type(exc).__name__)
        raise SystemExit(1)
