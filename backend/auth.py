from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .database import Database, now_iso


SESSION_DAYS = 14
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


class AuthError(ValueError):
    """Prihlasovanie alebo vytvorenie účtu zlyhalo."""


def _clean_username(value: Any) -> str:
    username = str(value or "").strip()
    if not 2 <= len(username) <= 80:
        raise AuthError("Meno používateľa musí mať 2 až 80 znakov.")
    return username


def _clean_password(value: Any) -> str:
    password = str(value or "")
    if len(password) < 10:
        raise AuthError("Heslo musí mať aspoň 10 znakov.")
    if len(password) > 1024:
        raise AuthError("Heslo je príliš dlhé.")
    return password


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return "$".join(
        [
            "scrypt",
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(derived).decode("ascii"),
        ]
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, stored = encoded.split("$")
        if algorithm != "scrypt":
            return False
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=base64.b64decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
        )
        return hmac.compare_digest(derived, base64.b64decode(stored))
    except (ValueError, TypeError):
        return False


class AuthService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def setup(self, username_value: Any, password_value: Any) -> tuple[dict[str, str], str]:
        username = _clean_username(username_value)
        password = _clean_password(password_value)
        user = {"id": str(uuid.uuid4()), "username": username}
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                raise AuthError("Pracovná plocha už má vytvorený účet.")
            connection.execute(
                "INSERT INTO users(id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (user["id"], username, hash_password(password), now_iso()),
            )
            token = self._create_session(connection, user["id"])
        return user, token

    def login(self, username_value: Any, password_value: Any) -> tuple[dict[str, str], str]:
        username = str(username_value or "").strip()
        password = str(password_value or "")
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT id, username, password_hash FROM users WHERE username = ? COLLATE NOCASE", (username,)
            ).fetchone()
            if not row or not verify_password(password, row["password_hash"]):
                raise AuthError("Nesprávne meno používateľa alebo heslo.")
            user = {"id": row["id"], "username": row["username"]}
            token = self._create_session(connection, user["id"])
        return user, token

    def session_user(self, token: str | None) -> dict[str, str] | None:
        if not token:
            return None
        token_hash = self._token_hash(token)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.database.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            row = connection.execute(
                """
                SELECT u.id, u.username FROM sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = ? AND s.expires_at > ?
                """,
                (token_hash, now),
            ).fetchone()
        return {"id": row["id"], "username": row["username"]} if row else None

    def logout(self, token: str | None) -> None:
        if not token:
            return
        with self.database.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (self._token_hash(token),))

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _create_session(self, connection: sqlite3.Connection, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        expires_at = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds")
        connection.execute(
            "INSERT INTO sessions(id, user_id, token_hash, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, self._token_hash(token), now_iso(), expires_at),
        )
        return token
