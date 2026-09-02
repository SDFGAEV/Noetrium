"""Crash-durable journal provider for multi-agent delivery and recovery.

The coordinator owns invariants; this provider owns only durable transcript
and checkpoint storage.
"""

from __future__ import annotations

from collections.abc import Mapping
import sqlite3
from pathlib import Path
from threading import RLock

from noetrium.contracts.json import JsonValue, canonical_text, require_sha256, strict_json_loads

from .contracts import (
    MultiAgentCheckpoint,
    MultiAgentDeliveryReceipt,
    MultiAgentMessage,
    MultiAgentJournalPort,
)


def _message_document(message: MultiAgentMessage) -> dict[str, JsonValue]:
    return {
        "sender": message.sender,
        "recipient": message.recipient,
        "content": message.content,
        "turn": message.turn,
        "conversation_id": message.conversation_id,
        "causal_parent_ids": message.causal_parent_ids,
        "delivery_attempt": message.delivery_attempt,
    }


def _message_from(value: object) -> MultiAgentMessage:
    if not isinstance(value, Mapping):
        raise ValueError("journal message must be a mapping")
    parents = value.get("causal_parent_ids", ())
    if not isinstance(parents, (list, tuple)):
        raise ValueError("journal causal_parent_ids must be a sequence")
    return MultiAgentMessage(
        value.get("sender"),
        value.get("recipient"),
        value.get("content"),
        value.get("turn"),
        value.get("conversation_id"),
        tuple(parents),
        value.get("delivery_attempt", 0),
    )


def _checkpoint_document(checkpoint: MultiAgentCheckpoint) -> dict[str, JsonValue]:
    return {
        "schema_version": checkpoint.schema_version,
        "topology_digest": checkpoint.topology_digest,
        "conversation_id": checkpoint.conversation_id,
        "pending": tuple(_message_document(row) for row in checkpoint.pending),
        "delivered_message_ids": checkpoint.delivered_message_ids,
        "round": checkpoint.round,
        "delivered_messages": tuple(
            _message_document(row) for row in checkpoint.delivered_messages
        ),
    }
def _checkpoint_from(value: object) -> MultiAgentCheckpoint:
    if not isinstance(value, Mapping):
        raise ValueError("journal checkpoint must be a mapping")
    pending = value.get("pending", ())
    delivered = value.get("delivered_messages", ())
    delivered_ids = value.get("delivered_message_ids", ())
    if not all(isinstance(row, (list, tuple)) for row in (pending, delivered, delivered_ids)):
        raise ValueError("journal checkpoint sequences are malformed")
    return MultiAgentCheckpoint(
        value.get("schema_version"),
        value.get("topology_digest"),
        value.get("conversation_id"),
        tuple(_message_from(row) for row in pending),
        tuple(delivered_ids),
        value.get("round"),
        tuple(_message_from(row) for row in delivered),
    )


def _receipt_document(receipt: MultiAgentDeliveryReceipt) -> dict[str, JsonValue]:
    return {
        "message_id": receipt.message_id,
        "sender": receipt.sender,
        "recipient": receipt.recipient,
        "status": receipt.status.value,
        "attempt": receipt.attempt,
        "round": receipt.round,
        "detail": receipt.detail,
    }


class SQLiteMultiAgentJournal(MultiAgentJournalPort):
    """SQLite WAL journal with idempotent records and latest checkpoints."""

    durability = "crash_durable"

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(
            str(self.path), check_same_thread=False, isolation_level=None
        )
        with self._lock:
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS multi_agent_deliveries (
                    receipt_id TEXT PRIMARY KEY,
                    message_id TEXT NOT NULL,
                    message_json TEXT NOT NULL,
                    receipt_json TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS multi_agent_checkpoints (
                    checkpoint_digest TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    checkpoint_json TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS multi_agent_latest (
                    conversation_id TEXT PRIMARY KEY,
                    checkpoint_digest TEXT NOT NULL
                )
                """
            )
    def record(
        self,
        message: MultiAgentMessage,
        receipt: MultiAgentDeliveryReceipt,
    ) -> None:
        if type(message) is not MultiAgentMessage or type(receipt) is not MultiAgentDeliveryReceipt:
            raise TypeError("multi-agent journal records require typed message and receipt")
        if receipt.message_id != message.message_id:
            raise ValueError("multi-agent journal receipt/message identity mismatch")
        message_json = canonical_text(_message_document(message))
        receipt_json = canonical_text(_receipt_document(receipt))
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute(
                    "SELECT message_json, receipt_json FROM multi_agent_deliveries "
                    "WHERE receipt_id = ?",
                    (receipt.receipt_id,),
                ).fetchone()
                if row is not None and (row[0] != message_json or row[1] != receipt_json):
                    raise ValueError("multi-agent journal receipt identity collision")
                self._connection.execute(
                    "INSERT OR IGNORE INTO multi_agent_deliveries "
                    "(receipt_id, message_id, message_json, receipt_json) VALUES (?, ?, ?, ?)",
                    (receipt.receipt_id, message.message_id, message_json, receipt_json),
                )
                self._connection.execute("COMMIT")
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise

    def checkpoint(self, checkpoint: MultiAgentCheckpoint) -> None:
        if type(checkpoint) is not MultiAgentCheckpoint:
            raise TypeError("multi-agent journal checkpoint must be typed")
        document = canonical_text(_checkpoint_document(checkpoint))
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute(
                    "SELECT checkpoint_json FROM multi_agent_checkpoints "
                    "WHERE checkpoint_digest = ?",
                    (checkpoint.checkpoint_digest,),
                ).fetchone()
                if row is not None and row[0] != document:
                    raise ValueError("multi-agent journal checkpoint identity collision")
                self._connection.execute(
                    "INSERT OR IGNORE INTO multi_agent_checkpoints "
                    "(checkpoint_digest, conversation_id, checkpoint_json) VALUES (?, ?, ?)",
                    (checkpoint.checkpoint_digest, checkpoint.conversation_id, document),
                )
                self._connection.execute(
                    "INSERT INTO multi_agent_latest (conversation_id, checkpoint_digest) "
                    "VALUES (?, ?) ON CONFLICT(conversation_id) DO UPDATE SET "
                    "checkpoint_digest = excluded.checkpoint_digest",
                    (checkpoint.conversation_id, checkpoint.checkpoint_digest),
                )
                self._connection.execute("COMMIT")
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
    def latest_checkpoint(self, conversation_id: str) -> MultiAgentCheckpoint | None:
        if type(conversation_id) is not str or not conversation_id.strip():
            raise ValueError("multi-agent journal conversation_id must be non-empty")
        with self._lock:
            row = self._connection.execute(
                "SELECT c.checkpoint_json, c.checkpoint_digest "
                "FROM multi_agent_latest l JOIN multi_agent_checkpoints c "
                "ON c.checkpoint_digest = l.checkpoint_digest "
                "WHERE l.conversation_id = ?",
                (conversation_id,),
            ).fetchone()
        if row is None:
            return None
        document = strict_json_loads(row[0])
        checkpoint = _checkpoint_from(document)
        require_sha256(row[1], "multi-agent journal checkpoint_digest")
        if checkpoint.conversation_id != conversation_id:
            raise ValueError("multi-agent journal conversation identity mismatch")
        if checkpoint.checkpoint_digest != row[1]:
            raise ValueError("multi-agent journal checkpoint digest mismatch")
        return checkpoint

    def close(self) -> None:
        with self._lock:
            self._connection.close()


__all__ = ["SQLiteMultiAgentJournal"]
