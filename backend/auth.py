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
        now_value = datetime.now(timezone.utc)
        now = now_value.isoformat(timespec="seconds")
        with self.database.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            row = connection.execute(
                """
                SELECT u.id, u.username, s.last_active_at,
                       COALESCE(p.auto_lock_minutes, 0) AS auto_lock_minutes
                FROM sessions s
                JOIN users u ON u.id = s.user_id
                LEFT JOIN user_preferences p ON p.user_id = u.id
                WHERE s.token_hash = ? AND s.expires_at > ?
                """,
                (token_hash, now),
            ).fetchone()
            if not row:
                return None
            auto_lock_minutes = max(0, int(row["auto_lock_minutes"] or 0))
            last_active_at = self._session_timestamp(row["last_active_at"], now_value)
            if auto_lock_minutes and now_value - last_active_at >= timedelta(minutes=auto_lock_minutes):
                connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
                return None
        return {"id": row["id"], "username": row["username"]}

    def touch_session(self, token: str | None) -> dict[str, str] | None:
        user = self.session_user(token)
        if not user or not token:
            return None
        self.mark_session_active(token)
        return user

    def mark_session_active(self, token: str | None) -> bool:
        if not token:
            return False
        now = now_iso()
        with self.database.connect() as connection:
            result = connection.execute(
                "UPDATE sessions SET last_active_at = ? WHERE token_hash = ? AND expires_at > ?",
                (now, self._token_hash(token), now),
            )
        return result.rowcount == 1

    def change_password(
        self,
        user_id: str,
        current_password_value: Any,
        next_password_value: Any,
    ) -> tuple[dict[str, str], str]:
        current_password = str(current_password_value or "")
        next_password = _clean_password(next_password_value)
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT id, username, password_hash FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if not row or not verify_password(current_password, row["password_hash"]):
                raise AuthError("Súčasné heslo nie je správne.")
            connection.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(next_password), user_id),
            )
            connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            token = self._create_session(connection, user_id)
        return {"id": row["id"], "username": row["username"]}, token

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
        created_at = now_iso()
        expires_at = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds")
        connection.execute(
            """
            INSERT INTO sessions(id, user_id, token_hash, created_at, last_active_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), user_id, self._token_hash(token), created_at, created_at, expires_at),
        )
        return token

    @staticmethod
    def _session_timestamp(value: Any, fallback: datetime) -> datetime:
        try:
            timestamp = datetime.fromisoformat(str(value))
            if timestamp.tzinfo is None:
                return timestamp.replace(tzinfo=timezone.utc)
            return timestamp.astimezone(timezone.utc)
        except (TypeError, ValueError):
            return fallback
