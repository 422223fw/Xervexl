"""Private durable sign-in grants. Bearer secrets are stored only as SHA-256 hashes."""
import hashlib
import hmac
import json
import re
import time
from pathlib import Path


class SessionStore:
    def __init__(self, path):
        self.path = Path(path)
        self.tokens = {}
        if self.path.exists():
            data = json.loads(self.path.read_text('utf-8'))
            if data.get('version') != 1 or not isinstance(data.get('tokens'), dict):
                raise ValueError('Unsupported remembered-session data; original file was left intact.')
            for key, record in data['tokens'].items():
                if not re.fullmatch('[0-9a-f]{64}', key) or not isinstance(record, dict):
                    raise ValueError('Invalid remembered-session data; original file was left intact.')
                if not isinstance(record.get('username'), str) or not re.fullmatch('[0-9a-f]{64}', str(record.get('credential', ''))):
                    raise ValueError('Invalid remembered-session record; original file was left intact.')
            self.tokens = data['tokens']

    @staticmethod
    def key(token):
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def credential(user):
        return hashlib.sha256(user['password'].encode()).hexdigest()

    def save(self):
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(dict(version=1, tokens=self.tokens), separators=(',', ':')), 'utf-8')
        for attempt in range(6):
            try:
                temporary.replace(self.path)
                return
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(.02*(attempt+1))

    def add(self, token, user):
        key = self.key(token)
        self.tokens[key] = dict(username=user['username'].lower(), credential=self.credential(user))
        try:
            self.save()
        except OSError:
            self.tokens.pop(key, None)
            raise

    def find(self, token, users):
        if not isinstance(token, str) or not 1 <= len(token) <= 128:
            return None
        record = self.tokens.get(self.key(token))
        user = users.get(record['username']) if record else None
        if not user or not user.get('password') or not hmac.compare_digest(record['credential'], self.credential(user)):
            return None
        return user

    def remove(self, token):
        key = self.key(token)
        record = self.tokens.pop(key, None)
        if record is not None:
            try:
                self.save()
            except OSError:
                self.tokens[key] = record
                raise

    def revoke_user(self, username):
        original = self.tokens
        self.tokens = {key: record for key, record in original.items() if record['username'] != username.lower()}
        try:
            self.save()
        except OSError:
            self.tokens = original
            raise
