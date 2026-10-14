import hashlib
import json
import tempfile
import threading
import time
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch
from server import Arena, AuthenticationError, Handler, ThreadingHTTPServer
from session_store import SessionStore

ROOT = Path(__file__).resolve().parents[1]


class SessionTests(unittest.TestCase):
    def setUp(self):
        runtime = ROOT/'data'/'tests';runtime.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=runtime)
        self.path = Path(self.temp.name)/'accounts.json'
        self.arena = Arena(self.path, seed=2)
        self.creds = dict(username='Remembered', email='remembered@example.com', password='test-passphrase')
        self.token = self.arena.request('/auth/register', self.creds)['token']

    def tearDown(self):
        self.temp.cleanup()

    def test_restarting_server_restores_account_without_password_or_new_fighter(self):
        user = self.arena.users['remembered'];user.update(coins=1234, skill=15, inventory=['knife','arming'], weapon='arming')
        self.arena.save()
        restarted = Arena(self.path, seed=3)
        resumed = restarted.request('/auth/resume', {}, self.token)
        self.assertTrue(resumed['authenticated'])
        for key in ('coins', 'skill', 'weapon', 'inventory'):
            self.assertEqual(resumed['profile'][key], user[key])
        self.assertEqual(restarted.sessions[self.token]['fighter'], '')
        self.assertTrue(all(f['bot'] for f in restarted.fighters.values()))
        self.assertNotIn('password', resumed['profile'])
        self.assertNotIn('email', resumed['profile'])

    def test_inactivity_removes_avatar_without_expiring_sign_in(self):
        player = self.arena.request('/arena/join', {}, self.token)['player']
        self.arena.sessions[self.token]['touched'] = time.monotonic()-86400*100
        self.arena.tick(.03)
        self.assertNotIn(player, self.arena.fighters)
        self.assertNotIn(self.token, self.arena.sessions)
        profile = self.arena.request('/me', {}, self.token)['profile']
        self.assertEqual(profile['username'], 'Remembered')
        self.assertTrue(self.arena.request('/arena/join', {}, self.token)['player'])

    def test_logout_revokes_durable_grant_after_restart_and_is_idempotent(self):
        self.arena.request('/auth/logout', {}, self.token)
        self.assertTrue(self.arena.request('/auth/logout', {}, self.token)['logged_out'])
        restarted = Arena(self.path, seed=3)
        with self.assertRaises(AuthenticationError):restarted.request('/auth/resume', {}, self.token)
        with self.assertRaises(AuthenticationError):restarted.request('/arena/join', {}, self.token)
        self.assertEqual(restarted.remembered.tokens, {})

    def test_logging_out_one_device_does_not_log_out_another(self):
        second = self.arena.request('/auth/login', self.creds)['token']
        self.arena.request('/auth/logout', {}, self.token)
        restarted = Arena(self.path, seed=3)
        self.assertTrue(restarted.request('/auth/resume', {}, second)['authenticated'])
        with self.assertRaises(AuthenticationError):restarted.request('/auth/resume', {}, self.token)

    def test_password_reset_revokes_saved_sessions_including_inactive_ones(self):
        second = self.arena.request('/auth/login', self.creds)['token']
        self.arena.sessions.clear()
        code = 'isolated-reset-code'
        self.arena.resets[hashlib.sha256(code.encode()).hexdigest()] = ('remembered', time.monotonic()+60)
        self.arena.request('/auth/reset', dict(code=code, password='new-test-passphrase'))
        restarted = Arena(self.path, seed=3)
        for token in (self.token, second):
            with self.assertRaises(AuthenticationError):restarted.request('/auth/resume', {}, token)
        self.assertTrue(restarted.request('/auth/login', dict(username='Remembered', password='new-test-passphrase'))['token'])

    def test_changed_password_rejects_old_grant_even_if_revocation_file_was_not_written(self):
        from server import password_hash
        self.arena.users['remembered']['password'] = password_hash('new-test-passphrase')
        self.arena.save()
        restarted = Arena(self.path, seed=3)
        with self.assertRaises(AuthenticationError):restarted.request('/auth/resume', {}, self.token)

    def test_private_server_store_contains_token_hashes_without_bearer_secrets(self):
        stored = self.arena.remembered.path.read_text()
        self.assertNotIn(self.token, stored)
        self.assertNotIn(self.creds['password'], stored)
        self.assertNotIn(self.creds['email'], stored)
        data = json.loads(stored)
        self.assertIn(hashlib.sha256(self.token.encode()).hexdigest(), data['tokens'])
        self.assertEqual(set(next(iter(data['tokens'].values()))), {'username', 'credential'})

    def test_unknown_or_wrong_server_token_never_resumes_an_account(self):
        other = Arena(Path(self.temp.name)/'other-accounts.json', seed=3)
        for token in (self.token, 'invented-token', ''):
            with self.assertRaises(AuthenticationError):other.request('/auth/resume', {}, token)

    def test_rejoining_with_restored_token_still_allows_only_one_avatar_per_account(self):
        first = self.arena.request('/arena/join', {}, self.token)['player']
        second = self.arena.request('/auth/login', self.creds)['token']
        self.arena.request('/arena/join', {}, second)
        self.arena.request('/auth/resume', {}, self.token)
        third = self.arena.request('/arena/join', {}, self.token)['player']
        self.assertNotEqual(first, third)
        self.assertEqual(sum(not f['bot'] for f in self.arena.fighters.values()), 1)

    def test_failed_revocation_checkpoint_keeps_grant_for_a_retry(self):
        with patch.object(Path, 'replace', side_effect=PermissionError('locked')), patch('session_store.time.sleep'):
            with self.assertRaises(PermissionError):self.arena.request('/auth/logout', {}, self.token)
        self.assertTrue(self.arena.request('/auth/resume', {}, self.token)['authenticated'])
        self.arena.request('/auth/logout', {}, self.token)
        self.assertEqual(SessionStore(self.arena.remembered.path).tokens, {})

    def test_http_resume_returns_an_explicit_invalid_auth_code(self):
        class TestHandler(Handler):pass
        TestHandler.arena = self.arena;TestHandler.limits = {}
        http = ThreadingHTTPServer(('127.0.0.1',0), TestHandler)
        service = threading.Thread(target=http.serve_forever, daemon=True);service.start()
        try:
            connection = HTTPConnection('127.0.0.1', http.server_port)
            connection.request('POST', '/auth/resume', '{}', {'Authorization':'Bearer invalid-token','Content-Type':'application/json'})
            response = connection.getresponse();body = json.loads(response.read());connection.close()
            self.assertEqual(response.status, 401)
            self.assertEqual(body['code'], 'auth_required')
        finally:
            http.shutdown();http.server_close();service.join()


if __name__ == '__main__':unittest.main()
