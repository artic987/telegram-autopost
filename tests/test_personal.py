import json
import sys
import time
import types
import unittest
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock

import personal


class FakeUser:
    def __init__(self, uid):
        self.id, self.bot, self.access_hash, self.first_name = uid, False, 1234, 'Friend'


class FakeClient:
    def __init__(self):
        self.state_message = None
        self.payload = None
        self.sent = []
        self.lookups = []
        self.commands = []
        self.latest = None
        self.target_id = 39

    async def connect(self): pass
    async def disconnect(self): pass
    async def is_user_authorized(self): return True
    async def get_me(self): return FakeUser(1)

    async def get_entity(self, target):
        self.lookups.append(target)
        return FakeUser(self.target_id)

    async def get_messages(self, entity, limit):
        assert entity.id == self.target_id
        return [self.latest] if self.latest else []

    async def iter_messages(self, peer, **kw):
        assert peer == 'me'
        if kw.get('search'):
            if self.state_message: yield self.state_message
        else:
            for msg in self.commands:
                if msg.id > kw['min_id']: yield msg

    async def download_media(self, msg, file): return self.payload

    async def send_file(self, peer, data, caption, **kw):
        assert peer == 'me'
        self.payload = data.getvalue()
        self.state_message = types.SimpleNamespace(id=10, out=True, raw_text=caption, document=True)
        return self.state_message

    async def edit_message(self, peer, mid, text, file, **kw):
        self.payload = file.getvalue()
        return self.state_message

    async def send_message(self, peer, text, **kw):
        self.sent.append((peer, text))


class LogicTests(unittest.TestCase):
    def test_dates(self):
        self.assertTrue(personal.date_matches('9.8', datetime(2026,8,9)))
        self.assertFalse(personal.date_matches('29.02', datetime(2027,2,28)))
        self.assertTrue(personal.date_matches('29.02', datetime(2028,2,29)))
        with self.assertRaises(ValueError): personal.date_matches('31.04', datetime.now())

    def test_old_outgoing_and_cooldown(self):
        now = time.time()
        msg = types.SimpleNamespace(out=False, date=datetime.fromtimestamp(now, timezone.utc))
        self.assertTrue(personal.reply_due(msg, now-1, 0, now))
        self.assertFalse(personal.reply_due(msg, now+1, 0, now))
        self.assertFalse(personal.reply_due(msg, now-1, now-100, now))
        msg.out = True
        self.assertFalse(personal.reply_due(msg, now-1, 0, now))


class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = FakeClient()
        errors = types.SimpleNamespace()
        for name in ['RPCError','UsernameNotOccupiedError','UsernameInvalidError',
                     'UserIsBlockedError','YouBlockedUserError','UserPrivacyRestrictedError',
                     'PeerFloodError','FloodWaitError']:
            setattr(errors, name, type(name, (Exception,), {}))
        module = types.ModuleType('telethon')
        module.TelegramClient = lambda *a, **k: self.client
        module.errors = errors
        module.types = types.SimpleNamespace(User=FakeUser, InputPeerUser=lambda uid, h: FakeUser(uid))
        sessions = types.ModuleType('telethon.sessions')
        sessions.StringSession = lambda s: s
        self.patcher = patch.dict(sys.modules, {'telethon':module, 'telethon.sessions':sessions})
        self.patcher.start()
        self.env = patch.dict('os.environ', {'TG_API_ID':'1','TG_API_HASH':'test','TG_STRING_SESSION':'test'})
        self.env.start()
        self.sleep = patch('personal.asyncio.sleep', new_callable=AsyncMock)
        self.sleep.start()

    async def asyncTearDown(self):
        self.sleep.stop(); self.env.stop(); self.patcher.stop()

    async def test_only_exact_target_and_no_duplicate_across_runs(self):
        await personal.run()  # Initialization never answers old messages.
        self.assertEqual(self.client.lookups, ['addvk39'])
        self.assertTrue(all(peer == 'me' for peer, _ in self.client.sent))
        self.client.latest = types.SimpleNamespace(out=False, date=datetime.now(timezone.utc))
        await personal.run()
        await personal.run()
        replies = [peer for peer, _ in self.client.sent if peer != 'me']
        self.assertEqual([p.id for p in replies], [39])

    async def test_username_reassignment_fails_closed(self):
        await personal.run()
        self.client.target_id = 88
        with self.assertRaises(RuntimeError): await personal.run()
        self.assertTrue(all(peer == 'me' for peer, _ in self.client.sent))

    async def test_off_command_prevents_reply(self):
        await personal.run()
        self.client.commands = [types.SimpleNamespace(id=20, out=True, raw_text='/helper off')]
        self.client.latest = types.SimpleNamespace(out=False, date=datetime.now(timezone.utc))
        await personal.run()
        self.assertFalse(json.loads(self.client.payload)['enabled'])
        self.assertTrue(all(peer == 'me' for peer, _ in self.client.sent))

    async def test_birthday_persisted_before_delivery(self):
        await personal.run()
        state = json.loads(self.client.payload)
        state['friends']['50'] = dict(id=50, access_hash=5, target='@friend', date='07.09', name='Friend')
        self.client.payload = json.dumps(state).encode()
        fake_datetime = unittest.mock.Mock(wraps=datetime)
        fake_datetime.now.return_value = datetime(2026,9,7,10,5,tzinfo=personal.MSK)
        with patch('personal.datetime', fake_datetime):
            await personal.run()
            await personal.run()
        delivered = [peer.id for peer, _ in self.client.sent if peer != 'me']
        self.assertEqual(delivered, [50])
        self.assertIn('birthday:50:2026', json.loads(self.client.payload)['sent'])

if __name__ == '__main__': unittest.main()
