from __future__ import annotations

import json
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class StaleRevision(Exception):
    pass


class Store:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "studio.sqlite3"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL,
                    source_type TEXT NOT NULL, source_url TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL, edits TEXT NOT NULL, published TEXT NOT NULL,
                    token TEXT NOT NULL UNIQUE, revision INTEGER NOT NULL DEFAULT 1,
                    enabled INTEGER NOT NULL DEFAULT 1, interval_minutes INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, refreshed_at TEXT NOT NULL,
                    last_error TEXT NOT NULL DEFAULT '', source_headers TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subscription_id TEXT NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
                    label TEXT NOT NULL, source TEXT NOT NULL, edits TEXT NOT NULL,
                    yaml TEXT NOT NULL, created_at TEXT NOT NULL
                );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get(self, sub_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM subscriptions WHERE id=?", (sub_id,)).fetchone()
        return dict(row) if row else None

    def list(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM subscriptions ORDER BY created_at,id")]

    def create(self, title, source_type, source_url, source, edits, published, headers):
        sub_id = uuid.uuid4().hex
        stamp = now()
        with self.connect() as db:
            db.execute("""INSERT INTO subscriptions
                (id,title,source_type,source_url,source,edits,published,token,created_at,updated_at,refreshed_at,source_headers)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (sub_id, title, source_type, source_url, source, json.dumps(edits, ensure_ascii=False),
                 published, secrets.token_urlsafe(24), stamp, stamp, stamp, json.dumps(headers)))
            self.snapshot(db, sub_id, "首次导入")
        return sub_id

    @staticmethod
    def snapshot(db, sub_id, label):
        row = db.execute("SELECT * FROM subscriptions WHERE id=?", (sub_id,)).fetchone()
        db.execute("INSERT INTO history(subscription_id,label,source,edits,yaml,created_at) VALUES(?,?,?,?,?,?)",
                   (sub_id, label, row["source"], row["edits"], row["published"], now()))
        # Keep the newest 50 full snapshots per subscription.
        db.execute("""DELETE FROM history WHERE subscription_id=? AND id NOT IN
                    (SELECT id FROM history WHERE subscription_id=? ORDER BY id DESC LIMIT 50)""", (sub_id, sub_id))

    def update(self, sub_id, revision, values, label=None):
        allowed = {"title", "source", "edits", "published", "last_error", "refreshed_at",
                   "enabled", "interval_minutes", "token", "source_headers"}
        if not values or not set(values) <= allowed:
            raise ValueError("Invalid update")
        values = {**values, "updated_at": now()}
        with self.connect() as db:
            statement = ",".join(f"{key}=?" for key in values)
            result = db.execute(f"UPDATE subscriptions SET {statement},revision=revision+1 WHERE id=? AND revision=?",
                                (*values.values(), sub_id, revision))
            if result.rowcount != 1:
                raise StaleRevision()
            if label:
                self.snapshot(db, sub_id, label)

    def history(self, sub_id):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT id,label,created_at,length(yaml) AS size FROM history WHERE subscription_id=? ORDER BY id DESC", (sub_id,))]

    def historical(self, sub_id, history_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM history WHERE subscription_id=? AND id=?", (sub_id, history_id)).fetchone()
            return dict(row) if row else None

    def by_token(self, token):
        with self.connect() as db:
            row = db.execute("SELECT * FROM subscriptions WHERE token=? AND enabled=1", (token,)).fetchone()
            return dict(row) if row else None

    def delete(self, sub_id, revision):
        with self.connect() as db:
            result = db.execute("DELETE FROM subscriptions WHERE id=? AND revision=?", (sub_id, revision))
            if result.rowcount != 1:
                raise StaleRevision()
