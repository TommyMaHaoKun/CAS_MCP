"""Persist review drafts and save receipts across MCP clients and restarts."""

import hashlib
import json
import os
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path


def state_directory() -> Path:
    if os.environ.get("CAS_MONSTER_STATE_DIR"):
        return Path(os.environ["CAS_MONSTER_STATE_DIR"]).expanduser()
    if os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "CAS Monster"
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "cas-monster"


class DraftStore:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("""
                CREATE TABLE IF NOT EXISTS drafts (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL, state TEXT NOT NULL,
                    receipts TEXT NOT NULL
                )
            """)
            yield db

    @staticmethod
    def id_for(payload: dict, account: str) -> str:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256((account + "\0" + text).encode("utf-8")).hexdigest()

    def prepare(self, payload: dict, account: str) -> str:
        draft_id = self.id_for(payload, account)
        receipts = [
            {"kind": kind, "index": i, "state": "pending"}
            for kind, entries in payload.items()
            for i in range(1, len(entries) + 1)
        ]
        with self.connection() as db:
            db.execute(
                "INSERT OR IGNORE INTO drafts VALUES (?, ?, 'prepared', ?)",
                (draft_id, json.dumps(payload, ensure_ascii=False), json.dumps(receipts)),
            )
        return draft_id

    def get(self, draft_id: str) -> tuple[dict, str, list]:
        with self.connection() as db:
            row = db.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if row is None:
            raise ValueError("Draft not found. Run cas_prepare_submission first.")
        return json.loads(row["payload"]), row["state"], json.loads(row["receipts"])

    def claim(self, draft_id: str) -> bool:
        with self.connection() as db:
            updated = db.execute(
                "UPDATE drafts SET state = 'submitting' WHERE id = ? AND state = 'prepared'",
                (draft_id,),
            )
        return updated.rowcount == 1

    def update(self, draft_id: str, state: str, receipts: list) -> None:
        with self.connection() as db:
            db.execute(
                "UPDATE drafts SET state = ?, receipts = ? WHERE id = ?",
                (state, json.dumps(receipts), draft_id),
            )
